"""SQLAlchemy model for Email Notifications and Dispatch Tracking.

Aligns strictly with Phase C13 database specification v2.1.0.
Tracks email dispatches with status, error messages, and retry counts.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.enquiry import Enquiry


class NotificationLog(Base):
    """Notification dispatch log providing durability for in-process background tasks."""

    __tablename__ = "notification_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    enquiry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("enquiries.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    notification_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # 'BUYER_CONFIRMATION', 'ADMIN_ALERT', 'ASSIGNMENT_NOTICE'
    status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        nullable=False,
        index=True,
    )  # 'PENDING', 'SENT', 'FAILED'
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    enquiry: Mapped[Optional["Enquiry"]] = relationship("Enquiry", back_populates="notifications")

    __table_args__ = (
        Index("idx_notification_logs_retry", "status", "retry_count"),
    )
