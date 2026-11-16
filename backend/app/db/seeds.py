"""Division and Role Seed Data for EDEN BOUNTY Sdn. Bhd.

Aligns strictly with Phase C13 specification v2.1.0.
Seed operations are idempotent (upsert/no duplicates).
"""

from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import AdminRole
from app.models.division import Division

# Every division record (EB-DIV-01 to EB-DIV-10). Rows are never removed and IDs/codes never change,
# because historical enquiries reference them. Divisions withdrawn from the public site are kept with
# is_active=False (CR-C1): the public listing and RFQ intake only accept active divisions.
DIVISIONS_SEED_DATA: list[dict[str, Any]] = [
    {
        "id": "mineral-water",
        "code": "EB-DIV-01",
        "name": "Mineral Water",
        "sector": "Commercial Division",
        "accent_color": "#0284C7",
        "is_active": True,
        "manufacturer_attribution": None,
        "disclaimer": None,
    },
    {
        "id": "scrap-trading",
        "code": "EB-DIV-02",
        "name": "Scrap Trading",
        "sector": "Commercial Division",
        "accent_color": "#10B981",
        "is_active": True,
        "manufacturer_attribution": None,
        "disclaimer": None,
    },
    {
        "id": "construction",
        "code": "EB-DIV-03",
        "name": "Construction",
        "sector": "Commercial Division",
        "accent_color": "#F59E0B",
        "is_active": True,
        "manufacturer_attribution": None,
        "disclaimer": None,
    },
    {
        "id": "shisha-tobacco-trading",
        "code": "EB-DIV-05",
        "name": "Shisha Tobacco Trading",
        "sector": "Commercial Division",
        "accent_color": "#EC4899",
        # Withdrawn from the public site per client instruction; retained for historical enquiries.
        "is_active": False,
        "manufacturer_attribution": None,
        "disclaimer": None,
    },
    {
        "id": "axe-oil",
        "code": "EB-DIV-06",
        "name": "Axe Oil",
        "sector": "Commercial Division",
        "accent_color": "#14B8A6",
        # Withdrawn from the public site per client instruction; retained for historical enquiries.
        "is_active": False,
        "manufacturer_attribution": None,
        "disclaimer": None,
    },
    {
        "id": "petroleum-products",
        "code": "EB-DIV-07",
        "name": "Petroleum Products",
        "sector": "Commercial Division",
        "accent_color": "#EF4444",
        "is_active": True,
        "manufacturer_attribution": None,
        "disclaimer": None,
    },
    {
        "id": "lubricants",
        "code": "EB-DIV-08",
        "name": "Industrial Lubricants",
        "sector": "Commercial Division",
        "accent_color": "#F97316",
        # Withdrawn from the public site (CR-C1); retained for historical enquiries.
        "is_active": False,
        "manufacturer_attribution": None,
        "disclaimer": None,
    },
    {
        "id": "furnace-oil",
        "code": "EB-DIV-09",
        "name": "Furnace Oil",
        "sector": "Commercial Division",
        "accent_color": "#6366F1",
        "is_active": True,
        "manufacturer_attribution": None,
        "disclaimer": None,
    },
    {
        "id": "agricultural-drones",
        "code": "EB-DIV-10",
        "name": "Drone",
        "sector": "Commercial Division",
        "accent_color": "#00E5FF",
        "is_active": True,
        "manufacturer_attribution": None,
        "disclaimer": (
            "EDEN BOUNTY does not manufacture drones, claim official partnership "
            "or authorized dealership without written confirmation, own or operate an "
            "aircraft fleet, or provide flight or spraying services."
        ),
    },
]

# Strictly two administrative roles for the initial release
ROLES_SEED_DATA: list[dict[str, Any]] = [
    {
        "id": "SUPER_ADMIN",
        "name": "Super Administrator",
        "description": (
            "Full system authority: manages enquiries across all divisions, "
            "assigns enquiries, creates/manages admin accounts, inspects audit logs "
            "and notification health."
        ),
    },
    {
        "id": "OPERATIONS_ADMIN",
        "name": "Operations Administrator",
        "description": (
            "Central trading desk operations: reviews and triages incoming enquiries, "
            "assigns to divisions, updates statuses, records internal notes and follow-ups."
        ),
    },
]


async def seed_divisions(session: AsyncSession) -> int:
    """Idempotently seeds all division records (active and inactive)."""
    seeded_count = 0
    for div_data in DIVISIONS_SEED_DATA:
        stmt = insert(Division).values(**div_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Division.id],
            set_={
                "code": stmt.excluded.code,
                "name": stmt.excluded.name,
                "sector": stmt.excluded.sector,
                "accent_color": stmt.excluded.accent_color,
                "is_active": stmt.excluded.is_active,
                "manufacturer_attribution": stmt.excluded.manufacturer_attribution,
                "disclaimer": stmt.excluded.disclaimer,
            },
        )
        await session.execute(stmt)
        seeded_count += 1
    await session.commit()
    return seeded_count


async def seed_roles(session: AsyncSession) -> int:
    """Idempotently seeds the two approved administrative roles."""
    seeded_count = 0
    for role_data in ROLES_SEED_DATA:
        stmt = insert(AdminRole).values(**role_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=[AdminRole.id],
            set_={
                "name": stmt.excluded.name,
                "description": stmt.excluded.description,
            },
        )
        await session.execute(stmt)
        seeded_count += 1
    await session.commit()
    return seeded_count


async def seed_all(session: AsyncSession) -> dict[str, int]:
    """Idempotently seeds all initial static master data."""
    divs = await seed_divisions(session)
    roles = await seed_roles(session)
    return {"divisions": divs, "roles": roles}
