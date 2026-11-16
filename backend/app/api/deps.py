"""FastAPI Dependencies for Authentication, Session Validation, CSRF, and RBAC.

Phase C13.2 — Administrator Authentication & Session Management.
Adheres strictly to C13-security-design.md v2.1.0 and C13-api-specification.md v2.1.0.
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlparse

from app.core.config import settings
from app.core.security import constant_time_compare, hash_session_token
from app.db.session import AsyncSessionLocal
from app.models.admin import AdminSession, AdminUser
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields a database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


def validate_request_origin(request: Request) -> None:
    """Validates that incoming state-changing requests originate from an allowed origin.

    Checks Origin header or fallback Referer header against settings.CORS_ORIGINS.
    """
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")

    target_origin = origin
    if not target_origin and referer:
        parsed = urlparse(referer)
        target_origin = f"{parsed.scheme}://{parsed.netloc}"

    if target_origin:
        # Check against allowed CORS origins and authorized preview origin
        allowed = [o.rstrip("/") for o in settings.all_allowed_origins]
        if target_origin.rstrip("/") not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Request origin not permitted by security policy",
            )


async def get_current_session_and_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    eb_admin_session: Annotated[str | None, Cookie()] = None,
) -> tuple[AdminSession, AdminUser]:
    """Validates the HTTP-only session cookie against PostgreSQL admin_sessions.

    Enforces:
    - Session existence via cryptographic token digest (raw token is never in DB).
    - Session expiration check.
    - Active account check (rejects inactive or soft-deleted administrators).
    - Account lockout check.
    - Updates last_activity_at on valid request.
    """
    if not eb_admin_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. No session cookie provided.",
        )

    # Compute SHA-256 digest of incoming raw token
    token_digest = hash_session_token(eb_admin_session)

    # Fetch session and eagerly load admin user and roles
    stmt = (
        select(AdminSession)
        .options(
            selectinload(AdminSession.admin_user).selectinload(AdminUser.roles),
        )
        .where(AdminSession.id == token_digest)
    )
    result = await db.execute(stmt)
    admin_session = result.scalar_one_or_none()

    now = datetime.now(UTC)

    if not admin_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or unrecognized session",
        )

    # Verify session expiration
    if admin_session.expires_at <= now:
        await db.delete(admin_session)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired. Please log in again.",
        )

    user = admin_session.admin_user
    if not user:
        await db.delete(admin_session)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account associated with this session no longer exists.",
        )

    # Check account active and soft-deleted status
    if not user.is_active or user.deleted_at is not None:
        await db.delete(admin_session)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Administrator account is deactivated or deleted.",
        )

    # Check account lockout
    if user.locked_until and user.locked_until > now:
        await db.delete(admin_session)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Administrator account is temporarily locked.",
        )

    # Update session last activity timestamp
    admin_session.last_activity_at = now
    await db.commit()

    return admin_session, user


async def get_current_user(
    auth: Annotated[tuple[AdminSession, AdminUser], Depends(get_current_session_and_user)],
) -> AdminUser:
    """Dependency returning the validated AdminUser instance."""
    return auth[1]


async def get_current_session(
    auth: Annotated[tuple[AdminSession, AdminUser], Depends(get_current_session_and_user)],
) -> AdminSession:
    """Dependency returning the validated AdminSession instance."""
    return auth[0]


async def verify_csrf_token(
    request: Request,
    auth: Annotated[tuple[AdminSession, AdminUser], Depends(get_current_session_and_user)],
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> None:
    """Verifies layered CSRF defense for state-changing requests.

    Requirements:
    1. Origin / Referer validation.
    2. Explicit matching of X-CSRF-Token header against session.csrf_token using constant-time comparison.
    """
    # 1. Origin validation
    validate_request_origin(request)

    # 2. CSRF Token validation
    session = auth[0]
    if not x_csrf_token or not constant_time_compare(x_csrf_token, session.csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token validation failed. Invalid or missing X-CSRF-Token header.",
        )


def require_roles(*allowed_role_ids: str):
    """Centralized RBAC dependency factory enforcing required administrative roles.

    Raises HTTP 403 Forbidden if user lacks required role.
    """

    async def role_checker(
        user: Annotated[AdminUser, Depends(get_current_user)],
    ) -> AdminUser:
        user_role_ids = {role.id for role in user.roles}
        if not any(role_id in user_role_ids for role_id in allowed_role_ids):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {', '.join(allowed_role_ids)}",
            )
        return user

    return role_checker


# Pre-configured RBAC dependencies:
require_admin_user = require_roles("SUPER_ADMIN", "OPERATIONS_ADMIN")
require_super_admin = require_roles("SUPER_ADMIN")
require_operations_admin = require_roles("SUPER_ADMIN", "OPERATIONS_ADMIN")


# ==============================================================================
# Customer / investor portal authentication (CR-C4)
# ==============================================================================

from app.models.portal import (
    PORTAL_ROLE_CUSTOMER,
    PORTAL_ROLE_INVESTOR,
    PortalSession,
    PortalUser,
)
from app.services.portal_auth import cookie_name_for

PortalAuth = tuple[PortalSession, PortalUser]


def portal_auth(role: str):
    """Dependency factory: validates the session cookie belonging to ``role`` only.

    Each role has its own cookie, and the session row, the account and the requested area must
    all agree on the role. A customer session therefore cannot be replayed against investor
    endpoints (or the reverse) by renaming the cookie, and neither can reach administrator
    endpoints, which read a different cookie backed by a different table.
    """
    cookie_name = cookie_name_for(role)

    async def dependency(request: Request, db: Annotated[AsyncSession, Depends(get_db)]) -> PortalAuth:
        raw_token = request.cookies.get(cookie_name)
        if not raw_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

        stmt = (
            select(PortalSession)
            .options(selectinload(PortalSession.portal_user))
            .where(PortalSession.id == hash_session_token(raw_token))
        )
        session = (await db.execute(stmt)).scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or unrecognized session")

        now = datetime.now(UTC)
        user = session.portal_user
        invalid = (
            session.expires_at <= now
            or user is None
            or not user.is_active
            or user.email_verified_at is None
            or (user.locked_until is not None and user.locked_until > now)
        )
        if invalid:
            await db.delete(session)
            await db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is no longer valid")

        if session.role != role or user.role != role:
            # Wrong area for this account. The session is left intact; access is simply refused.
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account cannot access this area")

        session.last_activity_at = now
        await db.commit()
        return session, user

    return dependency


def portal_csrf(role: str):
    """Dependency factory: origin check plus X-CSRF-Token match for state-changing portal requests."""
    auth_dependency = portal_auth(role)

    async def dependency(
        request: Request,
        auth: Annotated[PortalAuth, Depends(auth_dependency)],
        x_csrf_token: Annotated[str | None, Header()] = None,
    ) -> PortalAuth:
        validate_request_origin(request)
        if not x_csrf_token or not constant_time_compare(x_csrf_token, auth[0].csrf_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token validation failed. Invalid or missing X-CSRF-Token header.",
            )
        return auth

    return dependency


customer_auth = portal_auth(PORTAL_ROLE_CUSTOMER)
customer_csrf = portal_csrf(PORTAL_ROLE_CUSTOMER)
investor_auth = portal_auth(PORTAL_ROLE_INVESTOR)
investor_csrf = portal_csrf(PORTAL_ROLE_INVESTOR)
