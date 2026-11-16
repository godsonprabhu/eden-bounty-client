"""Automated Test Suite for Phase C13.4 Stage 4.2: Commercial Enquiry Dossier & Timeline.

Tests:
1. Dossier endpoint requires administrator authentication (401 without session cookie).
2. Role authorization: both SUPER_ADMIN and OPERATIONS_ADMIN succeed (200 OK).
3. Complete enquiry snapshot (submitter contact details, requirements, divisions, assignment).
4. Network metadata omission (SEC-02 privacy: source_ip, client_user_agent absent).
5. Nonexistent enquiry UUID returns HTTP 404 Not Found.
6. Soft-deleted enquiry returns HTTP 404 Not Found.
7. Malformed UUID string returns HTTP 422 Unprocessable Content.
8. Operational collections data integrity (assignments, status history, notes with actors and timestamps).
9. Inactive / historical administrator references resolved gracefully in audit lookup.
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
async def setup_dossier_database(db_session: AsyncSession, async_client: AsyncClient):
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
    email: str = "ops_dossier@edenbounty.org",
    role: str = "OPERATIONS_ADMIN",
    first_name: str = "Operations",
    last_name: str = "Manager",
) -> AdminUser:
    """Helper to provision an administrator."""
    user = AdminUser(
        email=email,
        password_hash=hash_password("SuperSecretPass2026!#"),
        first_name=first_name,
        last_name=last_name,
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
    async_client: AsyncClient, email: str = "ops_dossier@edenbounty.org"
) -> str:
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


async def create_test_enquiry(
    db: AsyncSession,
    ref: str = "EB-DOSSIER-001",
    division_id: str = "petroleum-products",
    status_str: str = "UNDER_REVIEW",
    company: str = "Apex Oceanic Energy Ltd",
    contact: str = "Captain Marcus Vance",
    email: str = "m.vance@apex-oceanic.com",
    phone: str = "+65-6888-9999",
    country: str = "Singapore",
    assignee_id: uuid.UUID | None = None,
    deleted_at_dt: datetime | None = None,
) -> Enquiry:
    """Helper to provision test enquiry with complete specifications snapshot."""
    now = datetime.now(UTC)
    enq = Enquiry(
        reference_number=ref,
        idempotency_key=f"idem-{ref}-{uuid.uuid4()}",
        request_payload_hash=f"hash-{ref}",
        full_name=contact,
        company_name=company,
        business_email=email,
        contact_number=phone,
        country=country,
        initial_division_id=division_id,
        current_division_id=division_id,
        product_focus="Low Sulfur Marine Gasoil (LSMGO 0.1%S)",
        quantity=Decimal("5000.00"),
        unit_of_measurement="MT",
        specifications="ISO 8217:2017 compliant DMA grade fuel, flash point > 60C, sulfur max 0.10%.",
        additional_notes="Vessel ETA Jurong Port on 2026-11-20. Bunkering coordination required.",
        preferred_incoterm="CIF",
        target_destination_port="Jurong Port, Singapore",
        status=status_str,
        assigned_admin_id=assignee_id,
        source_ip="198.51.100.42",
        client_user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        created_at=now - timedelta(days=2),
        updated_at=now - timedelta(hours=1),
        deleted_at=deleted_at_dt,
    )
    db.add(enq)
    await db.commit()
    await db.refresh(enq)
    return enq


@pytest.mark.asyncio
async def test_01_dossier_authentication_required(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies that GET /api/v1/admin/rfqs/{id} rejects unauthenticated requests with HTTP 401."""
    enq = await create_test_enquiry(db_session)
    res = await async_client.get(f"/api/v1/admin/rfqs/{enq.id}")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Authentication required" in res.json()["detail"]


@pytest.mark.asyncio
async def test_02_dossier_rbac_super_admin_and_operations_admin(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies that both SUPER_ADMIN and OPERATIONS_ADMIN possess authorized read access."""
    await create_admin(db_session, "super_dossier@edenbounty.org", "SUPER_ADMIN")
    await create_admin(db_session, "ops_dossier@edenbounty.org", "OPERATIONS_ADMIN")
    enq = await create_test_enquiry(db_session)

    # 1. SUPER_ADMIN Access
    cookie_super = await login_admin(async_client, "super_dossier@edenbounty.org")
    res_super = await async_client.get(
        f"/api/v1/admin/rfqs/{enq.id}",
        cookies={settings.SESSION_COOKIE_NAME: cookie_super},
    )
    assert res_super.status_code == status.HTTP_200_OK
    assert res_super.json()["data"]["id"] == str(enq.id)

    # 2. OPERATIONS_ADMIN Access
    cookie_ops = await login_admin(async_client, "ops_dossier@edenbounty.org")
    res_ops = await async_client.get(
        f"/api/v1/admin/rfqs/{enq.id}",
        cookies={settings.SESSION_COOKIE_NAME: cookie_ops},
    )
    assert res_ops.status_code == status.HTTP_200_OK
    assert res_ops.json()["data"]["id"] == str(enq.id)


@pytest.mark.asyncio
async def test_03_dossier_complete_data_snapshot(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies that full submitter snapshot, commercial specifications, and metadata are returned."""
    admin = await create_admin(db_session, "dossier_data@edenbounty.org")
    cookie = await login_admin(async_client, "dossier_data@edenbounty.org")
    enq = await create_test_enquiry(db_session, assignee_id=admin.id)

    res = await async_client.get(
        f"/api/v1/admin/rfqs/{enq.id}",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()["data"]

    # Submitter Contact Snapshot
    assert data["full_name"] == "Captain Marcus Vance"
    assert data["company_name"] == "Apex Oceanic Energy Ltd"
    assert data["business_email"] == "m.vance@apex-oceanic.com"
    assert data["contact_number"] == "+65-6888-9999"
    assert data["country"] == "Singapore"

    # Commercial Requirements Snapshot
    assert data["initial_division"]["id"] == "petroleum-products"
    assert data["initial_division"]["name"] == "Petroleum Products"
    assert data["current_division"]["id"] == "petroleum-products"
    assert data["product_focus"] == "Low Sulfur Marine Gasoil (LSMGO 0.1%S)"
    assert float(data["quantity"]) == 5000.00
    assert data["unit_of_measurement"] == "MT"
    assert "ISO 8217:2017 compliant" in data["specifications"]
    assert "Bunkering coordination required" in data["additional_notes"]
    assert data["preferred_incoterm"] == "CIF"
    assert data["target_destination_port"] == "Jurong Port, Singapore"

    # Status & Routing
    assert data["id"] == str(enq.id)
    assert data["reference_number"] == "EB-DOSSIER-001"
    assert data["status"] == "UNDER_REVIEW"
    assert data["assigned_admin"]["id"] == str(admin.id)
    assert data["assigned_admin"]["email"] == "dossier_data@edenbounty.org"


@pytest.mark.asyncio
async def test_04_dossier_privacy_network_metadata_omitted(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """SEC-02 Privacy Hardening: Asserts IP address and client user-agent are absent from schema and response."""
    await create_admin(db_session, "privacy_dossier@edenbounty.org")
    cookie = await login_admin(async_client, "privacy_dossier@edenbounty.org")
    enq = await create_test_enquiry(db_session)

    res = await async_client.get(
        f"/api/v1/admin/rfqs/{enq.id}",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()["data"]

    # Assert keys are absent from JSON response dictionary
    assert "source_ip" not in data
    assert "client_user_agent" not in data
    assert "ip_address" not in data
    assert "user_agent" not in data

    # Assert database-stored IP is strictly scrubbed from raw response body
    assert "198.51.100.42" not in res.text
    assert "Mozilla/5.0" not in res.text


@pytest.mark.asyncio
async def test_05_dossier_not_found_on_nonexistent_uuid(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies that querying a nonexistent UUID returns HTTP 404 Not Found."""
    await create_admin(db_session, "nf_dossier@edenbounty.org")
    cookie = await login_admin(async_client, "nf_dossier@edenbounty.org")

    random_id = uuid.uuid4()
    res = await async_client.get(
        f"/api/v1/admin/rfqs/{random_id}",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert "Enquiry not found" in res.json()["detail"]


@pytest.mark.asyncio
async def test_06_dossier_not_found_on_soft_deleted_enquiry(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies that soft-deleted enquiries are strictly excluded and return HTTP 404 Not Found."""
    await create_admin(db_session, "deleted_dossier@edenbounty.org")
    cookie = await login_admin(async_client, "deleted_dossier@edenbounty.org")
    deleted_enq = await create_test_enquiry(
        db_session,
        ref="EB-DELETED-001",
        deleted_at_dt=datetime.now(UTC),
    )

    res = await async_client.get(
        f"/api/v1/admin/rfqs/{deleted_enq.id}",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert "Enquiry not found" in res.json()["detail"]


@pytest.mark.asyncio
async def test_07_dossier_invalid_uuid_rejected(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies that malformed UUID path parameters return HTTP 422 Unprocessable Content."""
    await create_admin(db_session, "invalid_dossier@edenbounty.org")
    cookie = await login_admin(async_client, "invalid_dossier@edenbounty.org")

    res = await async_client.get(
        "/api/v1/admin/rfqs/not-a-valid-uuid",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
    )
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_08_dossier_timeline_data_integrity(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies complete retrieval of assignments, status history, and notes with actor and timestamp metadata."""
    admin_ops = await create_admin(db_session, "ops_lead@edenbounty.org", first_name="Alex", last_name="Wong")
    admin_lead = await create_admin(db_session, "trade_head@edenbounty.org", first_name="Sarah", last_name="Jenkins")
    cookie = await login_admin(async_client, "ops_lead@edenbounty.org")
    enq = await create_test_enquiry(db_session)

    now = datetime.now(UTC)

    # 1. Add assignments
    assign1 = EnquiryAssignment(
        enquiry_id=enq.id,
        previous_division_id="petroleum-products",
        new_division_id="petroleum-products",
        previous_admin_id=None,
        new_admin_id=admin_ops.id,
        assignment_rationale="Initial triage assignment to bunker trade specialist.",
        assigned_by_admin_id=admin_lead.id,
        assigned_at=now - timedelta(hours=5),
    )
    db_session.add(assign1)

    # 2. Add status history
    status1 = EnquiryStatusHistory(
        enquiry_id=enq.id,
        old_status="NEW",
        new_status="UNDER_REVIEW",
        change_reason="Technical specifications and vessel ETA verified with port agent.",
        changed_by_admin_id=admin_ops.id,
        created_at=now - timedelta(hours=4),
    )
    db_session.add(status1)

    # 3. Add internal note
    note1 = EnquiryNote(
        enquiry_id=enq.id,
        admin_user_id=admin_ops.id,
        note_text="Confirmed MPA bunkering license requirement for Singapore waters.",
        is_internal_only=True,
        created_at=now - timedelta(hours=3),
    )
    db_session.add(note1)
    await db_session.commit()

    # Query Dossier
    res = await async_client.get(
        f"/api/v1/admin/rfqs/{enq.id}",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()["data"]

    # Verify assignments collection
    assert len(data["assignments"]) == 1
    a_item = data["assignments"][0]
    assert a_item["new_admin"]["id"] == str(admin_ops.id)
    assert a_item["new_admin"]["name"] == "Alex Wong"
    assert a_item["assigned_by_admin"]["id"] == str(admin_lead.id)
    assert a_item["assigned_by_admin"]["name"] == "Sarah Jenkins"
    assert "Initial triage assignment" in a_item["assignment_rationale"]

    # Verify status history collection
    assert len(data["status_history"]) == 1
    s_item = data["status_history"][0]
    assert s_item["old_status"] == "NEW"
    assert s_item["new_status"] == "UNDER_REVIEW"
    assert s_item["changed_by_admin"]["id"] == str(admin_ops.id)
    assert "Technical specifications" in s_item["change_reason"]

    # Verify notes collection
    assert len(data["notes"]) == 1
    n_item = data["notes"][0]
    assert n_item["author_admin"]["id"] == str(admin_ops.id)
    assert "MPA bunkering license" in n_item["note_text"]
    assert n_item["is_internal_only"] is True


@pytest.mark.asyncio
async def test_09_dossier_inactive_historical_admin_resolved(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """Verifies that deactivated historical administrators are gracefully resolved by name in audit lookup."""
    await create_admin(db_session, "active_admin@edenbounty.org")
    cookie = await login_admin(async_client, "active_admin@edenbounty.org")

    # Create an administrator and subsequently deactivate them
    retired_admin = await create_admin(
        db_session,
        "retired_admin@edenbounty.org",
        first_name="Arthur",
        last_name="Pendelton",
    )
    retired_admin.is_active = False
    await db_session.commit()

    enq = await create_test_enquiry(db_session)
    status_entry = EnquiryStatusHistory(
        enquiry_id=enq.id,
        old_status="NEW",
        new_status="CONTACTED",
        change_reason="Historical status progression performed prior to retirement.",
        changed_by_admin_id=retired_admin.id,
        created_at=datetime.now(UTC) - timedelta(days=30),
    )
    db_session.add(status_entry)
    await db_session.commit()

    res = await async_client.get(
        f"/api/v1/admin/rfqs/{enq.id}",
        cookies={settings.SESSION_COOKIE_NAME: cookie},
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()["data"]

    # Ensure the inactive admin's name was resolved
    assert len(data["status_history"]) == 1
    assert data["status_history"][0]["changed_by_admin"]["name"] == "Arthur Pendelton"
    assert data["status_history"][0]["changed_by_admin"]["email"] == "retired_admin@edenbounty.org"
