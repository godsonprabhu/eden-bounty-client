"""Authentication helpers for customer and investor portal accounts (CR-C4).

Mirrors the administrator flow (Argon2id, constant-time behaviour for unknown accounts,
layered sign-in throttling, SHA-256 session digests, per-session CSRF token) for the separate
``portal_users`` / ``portal_sessions`` tables. See app/core/login_throttle.py for the layers.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.login_throttle import login_failure_throttle
from app.core.rate_limit import get_client_ip
from app.core.security import (
    generate_csrf_token,
    generate_session_token,
    has_usable_password,
    hash_session_token,
    verify_dummy_password,
    verify_password,
)
from app.models.audit import AuditLog
from app.models.portal import (
    PORTAL_ROLE_CUSTOMER,
    PORTAL_ROLE_INVESTOR,
    PortalSession,
    PortalUser,
)
from app.services.audit import UNKNOWN_ACCOUNT_ID, record_security_event

# Where each role lands after signing in. Decided here, on the server, never by the client.
PORTAL_HOME = {PORTAL_ROLE_CUSTOMER: "/account", PORTAL_ROLE_INVESTOR: "/investors/portal"}


def cookie_name_for(role: str) -> str:
    if role == PORTAL_ROLE_CUSTOMER:
        return settings.CUSTOMER_SESSION_COOKIE_NAME
    if role == PORTAL_ROLE_INVESTOR:
        return settings.INVESTOR_SESSION_COOKIE_NAME
    raise ValueError(f"Unknown portal role: {role}")


@dataclass
class SignInOutcome:
    """Result of a credential check. ``reason`` is for the audit ledger only; callers always
    answer the client with the same generic error."""

    user: PortalUser | None = None
    account: PortalUser | None = None
    reason: str | None = None


async def authenticate_portal_user(
    db: AsyncSession, email: str, password: str, role: str | None = None, *, throttled: bool = False
) -> SignInOutcome:
    """Verifies credentials for an account (matching ``role`` if provided).

    An account of a different role, an unknown email, an inactive, locked or invitation-pending
    account, a throttled client and a wrong password are indistinguishable to the caller and all
    cost one Argon2id verification. ``throttled`` (per account + client address limit reached)
    refuses the attempt without touching the account-wide counter, so one client cannot push an
    account into the account-wide lock. Commits counter changes.
    """
    stmt = select(PortalUser).where(PortalUser.email == email.strip().lower()).with_for_update()
    user = (await db.execute(stmt)).scalar_one_or_none()
    now = datetime.now(UTC)

    if not user:
        verify_dummy_password()
        return SignInOutcome(reason="unknown_account")
    if role is not None and user.role != role:
        verify_dummy_password()
        return SignInOutcome(account=user, reason="wrong_portal")
    if not user.is_active:
        verify_dummy_password()
        return SignInOutcome(account=user, reason="inactive")

    if user.locked_until:
        if user.locked_until > now:
            verify_dummy_password()
            return SignInOutcome(account=user, reason="account_locked")
        user.locked_until = None
        user.failed_login_attempts = 0

    if throttled:
        verify_dummy_password()
        return SignInOutcome(account=user, reason="client_throttled")

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.ACCOUNT_LOCKOUT_MAX_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=settings.LOCKOUT_DURATION_MINUTES)
        await db.commit()
        reason = "bad_password" if has_usable_password(user.password_hash) else "invitation_pending"
        return SignInOutcome(account=user, reason=reason)

    if user.email_verified_at is None:
        return SignInOutcome(account=user, reason="email_unverified")

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    return SignInOutcome(user=user, account=user)


async def record_failed_sign_in(
    db: AsyncSession,
    request: Request,
    email: str,
    *,
    portal: str,
    reason: str | None,
    account_table: str | None = None,
    account_id: uuid.UUID | None = None,
    account_email: str | None = None,
) -> None:
    """Counts the failure in the in-memory throttles and writes a SIGN_IN_FAILED audit event.

    The attempted address is recorded only when it belongs to an account. No password, hash or
    token is ever recorded.
    """
    await login_failure_throttle.record_failure(request, email)
    record_security_event(
        db,
        "SIGN_IN_FAILED",
        account_table or "unknown_account",
        account_id or UNKNOWN_ACCOUNT_ID,
        actor_email=account_email,
        new_state={"portal": portal, "reason": reason or "unknown"},
        request=request,
    )
    await db.commit()


async def create_portal_session(
    db: AsyncSession, user: PortalUser, request: Request, response: Response
) -> str:
    """Creates the server-side session, sets the role-specific HttpOnly cookie, returns the CSRF token."""
    now = datetime.now(UTC)
    raw_token = generate_session_token()
    csrf_token = generate_csrf_token()
    expires_at = now + timedelta(seconds=settings.SESSION_MAX_AGE_SECONDS)
    client_ip = get_client_ip(request)

    db.add(
        PortalSession(
            id=hash_session_token(raw_token),
            portal_user_id=user.id,
            role=user.role,
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent"),
            csrf_token=csrf_token,
            expires_at=expires_at,
            created_at=now,
            last_activity_at=now,
        )
    )
    db.add(
        AuditLog(
            actor_admin_id=None,
            actor_email=user.email,
            ip_address=client_ip,
            action=f"PORTAL_LOGIN_{user.role}",
            entity_table="portal_users",
            entity_id=user.id,
            old_state=None,
            new_state=None,
            client_user_agent=request.headers.get("user-agent"),
        )
    )
    await db.commit()

    response.set_cookie(
        key=cookie_name_for(user.role),
        value=raw_token,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        expires=expires_at,
        path=settings.SESSION_COOKIE_PATH,
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )
    return csrf_token


def clear_portal_cookie(response: Response, role: str) -> None:
    response.delete_cookie(
        key=cookie_name_for(role),
        path=settings.SESSION_COOKIE_PATH,
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )
