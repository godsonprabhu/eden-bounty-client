"""Allow RFQ enquiries to omit a contact number, independently of 0003.

Revision ID: 0005_optional_contact_nullable
Revises: 0002_add_enquiry_idempotency
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from alembic.migration import MigrationContext

revision: str = "0005_optional_contact_nullable"
down_revision: str | None = "0002_add_enquiry_idempotency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALEMBIC_VERSION_NUM_LENGTH = 64


def _contact_number_is_nullable(bind: sa.Connection) -> bool:
    columns = sa.inspect(bind).get_columns("enquiries", schema="public")
    contact_number = next(
        (column for column in columns if column["name"] == "contact_number"),
        None,
    )
    if contact_number is None:
        raise RuntimeError("Expected public.enquiries.contact_number to exist.")
    return bool(contact_number["nullable"])


def _ensure_revision_id_capacity(bind: sa.Connection) -> None:
    columns = sa.inspect(bind).get_columns("alembic_version")
    version_num = next(
        (column for column in columns if column["name"] == "version_num"),
        None,
    )
    if version_num is None:
        raise RuntimeError("Expected alembic_version.version_num to exist.")

    current_length = getattr(version_num["type"], "length", None)
    # TEXT and VARCHAR without a length are unbounded. Do not replace them
    # with a bounded type, and leave already-sufficient bounded types alone.
    if current_length is None or current_length >= ALEMBIC_VERSION_NUM_LENGTH:
        return

    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=version_num["type"],
        type_=sa.String(length=ALEMBIC_VERSION_NUM_LENGTH),
        existing_nullable=False,
        nullable=False,
    )


def upgrade() -> None:
    bind = op.get_bind()
    # Alembic's default version_num is VARCHAR(32), but the preserved 0004
    # revision identifier is 36 characters. Widen before Alembic records it.
    _ensure_revision_id_capacity(bind)
    if _contact_number_is_nullable(bind):
        return

    op.alter_column(
        "enquiries",
        "contact_number",
        schema="public",
        existing_type=sa.String(length=50),
        existing_nullable=False,
        nullable=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    has_missing_contact_numbers = bind.scalar(
        sa.text(
            "SELECT EXISTS ("
            "SELECT 1 FROM public.enquiries WHERE contact_number IS NULL"
            ")"
        )
    )
    if has_missing_contact_numbers:
        raise RuntimeError(
            "Cannot make enquiries.contact_number NOT NULL while rows omit a contact number."
        )

    # The legacy 0004 branch also establishes this schema state. When Alembic
    # has already split the merged revision back into its parent heads, keep
    # the column nullable while 0004 remains applied.
    current_heads = MigrationContext.configure(bind).get_current_heads()
    if "0004_optional_enquiry_contact_number" in current_heads:
        return

    if not _contact_number_is_nullable(bind):
        return

    op.alter_column(
        "enquiries",
        "contact_number",
        schema="public",
        existing_type=sa.String(length=50),
        existing_nullable=True,
        nullable=False,
    )
