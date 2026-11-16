"""Tests for Commercial Division and Administrative Role Seed Data."""

import pytest
from app.db.seeds import seed_all
from app.models.admin import AdminRole
from app.models.division import Division
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_all_division_records_seeded(db_session: AsyncSession):
    """Verify that every canonical division record (active and inactive) exists."""
    result = await db_session.execute(select(Division).order_by(Division.code))
    divisions = result.scalars().all()
    # 9 canonical divisions (8 active + 1 inactive historical lubricants; duplicate building-promotions removed)
    assert len(divisions) == 9

    division_codes = [d.code for d in divisions]
    expected_codes = ["EB-DIV-01", "EB-DIV-02", "EB-DIV-03", "EB-DIV-05", "EB-DIV-06", "EB-DIV-07", "EB-DIV-08", "EB-DIV-09", "EB-DIV-10"]
    assert division_codes == expected_codes


@pytest.mark.asyncio
async def test_drone_division_has_no_manufacturer_attribution(db_session: AsyncSession):
    """Verify the drone division keeps its ID/code, is named 'Drone', and names no manufacturer (CR-C1)."""
    result = await db_session.execute(
        select(Division).where(Division.code == "EB-DIV-10")
    )
    drone_div = result.scalar_one_or_none()
    assert drone_div is not None
    assert drone_div.id == "agricultural-drones"
    assert drone_div.name == "Drone"
    assert drone_div.manufacturer_attribution is None
    assert "does not manufacture drones" in drone_div.disclaimer
    assert "claim official partnership" in drone_div.disclaimer
    assert "authorized dealership" in drone_div.disclaimer


@pytest.mark.asyncio
async def test_withdrawn_divisions_are_inactive_not_deleted(db_session: AsyncSession):
    """Withdrawn divisions stay in the table as inactive for historical reference."""
    result = await db_session.execute(select(Division))
    by_id = {d.id: d for d in result.scalars().all()}

    inactive_ids = {d_id for d_id, d in by_id.items() if not d.is_active}
    assert inactive_ids == {"lubricants", "shisha-tobacco-trading", "axe-oil"}

    # Codes are preserved for the withdrawn records
    assert by_id["lubricants"].code == "EB-DIV-08"
    assert by_id["shisha-tobacco-trading"].code == "EB-DIV-05"
    assert by_id["axe-oil"].code == "EB-DIV-06"

    # Construction absorbs building promotion; its ID and code are unchanged
    assert by_id["construction"].name == "Construction"
    assert by_id["construction"].code == "EB-DIV-03"
    assert by_id["construction"].is_active is True


@pytest.mark.asyncio
async def test_no_garuda_reference_in_division_data(db_session: AsyncSession):
    """CR-C1: no division record references Garuda in any text field."""
    result = await db_session.execute(select(Division))
    for d in result.scalars().all():
        blob = " ".join(filter(None, [d.name, d.sector, d.manufacturer_attribution, d.disclaimer]))
        assert "garuda" not in blob.lower()


@pytest.mark.asyncio
async def test_initial_roles_seeded(db_session: AsyncSession):
    """Verify that only SUPER_ADMIN and OPERATIONS_ADMIN roles exist."""
    result = await db_session.execute(select(AdminRole).order_by(AdminRole.id))
    roles = result.scalars().all()
    role_ids = {r.id for r in roles}
    assert role_ids == {"SUPER_ADMIN", "OPERATIONS_ADMIN"}


@pytest.mark.asyncio
async def test_seed_idempotency(db_session: AsyncSession):
    """Verify that running seed operations multiple times produces no duplicate rows."""
    # Count before
    div_count_1 = (await db_session.execute(select(func.count(Division.id)))).scalar()
    role_count_1 = (await db_session.execute(select(func.count(AdminRole.id)))).scalar()

    # Re-run seed
    await seed_all(db_session)

    # Count after
    div_count_2 = (await db_session.execute(select(func.count(Division.id)))).scalar()
    role_count_2 = (await db_session.execute(select(func.count(AdminRole.id)))).scalar()

    assert div_count_1 == div_count_2 == 9
    assert role_count_1 == role_count_2 == 2
