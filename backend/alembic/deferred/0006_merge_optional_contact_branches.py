"""Merge the notification and optional contact-number migration branches."""

from collections.abc import Sequence

revision: str = "0006_merge_contact_branches"
down_revision: str | Sequence[str] | None = (
    "0004_optional_enquiry_contact_number",
    "0005_optional_contact_nullable",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge migration histories; both parent revisions establish the same nullable state."""


def downgrade() -> None:
    """Split the merged migration history back into its two parent heads."""
