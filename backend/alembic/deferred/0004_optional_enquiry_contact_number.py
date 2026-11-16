"""Allow RFQ submitters to omit their contact telephone number."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_optional_enquiry_contact_number"
down_revision: str | None = "0003_v43_0_0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "enquiries",
        "contact_number",
        existing_type=sa.String(length=50),
        existing_nullable=False,
        nullable=True,
    )


def downgrade() -> None:
    has_missing_contact_numbers = op.get_bind().scalar(
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

    op.alter_column(
        "enquiries",
        "contact_number",
        existing_type=sa.String(length=50),
        existing_nullable=True,
        nullable=False,
    )
