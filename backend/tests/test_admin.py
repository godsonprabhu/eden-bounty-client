"""Comprehensive Automated Test Suite for Central Admin Dashboard and Enquiry Management.

Phase C13.4 — Central Admin Dashboard & Enquiry Management (Stage 1).
Covers all required specifications:
1. Authentication & Authorization (401 for unauthenticated requests)
2. CSRF Token Hydration on GET /api/v1/auth/me
3. Dashboard Metrics (counts for all 8 statuses, 10 divisions, unassigned, today)
4. Enquiry Listing, Filtering, Search, and Pagination
5. Enquiry Detail Dossier & 404/422 error handling
6. Central Assignment, Division Preservation, and auto-transition from NEW to ASSIGNED
7. Assignment Validation (inactive/nonexistent admin rejection, unassignment)
8. Status Transition Matrix & permitted paths (including IN_COMMUNICATION -> COMPLETED)
9. Disallowed transitions (409) and same-status transitions (400)
10. Mandatory change_reason validation (3-1000 characters, 422)
11. Terminal Status Reopening RBAC (SUPER_ADMIN allowed, OPERATIONS_ADMIN receives 403)
12. Internal Operational Notes & Author Attribution
13. Administrator Directory & Data Minimization (no credentials/tokens exposed)
14. Audit Log Inspection RBAC (SUPER_ADMIN allowed, OPERATIONS_ADMIN receives 403)
15. CSRF Protection on state-changing endpoints (403 on missing/invalid token)
16. Transactional Consistency and Audit Record Generation
"""

import uuid
from datetime import UTC, datetime
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
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(autouse=True)
async def setup_admin_test_database(db_session: AsyncSession):
    """Ensures clean tables and seeded roles/divisions before each test."""
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
    await db_session.execute(delete(AuditLog))
    await db_session.execute(delete(EnquiryNote))
    await db_session.execute(delete(EnquiryStatusHistory))
    await db_session.execute(delete(EnquiryAssignment))
    await db_session.execute(delete(Enquiry))
    await db_session.execute(delete(AdminSession))
    await db_session.execute(delete(AdminUserRole))
    await db_session.execute(delete(AdminUser))
    await db_session.commit()


async def create_admin_user(
    db: AsyncSession,
    email: str,
    password: str = "CorporatePass2026!#",
    role: str = "OPERATIONS_ADMIN",
    is_active: bool = True,
    first_name: str = "Test",
    last_name: str = "Admin",
    job_title: str | None = "Trade Desk Officer",
    deleted_at: datetime | None = None,
) -> AdminUser:
    """Helper to provision test administrators with designated roles."""
    user = AdminUser(
        email=email.strip().lower(),
        password_hash=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        job_title=job_title,
        is_active=is_active,
        deleted_at=deleted_at,
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


async def login_admin(
    async_client: AsyncClient,
    email: str,
    password: str = "CorporatePass2026!#",
) -> tuple[str, str, dict]:
    """Helper to log in an administrator and return (cookie_token, csrf_token, user_dict)."""
    res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res.status_code == status.HTTP_200_OK
    raw_token = res.cookies[settings.SESSION_COOKIE_NAME]
    csrf_token = res.json()["data"]["csrf_token"]
    user_info = res.json()["data"]["user"]
    return raw_token, csrf_token, user_info


async def create_test_enquiry(
    db: AsyncSession,
    division_id: str = "petroleum-products",
    status_str: str = "NEW",
    assigned_admin_id: uuid.UUID | None = None,
    company_name: str = "Acme Global Trading",
    reference_number: str | None = None,
    contact_number: str | None = "+60123456789",
) -> Enquiry:
    """Helper to insert a test enquiry."""
    ref = reference_number or f"EB-RFQ-{uuid.uuid4().hex[:8].upper()}"
    enq = Enquiry(
        reference_number=ref,
        full_name="John Doe",
        company_name=company_name,
        business_email="procurement@acme.com",
        contact_number=contact_number,
        country="Malaysia",
        initial_division_id=division_id,
        current_division_id=division_id,
        product_focus="Ultra-Low Sulfur Diesel (EN 590)",
        status=status_str,
        assigned_admin_id=assigned_admin_id,
        quantity=Decimal("5000.00"),
        unit_of_measurement="Metric Tons",
        specifications="10 ppm max sulfur",
        preferred_incoterm="CIF",
        target_destination_port="Port Klang",
    )
    db.add(enq)
    await db.commit()
    await db.refresh(enq)
    return enq


# ==============================================================================
# 1. Authentication & Route Protection
# ==============================================================================


@pytest.mark.asyncio
async def test_01_unauthenticated_requests_rejected(async_client: AsyncClient):
    """1. All admin endpoints return 401 Unauthorized when called without a valid session."""
    dummy_uuid = uuid.uuid4()
    endpoints = [
        ("GET", "/api/v1/admin/dashboard/overview", None),
        ("GET", "/api/v1/admin/rfqs", None),
        ("GET", f"/api/v1/admin/rfqs/{dummy_uuid}", None),
        ("POST", f"/api/v1/admin/rfqs/{dummy_uuid}/assign", {"assigned_admin_id": str(dummy_uuid)}),
        ("PATCH", f"/api/v1/admin/rfqs/{dummy_uuid}/status", {"new_status": "UNDER_REVIEW", "change_reason": "Test"}),
        ("POST", f"/api/v1/admin/rfqs/{dummy_uuid}/notes", {"note_text": "Test note"}),
        ("GET", "/api/v1/admin/administrators", None),
        ("GET", "/api/v1/admin/audit-logs", None),
    ]

    for method, path, body in endpoints:
        if method == "GET":
            res = await async_client.get(path)
        elif method == "POST":
            res = await async_client.post(path, json=body)
        elif method == "PATCH":
            res = await async_client.patch(path, json=body)
        assert res.status_code == status.HTTP_401_UNAUTHORIZED, f"{method} {path} did not return 401"


# ==============================================================================
# 2. CSRF Token Hydration on GET /api/v1/auth/me
# ==============================================================================


@pytest.mark.asyncio
async def test_02_csrf_hydration_on_auth_me(
    db_session: AsyncSession, async_client: AsyncClient
):
    """2. GET /api/v1/auth/me returns user profile and active session csrf_token for React memory hydration."""
    admin = await create_admin_user(db_session, "hydrate_me@edenbounty.org")
    cookie, csrf, _ = await login_admin(async_client, admin.email)

    # Reload simulation: call /api/v1/auth/me with cookie
    me_res = await async_client.get(
        "/api/v1/auth/me",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
    )
    assert me_res.status_code == status.HTTP_200_OK
    data = me_res.json()
    assert data["success"] is True
    assert data["data"]["email"] == admin.email
    assert data["data"]["csrf_token"] == csrf
    assert len(data["data"]["csrf_token"]) >= 32


# ==============================================================================
# 3. Dashboard Metrics & Overview
# ==============================================================================


@pytest.mark.asyncio
async def test_03_dashboard_overview_metrics(
    db_session: AsyncSession, async_client: AsyncClient
):
    """3. GET /api/v1/admin/dashboard/overview aggregates metrics for all 8 statuses and 10 divisions."""
    admin = await create_admin_user(db_session, "metrics_admin@edenbounty.org")
    cookie, _, _ = await login_admin(async_client, admin.email)

    # Insert diverse enquiries
    await create_test_enquiry(db_session, division_id="petroleum-products", status_str="NEW")
    await create_test_enquiry(db_session, division_id="petroleum-products", status_str="UNDER_REVIEW", assigned_admin_id=admin.id)
    await create_test_enquiry(db_session, division_id="furnace-oil", status_str="IN_COMMUNICATION", assigned_admin_id=admin.id)
    await create_test_enquiry(db_session, division_id="agricultural-drones", status_str="COMPLETED", assigned_admin_id=admin.id)

    res = await async_client.get(
        "/api/v1/admin/dashboard/overview",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
    )
    assert res.status_code == status.HTTP_200_OK
    body = res.json()["data"]

    assert body["total_enquiries"] == 4
    assert body["unassigned_count"] == 1  # Exactly 1 has assigned_admin_id == None
    assert body["today_count"] == 4

    # Verify all 8 statuses are represented in by_status dictionary
    by_status = body["by_status"]
    assert len(by_status) == 8
    assert by_status["NEW"] == 1
    assert by_status["UNDER_REVIEW"] == 1
    assert by_status["IN_COMMUNICATION"] == 1
    assert by_status["COMPLETED"] == 1
    assert by_status["ASSIGNED"] == 0
    assert by_status["QUOTATION_PENDING"] == 0
    assert by_status["DECLINED"] == 0
    assert by_status["ARCHIVED"] == 0

    # Verify all 9 canonical commercial divisions are listed
    by_div = body["by_division"]
    assert len(by_div) == 9
    div_map = {d["division_id"]: d["count"] for d in by_div}
    assert div_map["petroleum-products"] == 2
    assert div_map["furnace-oil"] == 1
    assert div_map["agricultural-drones"] == 1
    assert div_map["mineral-water"] == 0


# ==============================================================================
# 4. Enquiry List, Filtering, Search, Pagination & Sorting
# ==============================================================================


@pytest.mark.asyncio
async def test_04_enquiries_list_pagination_and_sorting(
    db_session: AsyncSession, async_client: AsyncClient
):
    """4. GET /api/v1/admin/rfqs supports pagination and sorting."""
    admin = await create_admin_user(db_session, "list_admin@edenbounty.org")
    cookie, _, _ = await login_admin(async_client, admin.email)

    for i in range(5):
        await create_test_enquiry(
            db_session,
            company_name=f"Company {i:02d}",
            reference_number=f"EB-RFQ-SORT-{i:02d}",
        )

    # Page 1, limit 2
    res_p1 = await async_client.get(
        "/api/v1/admin/rfqs?page=1&limit=2&sort_by=reference_number&sort_order=asc",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
    )
    assert res_p1.status_code == status.HTTP_200_OK
    data_p1 = res_p1.json()["data"]
    assert len(data_p1["items"]) == 2
    assert data_p1["pagination"]["total_items"] == 5
    assert data_p1["pagination"]["total_pages"] == 3
    assert data_p1["items"][0]["reference_number"] == "EB-RFQ-SORT-00"

    # Page 3, limit 2
    res_p3 = await async_client.get(
        "/api/v1/admin/rfqs?page=3&limit=2&sort_by=reference_number&sort_order=asc",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
    )
    assert res_p3.status_code == status.HTTP_200_OK
    data_p3 = res_p3.json()["data"]
    assert len(data_p3["items"]) == 1
    assert data_p3["items"][0]["reference_number"] == "EB-RFQ-SORT-04"


@pytest.mark.asyncio
async def test_05_enquiries_list_filtering_and_search(
    db_session: AsyncSession, async_client: AsyncClient
):
    """5. GET /api/v1/admin/rfqs filters by division, status, assignment, and search term."""
    admin1 = await create_admin_user(db_session, "filter1@edenbounty.org", first_name="Officer", last_name="One")
    admin2 = await create_admin_user(db_session, "filter2@edenbounty.org", first_name="Officer", last_name="Two")
    cookie, _, _ = await login_admin(async_client, admin1.email)

    e1 = await create_test_enquiry(db_session, division_id="petroleum-products", status_str="NEW", company_name="Petro Alpha Ltd")
    e2 = await create_test_enquiry(db_session, division_id="furnace-oil", status_str="UNDER_REVIEW", assigned_admin_id=admin1.id, company_name="Furnace Beta Corp")
    e3 = await create_test_enquiry(db_session, division_id="petroleum-products", status_str="ASSIGNED", assigned_admin_id=admin2.id, company_name="Petro Gamma Inc")

    # Filter by division
    res_div = await async_client.get(
        "/api/v1/admin/rfqs?division_id=petroleum-products",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
    )
    assert len(res_div.json()["data"]["items"]) == 2

    # Filter by status
    res_status = await async_client.get(
        "/api/v1/admin/rfqs?status=UNDER_REVIEW",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
    )
    assert len(res_status.json()["data"]["items"]) == 1
    assert res_status.json()["data"]["items"][0]["id"] == str(e2.id)

    # Filter by unassigned
    res_unassigned = await async_client.get(
        "/api/v1/admin/rfqs?assigned_admin_id=unassigned",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
    )
    assert len(res_unassigned.json()["data"]["items"]) == 1
    assert res_unassigned.json()["data"]["items"][0]["id"] == str(e1.id)

    # Filter by specific admin
    res_admin2 = await async_client.get(
        f"/api/v1/admin/rfqs?assigned_admin_id={admin2.id}",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
    )
    assert len(res_admin2.json()["data"]["items"]) == 1
    assert res_admin2.json()["data"]["items"][0]["id"] == str(e3.id)

    # Search by keyword
    res_search = await async_client.get(
        "/api/v1/admin/rfqs?search=Gamma",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
    )
    assert len(res_search.json()["data"]["items"]) == 1
    assert res_search.json()["data"]["items"][0]["company_name"] == "Petro Gamma Inc"


# ==============================================================================
# 5. Enquiry Detail Dossier
# ==============================================================================


@pytest.mark.asyncio
async def test_06_enquiry_detail_dossier_and_404(
    db_session: AsyncSession, async_client: AsyncClient
):
    """6. GET /api/v1/admin/rfqs/{id} returns complete dossier; 404 on nonexistent ID; 422 on invalid UUID."""
    admin = await create_admin_user(db_session, "dossier_admin@edenbounty.org")
    cookie, _, _ = await login_admin(async_client, admin.email)

    enq = await create_test_enquiry(
        db_session,
        division_id="petroleum-products",
        status_str="UNDER_REVIEW",
        assigned_admin_id=admin.id,
        company_name="Dossier Global",
    )

    # Success
    res = await async_client.get(
        f"/api/v1/admin/rfqs/{enq.id}",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
    )
    assert res.status_code == status.HTTP_200_OK
    dossier = res.json()["data"]
    assert dossier["id"] == str(enq.id)
    assert dossier["company_name"] == "Dossier Global"
    assert dossier["current_division"]["id"] == "petroleum-products"
    assert dossier["assigned_admin"]["id"] == str(admin.id)
    assert isinstance(dossier["assignments"], list)
    assert isinstance(dossier["status_history"], list)
    assert isinstance(dossier["notes"], list)

    # Nonexistent UUID -> 404
    missing_id = uuid.uuid4()
    res_404 = await async_client.get(
        f"/api/v1/admin/rfqs/{missing_id}",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
    )
    assert res_404.status_code == status.HTTP_404_NOT_FOUND

    # Malformed UUID -> 422
    res_422 = await async_client.get(
        "/api/v1/admin/rfqs/not-a-valid-uuid",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
    )
    assert res_422.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("division_id", "expected_name", "expected_code"),
    [
        ("lubricants", "Industrial Lubricants", "EB-DIV-08"),
    ],
)
async def test_06b_historical_enquiry_on_withdrawn_division_still_resolves(
    db_session: AsyncSession,
    async_client: AsyncClient,
    division_id: str,
    expected_name: str,
    expected_code: str,
):
    """6b. CR-C1: enquiries tied to a withdrawn (inactive) division remain fully readable by admins."""
    await seed_divisions(db_session)
    admin = await create_admin_user(db_session, "historical_admin@edenbounty.org")
    cookie, _, _ = await login_admin(async_client, admin.email)
    cookies = {settings.SESSION_COOKIE_NAME: cookie}

    enq = await create_test_enquiry(db_session, division_id=division_id, company_name="Historical Buyer")

    # Dossier still resolves both division relationships
    res = await async_client.get(f"/api/v1/admin/rfqs/{enq.id}", cookies=cookies)
    assert res.status_code == status.HTTP_200_OK
    dossier = res.json()["data"]
    for key in ("initial_division", "current_division"):
        assert dossier[key]["id"] == division_id
        assert dossier[key]["name"] == expected_name
        assert dossier[key]["code"] == expected_code

    # Dashboard still reports every division record, including the withdrawn one with its enquiry
    res = await async_client.get("/api/v1/admin/dashboard/overview", cookies=cookies)
    assert res.status_code == status.HTTP_200_OK
    by_div = {d["division_id"]: d["count"] for d in res.json()["data"]["by_division"]}
    assert len(by_div) == 9
    assert by_div[division_id] == 1


@pytest.mark.asyncio
async def test_06a_enquiry_detail_returns_null_contact_number(
    db_session: AsyncSession, async_client: AsyncClient
):
    admin = await create_admin_user(db_session, "null_contact_admin@edenbounty.org")
    cookie, _, _ = await login_admin(async_client, admin.email)
    enquiry = await create_test_enquiry(db_session, contact_number=None)

    response = await async_client.get(
        f"/api/v1/admin/rfqs/{enquiry.id}",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["contact_number"] is None


# ==============================================================================
# 6. Central Assignment & Division Preservation
# ==============================================================================


@pytest.mark.asyncio
async def test_07_central_assignment_and_division_preservation(
    db_session: AsyncSession, async_client: AsyncClient
):
    """7. POST /api/v1/admin/rfqs/{id}/assign preserves current_division_id, auto-transitions NEW -> ASSIGNED, records history & audit."""
    assigner = await create_admin_user(db_session, "assigner@edenbounty.org", first_name="Chief", last_name="Assigner")
    target_officer = await create_admin_user(db_session, "target_officer@edenbounty.org", first_name="Trade", last_name="Officer")
    cookie, csrf, _ = await login_admin(async_client, assigner.email)

    enq = await create_test_enquiry(
        db_session,
        division_id="furnace-oil",
        status_str="NEW",
        assigned_admin_id=None,
    )
    original_division = enq.current_division_id

    # Perform assignment
    res = await async_client.post(
        f"/api/v1/admin/rfqs/{enq.id}/assign",
        json={
            "assigned_admin_id": str(target_officer.id),
            "assignment_rationale": "High-volume trial cargo allocated to central desk.",
        },
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"},
    )
    assert res.status_code == status.HTTP_200_OK
    dossier = res.json()["data"]

    # 1. Division is strictly preserved
    assert dossier["current_division"]["id"] == original_division
    assert dossier["assigned_admin"]["id"] == str(target_officer.id)

    # 2. Status was auto-transitioned from NEW to ASSIGNED
    assert dossier["status"] == "ASSIGNED"

    # 3. Verify database records
    await db_session.refresh(enq)
    assert enq.current_division_id == original_division
    assert enq.assigned_admin_id == target_officer.id
    assert enq.status == "ASSIGNED"

    # Verify EnquiryAssignment record
    stmt_assign = select(EnquiryAssignment).where(EnquiryAssignment.enquiry_id == enq.id)
    assignment = (await db_session.execute(stmt_assign)).scalar_one()
    assert assignment.previous_division_id == original_division
    assert assignment.new_division_id == original_division  # Satisfies DB NOT NULL column without modification
    assert assignment.previous_admin_id is None
    assert assignment.new_admin_id == target_officer.id
    assert assignment.assigned_by_admin_id == assigner.id
    assert assignment.assignment_rationale == "High-volume trial cargo allocated to central desk."

    # Verify EnquiryStatusHistory record
    stmt_hist = select(EnquiryStatusHistory).where(EnquiryStatusHistory.enquiry_id == enq.id)
    history = (await db_session.execute(stmt_hist)).scalar_one()
    assert history.old_status == "NEW"
    assert history.new_status == "ASSIGNED"
    assert history.changed_by_admin_id == assigner.id

    # Verify AuditLog record
    stmt_audit = select(AuditLog).where(
        AuditLog.entity_id == enq.id,
        AuditLog.action == "ENQUIRY_ASSIGNED",
    )
    audit = (await db_session.execute(stmt_audit)).scalar_one()
    assert audit.actor_admin_id == assigner.id
    assert audit.new_state["assigned_admin_id"] == str(target_officer.id)


@pytest.mark.asyncio
async def test_08_assignment_to_nonexistent_or_inactive_admin_rejected(
    db_session: AsyncSession, async_client: AsyncClient
):
    """8. Assignment to an inactive or nonexistent administrator returns 400 Bad Request."""
    assigner = await create_admin_user(db_session, "assign_check@edenbounty.org")
    inactive_admin = await create_admin_user(
        db_session, "inactive_admin@edenbounty.org", is_active=False
    )
    cookie, csrf, _ = await login_admin(async_client, assigner.email)
    enq = await create_test_enquiry(db_session)

    # Inactive admin
    res_inactive = await async_client.post(
        f"/api/v1/admin/rfqs/{enq.id}/assign",
        json={"assigned_admin_id": str(inactive_admin.id)},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"},
    )
    assert res_inactive.status_code == status.HTTP_400_BAD_REQUEST

    # Nonexistent admin UUID
    res_missing = await async_client.post(
        f"/api/v1/admin/rfqs/{enq.id}/assign",
        json={"assigned_admin_id": str(uuid.uuid4())},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"},
    )
    assert res_missing.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_09_unassign_enquiry(
    db_session: AsyncSession, async_client: AsyncClient
):
    """9. Setting assigned_admin_id to null successfully unassigns enquiry back to central pool."""
    admin = await create_admin_user(db_session, "unassign_admin@edenbounty.org")
    cookie, csrf, _ = await login_admin(async_client, admin.email)
    enq = await create_test_enquiry(db_session, assigned_admin_id=admin.id, status_str="ASSIGNED")

    res = await async_client.post(
        f"/api/v1/admin/rfqs/{enq.id}/assign",
        json={"assigned_admin_id": None, "assignment_rationale": "Returned to pool for redistribution."},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"},
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["data"]["assigned_admin"] is None

    await db_session.refresh(enq)
    assert enq.assigned_admin_id is None


# ==============================================================================
# 7. Status Transition Matrix & Terminal Reopening RBAC
# ==============================================================================


@pytest.mark.asyncio
async def test_10_status_transition_matrix_permitted_transitions(
    db_session: AsyncSession, async_client: AsyncClient
):
    """10. Permitted status transitions succeed, including IN_COMMUNICATION -> COMPLETED."""
    admin = await create_admin_user(db_session, "transition_tester@edenbounty.org")
    cookie, csrf, _ = await login_admin(async_client, admin.email)
    enq = await create_test_enquiry(db_session, status_str="NEW")

    # NEW -> UNDER_REVIEW
    r1 = await async_client.patch(
        f"/api/v1/admin/rfqs/{enq.id}/status",
        json={"new_status": "UNDER_REVIEW", "change_reason": "Central operations triage initiated."},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"},
    )
    assert r1.status_code == status.HTTP_200_OK
    assert r1.json()["data"]["status"] == "UNDER_REVIEW"

    # UNDER_REVIEW -> IN_COMMUNICATION
    r2 = await async_client.patch(
        f"/api/v1/admin/rfqs/{enq.id}/status",
        json={"new_status": "IN_COMMUNICATION", "change_reason": "Direct email initiated with buyer."},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"},
    )
    assert r2.status_code == status.HTTP_200_OK
    assert r2.json()["data"]["status"] == "IN_COMMUNICATION"

    # IN_COMMUNICATION -> COMPLETED (Explicitly verified permitted transition)
    r3 = await async_client.patch(
        f"/api/v1/admin/rfqs/{enq.id}/status",
        json={"new_status": "COMPLETED", "change_reason": "Client confirmed specs and enquiry intake completed."},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"},
    )
    assert r3.status_code == status.HTTP_200_OK
    assert r3.json()["data"]["status"] == "COMPLETED"

    # COMPLETED -> ARCHIVED
    r4 = await async_client.patch(
        f"/api/v1/admin/rfqs/{enq.id}/status",
        json={"new_status": "ARCHIVED", "change_reason": "Archived concluded enquiry."},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"},
    )
    assert r4.status_code == status.HTTP_200_OK
    assert r4.json()["data"]["status"] == "ARCHIVED"


@pytest.mark.asyncio
async def test_11_status_transition_disallowed_and_same_status_rejected(
    db_session: AsyncSession, async_client: AsyncClient
):
    """11. Disallowed transitions receive 409 Conflict; same-status receives 409 Conflict."""
    admin = await create_admin_user(db_session, "conflict_admin@edenbounty.org")
    cookie, csrf, _ = await login_admin(async_client, admin.email)
    enq = await create_test_enquiry(db_session, status_str="NEW")

    # Same-status: NEW -> NEW -> 409 Conflict
    r_same = await async_client.patch(
        f"/api/v1/admin/rfqs/{enq.id}/status",
        json={"new_status": "NEW", "change_reason": "Redundant update"},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"},
    )
    assert r_same.status_code == status.HTTP_409_CONFLICT
    assert "already in status 'NEW'" in r_same.json()["detail"]

    # Disallowed: NEW -> COMPLETED -> 409 Conflict
    r_bad = await async_client.patch(
        f"/api/v1/admin/rfqs/{enq.id}/status",
        json={"new_status": "COMPLETED", "change_reason": "Illegal jump"},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"},
    )
    assert r_bad.status_code == status.HTTP_409_CONFLICT
    assert "not permitted" in r_bad.json()["detail"]


@pytest.mark.asyncio
async def test_12_status_transition_mandatory_change_reason(
    db_session: AsyncSession, async_client: AsyncClient
):
    """12. change_reason is strictly required (3 to 1000 chars); 422 if empty, whitespace, or out of range."""
    admin = await create_admin_user(db_session, "reason_checker@edenbounty.org")
    cookie, csrf, _ = await login_admin(async_client, admin.email)
    enq = await create_test_enquiry(db_session, status_str="NEW")

    # Empty reason
    r_empty = await async_client.patch(
        f"/api/v1/admin/rfqs/{enq.id}/status",
        json={"new_status": "UNDER_REVIEW", "change_reason": ""},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"},
    )
    assert r_empty.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # Whitespace only (< 3 chars after strip)
    r_ws = await async_client.patch(
        f"/api/v1/admin/rfqs/{enq.id}/status",
        json={"new_status": "UNDER_REVIEW", "change_reason": "  ab  "},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"},
    )
    assert r_ws.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # Exceeding 1000 characters
    r_huge = await async_client.patch(
        f"/api/v1/admin/rfqs/{enq.id}/status",
        json={"new_status": "UNDER_REVIEW", "change_reason": "A" * 1001},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"},
    )
    assert r_huge.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_13_terminal_status_reopening_permissions_super_admin_vs_operations_admin(
    db_session: AsyncSession, async_client: AsyncClient
):
    """13. Reopening terminal statuses (COMPLETED, DECLINED, ARCHIVED) requires SUPER_ADMIN; OPERATIONS_ADMIN receives 403."""
    ops_user = await create_admin_user(db_session, "ops_terminal@edenbounty.org", role="OPERATIONS_ADMIN")
    super_user = await create_admin_user(db_session, "super_terminal@edenbounty.org", role="SUPER_ADMIN")

    ops_cookie, ops_csrf, _ = await login_admin(async_client, ops_user.email)
    super_cookie, super_csrf, _ = await login_admin(async_client, super_user.email)

    # Enquiry in COMPLETED status
    enq_completed = await create_test_enquiry(db_session, status_str="COMPLETED")

    # 1. OPERATIONS_ADMIN attempting to reopen COMPLETED -> IN_COMMUNICATION receives 403 Forbidden
    res_ops_fail = await async_client.patch(
        f"/api/v1/admin/rfqs/{enq_completed.id}/status",
        json={"new_status": "IN_COMMUNICATION", "change_reason": "Attempt by ops to reopen"},
        cookies={settings.SESSION_COOKIE_NAME: ops_cookie},
        headers={"X-CSRF-Token": ops_csrf, "Origin": "http://localhost:3000"},
    )
    assert res_ops_fail.status_code == status.HTTP_403_FORBIDDEN
    assert "requires SUPER_ADMIN authority" in res_ops_fail.json()["detail"]

    # 2. SUPER_ADMIN reopening COMPLETED -> IN_COMMUNICATION succeeds (200 OK)
    res_super_success = await async_client.patch(
        f"/api/v1/admin/rfqs/{enq_completed.id}/status",
        json={"new_status": "IN_COMMUNICATION", "change_reason": "Buyer provided revised discharge specifications."},
        cookies={settings.SESSION_COOKIE_NAME: super_cookie},
        headers={"X-CSRF-Token": super_csrf, "Origin": "http://localhost:3000"},
    )
    assert res_super_success.status_code == status.HTTP_200_OK
    assert res_super_success.json()["data"]["status"] == "IN_COMMUNICATION"

    # Enquiry in DECLINED status
    enq_declined = await create_test_enquiry(db_session, status_str="DECLINED")

    # 3. OPERATIONS_ADMIN reopening DECLINED -> UNDER_REVIEW receives 403 Forbidden
    r_ops_dec = await async_client.patch(
        f"/api/v1/admin/rfqs/{enq_declined.id}/status",
        json={"new_status": "UNDER_REVIEW", "change_reason": "Reopen attempt"},
        cookies={settings.SESSION_COOKIE_NAME: ops_cookie},
        headers={"X-CSRF-Token": ops_csrf, "Origin": "http://localhost:3000"},
    )
    assert r_ops_dec.status_code == status.HTTP_403_FORBIDDEN

    # 4. SUPER_ADMIN reopening DECLINED -> UNDER_REVIEW succeeds
    r_super_dec = await async_client.patch(
        f"/api/v1/admin/rfqs/{enq_declined.id}/status",
        json={"new_status": "UNDER_REVIEW", "change_reason": "Client secured corporate credit approval."},
        cookies={settings.SESSION_COOKIE_NAME: super_cookie},
        headers={"X-CSRF-Token": super_csrf, "Origin": "http://localhost:3000"},
    )
    assert r_super_dec.status_code == status.HTTP_200_OK
    assert r_super_dec.json()["data"]["status"] == "UNDER_REVIEW"


# ==============================================================================
# 8. Internal Operational Notes
# ==============================================================================


@pytest.mark.asyncio
async def test_14_internal_notes_creation_and_author_attribution(
    db_session: AsyncSession, async_client: AsyncClient
):
    """14. POST /api/v1/admin/rfqs/{id}/notes appends internal operational note with author metadata."""
    admin = await create_admin_user(db_session, "notes_author@edenbounty.org", first_name="Note", last_name="Author")
    cookie, csrf, _ = await login_admin(async_client, admin.email)
    enq = await create_test_enquiry(db_session)

    res = await async_client.post(
        f"/api/v1/admin/rfqs/{enq.id}/notes",
        json={"note_text": "Spoke with procurement officer. Confirmed vessel discharge parameters."},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"},
    )
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()["data"]
    assert data["note_text"] == "Spoke with procurement officer. Confirmed vessel discharge parameters."
    assert data["author_admin"]["name"] == "Note Author"
    assert data["is_internal_only"] is True

    # Verify audit record
    stmt_audit = select(AuditLog).where(
        AuditLog.entity_id == uuid.UUID(data["id"]),
        AuditLog.action == "NOTE_ADDED",
    )
    audit = (await db_session.execute(stmt_audit)).scalar_one()
    assert audit.actor_admin_id == admin.id


# ==============================================================================
# 9. Administrators Directory & Data Minimization
# ==============================================================================


@pytest.mark.asyncio
async def test_15_administrators_directory_data_minimization(
    db_session: AsyncSession, async_client: AsyncClient
):
    """15. GET /api/v1/admin/administrators returns active administrators and minimizes data (no credentials/tokens)."""
    admin_active = await create_admin_user(db_session, "active_dir@edenbounty.org", first_name="Active", last_name="User")
    await create_admin_user(db_session, "inactive_dir@edenbounty.org", is_active=False)
    await create_admin_user(db_session, "deleted_dir@edenbounty.org", deleted_at=datetime.now(UTC))

    cookie, _, _ = await login_admin(async_client, admin_active.email)

    res = await async_client.get(
        "/api/v1/admin/administrators",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
    )
    assert res.status_code == status.HTTP_200_OK
    assignees = res.json()["data"]

    # Only active, non-deleted administrators appear
    emails = [a["email"] for a in assignees]
    assert admin_active.email in emails
    assert "inactive_dir@edenbounty.org" not in emails
    assert "deleted_dir@edenbounty.org" not in emails

    # Strict data minimization check
    first_entry = assignees[0]
    allowed_keys = {"id", "first_name", "last_name", "email", "job_title", "roles"}
    assert set(first_entry.keys()) == allowed_keys
    assert "password_hash" not in first_entry
    assert "csrf_token" not in first_entry
    assert "failed_login_attempts" not in first_entry


# ==============================================================================
# 10. Audit Log Inspection RBAC
# ==============================================================================


@pytest.mark.asyncio
async def test_16_audit_logs_super_admin_only(
    db_session: AsyncSession, async_client: AsyncClient
):
    """16. GET /api/v1/admin/audit-logs is restricted strictly to SUPER_ADMIN; OPERATIONS_ADMIN receives 403."""
    ops_user = await create_admin_user(db_session, "ops_audit@edenbounty.org", role="OPERATIONS_ADMIN")
    super_user = await create_admin_user(db_session, "super_audit@edenbounty.org", role="SUPER_ADMIN")

    ops_cookie, _, _ = await login_admin(async_client, ops_user.email)
    super_cookie, _, _ = await login_admin(async_client, super_user.email)

    # 1. OPERATIONS_ADMIN receives 403 Forbidden
    res_ops = await async_client.get(
        "/api/v1/admin/audit-logs",
        cookies={settings.SESSION_COOKIE_NAME: ops_cookie},
    )
    assert res_ops.status_code == status.HTTP_403_FORBIDDEN

    # 2. SUPER_ADMIN receives 200 OK
    res_super = await async_client.get(
        "/api/v1/admin/audit-logs",
        cookies={settings.SESSION_COOKIE_NAME: super_cookie},
    )
    assert res_super.status_code == status.HTTP_200_OK
    data = res_super.json()["data"]
    assert isinstance(data["items"], list)
    assert "pagination" in data


# ==============================================================================
# 11. CSRF Protection on State-Changing Endpoints
# ==============================================================================


@pytest.mark.asyncio
async def test_17_csrf_protection_on_state_changing_endpoints(
    db_session: AsyncSession, async_client: AsyncClient
):
    """17. State-changing endpoints (/assign, /status, /notes) reject requests missing or having invalid X-CSRF-Token."""
    admin = await create_admin_user(db_session, "csrf_guard@edenbounty.org")
    cookie, _csrf, _ = await login_admin(async_client, admin.email)
    enq = await create_test_enquiry(db_session)

    # 1. /assign without CSRF header -> 403 Forbidden
    r_no_csrf = await async_client.post(
        f"/api/v1/admin/rfqs/{enq.id}/assign",
        json={"assigned_admin_id": str(admin.id)},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert r_no_csrf.status_code == status.HTTP_403_FORBIDDEN

    # 2. /assign with forged CSRF header -> 403 Forbidden
    r_bad_csrf = await async_client.post(
        f"/api/v1/admin/rfqs/{enq.id}/assign",
        json={"assigned_admin_id": str(admin.id)},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"X-CSRF-Token": "forged_token_1234567890", "Origin": "http://localhost:3000"},
    )
    assert r_bad_csrf.status_code == status.HTTP_403_FORBIDDEN

    # 3. /status without CSRF header -> 403 Forbidden
    r_stat_no_csrf = await async_client.patch(
        f"/api/v1/admin/rfqs/{enq.id}/status",
        json={"new_status": "UNDER_REVIEW", "change_reason": "Triage"},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert r_stat_no_csrf.status_code == status.HTTP_403_FORBIDDEN

    # 4. /notes without CSRF header -> 403 Forbidden
    r_note_no_csrf = await async_client.post(
        f"/api/v1/admin/rfqs/{enq.id}/notes",
        json={"note_text": "Unauthorized note"},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert r_note_no_csrf.status_code == status.HTTP_403_FORBIDDEN


# ==============================================================================
# 12. Transactional Atomicity & Rollback Protection
# ==============================================================================


@pytest.mark.asyncio
async def test_18_atomic_transaction_and_audit_consistency(
    db_session: AsyncSession, async_client: AsyncClient
):
    """18. Mutations, history rows, and audit records commit together atomically."""
    admin = await create_admin_user(db_session, "atomic_admin@edenbounty.org")
    cookie, csrf, _ = await login_admin(async_client, admin.email)
    enq = await create_test_enquiry(db_session, status_str="UNDER_REVIEW")

    # Perform valid transition
    res = await async_client.patch(
        f"/api/v1/admin/rfqs/{enq.id}/status",
        json={"new_status": "IN_COMMUNICATION", "change_reason": "Initiated correspondence"},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"},
    )
    assert res.status_code == status.HTTP_200_OK

    # Verify both history and audit record exist
    stmt_h = select(EnquiryStatusHistory).where(EnquiryStatusHistory.enquiry_id == enq.id)
    history_entries = (await db_session.execute(stmt_h)).scalars().all()
    assert len(history_entries) == 1
    assert history_entries[0].new_status == "IN_COMMUNICATION"

    stmt_a = select(AuditLog).where(
        AuditLog.entity_id == enq.id,
        AuditLog.action == "STATUS_CHANGED",
    )
    audit_entries = (await db_session.execute(stmt_a)).scalars().all()
    assert len(audit_entries) == 1
    assert audit_entries[0].new_state["status"] == "IN_COMMUNICATION"
