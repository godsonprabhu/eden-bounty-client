"""Automated Test Suite for Central Admin Dashboard Overview (Stage 3).

Phase C13.4 — Central Admin Dashboard & Enquiry Management (Stage 3).
Verifies:
1. Exact metric calculations across all 8 statuses, total volume, unassigned triage, and today's intake.
2. Verified inclusion of DECLINED and ARCHIVED in total and division counts.
3. Empty database state behavior.
4. UTC date boundary calculations for today's intake.
5. GET /api/v1/admin/dashboard/activity endpoint reusing AuditLog records.
6. RBAC access for both SUPER_ADMIN and OPERATIONS_ADMIN, and 401 for unauthenticated.
7. Data minimization and privacy verification (exclusion of customer PII and internal note text).
8. Query performance and timing verification.
"""

import time
from datetime import UTC, datetime, timedelta

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
from app.schemas.admin import VALID_STATUSES
from app.services.audit import record_audit_log
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(autouse=True)
async def setup_dashboard_test_database(db_session: AsyncSession, async_client: AsyncClient):
    """Ensures clean tables and seeded roles/divisions before each test."""
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
    yield
    async_client.cookies.clear()



async def create_test_admin(
    db: AsyncSession,
    email: str,
    password: str = "CorporatePass2026!#",
    role: str = "OPERATIONS_ADMIN",
    first_name: str = "Operations",
    last_name: str = "Admin",
) -> AdminUser:
    """Helper to provision test administrators with designated roles."""
    user = AdminUser(
        email=email.strip().lower(),
        password_hash=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        job_title="Operations Officer",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    user_role = AdminUserRole(
        admin_user_id=user.id,
        role_id=role,
        assigned_by=user.id,
    )
    db.add(user_role)
    await db.commit()
    return user


async def login_test_admin(
    client: AsyncClient,
    email: str,
    password: str = "CorporatePass2026!#",
) -> tuple[str, str, dict]:
    """Helper to log in an administrator and return (cookie, csrf_token, user_info)."""
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res.status_code == status.HTTP_200_OK
    cookie = res.cookies[settings.SESSION_COOKIE_NAME]
    csrf_token = res.json()["data"]["csrf_token"]
    user_info = res.json()["data"]["user"]
    return cookie, csrf_token, user_info


# ==============================================================================
# 1. Metric Calculation & Overview Tests
# ==============================================================================


@pytest.mark.anyio
async def test_01_dashboard_metrics_accuracy(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies exact calculation rules for all 8 statuses, total volume, and division distribution."""
    admin = await create_test_admin(db_session, "ops1@edenbounty.org", role="OPERATIONS_ADMIN")
    cookie, _, _ = await login_test_admin(async_client, "ops1@edenbounty.org")

    # Create 8 enquiries, one for each approved status, spread across 8 divisions
    all_statuses = sorted(VALID_STATUSES)
    divisions = [
        "mineral-water",
        "scrap-trading",
        "construction",
        "construction",
        "shisha-tobacco-trading",
        "axe-oil",
        "petroleum-products",
        "lubricants",
    ]

    for i, st in enumerate(all_statuses):
        enq = Enquiry(
            reference_number=f"EB-202611-000{i+1}",
            idempotency_key=f"idem-test-{i+1}",
            request_payload_hash=f"hash-{i+1}",
            full_name=f"Customer {i+1}",
            company_name=f"Company {i+1}",
            business_email=f"customer{i+1}@example.com",
            contact_number="+60123456789",
            country="Malaysia",
            initial_division_id=divisions[i],
            current_division_id=divisions[i],
            product_focus=f"Product Focus {i+1}",
            status=st,
            assigned_admin_id=admin.id if st == "ASSIGNED" else None,
        )
        db_session.add(enq)
    await db_session.commit()

    # Query overview
    res = await async_client.get(
        "/api/v1/admin/dashboard/overview",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()["data"]

    # 1. Total volume equals 8 (includes DECLINED and ARCHIVED)
    assert data["total_enquiries"] == 8

    # 2. Every single status count equals 1
    assert len(data["by_status"]) == 8
    for st in all_statuses:
        assert data["by_status"][st] == 1, f"Status {st} should have count 1"

    # 3. Sum of status counts exactly equals total_enquiries
    sum_statuses = sum(data["by_status"].values())
    assert sum_statuses == data["total_enquiries"]

    # 4. Division distribution contains all 9 canonical divisions
    assert len(data["by_division"]) == 9
    sum_divisions = sum(div["count"] for div in data["by_division"])
    assert sum_divisions == data["total_enquiries"]

    # Unrepresented divisions have count 0
    furnace_div = next(d for d in data["by_division"] if d["division_id"] == "furnace-oil")
    drone_div = next(d for d in data["by_division"] if d["division_id"] == "agricultural-drones")
    assert furnace_div["count"] == 0
    assert drone_div["count"] == 0

    # 5. Unassigned triage count: 7 unassigned (only ASSIGNED status has assigned_admin_id)
    assert data["unassigned_count"] == 7


@pytest.mark.anyio
async def test_02_dashboard_empty_database(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies dashboard overview returns clean zeroes on an empty database."""
    await create_test_admin(db_session, "ops_empty@edenbounty.org", role="OPERATIONS_ADMIN")
    cookie, _, _ = await login_test_admin(async_client, "ops_empty@edenbounty.org")

    res = await async_client.get(
        "/api/v1/admin/dashboard/overview",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()["data"]

    assert data["total_enquiries"] == 0
    assert data["unassigned_count"] == 0
    assert data["today_count"] == 0
    for st in VALID_STATUSES:
        assert data["by_status"][st] == 0
    assert len(data["by_division"]) == 9
    for div in data["by_division"]:
        assert div["count"] == 0


@pytest.mark.anyio
async def test_03_today_intake_utc_date_boundary(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies that today_count strictly applies UTC midnight boundary."""
    await create_test_admin(db_session, "ops_date@edenbounty.org", role="OPERATIONS_ADMIN")
    cookie, _, _ = await login_test_admin(async_client, "ops_date@edenbounty.org")

    now_utc = datetime.now(UTC)
    yesterday_utc = now_utc - timedelta(days=1)

    # 1. Enquiry created yesterday (UTC)
    old_enq = Enquiry(
        reference_number="EB-202611-OLD1",
        idempotency_key="idem-old",
        request_payload_hash="hash-old",
        full_name="Past Customer",
        company_name="Yesterday Corp",
        business_email="old@example.com",
        contact_number="+60123456789",
        country="Malaysia",
        initial_division_id="petroleum-products",
        current_division_id="petroleum-products",
        product_focus="Crude Oil",
        status="NEW",
        created_at=yesterday_utc,
    )
    # 2. Enquiry created today (UTC)
    today_enq = Enquiry(
        reference_number="EB-202611-NEW1",
        idempotency_key="idem-today",
        request_payload_hash="hash-today",
        full_name="Today Customer",
        company_name="Today Corp",
        business_email="today@example.com",
        contact_number="+60123456789",
        country="Malaysia",
        initial_division_id="petroleum-products",
        current_division_id="petroleum-products",
        product_focus="Diesel Fuel",
        status="NEW",
        created_at=now_utc,
    )
    db_session.add(old_enq)
    db_session.add(today_enq)
    await db_session.commit()

    res = await async_client.get(
        "/api/v1/admin/dashboard/overview",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()["data"]

    assert data["total_enquiries"] == 2
    # Only the today_enq is counted in today_count
    assert data["today_count"] == 1


# ==============================================================================
# 2. Operational Activity Feed Tests (Reusing AuditLog)
# ==============================================================================


@pytest.mark.anyio
async def test_04_dashboard_activity_audit_reuse(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies that GET /dashboard/activity reuses audit_logs records without leaking PII or notes."""
    admin1 = await create_test_admin(
        db_session, "actor1@edenbounty.org", first_name="Ahmad", last_name="Razak"
    )
    admin2 = await create_test_admin(
        db_session, "target2@edenbounty.org", first_name="Sarah", last_name="Jenkins"
    )
    cookie, _, _ = await login_test_admin(async_client, "actor1@edenbounty.org")

    # Create enquiry
    enquiry = Enquiry(
        reference_number="EB-202611-ACT1",
        idempotency_key="idem-act-1",
        request_payload_hash="hash-act-1",
        full_name="CONFIDENTIAL CLIENT NAME",
        company_name="CONFIDENTIAL COMPANY",
        business_email="secret@confidential.com",
        contact_number="+60199998888",
        country="Singapore",
        initial_division_id="agricultural-drones",
        current_division_id="agricultural-drones",
        product_focus="Agritech Drone Fleet",
        status="NEW",
    )
    db_session.add(enquiry)
    await db_session.flush()

    # 1. Record an ENQUIRY_ASSIGNED audit event
    await record_audit_log(
        session=db_session,
        actor_admin=admin1,
        action="ENQUIRY_ASSIGNED",
        entity_table="enquiries",
        entity_id=enquiry.id,
        old_state={"assigned_admin_id": None},
        new_state={"assigned_admin_id": str(admin2.id)},
    )

    # 2. Record a STATUS_CHANGED audit event
    await record_audit_log(
        session=db_session,
        actor_admin=admin1,
        action="STATUS_CHANGED",
        entity_table="enquiries",
        entity_id=enquiry.id,
        old_state={"status": "NEW"},
        new_state={"status": "UNDER_REVIEW", "change_reason": "Technical specification review initiated."},
    )

    # 3. Record a NOTE_ADDED audit event (MUST BE FILTERED OUT)
    note = EnquiryNote(
        enquiry_id=enquiry.id,
        admin_user_id=admin1.id,
        note_text="CONFIDENTIAL INTERNAL TRADE DESK NOTE: Awaiting supplier price.",
    )
    db_session.add(note)
    await db_session.flush()
    await record_audit_log(
        session=db_session,
        actor_admin=admin1,
        action="NOTE_ADDED",
        entity_table="enquiry_notes",
        entity_id=note.id,
        old_state=None,
        new_state={"note_id": str(note.id)},
    )
    await db_session.commit()

    # Query activity feed
    res = await async_client.get(
        "/api/v1/admin/dashboard/activity",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res.status_code == status.HTTP_200_OK
    items = res.json()["data"]

    # Exactly 2 operational events returned (NOTE_ADDED is excluded)
    assert len(items) == 2

    # Check deterministic ordering: latest first
    assert items[0]["event_type"] == "STATUS_CHANGED"
    assert "Status updated from NEW to UNDER_REVIEW" in items[0]["description"]
    assert items[0]["reference_number"] == "EB-202611-ACT1"
    assert items[0]["division_name"] == "Drone"
    assert items[0]["actor_name"] == "Ahmad Razak"

    assert items[1]["event_type"] == "ENQUIRY_ASSIGNED"
    assert "Enquiry assigned to Sarah Jenkins" in items[1]["description"]
    assert items[1]["reference_number"] == "EB-202611-ACT1"

    # Data minimization verification: verify no client PII or note text in response
    raw_response_text = res.text
    assert "CONFIDENTIAL CLIENT NAME" not in raw_response_text
    assert "secret@confidential.com" not in raw_response_text
    assert "+60199998888" not in raw_response_text
    assert "CONFIDENTIAL INTERNAL TRADE DESK NOTE" not in raw_response_text


@pytest.mark.anyio
async def test_05_dashboard_activity_rbac(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies that both SUPER_ADMIN and OPERATIONS_ADMIN can access dashboard activity, but unauthenticated cannot."""
    await create_test_admin(db_session, "ops_rbac@edenbounty.org", role="OPERATIONS_ADMIN")
    await create_test_admin(db_session, "super_rbac@edenbounty.org", role="SUPER_ADMIN")

    # 1. Unauthenticated request -> 401
    res_unauth = await async_client.get(
        "/api/v1/admin/dashboard/activity",
        headers={"Origin": "http://localhost:3000"},
    )
    assert res_unauth.status_code == status.HTTP_401_UNAUTHORIZED

    # 2. OPERATIONS_ADMIN -> 200 OK
    cookie_ops, _, _ = await login_test_admin(async_client, "ops_rbac@edenbounty.org")
    res_ops = await async_client.get(
        "/api/v1/admin/dashboard/activity",
        cookies={settings.SESSION_COOKIE_NAME: cookie_ops},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res_ops.status_code == status.HTTP_200_OK

    # 3. SUPER_ADMIN -> 200 OK
    cookie_super, _, _ = await login_test_admin(async_client, "super_rbac@edenbounty.org")
    res_super = await async_client.get(
        "/api/v1/admin/dashboard/activity",
        cookies={settings.SESSION_COOKIE_NAME: cookie_super},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res_super.status_code == status.HTTP_200_OK


@pytest.mark.anyio
async def test_06_dashboard_activity_limit_parameter(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies that the limit query parameter is respected."""
    admin = await create_test_admin(db_session, "ops_limit@edenbounty.org")
    cookie, _, _ = await login_test_admin(async_client, "ops_limit@edenbounty.org")

    enq = Enquiry(
        reference_number="EB-202611-LIM1",
        idempotency_key="idem-lim-1",
        request_payload_hash="hash-lim-1",
        full_name="Lim Customer",
        company_name="Lim Corp",
        business_email="lim@example.com",
        contact_number="+60123456789",
        country="Malaysia",
        initial_division_id="scrap-trading",
        current_division_id="scrap-trading",
        product_focus="Metal Scrap",
        status="NEW",
    )
    db_session.add(enq)
    await db_session.flush()

    for i in range(5):
        await record_audit_log(
            session=db_session,
            actor_admin=admin,
            action="STATUS_CHANGED",
            entity_table="enquiries",
            entity_id=enq.id,
            old_state={"status": "NEW"},
            new_state={"status": "UNDER_REVIEW"},
        )
    await db_session.commit()

    # Query with limit=2
    res = await async_client.get(
        "/api/v1/admin/dashboard/activity?limit=2",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res.status_code == status.HTTP_200_OK
    items = res.json()["data"]
    assert len(items) == 2


@pytest.mark.anyio
async def test_07_dashboard_query_performance_measurement(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Measures actual execution latency for overview and activity endpoints (target < 50ms)."""
    await create_test_admin(db_session, "ops_perf@edenbounty.org")
    cookie, _, _ = await login_test_admin(async_client, "ops_perf@edenbounty.org")

    # Measure GET /dashboard/overview latency
    t0 = time.perf_counter()
    res_overview = await async_client.get(
        "/api/v1/admin/dashboard/overview",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    t1 = time.perf_counter()
    overview_ms = (t1 - t0) * 1000
    assert res_overview.status_code == status.HTTP_200_OK

    # Measure GET /dashboard/activity latency
    t2 = time.perf_counter()
    res_activity = await async_client.get(
        "/api/v1/admin/dashboard/activity",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    t3 = time.perf_counter()
    activity_ms = (t3 - t2) * 1000
    assert res_activity.status_code == status.HTTP_200_OK

    # Measure GET /rfqs?limit=5 latency
    t4 = time.perf_counter()
    res_recent = await async_client.get(
        "/api/v1/admin/rfqs?limit=5&sort_by=created_at&sort_order=desc",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    t5 = time.perf_counter()
    recent_ms = (t5 - t4) * 1000
    assert res_recent.status_code == status.HTTP_200_OK

    print(f"\n[PERFORMANCE] GET /dashboard/overview latency: {overview_ms:.2f} ms")
    print(f"[PERFORMANCE] GET /dashboard/activity latency: {activity_ms:.2f} ms")
    print(f"[PERFORMANCE] GET /rfqs?limit=5 latency: {recent_ms:.2f} ms")

    # Assert reasonable execution latency under test harness (< 150ms in docker test setup)
    assert overview_ms < 150.0
    assert activity_ms < 150.0
    assert recent_ms < 150.0
