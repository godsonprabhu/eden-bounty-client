"""Align index and unique-constraint names with the SQLAlchemy model metadata.

Revision ID: 0007_align_index_names
Revises: 0005_optional_contact_nullable
Create Date: 2026-11-12

Why: migrations 0001/0002 created indexes named ``idx_*`` and UNIQUE constraints named ``*_key``,
while the ORM models declare ``index=True`` / ``unique=True`` (names ``ix_*``). Columns, types and
nullability already matched; only names (and three DESC/ASC variants) differed, so
``alembic revision --autogenerate`` reported 40 spurious drop/create operations.

This revision is metadata-only: no table or column changes, no data movement. Each statement is
issued separately (asyncpg prepared statements cannot contain multiple commands), all inside the
single Alembic transaction. New unique indexes are created *before* the old UNIQUE constraints are
dropped, so uniqueness is never lapsed.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007_align_index_names"
down_revision: str | None = "0005_optional_contact_nullable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Plain renames: identical definition, new name.
RENAMES: list[tuple[str, str]] = [
    ("idx_admin_sessions_user", "ix_admin_sessions_admin_user_id"),
    ("idx_admin_sessions_expires", "ix_admin_sessions_expires_at"),
    ("idx_audit_logs_actor", "ix_audit_logs_actor_admin_id"),
    ("idx_enquiries_assigned_admin", "ix_enquiries_assigned_admin_id"),
    ("idx_enquiries_current_div", "ix_enquiries_current_division_id"),
    ("idx_enquiries_idempotency_key", "ix_enquiries_idempotency_key"),
    ("idx_enquiries_status", "ix_enquiries_status"),
    ("idx_enquiries_created_at", "idx_enquiries_created_at_desc"),
    ("idx_enquiry_assignments_enquiry", "ix_enquiry_assignments_enquiry_id"),
    ("idx_enquiry_notes_enquiry", "ix_enquiry_notes_enquiry_id"),
    ("idx_enquiry_status_history_enquiry", "ix_enquiry_status_history_enquiry_id"),
    ("idx_notification_logs_enquiry", "ix_notification_logs_enquiry_id"),
    ("idx_notification_logs_status", "ix_notification_logs_status"),
]

# UNIQUE constraint (+ redundant plain index) -> single unique index, as declared by the models.
UNIQUES: list[tuple[str, str, str, str, str]] = [
    # table, column, old constraint, old plain index, new unique index
    ("admin_users", "email", "admin_users_email_key", "idx_admin_users_email", "ix_admin_users_email"),
    ("divisions", "code", "divisions_code_key", "idx_divisions_code", "ix_divisions_code"),
    ("enquiries", "reference_number", "enquiries_reference_number_key", "idx_enquiries_ref", "ix_enquiries_reference_number"),
]


def upgrade() -> None:
    for old, new in RENAMES:
        op.execute(f"ALTER INDEX public.{old} RENAME TO {new}")

    for table, column, constraint, plain_index, new_index in UNIQUES:
        op.execute(f"CREATE UNIQUE INDEX {new_index} ON public.{table} ({column})")
        op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT {constraint}")
        op.execute(f"DROP INDEX public.{plain_index}")

    # Models declare ascending single-column indexes here (btree serves both scan directions).
    op.execute("DROP INDEX public.idx_audit_logs_timestamp")
    op.execute('CREATE INDEX ix_audit_logs_timestamp ON public.audit_logs ("timestamp")')
    op.execute("DROP INDEX public.idx_enquiry_assignments_assigned_at")
    op.execute("CREATE INDEX ix_enquiry_assignments_assigned_at ON public.enquiry_assignments (assigned_at)")
    # The Enquiry model declares both an ascending (index=True) and a DESC index on created_at.
    op.execute("CREATE INDEX ix_enquiries_created_at ON public.enquiries (created_at)")


def downgrade() -> None:
    op.execute("DROP INDEX public.ix_enquiries_created_at")
    op.execute("DROP INDEX public.ix_enquiry_assignments_assigned_at")
    op.execute("CREATE INDEX idx_enquiry_assignments_assigned_at ON public.enquiry_assignments (assigned_at DESC)")
    op.execute("DROP INDEX public.ix_audit_logs_timestamp")
    op.execute('CREATE INDEX idx_audit_logs_timestamp ON public.audit_logs ("timestamp" DESC)')

    for table, column, constraint, plain_index, new_index in reversed(UNIQUES):
        op.execute(f"ALTER TABLE public.{table} ADD CONSTRAINT {constraint} UNIQUE ({column})")
        op.execute(f"CREATE INDEX {plain_index} ON public.{table} ({column})")
        op.execute(f"DROP INDEX public.{new_index}")

    for old, new in reversed(RENAMES):
        op.execute(f"ALTER INDEX public.{new} RENAME TO {old}")
