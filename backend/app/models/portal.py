"""SQLAlchemy models for the customer and investor portals (CR-C4 to CR-C7).

Portal accounts are deliberately separate from ``admin_users``: a customer or investor row can
never carry an administrative role, and administrator tables (referenced by audit logs and
enquiry assignments) are left untouched.

All monetary amounts are stored as exact NUMERIC values with an ISO 4217 currency code.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.division import Division
    from app.models.enquiry import Enquiry

PORTAL_ROLE_CUSTOMER = "CUSTOMER"
PORTAL_ROLE_INVESTOR = "INVESTOR"
PORTAL_ROLES = (PORTAL_ROLE_CUSTOMER, PORTAL_ROLE_INVESTOR)

ORDER_STATUSES = (
    "CONFIRMED",
    "PROCESSING",
    "READY_TO_SHIP",
    "SHIPPED",
    "IN_TRANSIT",
    "DELIVERED",
    "COMPLETED",
    "CANCELLED",
)
SHIPMENT_STATUSES = ("PREPARING", "SHIPPED", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED", "RETURNED")
INVESTMENT_STATUSES = ("PENDING", "ACTIVE", "MATURED", "EXITED", "CANCELLED")
DOCUMENT_CATEGORIES = ("FINANCIAL_REPORT", "INVESTMENT_DOCUMENT", "OTHER")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _updated_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PortalUser(Base):
    """A customer or investor account. Created and managed by administrators only."""

    __tablename__ = "portal_users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    sessions: Mapped[list["PortalSession"]] = relationship(
        "PortalSession", back_populates="portal_user", cascade="all, delete-orphan"
    )

    @property
    def invitation_pending(self) -> bool:
        """True until the account holder sets their own password through an invitation link."""
        from app.core.security import has_usable_password

        return not has_usable_password(self.password_hash)

    __table_args__ = (
        CheckConstraint(_in_list("role", PORTAL_ROLES), name="ck_portal_users_role"),
        # Emails are stored normalised so the unique index is case-insensitive in effect (migration 0009).
        CheckConstraint("email = lower(btrim(email))", name="ck_portal_users_email_normalized"),
    )


class PortalSession(Base):
    """Server-side session for a portal account. ``id`` is the SHA-256 digest of the cookie token."""

    __tablename__ = "portal_sessions"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    portal_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portal_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Role the session was issued for. Checked against the account on every request.
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    csrf_token: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = _created_at()
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    portal_user: Mapped["PortalUser"] = relationship("PortalUser", back_populates="sessions")

    __table_args__ = (CheckConstraint(_in_list("role", PORTAL_ROLES), name="ck_portal_sessions_role"),)


class Order(Base):
    """A customer order, created by an administrator (usually from a reviewed enquiry)."""

    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = _uuid_pk()
    reference_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portal_users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    enquiry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enquiries.id", ondelete="SET NULL"), nullable=True, index=True
    )
    division_id: Mapped[str] = mapped_column(String(50), ForeignKey("divisions.id", ondelete="RESTRICT"), nullable=False)
    product_description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    unit_of_measurement: Mapped[str | None] = mapped_column(String(50), nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="CONFIRMED", nullable=False, index=True)
    # Shown to the customer. Internal remarks belong in the audit log / enquiry notes.
    customer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    customer: Mapped["PortalUser"] = relationship("PortalUser")
    enquiry: Mapped[Optional["Enquiry"]] = relationship("Enquiry")
    division: Mapped["Division"] = relationship("Division")
    status_history: Mapped[list["OrderStatusHistory"]] = relationship(
        "OrderStatusHistory",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="desc(OrderStatusHistory.created_at)",
    )
    shipments: Mapped[list["Shipment"]] = relationship(
        "Shipment", back_populates="order", cascade="all, delete-orphan", order_by="Shipment.created_at"
    )

    __table_args__ = (
        CheckConstraint(_in_list("status", ORDER_STATUSES), name="ck_orders_status"),
        Index("idx_orders_created_at_desc", created_at.desc()),
    )


class OrderStatusHistory(Base):
    """Append-only record of order status changes. ``note`` is visible to the customer."""

    __tablename__ = "order_status_history"

    id: Mapped[uuid.UUID] = _uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    old_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()

    order: Mapped["Order"] = relationship("Order", back_populates="status_history")


class Shipment(Base):
    """A consignment for an order. An order may ship in more than one consignment."""

    __tablename__ = "shipments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    carrier: Mapped[str | None] = mapped_column(String(150), nullable=True)
    tracking_number: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    origin: Mapped[str | None] = mapped_column(String(150), nullable=True)
    destination: Mapped[str | None] = mapped_column(String(150), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="PREPARING", nullable=False)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estimated_delivery_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    order: Mapped["Order"] = relationship("Order", back_populates="shipments")
    events: Mapped[list["ShipmentEvent"]] = relationship(
        "ShipmentEvent",
        back_populates="shipment",
        cascade="all, delete-orphan",
        order_by="desc(ShipmentEvent.occurred_at)",
    )

    __table_args__ = (CheckConstraint(_in_list("status", SHIPMENT_STATUSES), name="ck_shipments_status"),)


class ShipmentEvent(Base):
    """A tracking update for a shipment, entered by an administrator."""

    __tablename__ = "shipment_events"

    id: Mapped[uuid.UUID] = _uuid_pk()
    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()

    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="events")


class Investment(Base):
    """An investment record for one investor in one business division."""

    __tablename__ = "investments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    reference_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    investor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portal_users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    division_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("divisions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="MYR", nullable=False)
    invested_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False, index=True)
    # Shown to the investor.
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    investor: Mapped["PortalUser"] = relationship("PortalUser")
    division: Mapped["Division"] = relationship("Division")

    __table_args__ = (
        CheckConstraint(_in_list("status", INVESTMENT_STATUSES), name="ck_investments_status"),
        CheckConstraint("amount > 0", name="ck_investments_amount_positive"),
    )


class InvestorDocument(Base):
    """A private document for one investor. The file lives in private storage, never under a public URL."""

    __tablename__ = "investor_documents"

    id: Mapped[uuid.UUID] = _uuid_pk()
    investor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portal_users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(30), default="FINANCIAL_REPORT", nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # Random name inside the private storage directory; never derived from user input.
    storage_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # Only published documents are visible to the investor.
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()

    investor: Mapped["PortalUser"] = relationship("PortalUser")

    __table_args__ = (CheckConstraint(_in_list("category", DOCUMENT_CATEGORIES), name="ck_investor_documents_category"),)


class InvestorUpdate(Base):
    """An announcement for investors. ``investor_id`` NULL means it is addressed to every investor."""

    __tablename__ = "investor_updates"

    id: Mapped[uuid.UUID] = _uuid_pk()
    investor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portal_users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()
