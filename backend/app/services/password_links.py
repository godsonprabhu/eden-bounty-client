"""Invitation and password-reset links for customer and investor accounts (security remediation, finding 1).

Token rules
- 256-bit random token from the OS CSPRNG; only its SHA-256 digest is stored.
- Single use: redeeming marks it used inside the same transaction that sets the password, under a
  row lock, so two concurrent redemptions cannot both succeed.
- Issuing any new link revokes every earlier unused link for that account.
- Invitations expire after ``INVITATION_TOKEN_TTL_HOURS`` (72 h); resets after
  ``RESET_TOKEN_TTL_MINUTES`` (30 min).
- Setting a password through a link revokes every session and every other outstanding link for
  the account and clears sign-in lockout counters.

Delivery
- ``EMAIL``: SMTP is enabled (production only); the link is emailed to the account address and is
  never shown to anyone else.
- ``MANUAL``: SMTP is not available. An administrator issues the link in the console, sees it
  exactly once, and passes it to the account holder over a channel they trust. The link lives in
  the URL fragment (``#token=``) so it is never sent to servers, proxies or analytics in a request
  line or Referer header. Limitations are documented in SECURITY_AUDIT.md.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import get_client_ip
from app.core.security import generate_link_token, hash_password, hash_session_token
from app.models.account_security import (
    TOKEN_PURPOSE_INVITE,
    TOKEN_PURPOSE_RESET,
    TOKEN_PURPOSE_VERIFY,
    PortalAuthToken,
)
from app.models.admin import AdminUser
from app.models.portal import PORTAL_ROLE_INVESTOR, PortalSession, PortalUser
from app.services.audit import record_security_event
from app.services.mailer import email_delivery_available, send_email

DELIVERY_EMAIL = "EMAIL"
DELIVERY_MANUAL = "MANUAL"

# Outcome of handing a link to its holder (reported to the issuing administrator).
STATUS_SENT = "SENT"  # the SMTP server accepted the message
STATUS_FAILED = "FAILED"  # sending failed; the link was revoked, nothing usable left the system
STATUS_PENDING = "PENDING"  # forgot-password only: sent after the response, outcome audited
STATUS_SHOWN_ONCE = "SHOWN_ONCE"  # MANUAL delivery: returned once to the issuing administrator
_MAX_TOKEN_LENGTH = 128


@dataclass
class IssuedLink:
    purpose: str
    delivery: str
    expires_at: datetime
    # Present only for MANUAL delivery, and only in the response to the administrator who issued it.
    link: str | None
    raw_token: str
    token_hash: str = ""
    status: str = STATUS_PENDING


def delivery_mode() -> str:
    return DELIVERY_EMAIL if email_delivery_available() else DELIVERY_MANUAL


def build_link(raw_token: str) -> str:
    return f"{settings.PUBLIC_SITE_URL.rstrip('/')}/reset-password#token={raw_token}"


def build_verify_link(raw_token: str) -> str:
    return f"{settings.PUBLIC_SITE_URL.rstrip('/')}/verify-email#token={raw_token}"


def login_path_for(role: str) -> str:
    return "/investors/login" if role == PORTAL_ROLE_INVESTOR else "/login"


def _ttl(purpose: str) -> timedelta:
    if purpose == TOKEN_PURPOSE_INVITE:
        return timedelta(hours=settings.INVITATION_TOKEN_TTL_HOURS)
    if purpose == TOKEN_PURPOSE_VERIFY:
        return timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_TTL_HOURS)
    return timedelta(minutes=settings.RESET_TOKEN_TTL_MINUTES)


async def revoke_outstanding_tokens(db: AsyncSession, user: PortalUser, now: datetime | None = None) -> None:
    await db.execute(
        update(PortalAuthToken)
        .where(
            PortalAuthToken.portal_user_id == user.id,
            PortalAuthToken.used_at.is_(None),
            PortalAuthToken.revoked_at.is_(None),
        )
        .values(revoked_at=now or datetime.now(UTC))
    )


async def issue_link(
    db: AsyncSession,
    user: PortalUser,
    purpose: str,
    *,
    request: Request | None = None,
    admin: AdminUser | None = None,
) -> IssuedLink:
    """Creates a new token for ``user`` (revoking earlier ones). Caller commits."""
    now = datetime.now(UTC)
    await revoke_outstanding_tokens(db, user, now)
    raw = generate_link_token()
    digest = hash_session_token(raw)
    expires_at = now + _ttl(purpose)
    db.add(
        PortalAuthToken(
            portal_user_id=user.id,
            purpose=purpose,
            token_hash=digest,
            created_at=now,
            expires_at=expires_at,
            created_by_admin_id=admin.id if admin else None,
            requested_ip=get_client_ip(request) if request else None,
        )
    )
    mode = delivery_mode()
    link_fn = build_verify_link if purpose == TOKEN_PURPOSE_VERIFY else build_link
    return IssuedLink(
        purpose=purpose,
        delivery=mode,
        expires_at=expires_at,
        link=link_fn(raw) if mode == DELIVERY_MANUAL else None,
        raw_token=raw,
        token_hash=digest,
        status=STATUS_SHOWN_ONCE if mode == DELIVERY_MANUAL else STATUS_PENDING,
    )


async def _send_link_email(email: str, full_name: str, issued: IssuedLink) -> bool:
    """Emails the link to the account address. True only when the SMTP server accepted it."""
    if issued.purpose == TOKEN_PURPOSE_VERIFY:
        link = build_verify_link(issued.raw_token)
        subject = "Verify your EDEN BOUNTY account"
        body = (
            f"Hello {full_name},\n\n"
            "Thank you for registering on EDEN BOUNTY. Please verify your email address by visiting the "
            f"link below. It can be used once and expires in {settings.EMAIL_VERIFICATION_TOKEN_TTL_HOURS} hours:\n\n"
            f"{link}\n\n"
            "If you did not register for this account, you can safely ignore this message.\n"
        )
    elif issued.purpose == TOKEN_PURPOSE_INVITE:
        link = build_link(issued.raw_token)
        subject = "Your EDEN BOUNTY account invitation"
        body = (
            f"Hello {full_name},\n\n"
            "An account has been created for you on the EDEN BOUNTY portal. Use the link below to set "
            f"your password. It can be used once and expires in {settings.INVITATION_TOKEN_TTL_HOURS} hours.\n\n"
            f"{link}\n\n"
            "If you were not expecting this, you can ignore this message.\n"
        )
    else:
        link = build_link(issued.raw_token)
        subject = "Reset your EDEN BOUNTY password"
        body = (
            f"Hello {full_name},\n\n"
            "A password reset was requested for your EDEN BOUNTY portal account. Use the link below to "
            f"choose a new password. It can be used once and expires in {settings.RESET_TOKEN_TTL_MINUTES} minutes.\n\n"
            f"{link}\n\n"
            "If you did not ask for this, ignore this message; your password has not been changed.\n"
        )
    return await send_email(email, subject, body)


async def _record_email_outcome(
    db: AsyncSession,
    *,
    user_id,
    role: str,
    email: str,
    issued: IssuedLink,
    sent: bool,
    admin: AdminUser | None,
    request: Request | None,
) -> None:
    """Audits the delivery outcome. A link that could not be delivered is revoked at once, so a
    failed send never leaves a usable token behind (the retry issues a fresh one). Caller commits."""
    if not sent:
        await db.execute(
            update(PortalAuthToken)
            .where(PortalAuthToken.token_hash == issued.token_hash, PortalAuthToken.used_at.is_(None), PortalAuthToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
    record_security_event(
        db,
        f"{role}_LINK_EMAIL_{STATUS_SENT if sent else STATUS_FAILED}",
        "portal_users",
        user_id,
        actor_admin=admin,
        actor_email=None if admin else email,
        new_state={"purpose": issued.purpose, "link_revoked": not sent},
        request=request,
    )


async def deliver_now(
    db: AsyncSession, user: PortalUser, issued: IssuedLink, *, admin: AdminUser, request: Request
) -> IssuedLink:
    """Administrator-issued links: sends while the administrator waits, so the response states
    the real outcome. Call after the token has been committed. Commits the outcome."""
    if issued.delivery != DELIVERY_EMAIL:
        return issued
    sent = await _send_link_email(user.email, user.full_name, issued)
    await _record_email_outcome(
        db, user_id=user.id, role=user.role, email=user.email, issued=issued, sent=sent, admin=admin, request=request
    )
    await db.commit()
    issued.status = STATUS_SENT if sent else STATUS_FAILED
    return issued


async def deliver_in_background(user_id, role: str, email: str, full_name: str, issued: IssuedLink) -> None:
    """Forgot-password links: runs after the generic response was returned (no timing or content
    signal to the requester). The outcome is audited and shown to administrators on the account
    page; a failed link is revoked."""
    from app.db.session import AsyncSessionLocal

    sent = await _send_link_email(email, full_name, issued)
    async with AsyncSessionLocal() as db:
        await _record_email_outcome(
            db, user_id=user_id, role=role, email=email, issued=issued, sent=sent, admin=None, request=None
        )
        await db.commit()


async def find_valid_token(
    db: AsyncSession, raw_token: str | None, *, lock: bool = False
) -> tuple[PortalAuthToken, PortalUser] | None:
    if not raw_token or len(raw_token) > _MAX_TOKEN_LENGTH:
        return None
    stmt = select(PortalAuthToken).where(PortalAuthToken.token_hash == hash_session_token(raw_token))
    if lock:
        stmt = stmt.with_for_update()
    token = (await db.execute(stmt)).scalar_one_or_none()
    now = datetime.now(UTC)
    if token is None or token.used_at is not None or token.revoked_at is not None or token.expires_at <= now:
        return None
    user = (await db.execute(select(PortalUser).where(PortalUser.id == token.portal_user_id).with_for_update())).scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    return token, user


async def redeem_link(db: AsyncSession, raw_token: str, new_password: str, request: Request) -> PortalUser | None:
    """Sets the password for the token's account. Returns None for any invalid, used, revoked or
    expired token (the caller answers generically). Commits on success."""
    found = await find_valid_token(db, raw_token, lock=True)
    if not found:
        return None
    token, user = found
    now = datetime.now(UTC)
    token.used_at = now
    await db.flush()  # mark this token used before the bulk revoke, so it is recorded as used, not revoked
    await revoke_outstanding_tokens(db, user, now)
    user.password_hash = hash_password(new_password)
    user.password_changed_at = now
    user.failed_login_attempts = 0
    user.locked_until = None
    if user.email_verified_at is None:
        user.email_verified_at = now
    await db.execute(delete(PortalSession).where(PortalSession.portal_user_id == user.id))
    action = "INVITATION_ACCEPTED" if token.purpose == TOKEN_PURPOSE_INVITE else "PASSWORD_RESET_COMPLETED"
    record_security_event(
        db, f"{user.role}_{action}", "portal_users", user.id, actor_email=user.email,
        new_state={"sessions_revoked": True}, request=request,
    )
    await db.commit()
    return user


async def redeem_verification_token(
    db: AsyncSession,
    raw_token: str,
    *,
    request: Request | None = None,
) -> PortalUser:
    """Verifies a portal account's email address using a single-use verification token."""
    raw = (raw_token or "").strip()
    if not raw or len(raw) > _MAX_TOKEN_LENGTH:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification link")

    digest = hash_session_token(raw)
    now = datetime.now(UTC)

    stmt = (
        select(PortalAuthToken, PortalUser)
        .join(PortalUser, PortalAuthToken.portal_user_id == PortalUser.id)
        .where(
            PortalAuthToken.token_hash == digest,
            PortalAuthToken.purpose == TOKEN_PURPOSE_VERIFY,
            PortalAuthToken.used_at.is_(None),
            PortalAuthToken.revoked_at.is_(None),
            PortalAuthToken.expires_at > now,
        )
        .with_for_update()
    )
    found = (await db.execute(stmt)).first()
    if not found:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification link")

    token, user = found
    token.used_at = now
    user.email_verified_at = now
    record_security_event(
        db,
        f"{user.role}_EMAIL_VERIFIED",
        "portal_users",
        user.id,
        actor_email=user.email,
        new_state={"email_verified": True},
        request=request,
    )
    await db.commit()
    await db.refresh(user)
    return user


__all__ = [
    "DELIVERY_EMAIL",
    "DELIVERY_MANUAL",
    "STATUS_FAILED",
    "STATUS_PENDING",
    "STATUS_SENT",
    "STATUS_SHOWN_ONCE",
    "TOKEN_PURPOSE_INVITE",
    "TOKEN_PURPOSE_RESET",
    "TOKEN_PURPOSE_VERIFY",
    "IssuedLink",
    "build_link",
    "build_verify_link",
    "deliver_in_background",
    "deliver_now",
    "delivery_mode",
    "find_valid_token",
    "issue_link",
    "login_path_for",
    "redeem_link",
    "redeem_verification_token",
    "revoke_outstanding_tokens",
]
