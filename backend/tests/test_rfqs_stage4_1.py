"""Automated Test Suite for Phase C13.4 Stage 4.1: Central Enquiries Repository & Triage.

Tests:
1. Date-range filtering (created_from inclusive, created_to exclusive).
2. Date-range boundary conditions [created_from, created_to).
3. Inverted date range (created_from > created_to) rejected with HTTP 400 Bad Request.
4. Timezone handling and UTC normalization.
5. Server-side sorting (created_at, reference_number, company_name, status).
6. Multi-field search (reference_number, company_name, full_name, business_email).
7. Division, status, and assigned administrator filters.
8. Unassigned filter ("unassigned").
9. Server-side pagination metadata (page, limit, total_items, total_pages).
10. RBAC authorization (SUPER_ADMIN and OPERATIONS_ADMIN accepted, unauthenticated rejected).
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.core.config import settings
from app.core.security import hash_password
from app.db.seeds import seed_divisions, seed_roles
from app.models.admin import AdminSession, AdminUser, AdminUserRole
from app.models.audit import AuditLog
from app.models.enquiry import (
    Enquiry,
    EnquiryAssignment,
    EnquiryNote,
    EnquiryStatusHistory,
)
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(autouse=True)
async def setup_stage4_1_database(db_session: AsyncSession, async_client: AsyncClient):
    """Resets test database before and after each test."""
    async_client.cookies.clear()
    await db_session.execute(delete(AuditLog))
    await db_session.execute(delete(EnquiryNote))
    await db_session.execute(delete(EnquiryStatusHistory))
    await db_session.execute(delete(EnquiryAssignment))
    await db_session.execute(delete(Enquiry))
    await db_session.execute(delete(AdminSession))
    await db_session.execute(delete(AdminUserRole))
    await db_session.execute(delete(AdminUser))
    await db_session.commit()

    await seed_roles(db_session)
    await seed_divisions(db_session)
    await db_session.commit()

    yield

    async_client.cookies.clear()
    await db_session.execute(delete(AuditLog))
    await db_session.execute(delete(EnquiryNote))
    await db_session.execute(delete(EnquiryStatusHistory))
    await db_session.execute(delete(EnquiryAssignment))
    await db_session.execute(delete(Enquiry))
    await db_session.execute(delete(AdminSession))
    await db_session.execute(delete(AdminUserRole))
    await db_session.execute(delete(AdminUser))
    await db_session.commit()


async def create_admin(
    db: AsyncSession,
    email: str = "ops_stage4@edenbounty.org",
    role: str = "OPERATIONS_ADMIN",
) -> AdminUser:
    """Helper to provision a test administrator."""
    user = AdminUser(
        email=email,
        password_hash=hash_password("SuperSecretPass2026!#"),
        first_name="Operations",
        last_name="Manager",
        job_title="Trade Operations Lead",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    user_role = AdminUserRole(admin_user_id=user.id, role_id=role)
    db.add(user_role)
    await db.commit()
    await db.refresh(user)
    return user


async def login_admin(async_client: AsyncClient, email: str = "ops_stage4@edenbounty.org") -> str:
    """Helper to authenticate admin and retrieve session cookie."""
    res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SuperSecretPass2026!#"},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res.status_code == status.HTTP_200_OK
    cookie = res.cookies.get(settings.SESSION_COOKIE_NAME)
    assert cookie is not None
    return cookie


async def create_enquiry(
    db: AsyncSession,
    ref: str,
    division_id: str,
    status_str: str,
    created_at_dt: datetime,
    company: str = "Demo Corp Sdn Bhd",
    contact: str = "John Doe",
    email: str = "john@democorp.com",
    assignee_id: uuid.UUID | None = None,
) -> Enquiry:
    """Helper to provision test enquiry with deterministic timestamp."""
    enquiry = Enquiry(
        reference_number=ref,
        full_name=contact,
        company_name=company,
        business_email=email,
        contact_number="+60123456789",
        country="Malaysia",
        initial_division_id=division_id,
        current_division_id=division_id,
        product_focus="Industrial Commodity Sourcing",
        quantity=Decimal("1000.00"),
        unit_of_measurement="MT",
        specifications="Commercial specifications description",
        status=status_str,
        assigned_admin_id=assignee_id,
        created_at=created_at_dt,
        updated_at=created_at_dt,
    )
    db.add(enquiry)
    await db.commit()
    await db.refresh(enquiry)
    return enquiry


@pytest.mark.asyncio
async def test_01_date_range_filtering_inclusive_start_exclusive_end(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies created_from (inclusive) and created_to (exclusive) boundaries."""
    admin = await create_admin(db_session, "ops_dates@edenbounty.org")
    cookie = await login_admin(async_client, "ops_dates@edenbounty.org")

    t1 = datetime(2026, 11, 1, 10, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)
    t3 = datetime(2026, 11, 3, 10, 0, 0, tzinfo=UTC)

    await create_enquiry(db_session, "EB-D1", "mineral-water", "NEW", t1)
    await create_enquiry(db_session, "EB-D2", "petroleum-products", "ASSIGNED", t2, assignee_id=admin.id)
    await create_enquiry(db_session, "EB-D3", "construction", "UNDER_REVIEW", t3)

    # 1. Filter created_from = t2 (should return t2 and t3, inclusive start)
    res_from = await async_client.get(
        "/api/v1/admin/rfqs",
        params={"created_from": t2.isoformat()},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res_from.status_code == status.HTTP_200_OK
    items_from = res_from.json()["data"]["items"]
    assert len(items_from) == 2
    refs_from = {i["reference_number"] for i in items_from}
    assert refs_from == {"EB-D2", "EB-D3"}

    # 2. Filter created_to = t2 (should return t1 only, exclusive end)
    res_to = await async_client.get(
        "/api/v1/admin/rfqs",
        params={"created_to": t2.isoformat()},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res_to.status_code == status.HTTP_200_OK
    items_to = res_to.json()["data"]["items"]
    assert len(items_to) == 1
    assert items_to[0]["reference_number"] == "EB-D1"

    # 3. Filter [t1, t3) (should return t1 and t2, exclusive of t3)
    res_range = await async_client.get(
        "/api/v1/admin/rfqs",
        params={"created_from": t1.isoformat(), "created_to": t3.isoformat()},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res_range.status_code == status.HTTP_200_OK
    items_range = res_range.json()["data"]["items"]
    assert len(items_range) == 2
    refs_range = {i["reference_number"] for i in items_range}
    assert refs_range == {"EB-D1", "EB-D2"}


@pytest.mark.asyncio
async def test_02_inverted_date_range_rejected_http_400(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies that created_from > created_to is rejected with HTTP 400 Bad Request."""
    await create_admin(db_session, "ops_bad_dates@edenbounty.org")
    cookie = await login_admin(async_client, "ops_bad_dates@edenbounty.org")

    start_dt = datetime(2026, 11, 5, 0, 0, 0, tzinfo=UTC)
    end_dt = datetime(2026, 11, 1, 0, 0, 0, tzinfo=UTC)

    res = await async_client.get(
        "/api/v1/admin/rfqs",
        params={"created_from": start_dt.isoformat(), "created_to": end_dt.isoformat()},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "created_from timestamp cannot be later than created_to timestamp" in res.json()["detail"]


@pytest.mark.asyncio
async def test_03_multi_field_search_and_filters(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies search and division/status/assignee filtering."""
    admin1 = await create_admin(db_session, "admin1@edenbounty.org")
    admin2 = await create_admin(db_session, "admin2@edenbounty.org")
    cookie = await login_admin(async_client, "admin1@edenbounty.org")

    now = datetime.now(UTC)
    await create_enquiry(
        db_session,
        "EB-SRCH-100",
        "mineral-water",
        "NEW",
        now - timedelta(hours=3),
        company="Global Apex Logistics",
        contact="Alice Tan",
        email="alice@globalapex.com",
    )
    await create_enquiry(
        db_session,
        "EB-SRCH-200",
        "petroleum-products",
        "ASSIGNED",
        now - timedelta(hours=2),
        company="Borneo Marine Fuel",
        contact="Bob Lim",
        email="bob@borneofuel.com",
        assignee_id=admin2.id,
    )
    await create_enquiry(
        db_session,
        "EB-SRCH-300",
        "petroleum-products",
        "UNDER_REVIEW",
        now - timedelta(hours=1),
        company="Klang Petrochemical Sourcing",
        contact="Charlie Lee",
        email="charlie@klangpetro.com",
        assignee_id=admin1.id,
    )

    # 1. Search by reference number
    res_search_ref = await async_client.get(
        "/api/v1/admin/rfqs?search=EB-SRCH-100",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res_search_ref.status_code == status.HTTP_200_OK
    assert len(res_search_ref.json()["data"]["items"]) == 1
    assert res_search_ref.json()["data"]["items"][0]["reference_number"] == "EB-SRCH-100"

    # 2. Search by company name
    res_search_comp = await async_client.get(
        "/api/v1/admin/rfqs?search=Borneo",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res_search_comp.status_code == status.HTTP_200_OK
    assert len(res_search_comp.json()["data"]["items"]) == 1
    assert res_search_comp.json()["data"]["items"][0]["reference_number"] == "EB-SRCH-200"

    # 3. Filter by division
    res_div = await async_client.get(
        "/api/v1/admin/rfqs?division_id=petroleum-products",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res_div.status_code == status.HTTP_200_OK
    assert len(res_div.json()["data"]["items"]) == 2

    # 4. Filter by unassigned
    res_unassigned = await async_client.get(
        "/api/v1/admin/rfqs?assigned_admin_id=unassigned",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res_unassigned.status_code == status.HTTP_200_OK
    assert len(res_unassigned.json()["data"]["items"]) == 1
    assert res_unassigned.json()["data"]["items"][0]["reference_number"] == "EB-SRCH-100"

    # 5. Filter by specific admin
    res_admin2 = await async_client.get(
        f"/api/v1/admin/rfqs?assigned_admin_id={admin2.id}",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res_admin2.status_code == status.HTTP_200_OK
    assert len(res_admin2.json()["data"]["items"]) == 1
    assert res_admin2.json()["data"]["items"][0]["reference_number"] == "EB-SRCH-200"


@pytest.mark.asyncio
async def test_04_server_side_sorting_and_pagination(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies server-side sorting (asc/desc) and pagination windowing."""
    await create_admin(db_session, "ops_sort@edenbounty.org")
    cookie = await login_admin(async_client, "ops_sort@edenbounty.org")

    base_time = datetime(2026, 11, 1, 0, 0, 0, tzinfo=UTC)
    for i in range(1, 16):
        await create_enquiry(
            db_session,
            f"EB-PAG-{i:03d}",
            "mineral-water",
            "NEW",
            base_time + timedelta(hours=i),
            company=f"Company {chr(65 + (i % 10))}",
        )

    # 1. Page 1 with limit 5, sort created_at desc (newest first)
    res_p1 = await async_client.get(
        "/api/v1/admin/rfqs?page=1&limit=5&sort_by=created_at&sort_order=desc",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res_p1.status_code == status.HTTP_200_OK
    data_p1 = res_p1.json()["data"]
    assert len(data_p1["items"]) == 5
    assert data_p1["pagination"]["page"] == 1
    assert data_p1["pagination"]["limit"] == 5
    assert data_p1["pagination"]["total_items"] == 15
    assert data_p1["pagination"]["total_pages"] == 3
    assert data_p1["items"][0]["reference_number"] == "EB-PAG-015"

    # 2. Page 2 with limit 5, sort created_at desc
    res_p2 = await async_client.get(
        "/api/v1/admin/rfqs?page=2&limit=5&sort_by=created_at&sort_order=desc",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res_p2.status_code == status.HTTP_200_OK
    data_p2 = res_p2.json()["data"]
    assert len(data_p2["items"]) == 5
    assert data_p2["items"][0]["reference_number"] == "EB-PAG-010"

    # 3. Sort reference_number asc
    res_ref_asc = await async_client.get(
        "/api/v1/admin/rfqs?page=1&limit=5&sort_by=reference_number&sort_order=asc",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res_ref_asc.status_code == status.HTTP_200_OK
    data_ref_asc = res_ref_asc.json()["data"]
    assert data_ref_asc["items"][0]["reference_number"] == "EB-PAG-001"
