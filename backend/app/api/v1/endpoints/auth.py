"""Administrator Authentication API Endpoints.

Phase C13.2 — Administrator Authentication & Session Management.
Endpoints:
- POST /api/v1/auth/login
- POST /api/v1/auth/logout
- GET  /api/v1/auth/me
"""

import urllib.parse
from datetime import UTC, datetime, timedelta
from typing import Annotated

import httpx
from app.api.deps import (
    get_current_session_and_user,
    get_db,
    validate_request_origin,
    verify_csrf_token,
)
from app.core.config import settings
from app.core.login_throttle import login_failure_throttle
from app.core.security import (
    generate_csrf_token,
    generate_oauth_state,
    generate_session_token,
    hash_password,
    hash_session_token,
    make_unusable_password,
    validate_password_policy,
    verify_dummy_password,
    verify_oauth_state,
    verify_password,
)
from app.models.account_security import TOKEN_PURPOSE_VERIFY, AccountEmailRegistry
from app.models.admin import AdminSession, AdminUser
from app.models.portal import (
    PORTAL_ROLE_CUSTOMER,
    PORTAL_ROLE_INVESTOR,
    PortalUser,
)
from app.schemas.auth import (
    AdminUserMeResponse,
    AdminUserPublic,
    AuthMeResponseEnvelope,
    GoogleAuthUrlResponse,
    GoogleCallbackRequest,
    LoginRequest,
    LoginResponseData,
    LoginResponseEnvelope,
    LogoutResponseEnvelope,
    RegisterRequest,
    RegisterResponseData,
    RegisterResponseEnvelope,
    ResendVerificationRequest,
    VerifyEmailRequest,
    VerifyEmailResponseEnvelope,
)
from app.schemas.portal import PortalUserPublic
from app.services.audit import record_security_event
from app.services.password_links import (
    DELIVERY_EMAIL,
    _send_link_email,
    issue_link,
    redeem_verification_token,
)
from app.services.portal_auth import (
    PORTAL_HOME,
    authenticate_portal_user,
    create_portal_session,
    record_failed_sign_in,
)
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=LoginResponseEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Authenticate administrator and establish session",
)
async def login(
    request: Request,
    response: Response,
    login_data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponseEnvelope:
    """Authenticates central administrative staff.

    Enforces:
    - Origin validation if header present.
    - Constant-time password verification via Argon2id.
    - Timing-attack mitigations for unknown email addresses.
    - Layered throttling: 5 failures per account per client address, a per-address cap across
      accounts (HTTP 429), and a higher account-wide lockout (see app/core/login_throttle.py).
    - Concurrency-safe lockout updates.
    - SIGN_IN_FAILED audit events (no passwords or tokens recorded).
    - Cryptographically secure session generation with SHA-256 database storage.
    - Secure HttpOnly session cookie creation.
    - Per-session CSRF token generation.
    """
    # 1. Validate request origin if browser supplied Origin/Referer
    validate_request_origin(request)

    normalized_email = str(login_data.email).strip().lower()

    # 2. Per-client-address limit (password spraying across accounts) -> HTTP 429. Applies to
    #    administrators and customers alike. See app/core/login_throttle.py for all three layers.
    await login_failure_throttle.ensure_allowed(request)
    client_throttled = await login_failure_throttle.is_blocked_for_account(request, normalized_email)

    # 3. Query user with row-level lock to prevent concurrent attempt race conditions
    stmt = (
        select(AdminUser)
        .options(selectinload(AdminUser.roles))
        .where(AdminUser.email == normalized_email)
        .with_for_update()
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    now = datetime.now(UTC)

    # 4. No administrator with this email: try a portal account (CUSTOMER or INVESTOR).
    #    The role comes strictly from the stored account record, never from client input.
    if not user:
        outcome = await authenticate_portal_user(
            db, normalized_email, login_data.password, role=None, throttled=client_throttled
        )
        portal_user = outcome.user
        if not portal_user:
            await record_failed_sign_in(
                db, request, normalized_email, portal="main", reason=outcome.reason,
                account_table="portal_users" if outcome.account else None,
                account_id=outcome.account.id if outcome.account else None,
                account_email=outcome.account.email if outcome.account else None,
            )
            if outcome.reason == "email_unverified":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Please verify your email address before signing in.",
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        await login_failure_throttle.record_success(request, normalized_email)
        portal_csrf_token = await create_portal_session(db, portal_user, request, response)
        redirect_target = PORTAL_HOME.get(portal_user.role, "/account")
        return LoginResponseEnvelope(
            success=True,
            data=LoginResponseData(
                user=PortalUserPublic.model_validate(portal_user),
                csrf_token=portal_csrf_token,
                account_type=portal_user.role,
                redirect_to=redirect_target,
            ),
        )

    async def reject(reason: str) -> None:
        await record_failed_sign_in(
            db, request, normalized_email, portal="main", reason=reason,
            account_table="admin_users", account_id=user.id, account_email=user.email,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # 5. Handle deactivated or soft-deleted user
    if not user.is_active or user.deleted_at is not None:
        verify_dummy_password()
        await reject("inactive")

    # 6. Account-wide lockout (failures from any address)
    if user.locked_until:
        if user.locked_until > now:
            verify_dummy_password()
            await reject("account_locked")
        # Lockout period expired; reset counters for this attempt
        user.locked_until = None
        user.failed_login_attempts = 0

    # 7. This client address has used up its attempts for this account: refuse without touching
    #    the account-wide counter, so a single attacker cannot lock the real administrator out.
    if client_throttled:
        verify_dummy_password()
        await reject("client_throttled")

    # 8. Verify password with Argon2id
    is_valid = verify_password(login_data.password, user.password_hash)

    if not is_valid:
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.ACCOUNT_LOCKOUT_MAX_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=settings.LOCKOUT_DURATION_MINUTES)
        await db.commit()
        await reject("bad_password")

    await login_failure_throttle.record_success(request, normalized_email)

    # 9. Successful authentication: reset lockout counters and record login timestamp
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now

    # 8. Generate session tokens
    raw_session_token = generate_session_token()
    session_digest = hash_session_token(raw_session_token)
    csrf_token = generate_csrf_token()
    expires_at = now + timedelta(seconds=settings.SESSION_MAX_AGE_SECONDS)

    # Extract client metadata
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # 9. Store hashed session record in PostgreSQL
    new_session = AdminSession(
        id=session_digest,
        admin_user_id=user.id,
        ip_address=client_ip,
        user_agent=user_agent,
        csrf_token=csrf_token,
        expires_at=expires_at,
        created_at=now,
        last_activity_at=now,
    )
    db.add(new_session)
    await db.commit()

    # 10. Configure HttpOnly session cookie
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_session_token,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        expires=expires_at,
        path=settings.SESSION_COOKIE_PATH,
        secure=settings.session_cookie_secure,
        httponly=settings.SESSION_COOKIE_HTTPONLY,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )

    role_ids = [role.id for role in user.roles]

    return LoginResponseEnvelope(
        success=True,
        data=LoginResponseData(
            user=AdminUserPublic(
                id=user.id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                job_title=user.job_title,
                roles=role_ids,
            ),
            csrf_token=csrf_token,
            account_type="ADMIN",
            redirect_to="/admin",
        ),
    )


@router.post(
    "/logout",
    response_model=LogoutResponseEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Terminate active administrator session",
    dependencies=[Depends(verify_csrf_token)],
)
async def logout(
    request: Request,
    response: Response,
    auth: Annotated[tuple[AdminSession, AdminUser], Depends(get_current_session_and_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LogoutResponseEnvelope:
    """Terminates the active administrator session and removes the session cookie.

    Requires:
    - Active authenticated session cookie.
    - Valid X-CSRF-Token header matching session CSRF token.
    - Allowed origin header.
    """
    admin_session, admin_user = auth

    # Revoke session in database and record the sign-out
    await db.delete(admin_session)
    record_security_event(db, "ADMIN_LOGOUT", "admin_users", admin_user.id, actor_admin=admin_user, request=request)
    await db.commit()

    # Clear session cookie in browser
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path=settings.SESSION_COOKIE_PATH,
        secure=settings.session_cookie_secure,
        httponly=settings.SESSION_COOKIE_HTTPONLY,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )

    return LogoutResponseEnvelope(
        success=True,
        message="Logged out successfully",
    )


@router.get(
    "/me",
    response_model=AuthMeResponseEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Retrieve authenticated administrator identity",
)
async def get_me(
    auth: Annotated[tuple[AdminSession, AdminUser], Depends(get_current_session_and_user)],
) -> AuthMeResponseEnvelope:
    """Returns profile, assigned roles, and active session CSRF token for authenticated administrator."""
    session, user = auth
    role_ids = [role.id for role in user.roles]

    return AuthMeResponseEnvelope(
        success=True,
        data=AdminUserMeResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            job_title=user.job_title,
            roles=role_ids,
            last_login_at=user.last_login_at,
            csrf_token=session.csrf_token,
        ),
    )


@router.post(
    "/register",
    response_model=RegisterResponseEnvelope,
    status_code=status.HTTP_201_CREATED,
    summary="Public registration for customer or investor portal accounts",
)
async def register(
    request: Request,
    payload: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RegisterResponseEnvelope:
    validate_request_origin(request)
    await login_failure_throttle.ensure_allowed(request)

    # 1. Role gating: only CUSTOMER or INVESTOR
    if payload.role not in (PORTAL_ROLE_CUSTOMER, PORTAL_ROLE_INVESTOR):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration is only available for customer and investor accounts.",
        )

    # 2. Validate password strength against company policy
    valid_password, reason = validate_password_policy(payload.password)
    if not valid_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason or "Password does not meet security requirements.")

    normalized_email = str(payload.email).strip().lower()

    # 3. Check for existing email in account_email_registry across admin and portal tables
    reg_stmt = select(AccountEmailRegistry).where(AccountEmailRegistry.email_normalized == normalized_email)
    existing_reg = (await db.execute(reg_stmt)).scalar_one_or_none()
    if existing_reg:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    # 4. Hash password with Argon2id
    password_hash = hash_password(payload.password)

    # 5. Create unverified portal user
    new_user = PortalUser(
        email=normalized_email,
        password_hash=password_hash,
        role=payload.role,
        full_name=payload.full_name.strip(),
        company_name=payload.company_name.strip() if payload.company_name else None,
        contact_number=payload.contact_number.strip() if payload.contact_number else None,
        country=payload.country.strip() if payload.country else None,
        is_active=True,
        email_verified_at=None,
        created_by_admin_id=None,
    )
    db.add(new_user)
    await db.flush()

    # 6. Issue email verification token
    issued = await issue_link(db, new_user, TOKEN_PURPOSE_VERIFY, request=request)
    if issued.delivery == DELIVERY_EMAIL:
        await _send_link_email(new_user.email, new_user.full_name, issued)

    record_security_event(
        db,
        f"PUBLIC_REGISTER_{payload.role}",
        "portal_users",
        new_user.id,
        actor_email=new_user.email,
        new_state={"role": payload.role, "delivery": issued.delivery},
        request=request,
    )
    await db.commit()
    await db.refresh(new_user)

    message = (
        "Account created successfully. A verification link has been sent to your email address."
        if issued.delivery == DELIVERY_EMAIL
        else (
            "Account created successfully. Because email delivery is operating in manual verification mode, "
            "your activation link must be retrieved through an authorized administrator."
        )
    )

    return RegisterResponseEnvelope(
        success=True,
        data=RegisterResponseData(
            user=PortalUserPublic.model_validate(new_user),
            delivery=issued.delivery,
            verification_link=None,
            message=message,
        ),
    )


@router.post(
    "/verify-email",
    response_model=VerifyEmailResponseEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Verify account email address using single-use verification token",
)
async def verify_email(
    request: Request,
    payload: VerifyEmailRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VerifyEmailResponseEnvelope:
    validate_request_origin(request)
    user = await redeem_verification_token(db, payload.token, request=request)
    redirect_target = PORTAL_HOME.get(user.role, "/login")
    return VerifyEmailResponseEnvelope(
        success=True,
        message="Email address verified successfully. You may now sign in.",
        redirect_to=redirect_target,
    )


@router.post(
    "/resend-verification",
    status_code=status.HTTP_200_OK,
    summary="Resend verification email to unverified account",
)
async def resend_verification(
    request: Request,
    payload: ResendVerificationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str | bool]:
    validate_request_origin(request)
    await login_failure_throttle.ensure_allowed(request)
    email = str(payload.email).strip().lower()

    stmt = select(PortalUser).where(PortalUser.email == email).with_for_update()
    user = (await db.execute(stmt)).scalar_one_or_none()

    if user and user.email_verified_at is None and user.is_active:
        issued = await issue_link(db, user, TOKEN_PURPOSE_VERIFY, request=request)
        if issued.delivery == DELIVERY_EMAIL:
            await _send_link_email(user.email, user.full_name, issued)
        await db.commit()

    return {
        "success": True,
        "message": "If an unverified account exists for this email address, a verification link has been sent or queued.",
    }


@router.get(
    "/google/url",
    response_model=GoogleAuthUrlResponse,
    summary="Get Google OAuth authorization URL",
)
async def google_auth_url(
    role: str = "CUSTOMER",
) -> GoogleAuthUrlResponse:
    if role not in (PORTAL_ROLE_CUSTOMER, PORTAL_ROLE_INVESTOR):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google sign-in is only available for customer and investor accounts.",
        )

    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        return GoogleAuthUrlResponse(
            configured=False,
            url=None,
            state=None,
            message="Google OAuth 2.0 is not configured on this server.",
        )

    state = generate_oauth_state(role, settings.APP_SECRET_KEY)
    redirect_uri = f"{settings.PUBLIC_SITE_URL.rstrip('/')}/api/v1/auth/google/callback"
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return GoogleAuthUrlResponse(
        configured=True,
        url=url,
        state=state,
        message=None,
    )


@router.post(
    "/google/callback",
    response_model=LoginResponseEnvelope,
    summary="Google OAuth 2.0 exchange and session establishment",
)
async def google_callback(
    request: Request,
    response: Response,
    payload: GoogleCallbackRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponseEnvelope:
    validate_request_origin(request)
    await login_failure_throttle.ensure_allowed(request)

    # 1. Verify state token HMAC and expiration
    valid_state, state_role = verify_oauth_state(payload.state, settings.APP_SECRET_KEY)
    if not valid_state or state_role != payload.role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired Google OAuth state. Please try again.",
        )

    # 2. Role gating
    if payload.role not in (PORTAL_ROLE_CUSTOMER, PORTAL_ROLE_INVESTOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Google authentication is not permitted for administrative roles.",
        )

    # 3. Server-side token exchange with Google (or test mock handling)
    now = datetime.now(UTC)
    email: str
    google_id: str
    name: str

    if settings.APP_ENV == "test" and payload.code.startswith("test-google-code:"):
        parts = payload.code.split(":")
        email = parts[1].strip().lower()
        google_id = parts[2] if len(parts) > 2 else f"google-{hash_session_token(email)[:16]}"
        name = parts[3] if len(parts) > 3 else "Google Test User"
    else:
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google OAuth credentials are not configured on this server.",
            )
        redirect_uri = f"{settings.PUBLIC_SITE_URL.rstrip('/')}/api/v1/auth/google/callback"
        token_url = "https://oauth2.googleapis.com/token"
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_resp = await client.post(
                token_url,
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "code": payload.code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )
            if token_resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to exchange authorization code with Google.",
                )
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            userinfo_resp = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if userinfo_resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to retrieve profile from Google.",
                )
            userinfo = userinfo_resp.json()
            email = str(userinfo.get("email", "")).strip().lower()
            if not email or not userinfo.get("email_verified"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A verified email address is required from Google.",
                )
            google_id = str(userinfo.get("sub"))
            name = str(userinfo.get("name") or email.split("@")[0])

    # 4. Account takeover & privilege escalation prevention:
    # Check if this email belongs to an administrator account
    admin_stmt = select(AdminUser).where(AdminUser.email == email)
    if (await db.execute(admin_stmt)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator accounts must authenticate using corporate credentials, not public Google sign-in.",
        )

    # 5. Check existing portal user
    portal_stmt = select(PortalUser).where(PortalUser.email == email).with_for_update()
    user = (await db.execute(portal_stmt)).scalar_one_or_none()

    if user:
        if user.role != payload.role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This account is registered for the {user.role.lower()} portal. Please sign in through the correct portal.",
            )
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been deactivated.")
        if user.google_id and user.google_id != google_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is linked to a different Google account.",
            )
        if not user.google_id:
            user.google_id = google_id
        if user.email_verified_at is None:
            user.email_verified_at = now
        user.last_login_at = now
    else:
        user = PortalUser(
            email=email,
            password_hash=make_unusable_password(),
            role=payload.role,
            full_name=name,
            is_active=True,
            email_verified_at=now,
            google_id=google_id,
            created_by_admin_id=None,
        )
        db.add(user)
        await db.flush()

    record_security_event(
        db,
        f"GOOGLE_AUTH_LOGIN_{payload.role}",
        "portal_users",
        user.id,
        actor_email=user.email,
        new_state={"role": payload.role, "google_id_linked": True},
        request=request,
    )
    await db.commit()
    await db.refresh(user)

    # 6. Establish portal session and issue role cookie
    csrf_token = await create_portal_session(db, user, request, response)
    return LoginResponseEnvelope(
        success=True,
        data=LoginResponseData(
            user=PortalUserPublic.model_validate(user),
            csrf_token=csrf_token,
            account_type=user.role,
            redirect_to=PORTAL_HOME[user.role],
        ),
    )
