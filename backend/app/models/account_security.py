"""Account security tables (security remediation, findings 1 and 5).

``portal_auth_tokens``
    Single-use invitation and password-reset links for customer and investor accounts. Only the
    SHA-256 digest of a token is stored; the raw token exists only in the link given to the account
    holder. Issuing a new link revokes every earlier unused link for the same account.

``account_email_registry``
    One row per administrator or portal account, keyed by the normalised (lower-case, trimmed)
    email address. Its primary key is what makes an email address unique *across* ``admin_users``
    and ``portal_users`` at the database level. Rows are written only by the triggers created in
    migration 0009; application code never inserts into it directly.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

TOKEN_PURPOSE_INVITE = "INVITE"
TOKEN_PURPOSE_RESET = "RESET"
TOKEN_PURPOSE_VERIFY = "VERIFY"
TOKEN_PURPOSES = (TOKEN_PURPOSE_INVITE, TOKEN_PURPOSE_RESET, TOKEN_PURPOSE_VERIFY)

REGISTRY_TABLES = ("admin_users", "portal_users")


class PortalAuthToken(Base):
    __tablename__ = "portal_auth_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portal_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portal_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    purpose: Mapped[str] = mapped_column(String(10), nullable=False)
    # SHA-256 hex digest of the raw token. The raw token is never stored.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    requested_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    __table_args__ = (
        CheckConstraint("purpose IN ('INVITE', 'RESET', 'VERIFY')", name="ck_portal_auth_tokens_purpose"),
    )


class AccountEmailRegistry(Base):
    __tablename__ = "account_email_registry"

    email_normalized: Mapped[str] = mapped_column(String(255), primary_key=True)
    account_table: Mapped[str] = mapped_column(String(20), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("account_table", "account_id", name="uq_account_email_registry_account"),
        CheckConstraint(
            "account_table IN ('admin_users', 'portal_users')", name="ck_account_email_registry_table"
        ),
        CheckConstraint("email_normalized = lower(btrim(email_normalized))", name="ck_account_email_registry_normalized"),
    )
