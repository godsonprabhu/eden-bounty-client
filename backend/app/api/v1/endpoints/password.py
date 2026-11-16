"""Public password endpoints for customer and investor accounts (security remediation, finding 1).

- POST /api/v1/auth/password/forgot  — request a reset link. Always the same answer.
- POST /api/v1/auth/password/status  — check an invitation/reset link before showing the form.
- POST /api/v1/auth/password/reset   — set a password from a link (invitation or reset).

Administrator passwords are not handled here: administrators are provisioned and reset with the
``create-admin`` CLI (DEPLOYMENT_GUIDE.md). A forgot-password request for an administrator email
gets the same generic answer as an unknown address and does nothing.

Tokens travel in the JSON body, never in a URL, so they do not reach access logs.
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, validate_request_origin
from app.core.config import settings
from app.core.login_throttle import login_failure_throttle, password_reset_throttle
from app.models.account_security import TOKEN_PURPOSE_RESET
from app.models.portal import PortalUser
from app.schemas.portal import (
    CompletePasswordLinkIn,
    Envelope,
    ForgotPasswordIn,
    LinkCompletedOut,
    LinkStatusOut,
    LinkTokenIn,
    Message,
)
from app.services.audit import record_security_event
from app.services.password_links import (
    DELIVERY_EMAIL,
    deliver_in_background,
    delivery_mode,
    find_valid_token,
    issue_link,
    login_path_for,
    redeem_link,
)

router = APIRouter(prefix="/auth/password", tags=["Authentication: password links"])

INVALID_LINK = "This link is invalid or has expired. Please request a new one."


def forgot_response(mode: str) -> str:
    """Wording depends only on the global delivery mode, never on the address submitted."""
    if mode == DELIVERY_EMAIL:
        return (
            "If an account exists for this email address, a password reset link has been sent to it. "
            f"The link expires in {settings.RESET_TOKEN_TTL_MINUTES} minutes."
        )
    return (
        "If an account exists for this email address, your request has been recorded and our team "
        "will contact you through your registered details to help you reset your password."
    )


@router.post("/forgot", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    payload: ForgotPasswordIn,
    request: Request,
    background: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Message:
    """Never reveals whether the address belongs to an account. Email is sent after the response
    is returned, so response time does not depend on it either."""
    validate_request_origin(request)
    await password_reset_throttle.check_ip(request)
    mode = delivery_mode()
    email = str(payload.email).strip().lower()

    if await password_reset_throttle.allow_email(email):
        user = (await db.execute(select(PortalUser).where(PortalUser.email == email))).scalar_one_or_none()
        if user is not None and user.is_active:
            if mode == DELIVERY_EMAIL:
                issued = await issue_link(db, user, TOKEN_PURPOSE_RESET, request=request)
                # Sent after the (identical) response; the outcome is audited, a failed link is
                # revoked, and administrators see it on the account page.
                background.add_task(deliver_in_background, user.id, user.role, user.email, user.full_name, issued)
            record_security_event(
                db, f"{user.role}_PASSWORD_RESET_REQUESTED", "portal_users", user.id,
                actor_email=user.email, new_state={"delivery": mode}, request=request,
            )
            await db.commit()

    return Message(message=forgot_response(mode))


@router.post("/status", response_model=Envelope[LinkStatusOut])
async def link_status(
    payload: LinkTokenIn,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Envelope[LinkStatusOut]:
    validate_request_origin(request)
    await login_failure_throttle.ensure_allowed(request)
    found = await find_valid_token(db, payload.token)
    if not found:
        await login_failure_throttle.record_failure(request)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_LINK)
    token, user = found
    return Envelope(
        data=LinkStatusOut(
            purpose=token.purpose, account_type=user.role, login_path=login_path_for(user.role), expires_at=token.expires_at
        )
    )


@router.post("/reset", response_model=Envelope[LinkCompletedOut])
async def complete_password_link(
    payload: CompletePasswordLinkIn,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Envelope[LinkCompletedOut]:
    """Sets the password, consumes the link, and signs the account out everywhere."""
    validate_request_origin(request)
    await login_failure_throttle.ensure_allowed(request)
    user = await redeem_link(db, payload.token, payload.new_password, request)
    if user is None:
        await db.rollback()
        await login_failure_throttle.record_failure(request)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_LINK)
    return Envelope(data=LinkCompletedOut(account_type=user.role, login_path=login_path_for(user.role)))


__all__ = ["INVALID_LINK", "forgot_response", "router"]
