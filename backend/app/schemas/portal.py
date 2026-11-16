"""Pydantic schemas for the customer portal, investor portal and their admin management (CR-C4 to CR-C7)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import validate_password_policy
from app.models.portal import (
    DOCUMENT_CATEGORIES,
    INVESTMENT_STATUSES,
    ORDER_STATUSES,
    PORTAL_ROLES,
    SHIPMENT_STATUSES,
)
from app.schemas.public import sanitize_text

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    success: bool = True
    data: T


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class _In(BaseModel):
    """Request bodies: unknown fields are rejected and free text is stripped of HTML."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*", mode="before")
    @classmethod
    def _sanitize(cls, v, info):
        if isinstance(v, str) and info.field_name not in {"password", "current_password", "new_password", "email", "token"}:
            cleaned = sanitize_text(v)
            return cleaned if cleaned is not None else ""
        return v


def _one_of(value: str, allowed: tuple[str, ...], label: str) -> str:
    clean = value.strip().upper()
    if clean not in allowed:
        raise ValueError(f"Invalid {label} '{value}'. Must be one of: {', '.join(allowed)}")
    return clean


def _check_password(value: str) -> str:
    ok, reason = validate_password_policy(value)
    if not ok:
        raise ValueError(reason or "Password does not meet the security policy.")
    return value


def _currency(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    clean = value.strip().upper()
    if len(clean) != 3 or not clean.isalpha():
        raise ValueError("Currency must be a 3-letter ISO 4217 code, e.g. MYR.")
    return clean


# ---------------------------------------------------------------- identity / auth
class PortalUserPublic(_Out):
    id: UUID
    email: EmailStr
    role: str
    full_name: str
    company_name: str | None = None
    contact_number: str | None = None
    country: str | None = None
    email_verified_at: datetime | None = None


class PortalMe(PortalUserPublic):
    last_login_at: datetime | None = None
    csrf_token: str


class PortalLoginData(BaseModel):
    user: PortalUserPublic
    csrf_token: str
    account_type: str
    redirect_to: str


class Message(BaseModel):
    success: bool = True
    message: str


class PasswordChangeIn(_In):
    current_password: str = Field(..., min_length=1, max_length=256)
    new_password: str = Field(..., min_length=1, max_length=256)

    _policy = field_validator("new_password")(_check_password)


class ProfileUpdateIn(_In):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    company_name: str | None = Field(default=None, max_length=200)
    contact_number: str | None = Field(default=None, max_length=50)
    country: str | None = Field(default=None, max_length=100)


# ---------------------------------------------------------------- shared read models
class DivisionRef(_Out):
    id: str
    code: str
    name: str


class ShipmentEventOut(_Out):
    id: UUID
    description: str
    location: str | None = None
    occurred_at: datetime


class ShipmentOut(_Out):
    id: UUID
    carrier: str | None = None
    tracking_number: str | None = None
    origin: str | None = None
    destination: str | None = None
    status: str
    shipped_at: datetime | None = None
    estimated_delivery_on: date | None = None
    delivered_at: datetime | None = None
    events: list[ShipmentEventOut] = []


class OrderStatusEventOut(_Out):
    old_status: str | None = None
    new_status: str
    note: str | None = None
    created_at: datetime


class OrderSummary(_Out):
    id: UUID
    reference_number: str
    division: DivisionRef
    product_description: str
    quantity: Decimal | None = None
    unit_of_measurement: str | None = None
    total_amount: Decimal | None = None
    currency: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class OrderDetail(OrderSummary):
    customer_note: str | None = None
    enquiry_reference: str | None = None
    status_history: list[OrderStatusEventOut] = []
    shipments: list[ShipmentOut] = []


class CustomerEnquirySummary(BaseModel):
    id: UUID
    reference_number: str
    division: DivisionRef
    product_focus: str
    status: str
    created_at: datetime
    updated_at: datetime


class EnquiryUpdateOut(BaseModel):
    kind: str  # STATUS | MESSAGE
    text: str
    created_at: datetime


class CustomerEnquiryDetail(CustomerEnquirySummary):
    quantity: Decimal | None = None
    unit_of_measurement: str | None = None
    specifications: str | None = None
    additional_notes: str | None = None
    preferred_incoterm: str | None = None
    target_destination_port: str | None = None
    updates: list[EnquiryUpdateOut] = []
    orders: list[OrderSummary] = []


class CustomerOverview(BaseModel):
    enquiries_total: int
    enquiries_open: int
    orders_total: int
    orders_active: int
    recent_enquiries: list[CustomerEnquirySummary]
    recent_orders: list[OrderSummary]


# ---------------------------------------------------------------- investor read models
class InvestmentOut(_Out):
    id: UUID
    reference_number: str
    division: DivisionRef
    amount: Decimal
    currency: str
    invested_on: date
    status: str
    summary: str | None = None
    created_at: datetime


class CurrencyTotal(BaseModel):
    currency: str
    total: Decimal
    active_total: Decimal


class DivisionAllocation(BaseModel):
    division: DivisionRef
    currency: str
    amount: Decimal
    share_percent: Decimal
    investments: int


class InvestorOverview(BaseModel):
    totals: list[CurrencyTotal]
    investments_count: int
    status_counts: dict[str, int]
    allocation: list[DivisionAllocation]
    recent_investments: list[InvestmentOut]


class InvestorDocumentOut(_Out):
    id: UUID
    title: str
    category: str
    original_filename: str
    content_type: str
    size_bytes: int
    is_published: bool
    published_at: datetime | None = None
    created_at: datetime


class InvestorUpdateOut(_Out):
    id: UUID
    investor_id: UUID | None = None
    title: str
    body: str
    is_published: bool
    published_at: datetime | None = None
    created_at: datetime


# ---------------------------------------------------------------- admin: accounts
class PortalUserAdminOut(PortalUserPublic):
    is_active: bool
    # True until the account holder sets their own password from an invitation link.
    invitation_pending: bool = False
    last_login_at: datetime | None = None
    locked_until: datetime | None = None
    created_at: datetime


class PasswordLinkOut(BaseModel):
    """A newly issued invitation or reset link.

    ``link`` is filled only when email delivery is unavailable (``delivery == "MANUAL"``). It is
    returned once, to the administrator who issued it, and is never stored or shown again.
    """

    purpose: str
    delivery: str
    # SENT: the SMTP server accepted it. FAILED: sending failed and the link was revoked (issue a
    # new one to retry). SHOWN_ONCE: MANUAL delivery, ``link`` is filled.
    delivery_status: str
    expires_at: datetime
    link: str | None = None


class LastLinkEmailOut(BaseModel):
    status: str  # SENT or FAILED
    at: datetime


class PortalUserCreatedOut(PortalUserAdminOut):
    invitation: PasswordLinkOut


class ActiveLinkOut(BaseModel):
    purpose: str
    created_at: datetime
    expires_at: datetime


class PortalUserCreateIn(_In):
    """Administrators never choose a customer's or investor's password: the account is created
    without one and the holder sets it from a single-use invitation link."""

    role: str
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=150)
    company_name: str | None = Field(default=None, max_length=200)
    contact_number: str | None = Field(default=None, max_length=50)
    country: str | None = Field(default=None, max_length=100)

    @field_validator("role")
    @classmethod
    def _role(cls, v: str) -> str:
        return _one_of(v, PORTAL_ROLES, "role")


class PortalUserUpdateIn(ProfileUpdateIn):
    is_active: bool | None = None


# ---------------------------------------------------------------- public: invitation / reset links
class ForgotPasswordIn(_In):
    email: EmailStr


class LinkTokenIn(_In):
    token: str = Field(..., min_length=16, max_length=128)


class CompletePasswordLinkIn(LinkTokenIn):
    new_password: str = Field(..., min_length=1, max_length=256)

    _policy = field_validator("new_password")(_check_password)


class LinkStatusOut(BaseModel):
    purpose: str
    account_type: str
    login_path: str
    expires_at: datetime


class LinkCompletedOut(BaseModel):
    account_type: str
    login_path: str


class AdminEnquiryRef(BaseModel):
    id: UUID
    reference_number: str
    company_name: str
    product_focus: str
    status: str
    created_at: datetime


class PortalUserAdminDetail(PortalUserAdminOut):
    # The newest invitation/reset link that can still be used (never the link itself).
    active_link: ActiveLinkOut | None = None
    # Latest forgot-password request recorded while email delivery was unavailable (last 7 days).
    reset_requested_at: datetime | None = None
    # Outcome of the most recent link email (last 7 days); FAILED means the link was revoked.
    last_link_email: LastLinkEmailOut | None = None
    enquiries: list[AdminEnquiryRef] = []
    orders: list[OrderSummary] = []
    investments: list[InvestmentOut] = []
    documents: list[InvestorDocumentOut] = []


class LinkCustomerIn(_In):
    customer_id: UUID | None = Field(
        default=None, description="Customer to link. null removes the link and makes the enquiry anonymous again."
    )


class EnquiryCustomerLink(BaseModel):
    customer: PortalUserPublic | None = None
    orders: list[OrderSummary] = []


class CustomerUpdateIn(_In):
    message: str = Field(..., min_length=1, max_length=2000)


# ---------------------------------------------------------------- admin: orders
class OrderCreateIn(_In):
    customer_id: UUID
    enquiry_id: UUID | None = None
    division_id: str | None = Field(default=None, max_length=50)
    product_description: str | None = Field(default=None, max_length=255)
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    unit_of_measurement: str | None = Field(default=None, max_length=50)
    total_amount: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=2)
    currency: str | None = None
    customer_note: str | None = Field(default=None, max_length=2000)

    _cur = field_validator("currency")(_currency)


class OrderStatusIn(_In):
    new_status: str
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("new_status")
    @classmethod
    def _status(cls, v: str) -> str:
        return _one_of(v, ORDER_STATUSES, "order status")


class ShipmentIn(_In):
    carrier: str | None = Field(default=None, max_length=150)
    tracking_number: str | None = Field(default=None, max_length=120)
    origin: str | None = Field(default=None, max_length=150)
    destination: str | None = Field(default=None, max_length=150)
    status: str | None = None
    shipped_at: datetime | None = None
    estimated_delivery_on: date | None = None
    delivered_at: datetime | None = None

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        return _one_of(v, SHIPMENT_STATUSES, "shipment status") if v else None


class ShipmentEventIn(_In):
    description: str = Field(..., min_length=1, max_length=500)
    location: str | None = Field(default=None, max_length=150)
    occurred_at: datetime | None = None


class AdminOrderSummary(OrderSummary):
    customer: PortalUserPublic


class AdminOrderDetail(OrderDetail):
    customer: PortalUserPublic
    enquiry_id: UUID | None = None


# ---------------------------------------------------------------- admin: investors
class InvestmentCreateIn(_In):
    investor_id: UUID
    division_id: str = Field(..., min_length=1, max_length=50)
    amount: Decimal = Field(..., gt=0, max_digits=16, decimal_places=2)
    currency: str = "MYR"
    invested_on: date
    status: str = "ACTIVE"
    summary: str | None = Field(default=None, max_length=2000)

    _cur = field_validator("currency")(_currency)

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        return _one_of(v, INVESTMENT_STATUSES, "investment status")


class InvestmentUpdateIn(_In):
    division_id: str | None = Field(default=None, min_length=1, max_length=50)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=16, decimal_places=2)
    currency: str | None = None
    invested_on: date | None = None
    status: str | None = None
    summary: str | None = Field(default=None, max_length=2000)

    _cur = field_validator("currency")(_currency)

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        return _one_of(v, INVESTMENT_STATUSES, "investment status") if v else None


class AdminInvestmentOut(InvestmentOut):
    investor: PortalUserPublic


class DocumentPublishIn(_In):
    is_published: bool


class InvestorUpdateIn(_In):
    investor_id: UUID | None = None
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=10000)
    is_published: bool = False


class InvestorUpdatePatchIn(_In):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=10000)
    is_published: bool | None = None


def document_category(value: str) -> str:
    return _one_of(value, DOCUMENT_CATEGORIES, "document category")


class PortalSummary(BaseModel):
    total_customers: int
    total_investors: int
    total_enquiries: int
    total_orders: int
    orders_by_status: dict[str, int]
    # Investment figures are confidential: null unless the administrator is a SUPER_ADMIN.
    investment_totals: list[CurrencyTotal] | None = None
    investments_count: int | None = None
