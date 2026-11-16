"""SQLAlchemy models for Administrative Users, Roles, and Sessions.

Aligns strictly with Phase C13 database specification v2.1.0.
Only two administrative roles in initial release: SUPER_ADMIN and OPERATIONS_ADMIN.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AdminUser(Base):
    """Central administrative user model for EDEN BOUNTY."""

    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    job_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    roles: Mapped[list["AdminRole"]] = relationship(
        "AdminRole",
        secondary="admin_user_roles",
        primaryjoin="AdminUser.id == foreign(AdminUserRole.admin_user_id)",
        secondaryjoin="AdminRole.id == foreign(AdminUserRole.role_id)",
        back_populates="users",
        lazy="selectin",
    )
    sessions: Mapped[list["AdminSession"]] = relationship(
        "AdminSession",
        back_populates="admin_user",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_admin_users_active", "is_active", postgresql_where=(deleted_at.is_(None))),
        # Emails are stored normalised so the unique index is case-insensitive in effect (migration 0009).
        CheckConstraint("email = lower(btrim(email))", name="ck_admin_users_email_normalized"),
    )


class AdminRole(Base):
    """Administrative role definition ('SUPER_ADMIN' or 'OPERATIONS_ADMIN')."""

    __tablename__ = "admin_roles"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    users: Mapped[list["AdminUser"]] = relationship(
        "AdminUser",
        secondary="admin_user_roles",
        primaryjoin="AdminRole.id == foreign(AdminUserRole.role_id)",
        secondaryjoin="AdminUser.id == foreign(AdminUserRole.admin_user_id)",
        back_populates="roles",
    )


class AdminUserRole(Base):
    """Associative table mapping admin users to administrative roles."""

    __tablename__ = "admin_user_roles"

    admin_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("admin_roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_users.id"),
        nullable=True,
    )


class AdminSession(Base):
    """Server-side session record for authenticated administrators."""

    __tablename__ = "admin_sessions"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    admin_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    csrf_token: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    admin_user: Mapped["AdminUser"] = relationship("AdminUser", back_populates="sessions")
