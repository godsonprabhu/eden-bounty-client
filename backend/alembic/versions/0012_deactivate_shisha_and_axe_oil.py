"""deactivate shisha and axe oil from active commercial offerings

Revision ID: 0012_deactivate_shisha_and_axe_oil
Revises: 0011_consolidate_building_promotions
Create Date: 2026-11-15 14:55:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0012_deactivate_shisha_and_axe_oil"
down_revision: Union[str, None] = "0011_consolidate_building_promotions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Mark shisha-tobacco-trading and axe-oil as inactive (withdrawn from public site)
    # Rows are preserved in the divisions table to maintain foreign key referential integrity
    # for historical enquiries, portal orders, and audit trail logs.
    op.execute(
        "UPDATE divisions SET is_active = false WHERE id IN ('shisha-tobacco-trading', 'axe-oil')"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE divisions SET is_active = true WHERE id IN ('shisha-tobacco-trading', 'axe-oil')"
    )
