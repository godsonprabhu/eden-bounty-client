"""Public registration, email verification, and Google OAuth support.

Revision ID: 0010_registration_verification
Revises: 0009_account_security
Create Date: 2026-11-14

Additive changes:
- Add ``email_verified_at`` to ``portal_users``: timestamp when the account holder verified their
  email. Unverified accounts cannot access protected customer or investor dashboards.
- Add ``google_id`` to ``portal_users``: unique indexed subject ID from Google OAuth/OIDC.
- Update CHECK constraint on ``portal_auth_tokens.purpose`` to include ``'VERIFY'`` in addition to
  ``'INVITE'`` and ``'RESET'``.
- Backfill existing ``portal_users`` with ``email_verified_at = created_at`` so pre-existing
  accounts remain fully verified.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_registration_verification"
down_revision: str | None = "0009_account_security"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add email_verified_at and google_id to portal_users
    op.add_column("portal_users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("portal_users", sa.Column("google_id", sa.String(length=255), nullable=True))
    op.create_index("ix_portal_users_google_id", "portal_users", ["google_id"], unique=True)

    # 2. Backfill existing portal users so pre-existing fixture/admin accounts are verified
    op.execute("UPDATE portal_users SET email_verified_at = created_at WHERE email_verified_at IS NULL")

    # 3. Update check constraint on portal_auth_tokens to allow 'VERIFY'
    op.drop_constraint("ck_portal_auth_tokens_purpose", "portal_auth_tokens", type_="check")
    op.create_check_constraint(
        "ck_portal_auth_tokens_purpose",
        "portal_auth_tokens",
        "purpose IN ('INVITE', 'RESET', 'VERIFY')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_portal_auth_tokens_purpose", "portal_auth_tokens", type_="check")
    op.create_check_constraint(
        "ck_portal_auth_tokens_purpose",
        "portal_auth_tokens",
        "purpose IN ('INVITE', 'RESET')",
    )
    op.drop_index("ix_portal_users_google_id", table_name="portal_users")
    op.drop_column("portal_users", "google_id")
    op.drop_column("portal_users", "email_verified_at")
