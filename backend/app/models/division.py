"""SQLAlchemy model for Commercial Trading Divisions.

Aligns strictly with Phase C13 database specification v2.1.0.
Contains every commercial trading division record (EB-DIV-01 to EB-DIV-10); withdrawn ones are kept with is_active=False.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.enquiry import Enquiry


class Division(Base):
    """Commercial trading division entity."""

    __tablename__ = "divisions"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sector: Mapped[str] = mapped_column(String(100), nullable=False)
    accent_color: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    manufacturer_attribution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    disclaimer: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    initial_enquiries: Mapped[list["Enquiry"]] = relationship(
        "Enquiry",
        foreign_keys="Enquiry.initial_division_id",
        back_populates="initial_division",
    )
    current_enquiries: Mapped[list["Enquiry"]] = relationship(
        "Enquiry",
        foreign_keys="Enquiry.current_division_id",
        back_populates="current_division",
    )
