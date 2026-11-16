"""Customer and investor portal endpoints (CR-C4, CR-C5, CR-C6).

Data isolation rule used throughout this module: every query is filtered by the identifier of
the authenticated account taken from the server-side session. No endpoint accepts a customer or
investor identifier from the client, and a record that belongs to someone else is reported as
404, exactly like a record that does not exist.
"""

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import (
    PortalAuth,
    customer_auth,
    customer_csrf,
    get_db,
    investor_auth,
    investor_csrf,
    validate_request_origin,
)
from app.core.login_throttle import login_failure_throttle
from app.core.security import hash_password, verify_password
from app.models.enquiry import Enquiry, EnquiryNote, EnquiryStatusHistory
from app.models.portal import (
    INVESTMENT_STATUSES,
    PORTAL_ROLE_CUSTOMER,
    PORTAL_ROLE_INVESTOR,
    Investment,
    InvestorDocument,
    InvestorUpdate,
    Order,
    PortalSession,
    PortalUser,
    Shipment,
)
from app.schemas.auth import LoginRequest
from app.schemas.portal import (
    CurrencyTotal,
    CustomerEnquiryDetail,
    CustomerEnquirySummary,
    CustomerOverview,
    DivisionAllocation,
    DivisionRef,
    EnquiryUpdateOut,
    Envelope,
    InvestmentOut,
    InvestorDocumentOut,
    InvestorOverview,
    InvestorUpdateOut,
    Message,
    OrderDetail,
    OrderSummary,
    PasswordChangeIn,
    PortalLoginData,
    PortalMe,
    PortalUserPublic,
    ProfileUpdateIn,
)
from app.services.audit import record_security_event
from app.services.password_links import revoke_outstanding_tokens
from app.services.portal_auth import (
    PORTAL_HOME,
    authenticate_portal_user,
    clear_portal_cookie,
    create_portal_session,
    record_failed_sign_in,
)
from app.services.storage import resolve_storage_path

customer_router = APIRouter(prefix="/customer", tags=["Customer Portal"])
investor_router = APIRouter(prefix="/investor", tags=["Investor Portal"])

CLOSED_ENQUIRY_STATUSES = {"COMPLETED", "CLOSED", "REJECTED", "CANCELLED", "DECLINED", "ARCHIVED"}
FINISHED_ORDER_STATUSES = {"COMPLETED", "CANCELLED"}
INVALID_CREDENTIALS = "Invalid email or password"


# ------------------------------------------------------------------ shared helpers
def _me(auth: PortalAuth) -> Envelope[PortalMe]:
    session, user = auth
    return Envelope(data=PortalMe(**PortalUserPublic.model_validate(user).model_dump(), last_login_at=user.last_login_at, csrf_token=session.csrf_token))


async def _logout(auth: PortalAuth, db: AsyncSession, request: Request, response: Response, role: str) -> Message:
    session, user = auth
    await db.delete(session)
    record_security_event(db, f"PORTAL_LOGOUT_{role}", "portal_users", user.id, actor_email=user.email, request=request)
    await db.commit()
    clear_portal_cookie(response, role)
    return Message(message="Logged out successfully")


async def _change_password(auth: PortalAuth, payload: PasswordChangeIn, db: AsyncSession, request: Request) -> Message:
    session, user = auth
    # A stolen session must not become an unlimited password-guessing oracle.
    await login_failure_throttle.ensure_allowed(request)
    if not verify_password(payload.current_password, user.password_hash):
        await login_failure_throttle.record_failure(request, user.email)
        record_security_event(
            db, f"{user.role}_PASSWORD_CHANGE_FAILED", "portal_users", user.id, actor_email=user.email,
            new_state={"reason": "bad_current_password"}, request=request,
        )
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must differ from the current one")
    now = datetime.now(UTC)
    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = now
    # Sign out every other device and cancel any outstanding reset/invitation link; keep the
    # session that made the change so the account holder is not thrown out mid-task.
    result = await db.execute(
        delete(PortalSession).where(PortalSession.portal_user_id == user.id, PortalSession.id != session.id)
    )
    await revoke_outstanding_tokens(db, user, now)
    record_security_event(
        db, f"{user.role}_PASSWORD_CHANGED", "portal_users", user.id, actor_email=user.email,
        new_state={"other_sessions_revoked": result.rowcount or 0}, request=request,
    )
    await db.commit()
    return Message(message="Password updated")


async def _update_profile(auth: PortalAuth, payload: ProfileUpdateIn, db: AsyncSession, request: Request) -> Envelope[PortalMe]:
    _, user = auth
    old: dict[str, str | None] = {}
    new: dict[str, str | None] = {}
    for field, value in payload.model_dump(exclude_unset=True).items():
        before = getattr(user, field)
        if field == "full_name":
            if value:
                user.full_name = value
        else:
            setattr(user, field, value or None)
        after = getattr(user, field)
        if after != before:
            old[field], new[field] = before, after
    if new:
        record_security_event(
            db, f"{user.role}_PROFILE_UPDATED", "portal_users", user.id, actor_email=user.email,
            old_state=old, new_state=new, request=request,
        )
    await db.commit()
    await db.refresh(user)
    return _me(auth)



def _enquiry_summary(enquiry: Enquiry) -> CustomerEnquirySummary:
    return CustomerEnquirySummary(
        id=enquiry.id,
        reference_number=enquiry.reference_number,
        division=DivisionRef.model_validate(enquiry.current_division),
        product_focus=enquiry.product_focus,
        status=enquiry.status,
        created_at=enquiry.created_at,
        updated_at=enquiry.updated_at,
    )


def _own_enquiries(user: PortalUser):
    return (
        select(Enquiry)
        .options(selectinload(Enquiry.current_division))
        .where(Enquiry.customer_id == user.id, Enquiry.deleted_at.is_(None))
    )


def _own_orders(user: PortalUser):
    return select(Order).options(selectinload(Order.division)).where(Order.customer_id == user.id)


# ------------------------------------------------------------------ customer: session
@customer_router.get("/me", response_model=Envelope[PortalMe], summary="Current customer identity")
async def customer_me(auth: Annotated[PortalAuth, Depends(customer_auth)]) -> Envelope[PortalMe]:
    return _me(auth)


@customer_router.post("/logout", response_model=Message, summary="End the customer session")
async def customer_logout(
    request: Request,
    response: Response,
    auth: Annotated[PortalAuth, Depends(customer_csrf)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Message:
    return await _logout(auth, db, request, response, PORTAL_ROLE_CUSTOMER)


@customer_router.post("/password", response_model=Message, summary="Change the customer's own password")
async def customer_password(
    payload: PasswordChangeIn,
    request: Request,
    auth: Annotated[PortalAuth, Depends(customer_csrf)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Message:
    return await _change_password(auth, payload, db, request)


@customer_router.patch("/profile", response_model=Envelope[PortalMe], summary="Update the customer's own contact details")
async def customer_profile(
    payload: ProfileUpdateIn,
    request: Request,
    auth: Annotated[PortalAuth, Depends(customer_csrf)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Envelope[PortalMe]:
    return await _update_profile(auth, payload, db, request)


# ------------------------------------------------------------------ customer: data
@customer_router.get("/overview", response_model=Envelope[CustomerOverview], summary="Customer dashboard summary")
async def customer_overview(
    auth: Annotated[PortalAuth, Depends(customer_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Envelope[CustomerOverview]:
    _, user = auth
    enquiries = (await db.execute(_own_enquiries(user).order_by(Enquiry.created_at.desc()))).scalars().all()
    orders = (await db.execute(_own_orders(user).order_by(Order.created_at.desc()))).scalars().all()
    return Envelope(
        data=CustomerOverview(
            enquiries_total=len(enquiries),
            enquiries_open=sum(1 for e in enquiries if e.status not in CLOSED_ENQUIRY_STATUSES),
            orders_total=len(orders),
            orders_active=sum(1 for o in orders if o.status not in FINISHED_ORDER_STATUSES),
            recent_enquiries=[_enquiry_summary(e) for e in enquiries[:5]],
            recent_orders=[OrderSummary.model_validate(o) for o in orders[:5]],
        )
    )


@customer_router.get("/enquiries", response_model=Envelope[list[CustomerEnquirySummary]], summary="The customer's own enquiries")
async def customer_enquiries(
    auth: Annotated[PortalAuth, Depends(customer_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Envelope[list[CustomerEnquirySummary]]:
    rows = (await db.execute(_own_enquiries(auth[1]).order_by(Enquiry.created_at.desc()))).scalars().all()
    return Envelope(data=[_enquiry_summary(e) for e in rows])


@customer_router.get("/enquiries/{enquiry_id}", response_model=Envelope[CustomerEnquiryDetail], summary="One of the customer's own enquiries")
async def customer_enquiry_detail(
    enquiry_id: UUID,
    auth: Annotated[PortalAuth, Depends(customer_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Envelope[CustomerEnquiryDetail]:
    _, user = auth
    enquiry = (await db.execute(_own_enquiries(user).where(Enquiry.id == enquiry_id))).scalar_one_or_none()
    if not enquiry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enquiry not found")

    # Customer-visible timeline: status changes (status names only, never the internal reason)
    # and notes an administrator explicitly marked as customer-visible.
    history = (
        await db.execute(select(EnquiryStatusHistory).where(EnquiryStatusHistory.enquiry_id == enquiry.id))
    ).scalars().all()
    messages = (
        await db.execute(
            select(EnquiryNote).where(EnquiryNote.enquiry_id == enquiry.id, EnquiryNote.is_internal_only.is_(False))
        )
    ).scalars().all()
    updates = [
        EnquiryUpdateOut(kind="STATUS", text=f"Status changed to {h.new_status.replace('_', ' ').title()}", created_at=h.created_at)
        for h in history
    ] + [EnquiryUpdateOut(kind="MESSAGE", text=n.note_text, created_at=n.created_at) for n in messages]
    updates.sort(key=lambda u: u.created_at, reverse=True)

    orders = (
        await db.execute(_own_orders(user).where(Order.enquiry_id == enquiry.id).order_by(Order.created_at.desc()))
    ).scalars().all()

    return Envelope(
        data=CustomerEnquiryDetail(
            **_enquiry_summary(enquiry).model_dump(),
            quantity=enquiry.quantity,
            unit_of_measurement=enquiry.unit_of_measurement,
            specifications=enquiry.specifications,
            additional_notes=enquiry.additional_notes,
            preferred_incoterm=enquiry.preferred_incoterm,
            target_destination_port=enquiry.target_destination_port,
            updates=updates,
            orders=[OrderSummary.model_validate(o) for o in orders],
        )
    )


@customer_router.get("/orders", response_model=Envelope[list[OrderDetail]], summary="The customer's own orders with tracking")
async def customer_orders(
    auth: Annotated[PortalAuth, Depends(customer_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Envelope[list[OrderDetail]]:
    stmt = (
        _own_orders(auth[1])
        .options(
            selectinload(Order.status_history),
            selectinload(Order.shipments).selectinload(Shipment.events),
            selectinload(Order.enquiry),
        )
        .order_by(Order.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return Envelope(data=[_order_detail(o) for o in rows])


def _order_detail(order: Order) -> OrderDetail:
    detail = OrderDetail.model_validate(order)
    detail.enquiry_reference = order.enquiry.reference_number if order.enquiry else None
    return detail


@customer_router.get("/orders/{order_id}", response_model=Envelope[OrderDetail], summary="One of the customer's own orders")
async def customer_order_detail(
    order_id: UUID,
    auth: Annotated[PortalAuth, Depends(customer_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Envelope[OrderDetail]:
    stmt = (
        _own_orders(auth[1])
        .options(
            selectinload(Order.status_history),
            selectinload(Order.shipments).selectinload(Shipment.events),
            selectinload(Order.enquiry),
        )
        .where(Order.id == order_id)
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return Envelope(data=_order_detail(order))


# ------------------------------------------------------------------ investor: session
@investor_router.post("/login", response_model=Envelope[PortalLoginData], summary="Investor sign-in (investor accounts only)")
async def investor_login(
    request: Request,
    response: Response,
    credentials: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Envelope[PortalLoginData]:
    """Authenticates investor accounts only. Administrator and customer credentials are refused
    here with the same generic error as a wrong password."""
    validate_request_origin(request)
    await login_failure_throttle.ensure_allowed(request)
    email = str(credentials.email).strip().lower()
    throttled = await login_failure_throttle.is_blocked_for_account(request, email)

    outcome = await authenticate_portal_user(db, email, credentials.password, PORTAL_ROLE_INVESTOR, throttled=throttled)
    user = outcome.user
    if not user:
        # Administrators are not portal accounts; an administrator email here is "unknown_account".
        await record_failed_sign_in(
            db, request, email, portal="investor", reason=outcome.reason,
            account_table="portal_users" if outcome.account else None,
            account_id=outcome.account.id if outcome.account else None,
            account_email=outcome.account.email if outcome.account else None,
        )
        if outcome.reason == "email_unverified":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please verify your email address before signing in.",
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS)
    await login_failure_throttle.record_success(request, email)

    csrf_token = await create_portal_session(db, user, request, response)
    return Envelope(
        data=PortalLoginData(
            user=PortalUserPublic.model_validate(user),
            csrf_token=csrf_token,
            account_type=PORTAL_ROLE_INVESTOR,
            redirect_to=PORTAL_HOME[PORTAL_ROLE_INVESTOR],
        )
    )


@investor_router.get("/me", response_model=Envelope[PortalMe], summary="Current investor identity")
async def investor_me(auth: Annotated[PortalAuth, Depends(investor_auth)]) -> Envelope[PortalMe]:
    return _me(auth)


@investor_router.post("/logout", response_model=Message, summary="End the investor session")
async def investor_logout(
    request: Request,
    response: Response,
    auth: Annotated[PortalAuth, Depends(investor_csrf)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Message:
    return await _logout(auth, db, request, response, PORTAL_ROLE_INVESTOR)


@investor_router.post("/password", response_model=Message, summary="Change the investor's own password")
async def investor_password(
    payload: PasswordChangeIn,
    request: Request,
    auth: Annotated[PortalAuth, Depends(investor_csrf)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Message:
    return await _change_password(auth, payload, db, request)


@investor_router.patch("/profile", response_model=Envelope[PortalMe], summary="Update the investor's own contact details")
async def investor_profile(
    payload: ProfileUpdateIn,
    request: Request,
    auth: Annotated[PortalAuth, Depends(investor_csrf)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Envelope[PortalMe]:
    return await _update_profile(auth, payload, db, request)


# ------------------------------------------------------------------ investor: data
def _own_investments(user: PortalUser):
    return select(Investment).options(selectinload(Investment.division)).where(Investment.investor_id == user.id)


@investor_router.get("/investments", response_model=Envelope[list[InvestmentOut]], summary="The investor's own investment records")
async def investor_investments(
    auth: Annotated[PortalAuth, Depends(investor_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Envelope[list[InvestmentOut]]:
    rows = (await db.execute(_own_investments(auth[1]).order_by(Investment.invested_on.desc()))).scalars().all()
    return Envelope(data=[InvestmentOut.model_validate(r) for r in rows])


@investor_router.get("/overview", response_model=Envelope[InvestorOverview], summary="Investor dashboard summary")
async def investor_overview(
    auth: Annotated[PortalAuth, Depends(investor_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Envelope[InvestorOverview]:
    """Totals are sums of recorded amounts only. Cancelled records are excluded from totals.
    No returns, valuations or projections are calculated."""
    rows = (await db.execute(_own_investments(auth[1]).order_by(Investment.invested_on.desc()))).scalars().all()
    counted = [r for r in rows if r.status != "CANCELLED"]

    totals: dict[str, Decimal] = defaultdict(Decimal)
    active: dict[str, Decimal] = defaultdict(Decimal)
    by_division: dict[tuple[str, str], list[Investment]] = defaultdict(list)
    for r in counted:
        totals[r.currency] += r.amount
        if r.status == "ACTIVE":
            active[r.currency] += r.amount
        by_division[(r.currency, r.division_id)].append(r)

    allocation = [
        DivisionAllocation(
            division=DivisionRef.model_validate(items[0].division),
            currency=currency,
            amount=sum((i.amount for i in items), Decimal(0)),
            share_percent=(sum((i.amount for i in items), Decimal(0)) / totals[currency] * 100).quantize(Decimal("0.1")),
            investments=len(items),
        )
        for (currency, _), items in by_division.items()
    ]
    allocation.sort(key=lambda a: (a.currency, -a.amount))

    return Envelope(
        data=InvestorOverview(
            totals=[CurrencyTotal(currency=c, total=t, active_total=active[c]) for c, t in sorted(totals.items())],
            investments_count=len(rows),
            status_counts={s: sum(1 for r in rows if r.status == s) for s in INVESTMENT_STATUSES},
            allocation=allocation,
            recent_investments=[InvestmentOut.model_validate(r) for r in rows[:5]],
        )
    )


@investor_router.get("/documents", response_model=Envelope[list[InvestorDocumentOut]], summary="Published documents for this investor")
async def investor_documents(
    auth: Annotated[PortalAuth, Depends(investor_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Envelope[list[InvestorDocumentOut]]:
    stmt = (
        select(InvestorDocument)
        .where(InvestorDocument.investor_id == auth[1].id, InvestorDocument.is_published.is_(True))
        .order_by(InvestorDocument.published_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return Envelope(data=[InvestorDocumentOut.model_validate(r) for r in rows])


@investor_router.get("/documents/{document_id}/download", summary="Authenticated download of one of the investor's own documents")
async def investor_document_download(
    document_id: UUID,
    auth: Annotated[PortalAuth, Depends(investor_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FileResponse:
    stmt = select(InvestorDocument).where(
        InvestorDocument.id == document_id,
        InvestorDocument.investor_id == auth[1].id,
        InvestorDocument.is_published.is_(True),
    )
    document = (await db.execute(stmt)).scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document_response(document)


def document_response(document: InvestorDocument) -> FileResponse:
    path = resolve_storage_path(document.storage_key)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return FileResponse(
        path,
        media_type=document.content_type,
        filename=document.original_filename,
        content_disposition_type="attachment",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            # If the file is ever rendered inline, it gets no scripts, no network and a unique origin.
            "Content-Security-Policy": "default-src 'none'; sandbox; frame-ancestors 'none'",
        },
    )


@investor_router.get("/updates", response_model=Envelope[list[InvestorUpdateOut]], summary="Published investor updates")
async def investor_updates(
    auth: Annotated[PortalAuth, Depends(investor_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Envelope[list[InvestorUpdateOut]]:
    """Updates addressed to this investor, plus announcements addressed to all investors."""
    stmt = (
        select(InvestorUpdate)
        .where(
            InvestorUpdate.is_published.is_(True),
            or_(InvestorUpdate.investor_id == auth[1].id, InvestorUpdate.investor_id.is_(None)),
        )
        .order_by(InvestorUpdate.published_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return Envelope(data=[InvestorUpdateOut.model_validate(r) for r in rows])


__all__ = ["customer_router", "document_response", "investor_router"]
