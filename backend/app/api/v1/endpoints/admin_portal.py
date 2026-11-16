"""Administrator management of customers, investors, orders and investments (CR-C7).

Permissions:
- Customers, enquiry linking and orders: SUPER_ADMIN or OPERATIONS_ADMIN.
- Investor accounts, investments, investor documents and investor updates: SUPER_ADMIN only,
  because they are confidential financial records.

Every mutation is CSRF-protected and writes an audit record in the same transaction.
"""

import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from app.api.deps import (
    get_current_user,
    get_db,
    require_admin_user,
    require_super_admin,
    verify_csrf_token,
)
from app.api.v1.endpoints.portal import document_response
from app.core.security import make_unusable_password
from app.models.account_security import (
    TOKEN_PURPOSE_INVITE,
    TOKEN_PURPOSE_RESET,
    TOKEN_PURPOSE_VERIFY,
    PortalAuthToken,
)
from app.models.admin import AdminUser
from app.models.audit import AuditLog
from app.models.division import Division
from app.models.enquiry import Enquiry, EnquiryNote
from app.models.portal import (
    ORDER_STATUSES,
    PORTAL_ROLE_CUSTOMER,
    PORTAL_ROLE_INVESTOR,
    PORTAL_ROLES,
    Investment,
    InvestorDocument,
    InvestorUpdate,
    Order,
    OrderStatusHistory,
    PortalSession,
    PortalUser,
    Shipment,
    ShipmentEvent,
)
from app.schemas.portal import (
    ActiveLinkOut,
    AdminEnquiryRef,
    AdminInvestmentOut,
    AdminOrderDetail,
    AdminOrderSummary,
    CurrencyTotal,
    CustomerUpdateIn,
    DocumentPublishIn,
    EnquiryCustomerLink,
    Envelope,
    InvestmentCreateIn,
    InvestmentOut,
    InvestmentUpdateIn,
    InvestorDocumentOut,
    InvestorUpdateIn,
    InvestorUpdateOut,
    InvestorUpdatePatchIn,
    LastLinkEmailOut,
    LinkCustomerIn,
    Message,
    OrderCreateIn,
    OrderStatusIn,
    OrderSummary,
    PasswordLinkOut,
    PortalSummary,
    PortalUserAdminDetail,
    PortalUserAdminOut,
    PortalUserCreatedOut,
    PortalUserCreateIn,
    PortalUserPublic,
    PortalUserUpdateIn,
    ShipmentEventIn,
    ShipmentEventOut,
    ShipmentIn,
    ShipmentOut,
    document_category,
)
from app.services.audit import record_audit_log
from app.services.password_links import (
    IssuedLink,
    deliver_now,
    issue_link,
    revoke_outstanding_tokens,
)
from app.services.storage import remove_stored_file, store_upload
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/admin", tags=["Admin: Customers, Investors & Orders"])

Db = Annotated[AsyncSession, Depends(get_db)]
Admin = Annotated[AdminUser, Depends(get_current_user)]
READ = [Depends(require_admin_user)]
WRITE = [Depends(require_admin_user), Depends(verify_csrf_token)]
SUPER_READ = [Depends(require_super_admin)]
SUPER_WRITE = [Depends(require_super_admin), Depends(verify_csrf_token)]


def _is_super(admin: AdminUser) -> bool:
    return any(r.id == "SUPER_ADMIN" for r in admin.roles)


def _require_role_access(admin: AdminUser, role: str) -> None:
    if role == PORTAL_ROLE_INVESTOR and not _is_super(admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Required role: SUPER_ADMIN",
        )


def _reference(prefix: str) -> str:
    return f"EB-{prefix}-{datetime.now(UTC):%Y%m%d}-{secrets.token_hex(4).upper()}"


def _jsonable(data: dict[str, Any]) -> dict[str, Any]:
    return {k: (str(v) if v is not None and not isinstance(v, (bool, int, str)) else v) for k, v in data.items()}


async def _get_portal_user(db: AsyncSession, user_id: UUID, role: str | None = None) -> PortalUser:
    user = (await db.execute(select(PortalUser).where(PortalUser.id == user_id))).scalar_one_or_none()
    if not user or (role and user.role != role):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return user


async def _get_division(db: AsyncSession, division_id: str) -> Division:
    division = (await db.execute(select(Division).where(Division.id == division_id))).scalar_one_or_none()
    if not division:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Division '{division_id}' does not exist")
    return division


# ============================================================================== overview
@router.get("/dashboard/portal-summary", response_model=Envelope[PortalSummary], dependencies=READ)
async def portal_summary(db: Db, admin: Admin) -> Envelope[PortalSummary]:
    """Totals for customers, investors, enquiries and orders. Investment figures only for SUPER_ADMIN."""
    role_counts = dict((await db.execute(select(PortalUser.role, func.count()).group_by(PortalUser.role))).all())
    order_counts = dict((await db.execute(select(Order.status, func.count()).group_by(Order.status))).all())
    total_enquiries = (await db.execute(select(func.count()).select_from(Enquiry).where(Enquiry.deleted_at.is_(None)))).scalar_one()

    investment_totals = None
    investments_count = None
    if _is_super(admin):
        rows = (
            await db.execute(
                select(Investment.currency, Investment.status, func.sum(Investment.amount), func.count())
                .where(Investment.status != "CANCELLED")
                .group_by(Investment.currency, Investment.status)
            )
        ).all()
        totals: dict[str, list[Decimal]] = {}
        investments_count = 0
        for currency, inv_status, amount, count in rows:
            bucket = totals.setdefault(currency, [Decimal(0), Decimal(0)])
            bucket[0] += amount
            if inv_status == "ACTIVE":
                bucket[1] += amount
            investments_count += count
        investment_totals = [CurrencyTotal(currency=c, total=t[0], active_total=t[1]) for c, t in sorted(totals.items())]

    return Envelope(
        data=PortalSummary(
            total_customers=role_counts.get(PORTAL_ROLE_CUSTOMER, 0),
            total_investors=role_counts.get(PORTAL_ROLE_INVESTOR, 0),
            total_enquiries=total_enquiries,
            total_orders=sum(order_counts.values()),
            orders_by_status={s: order_counts.get(s, 0) for s in ORDER_STATUSES},
            investment_totals=investment_totals,
            investments_count=investments_count,
        )
    )


# ============================================================================== accounts
@router.get("/portal-users", response_model=Envelope[list[PortalUserAdminOut]], dependencies=READ)
async def list_portal_users(
    db: Db,
    admin: Admin,
    role: Annotated[str, Query(description="CUSTOMER or INVESTOR")],
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> Envelope[list[PortalUserAdminOut]]:
    role = role.strip().upper()
    if role not in PORTAL_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="role must be CUSTOMER or INVESTOR")
    _require_role_access(admin, role)
    stmt = select(PortalUser).where(PortalUser.role == role).order_by(PortalUser.created_at.desc())
    if search and search.strip():
        like = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(PortalUser.email).like(like),
                func.lower(PortalUser.full_name).like(like),
                func.lower(func.coalesce(PortalUser.company_name, "")).like(like),
            )
        )
    rows = (await db.execute(stmt)).scalars().all()
    return Envelope(data=[PortalUserAdminOut.model_validate(r) for r in rows])


@router.post("/portal-users", response_model=Envelope[PortalUserCreatedOut], status_code=status.HTTP_201_CREATED, dependencies=WRITE)
async def create_portal_user(
    payload: PortalUserCreateIn, request: Request, response: Response, db: Db, admin: Admin
) -> Envelope[PortalUserCreatedOut]:
    """Creates a customer or investor account and issues its invitation link.

    The account has no usable password until the holder sets one from the link, so no administrator
    ever chooses or sees it. One email address maps to exactly one account across administrators,
    customers and investors (also enforced by the database, migration 0009)."""
    _require_role_access(admin, payload.role)
    email = str(payload.email).strip().lower()

    taken_by_admin = (await db.execute(select(AdminUser.id).where(AdminUser.email == email))).first()
    taken_by_portal = (await db.execute(select(PortalUser.id).where(PortalUser.email == email))).first()
    if taken_by_admin or taken_by_portal:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email address already exists")

    user = PortalUser(
        email=email,
        password_hash=make_unusable_password(),
        role=payload.role,
        full_name=payload.full_name,
        company_name=payload.company_name or None,
        contact_number=payload.contact_number or None,
        country=payload.country or None,
        created_by_admin_id=admin.id,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:  # concurrent creation of the same email (account_email_registry)
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email address already exists") from exc
    issued = await issue_link(db, user, TOKEN_PURPOSE_INVITE, request=request, admin=admin)
    await record_audit_log(
        db, admin, f"{payload.role}_ACCOUNT_CREATED", "portal_users", user.id, None,
        {"email": email, "role": payload.role, "full_name": user.full_name, "invitation_delivery": issued.delivery}, request,
    )
    await db.commit()
    await db.refresh(user)
    user_out = PortalUserAdminOut.model_validate(user).model_dump()
    # The account exists either way; if the invitation email fails, the link is revoked and the
    # administrator is told so and can resend it.
    issued = await deliver_now(db, user, issued, admin=admin, request=request)
    response.headers["Cache-Control"] = "no-store"
    return Envelope(data=PortalUserCreatedOut(**user_out, invitation=_link_out(issued)))


def _link_out(issued: IssuedLink) -> PasswordLinkOut:
    return PasswordLinkOut(
        purpose=issued.purpose, delivery=issued.delivery, delivery_status=issued.status,
        expires_at=issued.expires_at, link=issued.link,
    )


@router.get("/portal-users/{user_id}", response_model=Envelope[PortalUserAdminDetail], dependencies=READ)
async def get_portal_user(user_id: UUID, db: Db, admin: Admin) -> Envelope[PortalUserAdminDetail]:
    user = await _get_portal_user(db, user_id)
    _require_role_access(admin, user.role)
    detail = PortalUserAdminDetail(**PortalUserAdminOut.model_validate(user).model_dump())

    now = datetime.now(UTC)
    link = (
        await db.execute(
            select(PortalAuthToken)
            .where(
                PortalAuthToken.portal_user_id == user.id,
                PortalAuthToken.used_at.is_(None),
                PortalAuthToken.revoked_at.is_(None),
                PortalAuthToken.expires_at > now,
            )
            .order_by(PortalAuthToken.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if link:
        detail.active_link = ActiveLinkOut(purpose=link.purpose, created_at=link.created_at, expires_at=link.expires_at)
    last_email = (
        await db.execute(
            select(AuditLog.action, AuditLog.timestamp)
            .where(
                AuditLog.entity_table == "portal_users",
                AuditLog.entity_id == user.id,
                AuditLog.action.in_([f"{user.role}_LINK_EMAIL_SENT", f"{user.role}_LINK_EMAIL_FAILED"]),
                AuditLog.timestamp > now - timedelta(days=7),
            )
            .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
            .limit(1)
        )
    ).first()
    if last_email:
        detail.last_link_email = LastLinkEmailOut(status=last_email.action.rsplit("_", 1)[1], at=last_email.timestamp)
    detail.reset_requested_at = (
        await db.execute(
            select(func.max(AuditLog.timestamp)).where(
                AuditLog.entity_table == "portal_users",
                AuditLog.entity_id == user.id,
                AuditLog.action == f"{user.role}_PASSWORD_RESET_REQUESTED",
                AuditLog.timestamp > now - timedelta(days=7),
            )
        )
    ).scalar_one_or_none()

    if user.role == PORTAL_ROLE_CUSTOMER:
        enquiries = (
            await db.execute(
                select(Enquiry).where(Enquiry.customer_id == user.id, Enquiry.deleted_at.is_(None)).order_by(Enquiry.created_at.desc())
            )
        ).scalars().all()
        detail.enquiries = [
            AdminEnquiryRef(
                id=e.id, reference_number=e.reference_number, company_name=e.company_name,
                product_focus=e.product_focus, status=e.status, created_at=e.created_at,
            )
            for e in enquiries
        ]
        orders = (
            await db.execute(
                select(Order).options(selectinload(Order.division)).where(Order.customer_id == user.id).order_by(Order.created_at.desc())
            )
        ).scalars().all()
        detail.orders = [OrderSummary.model_validate(o) for o in orders]
    else:
        investments = (
            await db.execute(
                select(Investment).options(selectinload(Investment.division))
                .where(Investment.investor_id == user.id).order_by(Investment.invested_on.desc())
            )
        ).scalars().all()
        detail.investments = [InvestmentOut.model_validate(i) for i in investments]
        documents = (
            await db.execute(
                select(InvestorDocument).where(InvestorDocument.investor_id == user.id).order_by(InvestorDocument.created_at.desc())
            )
        ).scalars().all()
        detail.documents = [InvestorDocumentOut.model_validate(d) for d in documents]
    return Envelope(data=detail)


@router.patch("/portal-users/{user_id}", response_model=Envelope[PortalUserAdminOut], dependencies=WRITE)
async def update_portal_user(user_id: UUID, payload: PortalUserUpdateIn, request: Request, db: Db, admin: Admin) -> Envelope[PortalUserAdminOut]:
    user = await _get_portal_user(db, user_id)
    _require_role_access(admin, user.role)
    changes = payload.model_dump(exclude_unset=True)
    old = {k: getattr(user, k) for k in changes}
    for field, value in changes.items():
        if field == "full_name":
            if value:
                user.full_name = value
        elif field == "is_active":
            if value is not None:
                user.is_active = value
        else:
            setattr(user, field, value or None)
    if changes.get("is_active") is False:
        # Deactivation takes effect immediately: every open session and unused link is revoked.
        await db.execute(delete(PortalSession).where(PortalSession.portal_user_id == user.id))
        await revoke_outstanding_tokens(db, user)
    if changes.get("is_active") is True:
        user.failed_login_attempts = 0
        user.locked_until = None
    await record_audit_log(db, admin, f"{user.role}_ACCOUNT_UPDATED", "portal_users", user.id, _jsonable(old), _jsonable(changes), request)
    await db.commit()
    await db.refresh(user)
    return Envelope(data=PortalUserAdminOut.model_validate(user))


@router.post("/portal-users/{user_id}/password-link", response_model=Envelope[PasswordLinkOut], dependencies=WRITE)
async def issue_password_link(user_id: UUID, request: Request, response: Response, db: Db, admin: Admin) -> Envelope[PasswordLinkOut]:
    """Issues a fresh invitation (account has no password yet) or password-reset link.

    Replaces the former admin "set password" action: administrators can no longer choose or see a
    customer's or investor's password. Any earlier unused link is revoked. The current password
    keeps working until the holder uses the link, at which point every session is signed out.
    With email delivery the link goes only to the account address and the response reports whether
    the SMTP server accepted it (a failed link is revoked; call this again to retry). Otherwise it
    is returned here once for the administrator to pass on over a trusted channel."""
    user = await _get_portal_user(db, user_id)
    _require_role_access(admin, user.role)
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Activate the account before sending it a link")
    purpose = TOKEN_PURPOSE_INVITE if user.invitation_pending else TOKEN_PURPOSE_RESET
    issued = await issue_link(db, user, purpose, request=request, admin=admin)
    action = "INVITATION_ISSUED" if purpose == TOKEN_PURPOSE_INVITE else "PASSWORD_RESET_LINK_ISSUED"
    await record_audit_log(
        db, admin, f"{user.role}_{action}", "portal_users", user.id, None,
        {"delivery": issued.delivery, "expires_at": issued.expires_at.isoformat()}, request,
    )
    await db.commit()
    issued = await deliver_now(db, user, issued, admin=admin, request=request)
    response.headers["Cache-Control"] = "no-store"
    return Envelope(data=_link_out(issued))


@router.post("/portal-users/{user_id}/verification-link", response_model=Envelope[PasswordLinkOut], dependencies=WRITE)
async def issue_verification_link(
    user_id: UUID, request: Request, response: Response, db: Db, admin: Admin
) -> Envelope[PasswordLinkOut]:
    """Issues a single-use email verification link for an unverified customer or investor account.

    In manual delivery mode (local/preview with SMTP disabled), the link is returned once to the
    authenticated administrator to communicate to the account holder over a trusted channel. In
    production email mode, the link is dispatched via SMTP."""
    user = await _get_portal_user(db, user_id)
    _require_role_access(admin, user.role)
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Activate the account before sending it a link")
    if user.email_verified_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already verified")
    issued = await issue_link(db, user, TOKEN_PURPOSE_VERIFY, request=request, admin=admin)
    await record_audit_log(
        db,
        admin,
        f"{user.role}_EMAIL_VERIFICATION_LINK_ISSUED",
        "portal_users",
        user.id,
        None,
        {"delivery": issued.delivery, "expires_at": issued.expires_at.isoformat()},
        request,
    )
    await db.commit()
    issued = await deliver_now(db, user, issued, admin=admin, request=request)
    response.headers["Cache-Control"] = "no-store"
    return Envelope(data=_link_out(issued))


@router.post("/portal-users/{user_id}/verify", response_model=Envelope[PortalUserAdminOut], dependencies=WRITE)
async def verify_portal_user(
    user_id: UUID, request: Request, db: Db, admin: Admin
) -> Envelope[PortalUserAdminOut]:
    """Directly marks an unverified customer or investor account email as verified by an authorized administrator.

    Revokes any outstanding verification tokens for the user."""
    user = await _get_portal_user(db, user_id)
    _require_role_access(admin, user.role)
    if user.email_verified_at is not None:
        return Envelope(data=PortalUserAdminOut.model_validate(user))
    now = datetime.now(UTC)
    user.email_verified_at = now
    await revoke_outstanding_tokens(db, user, now)
    await record_audit_log(
        db,
        admin,
        f"{user.role}_EMAIL_ADMIN_VERIFIED",
        "portal_users",
        user.id,
        None,
        {"email_verified_at": now.isoformat()},
        request,
    )
    await db.commit()
    await db.refresh(user)
    return Envelope(data=PortalUserAdminOut.model_validate(user))


# ============================================================================== enquiry <-> customer
async def _get_enquiry(db: AsyncSession, enquiry_id: UUID) -> Enquiry:
    enquiry = (
        await db.execute(select(Enquiry).where(Enquiry.id == enquiry_id, Enquiry.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if not enquiry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enquiry not found")
    return enquiry


@router.get("/rfqs/{enquiry_id}/customer", response_model=Envelope[EnquiryCustomerLink], dependencies=READ)
async def get_enquiry_customer(enquiry_id: UUID, db: Db) -> Envelope[EnquiryCustomerLink]:
    """The customer account an enquiry is linked to (if any) and the orders created from it."""
    enquiry = await _get_enquiry(db, enquiry_id)
    customer = None
    if enquiry.customer_id:
        customer = (await db.execute(select(PortalUser).where(PortalUser.id == enquiry.customer_id))).scalar_one_or_none()
    orders = (
        await db.execute(
            select(Order).options(selectinload(Order.division)).where(Order.enquiry_id == enquiry.id).order_by(Order.created_at.desc())
        )
    ).scalars().all()
    return Envelope(
        data=EnquiryCustomerLink(
            customer=PortalUserPublic.model_validate(customer) if customer else None,
            orders=[OrderSummary.model_validate(o) for o in orders],
        )
    )


@router.post("/rfqs/{enquiry_id}/customer", response_model=Message, dependencies=WRITE)
async def link_enquiry_customer(enquiry_id: UUID, payload: LinkCustomerIn, request: Request, db: Db, admin: Admin) -> Message:
    """Links an enquiry to a customer account, or unlinks it (customer_id null).

    This explicit administrator action is the only way an enquiry becomes visible in a customer
    dashboard. Enquiries are never linked automatically from a matching email address.
    """
    enquiry = await _get_enquiry(db, enquiry_id)
    old = {"customer_id": str(enquiry.customer_id) if enquiry.customer_id else None}
    if payload.customer_id is None:
        enquiry.customer_id = None
        action = "ENQUIRY_CUSTOMER_UNLINKED"
    else:
        customer = await _get_portal_user(db, payload.customer_id, PORTAL_ROLE_CUSTOMER)
        enquiry.customer_id = customer.id
        action = "ENQUIRY_CUSTOMER_LINKED"
    await record_audit_log(
        db, admin, action, "enquiries", enquiry.id, old,
        {"customer_id": str(enquiry.customer_id) if enquiry.customer_id else None}, request,
    )
    await db.commit()
    return Message(message="Enquiry linked to customer" if payload.customer_id else "Enquiry unlinked")


@router.post("/rfqs/{enquiry_id}/customer-updates", response_model=Message, status_code=status.HTTP_201_CREATED, dependencies=WRITE)
async def add_customer_visible_update(enquiry_id: UUID, payload: CustomerUpdateIn, request: Request, db: Db, admin: Admin) -> Message:
    """Posts a message the linked customer can read. Internal notes use the existing notes endpoint
    and are never shown to customers."""
    enquiry = await _get_enquiry(db, enquiry_id)
    note = EnquiryNote(enquiry_id=enquiry.id, admin_user_id=admin.id, note_text=payload.message, is_internal_only=False)
    db.add(note)
    await db.flush()
    await record_audit_log(
        db, admin, "ENQUIRY_CUSTOMER_UPDATE_POSTED", "enquiry_notes", note.id, None,
        {"enquiry_id": str(enquiry.id), "is_internal_only": False}, request,
    )
    await db.commit()
    return Message(message="Customer-visible update posted")


# ============================================================================== orders
def _order_query():
    return select(Order).options(
        selectinload(Order.division),
        selectinload(Order.customer),
        selectinload(Order.enquiry),
        selectinload(Order.status_history),
        selectinload(Order.shipments).selectinload(Shipment.events),
    )


async def _get_order(db: AsyncSession, order_id: UUID) -> Order:
    order = (await db.execute(_order_query().where(Order.id == order_id))).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


def _admin_order_detail(order: Order) -> AdminOrderDetail:
    detail = AdminOrderDetail.model_validate(order)
    detail.enquiry_reference = order.enquiry.reference_number if order.enquiry else None
    return detail


@router.get("/orders", response_model=Envelope[list[AdminOrderSummary]], dependencies=READ)
async def list_orders(
    db: Db,
    order_status: Annotated[str | None, Query(alias="status")] = None,
    customer_id: UUID | None = None,
) -> Envelope[list[AdminOrderSummary]]:
    stmt = select(Order).options(selectinload(Order.division), selectinload(Order.customer)).order_by(Order.created_at.desc())
    if order_status:
        stmt = stmt.where(Order.status == order_status.strip().upper())
    if customer_id:
        stmt = stmt.where(Order.customer_id == customer_id)
    rows = (await db.execute(stmt)).scalars().all()
    return Envelope(data=[AdminOrderSummary.model_validate(o) for o in rows])


@router.post("/orders", response_model=Envelope[AdminOrderDetail], status_code=status.HTTP_201_CREATED, dependencies=WRITE)
async def create_order(payload: OrderCreateIn, request: Request, db: Db, admin: Admin) -> Envelope[AdminOrderDetail]:
    """Creates an order for a customer, optionally converting an enquiry.

    When ``enquiry_id`` is given, missing order fields default to the enquiry's values and the
    enquiry is linked to the customer (it must not already belong to a different customer).
    """
    customer = await _get_portal_user(db, payload.customer_id, PORTAL_ROLE_CUSTOMER)
    if not customer.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot create an order for a deactivated customer")

    enquiry: Enquiry | None = None
    if payload.enquiry_id:
        enquiry = await _get_enquiry(db, payload.enquiry_id)
        if enquiry.customer_id and enquiry.customer_id != customer.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This enquiry is linked to a different customer")

    division_id = payload.division_id or (enquiry.current_division_id if enquiry else None)
    product = payload.product_description or (enquiry.product_focus if enquiry else None)
    if not division_id or not product:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="division_id and product_description are required")
    await _get_division(db, division_id)
    if payload.total_amount is not None and not payload.currency:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="currency is required when total_amount is given")

    order = Order(
        reference_number=_reference("ORD"),
        customer_id=customer.id,
        enquiry_id=enquiry.id if enquiry else None,
        division_id=division_id,
        product_description=product,
        quantity=payload.quantity if payload.quantity is not None else (enquiry.quantity if enquiry else None),
        unit_of_measurement=payload.unit_of_measurement or (enquiry.unit_of_measurement if enquiry else None),
        total_amount=payload.total_amount,
        currency=payload.currency,
        status="CONFIRMED",
        customer_note=payload.customer_note or None,
        created_by_admin_id=admin.id,
    )
    db.add(order)
    await db.flush()
    db.add(OrderStatusHistory(order_id=order.id, old_status=None, new_status="CONFIRMED", note="Order created", changed_by_admin_id=admin.id))
    if enquiry and enquiry.customer_id is None:
        enquiry.customer_id = customer.id
        await record_audit_log(db, admin, "ENQUIRY_CUSTOMER_LINKED", "enquiries", enquiry.id, {"customer_id": None}, {"customer_id": str(customer.id), "via": "order"}, request)
    await record_audit_log(
        db, admin, "ORDER_CREATED", "orders", order.id, None,
        {"reference_number": order.reference_number, "customer_id": str(customer.id), "enquiry_id": str(enquiry.id) if enquiry else None},
        request,
    )
    new_order_id = order.id
    await db.commit()
    db.expire_all()
    return Envelope(data=_admin_order_detail(await _get_order(db, new_order_id)))


@router.get("/orders/{order_id}", response_model=Envelope[AdminOrderDetail], dependencies=READ)
async def get_order(order_id: UUID, db: Db) -> Envelope[AdminOrderDetail]:
    return Envelope(data=_admin_order_detail(await _get_order(db, order_id)))


@router.patch("/orders/{order_id}/status", response_model=Envelope[AdminOrderDetail], dependencies=WRITE)
async def update_order_status(order_id: UUID, payload: OrderStatusIn, request: Request, db: Db, admin: Admin) -> Envelope[AdminOrderDetail]:
    order = await _get_order(db, order_id)
    if order.status == payload.new_status:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Order is already {payload.new_status}")
    old_status = order.status
    order.status = payload.new_status
    db.add(OrderStatusHistory(order_id=order.id, old_status=old_status, new_status=payload.new_status, note=payload.note or None, changed_by_admin_id=admin.id))
    await record_audit_log(db, admin, "ORDER_STATUS_UPDATED", "orders", order.id, {"status": old_status}, {"status": payload.new_status}, request)
    await db.commit()
    db.expire_all()
    return Envelope(data=_admin_order_detail(await _get_order(db, order_id)))


def _apply_shipment(shipment: Shipment, payload: ShipmentIn) -> None:
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "status":
            if value:
                shipment.status = value
        elif isinstance(value, str):
            setattr(shipment, field, value or None)
        else:
            setattr(shipment, field, value)


@router.post("/orders/{order_id}/shipments", response_model=Envelope[ShipmentOut], status_code=status.HTTP_201_CREATED, dependencies=WRITE)
async def create_shipment(order_id: UUID, payload: ShipmentIn, request: Request, db: Db, admin: Admin) -> Envelope[ShipmentOut]:
    order = await _get_order(db, order_id)
    shipment = Shipment(order_id=order.id, created_by_admin_id=admin.id, status="PREPARING")
    _apply_shipment(shipment, payload)
    db.add(shipment)
    await db.flush()
    await record_audit_log(db, admin, "SHIPMENT_CREATED", "shipments", shipment.id, None, _jsonable(payload.model_dump(exclude_unset=True)), request)
    new_shipment_id = shipment.id
    await db.commit()
    return Envelope(data=await _shipment_out(db, new_shipment_id))


async def _get_shipment(db: AsyncSession, shipment_id: UUID) -> Shipment:
    shipment = (
        await db.execute(select(Shipment).options(selectinload(Shipment.events)).where(Shipment.id == shipment_id))
    ).scalar_one_or_none()
    if not shipment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found")
    return shipment


async def _shipment_out(db: AsyncSession, shipment_id: UUID) -> ShipmentOut:
    db.expire_all()
    return ShipmentOut.model_validate(await _get_shipment(db, shipment_id))


@router.patch("/shipments/{shipment_id}", response_model=Envelope[ShipmentOut], dependencies=WRITE)
async def update_shipment(shipment_id: UUID, payload: ShipmentIn, request: Request, db: Db, admin: Admin) -> Envelope[ShipmentOut]:
    shipment = await _get_shipment(db, shipment_id)
    changes = payload.model_dump(exclude_unset=True)
    old = _jsonable({k: getattr(shipment, k) for k in changes})
    _apply_shipment(shipment, payload)
    await record_audit_log(db, admin, "SHIPMENT_UPDATED", "shipments", shipment.id, old, _jsonable(changes), request)
    await db.commit()
    return Envelope(data=await _shipment_out(db, shipment_id))


@router.post("/shipments/{shipment_id}/events", response_model=Envelope[ShipmentEventOut], status_code=status.HTTP_201_CREATED, dependencies=WRITE)
async def add_shipment_event(shipment_id: UUID, payload: ShipmentEventIn, request: Request, db: Db, admin: Admin) -> Envelope[ShipmentEventOut]:
    shipment = await _get_shipment(db, shipment_id)
    event = ShipmentEvent(
        shipment_id=shipment.id,
        description=payload.description,
        location=payload.location or None,
        occurred_at=payload.occurred_at or datetime.now(UTC),
        created_by_admin_id=admin.id,
    )
    db.add(event)
    await db.flush()
    await record_audit_log(db, admin, "SHIPMENT_EVENT_ADDED", "shipment_events", event.id, None, {"shipment_id": str(shipment.id)}, request)
    await db.commit()
    await db.refresh(event)
    return Envelope(data=ShipmentEventOut.model_validate(event))


# ============================================================================== investments (SUPER_ADMIN)
async def _get_investment(db: AsyncSession, investment_id: UUID) -> Investment:
    investment = (
        await db.execute(
            select(Investment).options(selectinload(Investment.division), selectinload(Investment.investor)).where(Investment.id == investment_id)
        )
    ).scalar_one_or_none()
    if not investment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investment not found")
    return investment


@router.get("/investments", response_model=Envelope[list[AdminInvestmentOut]], dependencies=SUPER_READ)
async def list_investments(db: Db, investor_id: UUID | None = None) -> Envelope[list[AdminInvestmentOut]]:
    stmt = select(Investment).options(selectinload(Investment.division), selectinload(Investment.investor)).order_by(Investment.invested_on.desc())
    if investor_id:
        stmt = stmt.where(Investment.investor_id == investor_id)
    rows = (await db.execute(stmt)).scalars().all()
    return Envelope(data=[AdminInvestmentOut.model_validate(r) for r in rows])


@router.post("/investments", response_model=Envelope[AdminInvestmentOut], status_code=status.HTTP_201_CREATED, dependencies=SUPER_WRITE)
async def create_investment(payload: InvestmentCreateIn, request: Request, db: Db, admin: Admin) -> Envelope[AdminInvestmentOut]:
    investor = await _get_portal_user(db, payload.investor_id, PORTAL_ROLE_INVESTOR)
    await _get_division(db, payload.division_id)
    investment = Investment(
        reference_number=_reference("INV"),
        investor_id=investor.id,
        division_id=payload.division_id,
        amount=payload.amount,
        currency=payload.currency or "MYR",
        invested_on=payload.invested_on,
        status=payload.status,
        summary=payload.summary or None,
        created_by_admin_id=admin.id,
    )
    db.add(investment)
    await db.flush()
    await record_audit_log(
        db, admin, "INVESTMENT_CREATED", "investments", investment.id, None,
        _jsonable({"investor_id": investor.id, "division_id": payload.division_id, "amount": payload.amount, "currency": investment.currency, "status": payload.status}),
        request,
    )
    new_investment_id = investment.id
    await db.commit()
    db.expire_all()
    return Envelope(data=AdminInvestmentOut.model_validate(await _get_investment(db, new_investment_id)))


@router.patch("/investments/{investment_id}", response_model=Envelope[AdminInvestmentOut], dependencies=SUPER_WRITE)
async def update_investment(investment_id: UUID, payload: InvestmentUpdateIn, request: Request, db: Db, admin: Admin) -> Envelope[AdminInvestmentOut]:
    investment = await _get_investment(db, investment_id)
    changes = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None or k == "summary"}
    if "division_id" in changes:
        await _get_division(db, changes["division_id"])
    old = _jsonable({k: getattr(investment, k) for k in changes})
    for field, value in changes.items():
        setattr(investment, field, (value or None) if field == "summary" else value)
    await record_audit_log(db, admin, "INVESTMENT_UPDATED", "investments", investment.id, old, _jsonable(changes), request)
    await db.commit()
    db.expire_all()
    return Envelope(data=AdminInvestmentOut.model_validate(await _get_investment(db, investment_id)))


# ============================================================================== investor documents (SUPER_ADMIN)
@router.post("/investors/{investor_id}/documents", response_model=Envelope[InvestorDocumentOut], status_code=status.HTTP_201_CREATED, dependencies=SUPER_WRITE)
async def upload_investor_document(
    investor_id: UUID,
    request: Request,
    db: Db,
    admin: Admin,
    title: Annotated[str, Query(min_length=1, max_length=200)],
    filename: Annotated[str, Query(min_length=1, max_length=255)],
    category: Annotated[str, Query()] = "FINANCIAL_REPORT",
) -> Envelope[InvestorDocumentOut]:
    """Uploads a PDF for one investor. The request body is the raw file. The document is stored
    privately and stays unpublished (invisible to the investor) until explicitly published."""
    investor = await _get_portal_user(db, investor_id, PORTAL_ROLE_INVESTOR)
    try:
        category = document_category(category)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    safe_name = "".join(ch for ch in filename.replace("\\", "/").rsplit("/", 1)[-1] if ch.isalnum() or ch in " ._-()").strip() or "document.pdf"
    if not safe_name.lower().endswith(".pdf"):
        safe_name += ".pdf"

    storage_key, content_type, size, sha256 = await store_upload(request)
    try:
        document = InvestorDocument(
            investor_id=investor.id,
            title=title.strip(),
            category=category,
            original_filename=safe_name,
            storage_key=storage_key,
            content_type=content_type,
            size_bytes=size,
            sha256=sha256,
            is_published=False,
            uploaded_by_admin_id=admin.id,
        )
        db.add(document)
        await db.flush()
        await record_audit_log(
            db, admin, "INVESTOR_DOCUMENT_UPLOADED", "investor_documents", document.id, None,
            {"investor_id": str(investor.id), "title": document.title, "size_bytes": size, "sha256": sha256}, request,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        remove_stored_file(storage_key)
        raise
    await db.refresh(document)
    return Envelope(data=InvestorDocumentOut.model_validate(document))


async def _get_document(db: AsyncSession, document_id: UUID) -> InvestorDocument:
    document = (await db.execute(select(InvestorDocument).where(InvestorDocument.id == document_id))).scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.patch("/investor-documents/{document_id}", response_model=Envelope[InvestorDocumentOut], dependencies=SUPER_WRITE)
async def publish_investor_document(document_id: UUID, payload: DocumentPublishIn, request: Request, db: Db, admin: Admin) -> Envelope[InvestorDocumentOut]:
    document = await _get_document(db, document_id)
    old = {"is_published": document.is_published}
    document.is_published = payload.is_published
    document.published_at = datetime.now(UTC) if payload.is_published else None
    await record_audit_log(
        db, admin, "INVESTOR_DOCUMENT_PUBLISHED" if payload.is_published else "INVESTOR_DOCUMENT_UNPUBLISHED",
        "investor_documents", document.id, old, {"is_published": payload.is_published}, request,
    )
    await db.commit()
    await db.refresh(document)
    return Envelope(data=InvestorDocumentOut.model_validate(document))


@router.get("/investor-documents/{document_id}/download", dependencies=SUPER_READ)
async def download_investor_document(document_id: UUID, db: Db) -> FileResponse:
    return document_response(await _get_document(db, document_id))


# ============================================================================== investor updates (SUPER_ADMIN)
@router.get("/investor-updates", response_model=Envelope[list[InvestorUpdateOut]], dependencies=SUPER_READ)
async def list_investor_updates(db: Db, investor_id: UUID | None = None) -> Envelope[list[InvestorUpdateOut]]:
    stmt = select(InvestorUpdate).order_by(InvestorUpdate.created_at.desc())
    if investor_id:
        stmt = stmt.where(or_(InvestorUpdate.investor_id == investor_id, InvestorUpdate.investor_id.is_(None)))
    rows = (await db.execute(stmt)).scalars().all()
    return Envelope(data=[InvestorUpdateOut.model_validate(r) for r in rows])


@router.post("/investor-updates", response_model=Envelope[InvestorUpdateOut], status_code=status.HTTP_201_CREATED, dependencies=SUPER_WRITE)
async def create_investor_update(payload: InvestorUpdateIn, request: Request, db: Db, admin: Admin) -> Envelope[InvestorUpdateOut]:
    if payload.investor_id:
        await _get_portal_user(db, payload.investor_id, PORTAL_ROLE_INVESTOR)
    update = InvestorUpdate(
        investor_id=payload.investor_id,
        title=payload.title,
        body=payload.body,
        is_published=payload.is_published,
        published_at=datetime.now(UTC) if payload.is_published else None,
        created_by_admin_id=admin.id,
    )
    db.add(update)
    await db.flush()
    await record_audit_log(
        db, admin, "INVESTOR_UPDATE_CREATED", "investor_updates", update.id, None,
        {"investor_id": str(payload.investor_id) if payload.investor_id else None, "title": payload.title, "is_published": payload.is_published},
        request,
    )
    await db.commit()
    await db.refresh(update)
    return Envelope(data=InvestorUpdateOut.model_validate(update))


@router.patch("/investor-updates/{update_id}", response_model=Envelope[InvestorUpdateOut], dependencies=SUPER_WRITE)
async def patch_investor_update(update_id: UUID, payload: InvestorUpdatePatchIn, request: Request, db: Db, admin: Admin) -> Envelope[InvestorUpdateOut]:
    update = (await db.execute(select(InvestorUpdate).where(InvestorUpdate.id == update_id))).scalar_one_or_none()
    if not update:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Update not found")
    changes = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    old = {"is_published": update.is_published, "title": update.title}
    for field, value in changes.items():
        setattr(update, field, value)
    if "is_published" in changes:
        update.published_at = datetime.now(UTC) if changes["is_published"] else None
    await record_audit_log(db, admin, "INVESTOR_UPDATE_EDITED", "investor_updates", update.id, old, {k: v for k, v in changes.items() if k != "body"}, request)
    await db.commit()
    await db.refresh(update)
    return Envelope(data=InvestorUpdateOut.model_validate(update))
