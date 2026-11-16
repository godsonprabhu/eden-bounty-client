"""Add Idempotency Key and Request Payload Hash to Enquiries

Revision ID: 0002_add_enquiry_idempotency
Revises: 0001_initial_schema
Create Date: 2026-11-08 14:25:00.000000

Phase C13.3 — Final Corrective Pass:
Supports client-generated idempotency keys for repeat RFQ submissions.
Stores request payload hash for conflict detection.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_add_enquiry_idempotency"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "enquiries",
        sa.Column("idempotency_key", sa.String(128), nullable=True),
    )
    op.add_column(
        "enquiries",
        sa.Column("request_payload_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        "idx_enquiries_idempotency_key",
        "enquiries",
        ["idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_enquiries_idempotency_key", table_name="enquiries")
    op.drop_column("enquiries", "request_payload_hash")
    op.drop_column("enquiries", "idempotency_key")
