"""consolidate duplicate building promotions into construction

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-15 12:48:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0011_consolidate_building_promotions"
down_revision: Union[str, None] = "0010_registration_verification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Reassign any historical enquiries referencing building-promotions to the canonical construction service
    op.execute(
        "UPDATE enquiries SET initial_division_id = 'construction' WHERE initial_division_id = 'building-promotions'"
    )
    op.execute(
        "UPDATE enquiries SET current_division_id = 'construction' WHERE current_division_id = 'building-promotions'"
    )

    # 2. Reassign enquiry_assignments
    op.execute(
        "UPDATE enquiry_assignments SET previous_division_id = 'construction' WHERE previous_division_id = 'building-promotions'"
    )
    op.execute(
        "UPDATE enquiry_assignments SET new_division_id = 'construction' WHERE new_division_id = 'building-promotions'"
    )

    # 3. Reassign portal orders (if table exists)
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'orders') THEN
                UPDATE orders SET division_id = 'construction' WHERE division_id = 'building-promotions';
            END IF;
        END $$;
        """
    )

    # 4. Reassign portal investments (if table exists)
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'investments') THEN
                UPDATE investments SET division_id = 'construction' WHERE division_id = 'building-promotions';
            END IF;
        END $$;
        """
    )

    # 5. Delete duplicate building-promotions row from divisions table
    op.execute("DELETE FROM divisions WHERE id = 'building-promotions'")


def downgrade() -> None:
    # Re-insert building-promotions as inactive if rolled back
    op.execute(
        """
        INSERT INTO divisions (id, code, name, sector, accent_color, is_active)
        VALUES ('building-promotions', 'EB-DIV-04', 'Building Promotions', 'Commercial Division', '#8B5CF6', false)
        ON CONFLICT (id) DO NOTHING
        """
    )
