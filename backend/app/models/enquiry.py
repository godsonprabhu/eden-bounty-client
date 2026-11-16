"""SQLAlchemy models for Enquiries, Assignments, Status History, and Notes.

Aligns strictly with Phase C13 database specification v2.1.0.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.admin import AdminUser
    from app.models.division import Division
    from app.models.notification import NotificationLog


class Enquiry(Base):
    """Central commercial trade enquiry (RFQ) submitted via public website."""

    __tablename__ = "enquiries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    reference_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    # Submitter Contact Snapshot
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    business_email: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False)

    # Commercial Requirements Snapshot
    initial_division_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("divisions.id"),
        nullable=False,
    )
    current_division_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("divisions.id"),
        nullable=False,
        index=True,
    )
    product_focus: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    unit_of_measurement: Mapped[str | None] = mapped_column(String(50), nullable=True)
    specifications: Mapped[str | None] = mapped_column(Text, nullable=True)
    additional_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional Commercial Preferences
    preferred_incoterm: Mapped[str | None] = mapped_column(String(10), nullable=True)
    target_destination_port: Mapped[str | None] = mapped_column(String(150), nullable=True)

    # Idempotency & Repeat Submission Controls (Phase C13.3 Final Corrective Pass)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128),
        unique=True,
        nullable=True,
        index=True,
    )
    request_payload_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    # Operational Management
    status: Mapped[str] = mapped_column(String(50), default="NEW", nullable=False, index=True)
    assigned_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Ingestion Metadata
    # Customer portal link (CR-C5). Set only by explicit administrator confirmation; never inferred
    # from a matching email address. NULL for anonymous/unlinked enquiries.
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portal_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    client_user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    initial_division: Mapped["Division"] = relationship(
        "Division",
        foreign_keys=[initial_division_id],
        back_populates="initial_enquiries",
    )
    current_division: Mapped["Division"] = relationship(
        "Division",
        foreign_keys=[current_division_id],
        back_populates="current_enquiries",
    )
    assigned_admin: Mapped[Optional["AdminUser"]] = relationship(
        "AdminUser",
        foreign_keys=[assigned_admin_id],
    )
    assignments: Mapped[list["EnquiryAssignment"]] = relationship(
        "EnquiryAssignment",
        back_populates="enquiry",
        cascade="all, delete-orphan",
        order_by="desc(EnquiryAssignment.assigned_at)",
    )
    status_history: Mapped[list["EnquiryStatusHistory"]] = relationship(
        "EnquiryStatusHistory",
        back_populates="enquiry",
        cascade="all, delete-orphan",
        order_by="desc(EnquiryStatusHistory.created_at)",
    )
    notes: Mapped[list["EnquiryNote"]] = relationship(
        "EnquiryNote",
        back_populates="enquiry",
        cascade="all, delete-orphan",
        order_by="desc(EnquiryNote.created_at)",
    )
    notifications: Mapped[list["NotificationLog"]] = relationship(
        "NotificationLog",
        back_populates="enquiry",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_enquiries_created_at_desc", created_at.desc()),
    )


class EnquiryAssignment(Base):
    """Tracks assignment of enquiries to commercial divisions and administrators."""

    __tablename__ = "enquiry_assignments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    enquiry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("enquiries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_division_id: Mapped[str | None] = mapped_column(
        String(50),
        ForeignKey("divisions.id"),
        nullable=True,
    )
    new_division_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("divisions.id"),
        nullable=False,
    )
    previous_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_users.id"),
        nullable=True,
    )
    new_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_users.id"),
        nullable=True,
    )
    assignment_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_by_admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_users.id"),
        nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    enquiry: Mapped["Enquiry"] = relationship("Enquiry", back_populates="assignments")


class EnquiryStatusHistory(Base):
    """Chronological record of status changes for an enquiry."""

    __tablename__ = "enquiry_status_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    enquiry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("enquiries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_status: Mapped[str] = mapped_column(String(50), nullable=False)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by_admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_users.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    enquiry: Mapped["Enquiry"] = relationship("Enquiry", back_populates="status_history")


class EnquiryNote(Base):
    """Internal comments, correspondence records, and operational follow-ups."""

    __tablename__ = "enquiry_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    enquiry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("enquiries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    admin_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_users.id"),
        nullable=False,
    )
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal_only: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    enquiry: Mapped["Enquiry"] = relationship("Enquiry", back_populates="notes")
