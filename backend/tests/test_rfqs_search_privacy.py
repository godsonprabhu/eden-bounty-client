"""Automated Verification Suite for Privacy-Preserving Repository Search and Data Minimization.

Phase C13.4 Stage 4.1 Privacy Remediation:
SEC-01: Authenticated POST search mechanism with JSON request body.
SEC-02: Data minimization removing contact_name and business_email from list response schema.
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
async def setup_privacy_database(db_session: AsyncSession, async_client: AsyncClient):
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
    email: str = "ops_privacy@edenbounty.org",
    role: str = "OPERATIONS_ADMIN",
) -> AdminUser:
    """Helper to provision an administrator."""
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


async def login_admin(
    async_client: AsyncClient, email: str = "ops_privacy@edenbounty.org"
) -> tuple[str, str]:
    """Helper to authenticate admin and retrieve session cookie and CSRF token."""
    res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SuperSecretPass2026!#"},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res.status_code == status.HTTP_200_OK
    cookie = res.cookies.get(settings.SESSION_COOKIE_NAME)
    assert cookie is not None
    csrf_token = res.json()["data"]["csrf_token"]
    assert csrf_token is not None
    return cookie, csrf_token


async def create_enquiry(
    db: AsyncSession,
    ref: str,
    division_id: str,
    status_str: str,
    created_at_dt: datetime,
    company: str = "Demo Corp Sdn Bhd",
    contact: str = "Confidential Contact",
    email: str = "confidential@democorp.com",
    assignee_id: uuid.UUID | None = None,
    country: str = "Malaysia",
) -> Enquiry:
    """Helper to seed an enquiry."""
    enq = Enquiry(
        reference_number=ref,
        idempotency_key=f"idem-{ref}-{uuid.uuid4()}",
        request_payload_hash=f"hash-{ref}",
        full_name=contact,
        company_name=company,
        business_email=email,
        contact_number="+60123456789",
        country=country,
        initial_division_id=division_id,
        current_division_id=division_id,
        product_focus=f"Product Focus for {ref}",
        status=status_str,
        assigned_admin_id=assignee_id,
        quantity=Decimal("1000.00"),
        unit_of_measurement="MT",
        specifications="Commercial specifications description",
        created_at=created_at_dt,
        updated_at=created_at_dt,
    )
    db.add(enq)
    await db.commit()
    await db.refresh(enq)
    return enq


@pytest.mark.asyncio
async def test_01_post_search_requires_authentication(
    async_client: AsyncClient,
):
    """Verifies that unauthenticated POST repository search requests are rejected."""
    res = await async_client.post(
        "/api/v1/admin/rfqs/search",
        json={"search": "test"},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_02_post_search_requires_csrf_protection(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies that POST repository search enforces origin validation and CSRF token matching."""
    await create_admin(db_session, "csrf_test@edenbounty.org")
    cookie, csrf_token = await login_admin(async_client, "csrf_test@edenbounty.org")

    # 1. Missing CSRF Token header -> 403
    res_no_csrf = await async_client.post(
        "/api/v1/admin/rfqs/search",
        json={"page": 1, "limit": 25},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res_no_csrf.status_code == status.HTTP_403_FORBIDDEN
    assert "CSRF token validation failed" in res_no_csrf.json()["detail"]

    # 2. Invalid CSRF Token header -> 403
    res_invalid_csrf = await async_client.post(
        "/api/v1/admin/rfqs/search",
        json={"page": 1, "limit": 25},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000", "X-CSRF-Token": "invalid_forged_csrf_token_123"},
    )
    assert res_invalid_csrf.status_code == status.HTTP_403_FORBIDDEN
    assert "CSRF token validation failed" in res_invalid_csrf.json()["detail"]

    # 3. Disallowed / Malicious Origin -> 403
    res_bad_origin = await async_client.post(
        "/api/v1/admin/rfqs/search",
        json={"page": 1, "limit": 25},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://malicious-attacker-site.com", "X-CSRF-Token": csrf_token},
    )
    assert res_bad_origin.status_code == status.HTTP_403_FORBIDDEN
    assert "origin not permitted" in res_bad_origin.json()["detail"].lower()

    # 4. Valid Cookie, Origin, and CSRF Token -> 200
    res_valid = await async_client.post(
        "/api/v1/admin/rfqs/search",
        json={"page": 1, "limit": 25},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000", "X-CSRF-Token": csrf_token},
    )
    assert res_valid.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_03_role_authorization_super_admin_and_operations_admin(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies that both SUPER_ADMIN and OPERATIONS_ADMIN retain full search access."""
    await create_admin(db_session, "super_search@edenbounty.org", role="SUPER_ADMIN")
    await create_admin(db_session, "ops_search@edenbounty.org", role="OPERATIONS_ADMIN")

    # Super Admin
    cookie_super, csrf_super = await login_admin(async_client, "super_search@edenbounty.org")
    res_super = await async_client.post(
        "/api/v1/admin/rfqs/search",
        json={"page": 1, "limit": 10},
        cookies={settings.SESSION_COOKIE_NAME: cookie_super},
        headers={"Origin": "http://localhost:3000", "X-CSRF-Token": csrf_super},
    )
    assert res_super.status_code == status.HTTP_200_OK

    # Operations Admin
    cookie_ops, csrf_ops = await login_admin(async_client, "ops_search@edenbounty.org")
    res_ops = await async_client.post(
        "/api/v1/admin/rfqs/search",
        json={"page": 1, "limit": 10},
        cookies={settings.SESSION_COOKIE_NAME: cookie_ops},
        headers={"Origin": "http://localhost:3000", "X-CSRF-Token": csrf_ops},
    )
    assert res_ops.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_04_data_minimization_contact_name_and_business_email_omitted(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """SEC-02 Verification: Proves contact_name and business_email are absent from JSON response."""
    await create_admin(db_session, "min_test@edenbounty.org")
    cookie, csrf_token = await login_admin(async_client, "min_test@edenbounty.org")

    await create_enquiry(
        db_session,
        ref="EB-MIN-001",
        division_id="mineral-water",
        status_str="NEW",
        created_at_dt=datetime.now(UTC),
        company="Global Springs Ltd",
        contact="Alice Tan Secret",
        email="alice.secret@globalsprings.com",
    )

    # 1. Verify POST /search response
    res_post = await async_client.post(
        "/api/v1/admin/rfqs/search",
        json={"page": 1, "limit": 10},
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000", "X-CSRF-Token": csrf_token},
    )
    assert res_post.status_code == status.HTTP_200_OK
    items_post = res_post.json()["data"]["items"]
    assert len(items_post) == 1
    first_item_post = items_post[0]

    # Critical privacy assertions
    assert "contact_name" not in first_item_post, "PII leak: contact_name must not be in list response"
    assert "business_email" not in first_item_post, "PII leak: business_email must not be in list response"
    assert "contact_number" not in first_item_post, "PII leak: contact_number must not be in list response"

    # Preserved corporate fields
    assert first_item_post["reference_number"] == "EB-MIN-001"
    assert first_item_post["company_name"] == "Global Springs Ltd"
    assert first_item_post["country"] == "Malaysia"
    assert first_item_post["division_id"] == "mineral-water"
    assert first_item_post["status"] == "NEW"

    # 2. Verify GET /rfqs response also excludes contact_name and business_email
    res_get = await async_client.get(
        "/api/v1/admin/rfqs",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res_get.status_code == status.HTTP_200_OK
    first_item_get = res_get.json()["data"]["items"][0]
    assert "contact_name" not in first_item_get
    assert "business_email" not in first_item_get


@pytest.mark.asyncio
async def test_05_multi_field_search_in_post_body(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """SEC-01 Verification: Proves search functions across all 4 fields via POST JSON body."""
    await create_admin(db_session, "multi_search@edenbounty.org")
    cookie, csrf_token = await login_admin(async_client, "multi_search@edenbounty.org")

    now = datetime.now(UTC)
    await create_enquiry(
        db_session,
        ref="EB-SRCH-ALPHA",
        division_id="petroleum-products",
        status_str="NEW",
        created_at_dt=now - timedelta(hours=3),
        company="Borneo Bunkering Sdn Bhd",
        contact="Captain Marcus Vance",
        email="marcus@borneobunker.com",
    )
    await create_enquiry(
        db_session,
        ref="EB-SRCH-BETA",
        division_id="agricultural-drones",
        status_str="ASSIGNED",
        created_at_dt=now - timedelta(hours=2),
        company="Perak Smart Farming Co",
        contact="Dr Hasmizan Kadir",
        email="hasmizan@perakagro.my",
    )

    headers = {"Origin": "http://localhost:3000", "X-CSRF-Token": csrf_token}
    cookies = {settings.SESSION_COOKIE_NAME: cookie}

    # 1. Search by reference number in body
    res_ref = await async_client.post(
        "/api/v1/admin/rfqs/search",
        json={"search": "EB-SRCH-ALPHA"},
        cookies=cookies,
        headers=headers,
    )
    assert res_ref.status_code == status.HTTP_200_OK
    assert len(res_ref.json()["data"]["items"]) == 1
    assert res_ref.json()["data"]["items"][0]["reference_number"] == "EB-SRCH-ALPHA"

    # 2. Search by company name in body
    res_comp = await async_client.post(
        "/api/v1/admin/rfqs/search",
        json={"search": "Smart Farming"},
        cookies=cookies,
        headers=headers,
    )
    assert res_comp.status_code == status.HTTP_200_OK
    assert len(res_comp.json()["data"]["items"]) == 1
    assert res_comp.json()["data"]["items"][0]["reference_number"] == "EB-SRCH-BETA"

    # 3. Search by submitter personal name in body
    res_name = await async_client.post(
        "/api/v1/admin/rfqs/search",
        json={"search": "Marcus Vance"},
        cookies=cookies,
        headers=headers,
    )
    assert res_name.status_code == status.HTTP_200_OK
    assert len(res_name.json()["data"]["items"]) == 1
    assert res_name.json()["data"]["items"][0]["reference_number"] == "EB-SRCH-ALPHA"

    # 4. Search by email in body
    res_email = await async_client.post(
        "/api/v1/admin/rfqs/search",
        json={"search": "hasmizan@perakagro.my"},
        cookies=cookies,
        headers=headers,
    )
    assert res_email.status_code == status.HTTP_200_OK
    assert len(res_email.json()["data"]["items"]) == 1
    assert res_email.json()["data"]["items"][0]["reference_number"] == "EB-SRCH-BETA"


@pytest.mark.asyncio
async def test_06_post_body_filtering_sorting_and_pagination(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies that all filters, sorting, date ranges, and pagination operate correctly in POST body."""
    admin = await create_admin(db_session, "full_post@edenbounty.org")
    cookie, csrf_token = await login_admin(async_client, "full_post@edenbounty.org")

    base_time = datetime(2026, 11, 1, 0, 0, 0, tzinfo=UTC)
    for i in range(1, 16):
        await create_enquiry(
            db_session,
            ref=f"EB-FULL-{i:03d}",
            division_id="construction" if i % 2 == 0 else "mineral-water",
            status_str="NEW" if i <= 5 else "UNDER_REVIEW",
            created_at_dt=base_time + timedelta(hours=i),
            company=f"Entity {chr(65 + i)}",
            assignee_id=admin.id if i % 3 == 0 else None,
        )

    headers = {"Origin": "http://localhost:3000", "X-CSRF-Token": csrf_token}
    cookies = {settings.SESSION_COOKIE_NAME: cookie}

    # 1. Division filter in body
    res_div = await async_client.post(
        "/api/v1/admin/rfqs/search",
        json={"division_id": "construction"},
        cookies=cookies,
        headers=headers,
    )
    assert res_div.status_code == status.HTTP_200_OK
    assert len(res_div.json()["data"]["items"]) == 7

    # 2. Status filter in body
    res_st = await async_client.post(
        "/api/v1/admin/rfqs/search",
        json={"status": "NEW"},
        cookies=cookies,
        headers=headers,
    )
    assert res_st.status_code == status.HTTP_200_OK
    assert len(res_st.json()["data"]["items"]) == 5

    # 3. Unassigned filter in body
    res_unassigned = await async_client.post(
        "/api/v1/admin/rfqs/search",
        json={"assigned_admin_id": "unassigned"},
        cookies=cookies,
        headers=headers,
    )
    assert res_unassigned.status_code == status.HTTP_200_OK
    assert len(res_unassigned.json()["data"]["items"]) == 10

    # 4. Inverted date range in body rejected with HTTP 400
    res_inv = await async_client.post(
        "/api/v1/admin/rfqs/search",
        json={
            "created_from": (base_time + timedelta(days=5)).isoformat(),
            "created_to": base_time.isoformat(),
        },
        cookies=cookies,
        headers=headers,
    )
    assert res_inv.status_code == status.HTTP_400_BAD_REQUEST
    assert "created_from timestamp cannot be later than created_to timestamp" in res_inv.json()["detail"]

    # 5. Pagination and sorting in body
    res_page = await async_client.post(
        "/api/v1/admin/rfqs/search",
        json={"page": 2, "limit": 5, "sort_by": "created_at", "sort_order": "asc"},
        cookies=cookies,
        headers=headers,
    )
    assert res_page.status_code == status.HTTP_200_OK
    data_page = res_page.json()["data"]
    assert len(data_page["items"]) == 5
    assert data_page["pagination"]["page"] == 2
    assert data_page["pagination"]["total_items"] == 15
    assert data_page["items"][0]["reference_number"] == "EB-FULL-006"
