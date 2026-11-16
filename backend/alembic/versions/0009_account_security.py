"""Account security: invitation/reset tokens and cross-account email uniqueness.

Revision ID: 0009_account_security
Revises: 0008_portal_accounts_orders_investments
Create Date: 2026-11-13

Additive only (security remediation, findings 1 and 5):

- New table ``portal_auth_tokens``: single-use invitation and password-reset links. Stores the
  SHA-256 digest of each token, never the token itself.
- New table ``account_email_registry`` plus row triggers on ``admin_users`` and ``portal_users``:
  its primary key makes one normalised email address map to at most one account across both
  tables. A statement trigger keeps it correct after ``TRUNCATE``.
- New CHECK constraints ``ck_admin_users_email_normalized`` / ``ck_portal_users_email_normalized``:
  emails are stored lower-case and trimmed, so the existing per-table unique indexes are
  case-insensitive in effect.

Before anything is created, the existing rows are checked. If any email is not normalised or any
normalised email is used by more than one account, the upgrade stops with a count of the problem
rows (no addresses are printed) and changes nothing; see DATABASE_SETUP.md for how to resolve it.

No existing column, row, index or constraint is altered or removed. Downgrade drops only the
objects created here.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_account_security"
down_revision: str | None = "0008_portal_accounts_orders_investments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACCOUNT_TABLES = ("admin_users", "portal_users")
SYNC_FUNCTION = "eb_sync_account_email_registry"
TRUNCATE_FUNCTION = "eb_clear_account_email_registry"


class ExistingDataConflict(RuntimeError):
    """Existing account rows would violate the new constraints; nothing has been changed."""


def _preflight(bind: sa.engine.Connection) -> None:
    unnormalised = {
        table: bind.execute(sa.text(f"SELECT count(*) FROM {table} WHERE email <> lower(btrim(email))")).scalar_one()
        for table in ACCOUNT_TABLES
    }
    duplicates = bind.execute(
        sa.text(
            """
            SELECT count(*) FROM (
                SELECT lower(btrim(email)) AS e FROM admin_users
                UNION ALL
                SELECT lower(btrim(email)) FROM portal_users
            ) AS all_accounts
            GROUP BY e HAVING count(*) > 1
            """
        )
    ).all()
    problems = [f"{count} {table} row(s) with a non-normalised email" for table, count in unnormalised.items() if count]
    if duplicates:
        problems.append(f"{len(duplicates)} email address(es) used by more than one account (case-insensitive)")
    if problems:
        raise ExistingDataConflict(
            "Revision 0009 was not applied because existing data conflicts with the new constraints: "
            + "; ".join(problems)
            + ". No changes were made. Resolve the rows as described in DATABASE_SETUP.md and run the upgrade again."
        )


def upgrade() -> None:
    bind = op.get_bind()
    _preflight(bind)

    op.create_table(
        "portal_auth_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("portal_user_id", sa.UUID(), nullable=False),
        sa.Column("purpose", sa.String(length=10), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_admin_id", sa.UUID(), nullable=True),
        sa.Column("requested_ip", sa.String(length=45), nullable=True),
        sa.CheckConstraint("purpose IN ('INVITE', 'RESET')", name="ck_portal_auth_tokens_purpose"),
        sa.ForeignKeyConstraint(["created_by_admin_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["portal_user_id"], ["portal_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_portal_auth_tokens_portal_user_id", "portal_auth_tokens", ["portal_user_id"], unique=False)
    op.create_index("ix_portal_auth_tokens_token_hash", "portal_auth_tokens", ["token_hash"], unique=True)
    op.create_index("ix_portal_auth_tokens_expires_at", "portal_auth_tokens", ["expires_at"], unique=False)

    op.create_table(
        "account_email_registry",
        sa.Column("email_normalized", sa.String(length=255), nullable=False),
        sa.Column("account_table", sa.String(length=20), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("account_table IN ('admin_users', 'portal_users')", name="ck_account_email_registry_table"),
        sa.CheckConstraint(
            "email_normalized = lower(btrim(email_normalized))", name="ck_account_email_registry_normalized"
        ),
        sa.PrimaryKeyConstraint("email_normalized"),
        sa.UniqueConstraint("account_table", "account_id", name="uq_account_email_registry_account"),
    )

    for table in ACCOUNT_TABLES:
        op.create_check_constraint(f"ck_{table}_email_normalized", table, "email = lower(btrim(email))")

    # Register every existing account (the preflight guarantees there are no collisions).
    op.execute(
        """
        INSERT INTO account_email_registry (email_normalized, account_table, account_id)
        SELECT lower(btrim(email)), 'admin_users', id FROM admin_users
        UNION ALL
        SELECT lower(btrim(email)), 'portal_users', id FROM portal_users
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {SYNC_FUNCTION}() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                DELETE FROM account_email_registry
                 WHERE account_table = TG_TABLE_NAME AND account_id = OLD.id;
                RETURN OLD;
            END IF;
            IF TG_OP = 'UPDATE' THEN
                IF lower(btrim(NEW.email)) = lower(btrim(OLD.email)) AND NEW.id = OLD.id THEN
                    RETURN NEW;
                END IF;
                DELETE FROM account_email_registry
                 WHERE account_table = TG_TABLE_NAME AND account_id = OLD.id;
            END IF;
            -- A duplicate raises unique_violation on account_email_registry_pkey, aborting the write.
            INSERT INTO account_email_registry (email_normalized, account_table, account_id)
            VALUES (lower(btrim(NEW.email)), TG_TABLE_NAME, NEW.id);
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION {TRUNCATE_FUNCTION}() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            DELETE FROM account_email_registry WHERE account_table = TG_TABLE_NAME;
            RETURN NULL;
        END;
        $$
        """
    )
    for table in ACCOUNT_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_email_registry AFTER INSERT OR UPDATE OF email, id OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {SYNC_FUNCTION}()"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_email_registry_truncate AFTER TRUNCATE ON {table} "
            f"FOR EACH STATEMENT EXECUTE FUNCTION {TRUNCATE_FUNCTION}()"
        )


def downgrade() -> None:
    for table in ACCOUNT_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_email_registry_truncate ON {table}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_email_registry ON {table}")
    op.execute(f"DROP FUNCTION IF EXISTS {TRUNCATE_FUNCTION}()")
    op.execute(f"DROP FUNCTION IF EXISTS {SYNC_FUNCTION}()")
    for table in ACCOUNT_TABLES:
        op.drop_constraint(f"ck_{table}_email_normalized", table, type_="check")
    op.drop_table("account_email_registry")
    op.drop_index("ix_portal_auth_tokens_expires_at", table_name="portal_auth_tokens")
    op.drop_index("ix_portal_auth_tokens_token_hash", table_name="portal_auth_tokens")
    op.drop_index("ix_portal_auth_tokens_portal_user_id", table_name="portal_auth_tokens")
    op.drop_table("portal_auth_tokens")
