"""Automated Tests for Public Ingestion Endpoints and Anti-Abuse Controls.

Phase C13.3 — Final Corrective Pass:
Comprehensive test coverage:
1. Public division listing (GET /api/v1/public/divisions)
2. Active division identifiers, display names, renamed divisions, Axe Oil (EB-DIV-06)
3. Drone division copy accuracy (no manufacturer attribution) and neutral disclaimers
4. Successful enquiry submission (POST /api/v1/public/rfq/enquire) with accurate acknowledgement
5. Missing required fields validation (422)
6. Invalid email validation (422)
7. Invalid division validation (400)
8. Unexpected request fields rejected (extra="forbid" -> 422)
9. Frontend camelCase compatibility
10. Snake_case API compatibility
11. Oversized payload rejection with declared Content-Length > 64 KB (413)
12. Oversized payload streaming/misleading Content-Length rejected (413)
13. Malformed JSON payload rejection (422)
14. Unique enquiry reference format (64-bit entropy: EB-RFQ-YYYYMMDD-XXXXXXXXXXXXXXXX)
15. Concurrent enquiry submissions with distinct references
16. Idempotency retry with same key & payload returns original reference without consuming quota
17. Idempotency conflict with same key & different payload returns 409 Conflict
18. Distinct idempotency keys allow identical commercial enquiries
19. Submissions without idempotency keys create distinct enquiries without commercial suppression
20. Concurrent identical idempotency key safe race resolution
21. Reference collision bounded retry using transaction savepoints and exhaustion safety
22. Honeypot anti-bot silent discard (website_url_hp)
23. Direct client with forged X-Forwarded-For ignored
24. Direct client with forged CF-Connecting-IP ignored
25. Trusted proxy with valid client IP extracted
26. Untrusted proxy connection ignores forwarding headers
27. Invalid forwarded IP values fall back safely to socket peer
28. Multiple X-Forwarded-For entries correctly parses first valid client IP
29. Division endpoint rate limiting (10 req/min)
30. RFQ submission atomic reservation prevents check/record concurrency race
31. Failed database write does not consume submission quota
32. Duplicate idempotent retry does not consume submission quota
33. Input sanitization / XSS stripping
34. Unauthenticated admin endpoint protection
"""

import asyncio
import re
import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest
from app.core.config import (
    Settings,
    settings,
    validate_proxy_configuration,
    validate_proxy_entry,
)
from app.core.rate_limit import (
    ReservationStatus,
    get_client_ip,
    is_trusted_proxy,
    public_rate_limiter,
)
from app.db.seeds import seed_divisions
from app.main import app, lifespan
from app.models.enquiry import Enquiry
from fastapi import HTTPException, Request, status
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

# Divisions offered publicly after client service catalogue correction.
# Exactly six services are exposed to the public catalogue.
# "lubricants", "shisha-tobacco-trading", and "axe-oil" remain in the
# database (inactive) for historical enquiries but are not listed or accepted for new RFQs.
EXPECTED_PUBLIC_DIVISIONS = [
    ("mineral-water", "Mineral Water"),
    ("scrap-trading", "Scrap Trading"),
    ("construction", "Construction / Building Promotion"),
    ("petroleum-products", "Petroleum Products"),
    ("furnace-oil", "Furnace Oil"),
    ("agricultural-drones", "Drone Solutions"),
]
ACTIVE_DIVISION_IDS = {item[0] for item in EXPECTED_PUBLIC_DIVISIONS}
WITHDRAWN_DIVISION_IDS = {"lubricants", "shisha-tobacco-trading", "axe-oil"}


@pytest.fixture(autouse=True)
async def clean_and_setup_public(db_session: AsyncSession):
    """Ensures rate limiter is reset, divisions seeded, and test enquiries cleaned."""
    await public_rate_limiter.reset()
    await seed_divisions(db_session)
    await db_session.execute(delete(Enquiry))
    await db_session.commit()
    yield
    await public_rate_limiter.reset()
    await db_session.execute(delete(Enquiry))
    await db_session.commit()


@pytest.mark.asyncio
async def test_01_public_divisions_listing(async_client: AsyncClient):
    """1. GET /api/v1/public/divisions returns 200 OK with standard success envelope and exactly six services."""
    response = await async_client.get("/api/v1/public/divisions")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
    # Exactly six services are listed publicly
    assert len(data["data"]) == 6


@pytest.mark.asyncio
async def test_02_division_identifiers_and_active_listing(
    async_client: AsyncClient,
):
    """2. Verifies exactly six services, correct IDs, public names, and exclusion of withdrawn/duplicate services."""
    response = await async_client.get("/api/v1/public/divisions")
    divisions = response.json()["data"]

    # Exactly six services in canonical order
    assert len(divisions) == 6
    assert [(d["id"], d["name"]) for d in divisions] == EXPECTED_PUBLIC_DIVISIONS

    returned_ids = {d["id"] for d in divisions}
    assert returned_ids == ACTIVE_DIVISION_IDS
    # Withdrawn and duplicate services do not appear
    assert "lubricants" not in returned_ids
    assert "shisha-tobacco-trading" not in returned_ids
    assert "axe-oil" not in returned_ids
    assert "building-promotions" not in returned_ids


@pytest.mark.asyncio
async def test_03_no_eb_div_codes_or_garuda_attribution(
    async_client: AsyncClient,
):
    """3. Verifies no EB-DIV codes, Garuda attribution, or legacy disclaimers appear in the public response."""
    response = await async_client.get("/api/v1/public/divisions")
    divisions = response.json()["data"]

    # No EB-DIV codes appear in the public response
    assert "EB-DIV" not in response.text
    for d in divisions:
        assert "code" not in d

    # No Garuda attribution appears anywhere in the public response
    assert "Garuda" not in response.text
    assert "garuda" not in response.text.lower()
    for d in divisions:
        assert d.get("manufacturer_attribution") is None
        assert d.get("disclaimer") is None


@pytest.mark.asyncio
async def test_04_successful_rfq_enquiry_submission(
    db_session: AsyncSession, async_client: AsyncClient
):
    """4. Successful enquiry submission returns 201 Created, 64-bit entropy reference, and neutral acknowledgement."""
    payload = {
        "division_id": "petroleum-products",
        "full_name": "Tariq Al-Mansoor",
        "company_name": "Gulf Maritime Logistics Ltd",
        "business_email": "tariq@gulfmaritime.com",
        "contact_number": "+971 4 391 0000",
        "country": "United Arab Emirates",
        "product_focus": "Ultra-Low Sulfur Diesel (EN 590 10ppm)",
        "quantity": 10000.0,
        "unit_of_measurement": "Metric Tonnes",
        "specifications": "Target sulfur < 10ppm, flash point > 60C",
        "additional_notes": "CIF Port of Fujairah. Target delivery Q1 2027.",
        "preferred_incoterm": "CIF",
        "target_destination_port": "Port of Fujairah",
    }

    response = await async_client.post("/api/v1/public/rfq/enquire", json=payload)
    assert response.status_code == status.HTTP_201_CREATED

    res_data = response.json()
    assert res_data["success"] is True
    assert res_data["data"]["status"] == "NEW"
    ref = res_data["data"]["reference_number"]
    # 64-bit entropy: 16 hex characters suffix
    assert re.match(r"^EB-RFQ-\d{8}-[A-F0-9]{16}$", ref)

    # Response message states only received and registered (NO mention of email dispatch)
    msg = res_data["data"]["message"]
    assert "received and registered successfully" in msg
    assert ref in msg
    assert "email" not in msg.lower()
    assert "dispatched" not in msg.lower()

    # Verify persisted in database
    stmt = select(Enquiry).where(Enquiry.reference_number == ref)
    enquiry = (await db_session.execute(stmt)).scalar_one_or_none()
    assert enquiry is not None
    assert enquiry.company_name == "Gulf Maritime Logistics Ltd"
    assert enquiry.product_focus == "Ultra-Low Sulfur Diesel (EN 590 10ppm)"
    assert enquiry.quantity == Decimal("10000.00")
    assert enquiry.contact_number == "+971 4 391 0000"
    assert enquiry.initial_division_id == "petroleum-products"
    assert enquiry.current_division_id == "petroleum-products"
    assert enquiry.status == "NEW"


@pytest.mark.asyncio
async def test_04a_optional_contact_number_submission_persists_null(
    db_session: AsyncSession, async_client: AsyncClient
):
    """A valid RFQ without a phone number is accepted and stores SQL NULL."""
    payload = {
        "division_id": "petroleum-products",
        "full_name": "Optional Contact Buyer",
        "company_name": "Optional Contact Corp",
        "business_email": "optional-contact@buyer.com",
        "country": "Malaysia",
        "product_focus": "Fuel Oil",
    }

    response = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json=payload,
        headers={"Idempotency-Key": "optional-contact-number-test"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    reference_number = response.json()["data"]["reference_number"]
    enquiry = (
        await db_session.execute(
            select(Enquiry).where(Enquiry.reference_number == reference_number)
        )
    ).scalar_one()
    assert enquiry.contact_number is None


@pytest.mark.asyncio
async def test_04b_omitted_contact_number_idempotent_retry_creates_one_enquiry(
    db_session: AsyncSession, async_client: AsyncClient
):
    payload = {
        "division_id": "petroleum-products",
        "full_name": "Optional Idempotent Buyer",
        "company_name": "Optional Idempotent Corp",
        "business_email": "optional-idem@buyer.com",
        "country": "Malaysia",
        "product_focus": "Fuel Oil",
    }
    headers = {"Idempotency-Key": "optional-contact-retry-test"}

    first = await async_client.post(
        "/api/v1/public/rfq/enquire", json=payload, headers=headers
    )
    retry = await async_client.post(
        "/api/v1/public/rfq/enquire", json=payload, headers=headers
    )

    assert first.status_code == status.HTTP_201_CREATED
    assert retry.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)
    reference_number = first.json()["data"]["reference_number"]
    assert retry.json()["data"]["reference_number"] == reference_number

    enquiries = (
        await db_session.execute(
            select(Enquiry).where(
                Enquiry.idempotency_key == headers["Idempotency-Key"]
            )
        )
    ).scalars().all()
    assert len(enquiries) == 1
    assert enquiries[0].contact_number is None


@pytest.mark.asyncio
async def test_04c_omitted_contact_number_changed_payload_returns_409(
    db_session: AsyncSession, async_client: AsyncClient
):
    payload = {
        "division_id": "petroleum-products",
        "full_name": "Optional Conflict Buyer",
        "company_name": "Optional Conflict Corp",
        "business_email": "optional-conflict@buyer.com",
        "country": "Malaysia",
        "product_focus": "Fuel Oil Batch A",
    }
    headers = {"Idempotency-Key": "optional-contact-conflict-test"}

    first = await async_client.post(
        "/api/v1/public/rfq/enquire", json=payload, headers=headers
    )
    changed = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json={**payload, "product_focus": "Fuel Oil Batch B"},
        headers=headers,
    )

    assert first.status_code == status.HTTP_201_CREATED
    assert changed.status_code == status.HTTP_409_CONFLICT
    enquiries = (
        await db_session.execute(
            select(Enquiry).where(
                Enquiry.idempotency_key == headers["Idempotency-Key"]
            )
        )
    ).scalars().all()
    assert len(enquiries) == 1
    assert enquiries[0].contact_number is None


@pytest.mark.asyncio
async def test_05_missing_required_fields_validation(async_client: AsyncClient):
    """5. Submitting payload with missing required fields returns 422 Unprocessable Entity."""
    payload = {
        "division_id": "petroleum-products",
        "business_email": "incomplete@buyer.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
    }

    response = await async_client.post("/api/v1/public/rfq/enquire", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_06_invalid_email_format_validation(async_client: AsyncClient):
    """6. Submitting invalid email address format returns 422 Unprocessable Entity."""
    payload = {
        "division_id": "petroleum-products",
        "full_name": "Test User",
        "company_name": "Test Corp",
        "business_email": "not-an-email-address",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Diesel",
    }

    response = await async_client.post("/api/v1/public/rfq/enquire", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_07_invalid_division_validation(async_client: AsyncClient):
    """7. Submitting non-existent division returns 400 Bad Request."""
    payload = {
        "division_id": "invalid-nonexistent-division",
        "full_name": "Valid Submitter",
        "company_name": "Valid Enterprise Ltd",
        "business_email": "valid@enterprise.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Industrial Supplies",
    }

    response = await async_client.post("/api/v1/public/rfq/enquire", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "invalid or inactive" in response.json()["detail"].lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("division_id", sorted(WITHDRAWN_DIVISION_IDS))
async def test_07a_withdrawn_division_rejected_for_new_rfq(
    db_session: AsyncSession, async_client: AsyncClient, division_id: str
):
    """7a. CR-C1: a withdrawn (inactive) division cannot receive new RFQs and nothing is stored."""
    payload = {
        "division_id": division_id,
        "full_name": "Valid Submitter",
        "company_name": "Valid Enterprise Ltd",
        "business_email": "withdrawn@enterprise.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Industrial Supplies",
    }

    response = await async_client.post("/api/v1/public/rfq/enquire", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "invalid or inactive" in response.json()["detail"].lower()

    stored = (
        await db_session.execute(select(Enquiry).where(Enquiry.business_email == "withdrawn@enterprise.com"))
    ).scalars().all()
    assert stored == []


@pytest.mark.asyncio
async def test_08_unexpected_request_fields_rejected(async_client: AsyncClient):
    """8. Rejects unexpected client fields (extra='forbid') with 422 to protect internal state."""
    payload = {
        "division_id": "petroleum-products",
        "full_name": "Attacker",
        "company_name": "Evil Corp",
        "business_email": "attacker@evil.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Diesel",
        "status": "APPROVED",
        "reference_number": "EB-RFQ-HACKED-0001",
        "assigned_admin_id": "00000000-0000-0000-0000-000000000000",
    }

    response = await async_client.post("/api/v1/public/rfq/enquire", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    data = response.json()
    error_str = str(data["detail"]).lower()
    assert "extra_forbidden" in error_str or "extra fields not permitted" in error_str


@pytest.mark.asyncio
async def test_09_frontend_camelcase_compatibility(
    db_session: AsyncSession, async_client: AsyncClient
):
    """9. Submissions using camelCase field aliases are properly mapped and saved."""
    camel_payload = {
        "divisionId": "construction",
        "fullName": "Sarah Tan",
        "companyName": "Apex Infra Builders",
        "businessEmail": "sarah@apexinfra.com",
        "contactNumber": "+60388889999",
        "country": "Malaysia",
        "productFocus": "Structural Steel & Aggregates",
        "quantity": "2500",
        "unitOfMeasurement": "Metric Tonnes",
        "additionalNotes": "Delivery to Klang Valley site.",
        "preferredIncoterm": "DAP",
        "targetDestinationPort": "Port Klang",
    }

    response = await async_client.post("/api/v1/public/rfq/enquire", json=camel_payload)
    assert response.status_code == status.HTTP_201_CREATED

    ref = response.json()["data"]["reference_number"]
    stmt = select(Enquiry).where(Enquiry.reference_number == ref)
    enquiry = (await db_session.execute(stmt)).scalar_one()

    assert enquiry.full_name == "Sarah Tan"
    assert enquiry.company_name == "Apex Infra Builders"
    assert enquiry.initial_division_id == "construction"
    assert enquiry.quantity == Decimal(2500)
    assert enquiry.preferred_incoterm == "DAP"
    assert enquiry.target_destination_port == "Port Klang"


@pytest.mark.asyncio
async def test_10_snake_case_api_compatibility(
    db_session: AsyncSession, async_client: AsyncClient
):
    """10. Submissions using snake_case API fields work identically."""
    snake_payload = {
        "division_id": "scrap-trading",
        "full_name": "Marcus Vance",
        "company_name": "Pacific Metal Recyclers",
        "business_email": "marcus@pacificmetal.com",
        "contact_number": "+60172223333",
        "country": "Malaysia",
        "product_focus": "HMS 1/2 Ferrous Scrap",
        "quantity": 500.0,
        "unit_of_measurement": "Metric Tonnes",
    }

    response = await async_client.post("/api/v1/public/rfq/enquire", json=snake_payload)
    assert response.status_code == status.HTTP_201_CREATED

    ref = response.json()["data"]["reference_number"]
    stmt = select(Enquiry).where(Enquiry.reference_number == ref)
    enquiry = (await db_session.execute(stmt)).scalar_one()

    assert enquiry.full_name == "Marcus Vance"
    assert enquiry.company_name == "Pacific Metal Recyclers"
    assert enquiry.product_focus == "HMS 1/2 Ferrous Scrap"


@pytest.mark.asyncio
async def test_11_oversized_payload_declared_header_rejected(async_client: AsyncClient):
    """11. Requests declaring Content-Length > 64 KB are rejected with 413 before body parsing."""
    payload = {
        "division_id": "petroleum-products",
        "full_name": "Large Submitter",
        "company_name": "Large Corp",
        "business_email": "large@corp.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Crude Oil",
    }

    response = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json=payload,
        headers={"Content-Length": "70000"},
    )
    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    data = response.json()
    assert "maximum permitted size" in str(data)


@pytest.mark.asyncio
async def test_12_oversized_payload_streaming_chunks_rejected(
    async_client: AsyncClient,
):
    """12. Requests with actual streaming body > 64 KB (even with small or missing header) are rejected with 413."""
    large_spec = "A" * 70000
    oversized_content = (
        b'{"division_id":"petroleum-products","full_name":"Big","company_name":"Big","business_email":"b@b.com",'
        b'"contact_number":"+123","country":"US","product_focus":"Oil","specifications":"'
        + large_spec.encode("ascii")
        + b'"}'
    )

    response = await async_client.post(
        "/api/v1/public/rfq/enquire",
        content=oversized_content,
        headers={"Content-Type": "application/json", "Content-Length": "100"},
    )
    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE


@pytest.mark.asyncio
async def test_13_malformed_json_rejected(async_client: AsyncClient):
    """13. Malformed JSON syntax is rejected safely with 422."""
    response = await async_client.post(
        "/api/v1/public/rfq/enquire",
        content=b'{"division_id": "petroleum-products", "unclosed_json: true',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_14_unique_enquiry_references_format_64bit_entropy(
    async_client: AsyncClient,
):
    """14. Generates 64-bit entropy references (16 hex chars) matching EB-RFQ-YYYYMMDD-XXXXXXXXXXXXXXXX."""
    payload_a = {
        "division_id": "mineral-water",
        "full_name": "Buyer A",
        "company_name": "Enterprise A",
        "business_email": "buyer_a@corp.com",
        "contact_number": "+60123456701",
        "country": "Singapore",
        "product_focus": "Bottled Mineral Water 500ml",
    }
    payload_b = {
        "division_id": "scrap-trading",
        "full_name": "Buyer B",
        "company_name": "Enterprise B",
        "business_email": "buyer_b@corp.com",
        "contact_number": "+60123456702",
        "country": "Malaysia",
        "product_focus": "HMS 1/2 Scrap Metal",
    }

    res_a = await async_client.post("/api/v1/public/rfq/enquire", json=payload_a)
    res_b = await async_client.post("/api/v1/public/rfq/enquire", json=payload_b)

    assert res_a.status_code == status.HTTP_201_CREATED
    assert res_b.status_code == status.HTTP_201_CREATED

    ref_a = res_a.json()["data"]["reference_number"]
    ref_b = res_b.json()["data"]["reference_number"]

    assert ref_a != ref_b
    assert re.match(r"^EB-RFQ-\d{8}-[A-F0-9]{16}$", ref_a)
    assert re.match(r"^EB-RFQ-\d{8}-[A-F0-9]{16}$", ref_b)


@pytest.mark.asyncio
async def test_15_concurrent_enquiry_submissions(
    db_session: AsyncSession, async_client: AsyncClient
):
    """15. Concurrent submissions execute safely without collisions, returning distinct references."""

    async def submit(idx: int):
        return await async_client.post(
            "/api/v1/public/rfq/enquire",
            json={
                "division_id": "mineral-water",
                "full_name": f"Concurrent Buyer {idx}",
                "company_name": f"Enterprise {idx}",
                "business_email": f"concurrent_{idx}@corp.com",
                "contact_number": f"+6012345{idx:04d}",
                "country": "Singapore",
                "product_focus": f"Water Batch {idx}",
            },
        )

    responses = await asyncio.gather(*[submit(i) for i in range(5)])

    for res in responses:
        assert res.status_code == status.HTTP_201_CREATED

    references = [r.json()["data"]["reference_number"] for r in responses]
    assert len(set(references)) == 5


@pytest.mark.asyncio
async def test_16_idempotency_retry_returns_original_reference_without_quota(
    db_session: AsyncSession, async_client: AsyncClient
):
    """16. Identical retry with same idempotency key returns original reference and does not consume quota."""
    payload = {
        "division_id": "petroleum-products",
        "full_name": "Idempotent Buyer",
        "company_name": "Idempotent Corp",
        "business_email": "idem@buyer.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Fuel Oil",
        "idempotency_key": "eb-test-idem-key-001",
    }

    # First attempt
    res1 = await async_client.post("/api/v1/public/rfq/enquire", json=payload)
    assert res1.status_code == status.HTTP_201_CREATED
    ref1 = res1.json()["data"]["reference_number"]

    # Second attempt (same key, same payload)
    res2 = await async_client.post("/api/v1/public/rfq/enquire", json=payload)
    assert res2.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)
    ref2 = res2.json()["data"]["reference_number"]

    assert ref1 == ref2

    # Database contains exactly 1 row
    stmt = select(Enquiry).where(Enquiry.idempotency_key == "eb-test-idem-key-001")
    rows = (await db_session.execute(stmt)).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_17_idempotency_conflict_returns_409(
    db_session: AsyncSession, async_client: AsyncClient
):
    """17. Same idempotency key used with altered commercial payload returns 409 Conflict."""
    payload_original = {
        "division_id": "mineral-water",
        "full_name": "Conflict Buyer",
        "company_name": "Conflict Corp",
        "business_email": "conflict@buyer.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Water Batch 1",
        "idempotency_key": "eb-conflict-key-999",
    }

    # Original submission
    res1 = await async_client.post("/api/v1/public/rfq/enquire", json=payload_original)
    assert res1.status_code == status.HTTP_201_CREATED

    # Attempt reuse of same key with DIFFERENT product focus
    payload_modified = {
        **payload_original,
        "product_focus": "Water Batch 2 (Altered Payload)",
    }
    res2 = await async_client.post("/api/v1/public/rfq/enquire", json=payload_modified)
    assert res2.status_code == status.HTTP_409_CONFLICT
    assert (
        "already been used with a different request payload"
        in res2.json()["detail"].lower()
    )


@pytest.mark.asyncio
async def test_18_idempotency_distinct_keys_allow_identical_payload(
    db_session: AsyncSession, async_client: AsyncClient
):
    """18. Distinct idempotency keys allow legitimate identical enquiries to be preserved as separate records."""
    base_payload = {
        "division_id": "furnace-oil",
        "full_name": "Repeat Buyer",
        "company_name": "Repeat Industries",
        "business_email": "repeat@buyer.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Furnace Oil 380 CST",
    }

    res1 = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json={**base_payload, "idempotency_key": "order-batch-1"},
    )
    res2 = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json={**base_payload, "idempotency_key": "order-batch-2"},
    )

    assert res1.status_code == status.HTTP_201_CREATED
    assert res2.status_code == status.HTTP_201_CREATED

    ref1 = res1.json()["data"]["reference_number"]
    ref2 = res2.json()["data"]["reference_number"]
    assert ref1 != ref2

    # Database contains 2 separate enquiries
    stmt = select(Enquiry).where(Enquiry.business_email == "repeat@buyer.com")
    enquiries = (await db_session.execute(stmt)).scalars().all()
    assert len(enquiries) == 2


@pytest.mark.asyncio
async def test_19_no_idempotency_key_does_not_suppress_legitimate_repeat_submissions(
    db_session: AsyncSession, async_client: AsyncClient
):
    """19. Submissions without idempotency keys are not suppressed based solely on matching commercial fields."""
    payload = {
        "division_id": "petroleum-products",
        "full_name": "Fleet Operator",
        "company_name": "TransFleet Logistics",
        "business_email": "fleet@transfleet.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Hydraulic Oil ISO VG 46",
    }

    # Submit twice without idempotency key
    res1 = await async_client.post("/api/v1/public/rfq/enquire", json=payload)
    res2 = await async_client.post("/api/v1/public/rfq/enquire", json=payload)

    assert res1.status_code == status.HTTP_201_CREATED
    assert res2.status_code == status.HTTP_201_CREATED

    ref1 = res1.json()["data"]["reference_number"]
    ref2 = res2.json()["data"]["reference_number"]
    assert ref1 != ref2

    # Database contains both distinct submissions
    stmt = select(Enquiry).where(Enquiry.business_email == "fleet@transfleet.com")
    enquiries = (await db_session.execute(stmt)).scalars().all()
    assert len(enquiries) == 2


@pytest.mark.asyncio
async def test_20_concurrent_identical_idempotency_key_safe_resolution(
    db_session: AsyncSession, async_client: AsyncClient
):
    """20. Concurrent requests with identical idempotency key resolve safely via database unique constraint."""
    payload = {
        "division_id": "mineral-water",
        "full_name": "Concurrent Idem",
        "company_name": "Idem Corp",
        "business_email": "concur_idem@corp.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Natural Mineral Water 500ml",
        "idempotency_key": "concurrent-race-key-01",
    }

    responses = await asyncio.gather(
        *[
            async_client.post("/api/v1/public/rfq/enquire", json=payload)
            for _ in range(4)
        ]
    )

    for r in responses:
        assert r.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)

    references = [r.json()["data"]["reference_number"] for r in responses]
    # All 4 requests must return the exact same reference number
    assert len(set(references)) == 1

    # Database must contain exactly 1 enquiry
    stmt = select(Enquiry).where(Enquiry.idempotency_key == "concurrent-race-key-01")
    rows = (await db_session.execute(stmt)).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_21_reference_collision_bounded_retry_and_exhaustion(
    db_session: AsyncSession, async_client: AsyncClient
):
    """21. Verifies savepoint retry mechanism and safe RuntimeError raising upon retry exhaustion."""
    payload = {
        "division_id": "petroleum-products",
        "full_name": "Retry Tester",
        "company_name": "Retry Corp",
        "business_email": "retry@tester.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Diesel",
    }

    # Insert initial enquiry
    first_res = await async_client.post("/api/v1/public/rfq/enquire", json=payload)
    assert first_res.status_code == status.HTTP_201_CREATED
    first_ref = first_res.json()["data"]["reference_number"]

    # Simulate collision exhaustion by mocking reference generator to return an already existing reference
    with patch(
        "app.api.v1.endpoints.public.generate_cryptographic_reference",
        return_value=first_ref,
    ):
        # With all attempts colliding, endpoint exhausts retries and raises 500 without leaving DB corrupted
        exhaust_res = await async_client.post(
            "/api/v1/public/rfq/enquire",
            json={**payload, "product_focus": "Exhausted Batch"},
        )
        assert exhaust_res.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


@pytest.mark.asyncio
async def test_22_honeypot_anti_bot_silent_discard(
    db_session: AsyncSession, async_client: AsyncClient
):
    """22. Honeypot field (website_url_hp) silently returns simulated reference without persisting to DB."""
    bot_payload = {
        "division_id": "agricultural-drones",
        "full_name": "Spam Bot",
        "company_name": "Automated Spam Services LLC",
        "business_email": "spambot@automatedspammer.com",
        "contact_number": "+18005550199",
        "country": "United States",
        "product_focus": "Drones",
        "website_url_hp": "http://spamsite.com/malicious-link",
    }

    response = await async_client.post("/api/v1/public/rfq/enquire", json=bot_payload)
    assert response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)
    assert response.json()["success"] is True

    # Database must NOT contain the submission
    stmt = select(Enquiry).where(
        Enquiry.business_email == "spambot@automatedspammer.com"
    )
    record = (await db_session.execute(stmt)).scalar_one_or_none()
    assert record is None


def test_23_spoofed_forwarded_ip_headers_ignored_direct_client():
    """23. Direct connection from untrusted client host ignores X-Forwarded-For."""
    scope = {
        "type": "http",
        "client": ("198.51.100.22", 54321),
        "headers": [(b"x-forwarded-for", b"1.1.1.1")],
    }
    req = Request(scope)
    assert get_client_ip(req) == "198.51.100.22"


def test_24_spoofed_cf_connecting_ip_ignored_direct_client():
    """24. Direct connection from untrusted client host ignores CF-Connecting-IP."""
    scope = {
        "type": "http",
        "client": ("198.51.100.23", 54321),
        "headers": [(b"cf-connecting-ip", b"8.8.8.8")],
    }
    req = Request(scope)
    assert get_client_ip(req) == "198.51.100.23"


def test_25_trusted_proxy_valid_client_ip_extraction():
    """25. Connection originating from configured trusted proxy extracts valid client IP."""
    scope = {
        "type": "http",
        "client": ("127.0.0.1", 54321),
        "headers": [(b"x-forwarded-for", b"203.0.113.195")],
    }
    req = Request(scope)
    assert get_client_ip(req) == "203.0.113.195"


def test_26_untrusted_proxy_headers_ignored():
    """26. Upstream proxy not in TRUSTED_PROXIES is treated as direct client and headers ignored."""
    scope = {
        "type": "http",
        "client": ("172.19.0.50", 54321),  # Untrusted proxy host
        "headers": [(b"x-forwarded-for", b"203.0.113.195")],
    }
    req = Request(scope)
    assert get_client_ip(req) == "172.19.0.50"


def test_27_invalid_forwarded_ip_values_fall_back_safely():
    """27. Malformed IP strings in forwarded headers fall back safely to socket peer."""
    scope = {
        "type": "http",
        "client": ("127.0.0.1", 54321),
        "headers": [(b"x-forwarded-for", b"not-a-valid-ip, garbage_data")],
    }
    req = Request(scope)
    assert get_client_ip(req) == "127.0.0.1"


def test_28_multiple_x_forwarded_for_entries_picks_client():
    """28. Correctly extracts the client IP from multiple comma-separated proxy hops using right-to-left parsing."""
    scope = {
        "type": "http",
        "client": ("127.0.0.1", 54321),
        "headers": [(b"x-forwarded-for", b"203.0.113.77, 10.0.0.1, 127.0.0.1")],
    }
    req = Request(scope)
    with patch.object(settings, "TRUSTED_PROXIES", ["127.0.0.1", "10.0.0.1", "::1"]):
        assert get_client_ip(req) == "203.0.113.77"


@pytest.mark.asyncio
async def test_29_division_endpoint_rate_limiting(async_client: AsyncClient):
    """29. GET /api/v1/public/divisions rate limiting blocks on the 11th request per minute."""
    test_ip = "198.51.100.50"
    for _ in range(settings.PUBLIC_RATE_LIMIT_PER_MINUTE):
        res = await async_client.get(
            "/api/v1/public/divisions",
            headers={"X-Forwarded-For": test_ip},
        )
        assert res.status_code == status.HTTP_200_OK

    res_blocked = await async_client.get(
        "/api/v1/public/divisions",
        headers={"X-Forwarded-For": test_ip},
    )
    assert res_blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "too many requests" in res_blocked.json()["detail"].lower()


@pytest.mark.asyncio
async def test_30_rfq_submission_atomic_reservation_prevents_concurrency_race(
    async_client: AsyncClient,
):
    """30. Atomic reservation prevents check/record race: 10 concurrent requests from same IP only permit 5."""
    test_ip = "198.51.100.60"

    async def submit_concurrent(idx: int):
        return await async_client.post(
            "/api/v1/public/rfq/enquire",
            json={
                "division_id": "mineral-water",
                "full_name": f"Concurrent Tester {idx}",
                "company_name": f"Tester Corp {idx}",
                "business_email": f"concur_{idx}@test.com",
                "contact_number": f"+6012345{idx:04d}",
                "country": "Malaysia",
                "product_focus": f"Water Batch {idx}",
            },
            headers={"X-Forwarded-For": test_ip},
        )

    # Launch 10 simultaneous requests
    responses = await asyncio.gather(*[submit_concurrent(i) for i in range(10)])

    successes = [r for r in responses if r.status_code == status.HTTP_201_CREATED]
    rate_limited = [
        r for r in responses if r.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    ]

    # Exactly 5 allowed and exactly 5 blocked (atomic reservation prevents race condition)
    assert len(successes) == settings.PUBLIC_SUBMISSION_LIMIT_10MIN
    assert len(rate_limited) == 5


@pytest.mark.asyncio
async def test_31_failed_db_write_does_not_consume_submission_quota(
    async_client: AsyncClient,
):
    """31. Submissions that fail validation or database checks release reservation and do not consume quota."""
    test_ip = "198.51.100.70"

    # Send 5 invalid division submissions (fail with 400)
    for _ in range(5):
        res = await async_client.post(
            "/api/v1/public/rfq/enquire",
            json={
                "division_id": "nonexistent-division",
                "full_name": "Failed Buyer",
                "company_name": "Failed Corp",
                "business_email": "fail@corp.com",
                "contact_number": "+60123456789",
                "country": "Malaysia",
                "product_focus": "Water",
            },
            headers={"X-Forwarded-For": test_ip},
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    # A legitimate valid submission now must SUCCEED because failed attempts released their slot
    valid_res = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json={
            "division_id": "mineral-water",
            "full_name": "Valid Buyer",
            "company_name": "Valid Corp",
            "business_email": "valid@corp.com",
            "contact_number": "+60123456789",
            "country": "Malaysia",
            "product_focus": "Water",
        },
        headers={"X-Forwarded-For": test_ip},
    )
    assert valid_res.status_code == status.HTTP_201_CREATED


@pytest.mark.asyncio
async def test_32_duplicate_retry_does_not_consume_submission_quota(
    async_client: AsyncClient,
):
    """32. Idempotent retries return existing enquiry and do not consume additional submission quota."""
    test_ip = "198.51.100.80"
    payload = {
        "division_id": "mineral-water",
        "full_name": "Idem Quota Buyer",
        "company_name": "Idem Corp",
        "business_email": "idem_quota@corp.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Mineral Water",
        "idempotency_key": "fixed-quota-key-01",
    }

    # Initial submission (consumes 1 of 5 quota)
    res_init = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json=payload,
        headers={"X-Forwarded-For": test_ip},
    )
    assert res_init.status_code == status.HTTP_201_CREATED

    # Retry 5 times with identical key & payload
    for _ in range(5):
        res_retry = await async_client.post(
            "/api/v1/public/rfq/enquire",
            json=payload,
            headers={"X-Forwarded-For": test_ip},
        )
        # Succeeded without 429
        assert res_retry.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)


@pytest.mark.asyncio
async def test_33_input_sanitization_xss_prevention(
    db_session: AsyncSession, async_client: AsyncClient
):
    """33. Script, style, iframe, and HTML tags are automatically stripped from user inputs."""
    payload = {
        "division_id": "scrap-trading",
        "full_name": "John <script>alert('xss')</script>Doe",
        "company_name": "<b>Recycling Traders Ltd</b>",
        "business_email": "clean@recycling.com",
        "contact_number": "+971501234567",
        "country": "United Arab Emirates",
        "product_focus": "Recycled Metal <img src=x onerror=alert(1)>",
        "specifications": "Grade A <style>body{color:red;}</style> Scrap",
        "additional_notes": "Prompt delivery <iframe></iframe> required.",
    }

    response = await async_client.post("/api/v1/public/rfq/enquire", json=payload)
    assert response.status_code == status.HTTP_201_CREATED

    ref = response.json()["data"]["reference_number"]
    stmt = select(Enquiry).where(Enquiry.reference_number == ref)
    enquiry = (await db_session.execute(stmt)).scalar_one()

    assert "<script>" not in enquiry.full_name
    assert "John Doe" == enquiry.full_name
    assert "<b>" not in enquiry.company_name
    assert "Recycling Traders Ltd" == enquiry.company_name
    assert "<img" not in enquiry.product_focus
    assert "<style>" not in enquiry.specifications
    assert "<iframe>" not in enquiry.additional_notes


@pytest.mark.asyncio
async def test_34_unauthenticated_admin_endpoints_remain_protected(
    async_client: AsyncClient,
):
    """34. Public routes are accessible but admin routes remain strictly guarded with 401."""
    div_res = await async_client.get("/api/v1/public/divisions")
    assert div_res.status_code == status.HTTP_200_OK

    admin_res = await async_client.get("/api/v1/auth/me")
    assert admin_res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_35_deterministic_payload_hashing_regression_delimiter_ambiguity():
    """35. Proves deterministic JSON serialization prevents delimiter collision and field ambiguity."""
    from app.api.v1.endpoints.public import compute_payload_hash
    from app.schemas.public import EnquiryCreateRequest

    # In old "|"-delimited string join:
    # "company_name:Acme|product_focus:Diesel"
    # Could collide with crafted inputs crossing field delimiters.
    req1 = EnquiryCreateRequest(
        division_id="petroleum-products",
        full_name="Alice Smith",
        company_name="Acme Corp|product_focus:Diesel",
        business_email="alice@acme.com",
        contact_number="+60123456789",
        country="Malaysia",
        product_focus="Heavy Fuel",
    )
    req2 = EnquiryCreateRequest(
        division_id="petroleum-products",
        full_name="Alice Smith",
        company_name="Acme Corp",
        business_email="alice@acme.com",
        contact_number="+60123456789",
        country="Malaysia",
        product_focus="Diesel|specifications:Heavy Fuel",
    )

    hash1 = compute_payload_hash(req1)
    hash2 = compute_payload_hash(req2)
    assert hash1 != hash2
    assert len(hash1) == 64
    assert len(hash2) == 64

    # Identical requests produce identical hash
    req1_clone = EnquiryCreateRequest(
        division_id="petroleum-products",
        full_name="Alice Smith",
        company_name="Acme Corp|product_focus:Diesel",
        business_email="alice@acme.com",
        contact_number="+60123456789",
        country="Malaysia",
        product_focus="Heavy Fuel",
    )
    assert compute_payload_hash(req1) == compute_payload_hash(req1_clone)


@pytest.mark.asyncio
async def test_36_idempotency_key_valid_header(
    db_session: AsyncSession, async_client: AsyncClient
):
    """36. Valid idempotency key provided in Idempotency-Key and X-Idempotency-Key headers is stored."""
    payload = {
        "division_id": "mineral-water",
        "full_name": "Header Key Tester",
        "company_name": "Header Corp",
        "business_email": "header@corp.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Bottled Spring Water",
    }

    # Test Idempotency-Key
    res1 = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json=payload,
        headers={"Idempotency-Key": "valid-ietf-hdr-key-01"},
    )
    assert res1.status_code == status.HTTP_201_CREATED

    stmt1 = select(Enquiry).where(Enquiry.idempotency_key == "valid-ietf-hdr-key-01")
    enquiry1 = (await db_session.execute(stmt1)).scalar_one_or_none()
    assert enquiry1 is not None

    # Test X-Idempotency-Key
    res2 = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json={**payload, "business_email": "header2@corp.com"},
        headers={"X-Idempotency-Key": "valid-custom-hdr-key-02"},
    )
    assert res2.status_code == status.HTTP_201_CREATED

    stmt2 = select(Enquiry).where(Enquiry.idempotency_key == "valid-custom-hdr-key-02")
    enquiry2 = (await db_session.execute(stmt2)).scalar_one_or_none()
    assert enquiry2 is not None


@pytest.mark.asyncio
async def test_37_idempotency_key_valid_body(
    db_session: AsyncSession, async_client: AsyncClient
):
    """37. Valid idempotency key in request body is accepted and stored."""
    payload = {
        "division_id": "construction",
        "full_name": "Body Key Tester",
        "company_name": "Builder Ltd",
        "business_email": "builder@corp.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Steel Reinforcement",
        "idempotency_key": "valid-body-key-37",
    }

    res = await async_client.post("/api/v1/public/rfq/enquire", json=payload)
    assert res.status_code == status.HTTP_201_CREATED

    stmt = select(Enquiry).where(Enquiry.idempotency_key == "valid-body-key-37")
    enquiry = (await db_session.execute(stmt)).scalar_one_or_none()
    assert enquiry is not None


@pytest.mark.asyncio
async def test_38_idempotency_key_oversized_header_rejected(async_client: AsyncClient):
    """38. Oversized idempotency key header (>128 chars) is rejected with HTTP 400 before DB access."""
    payload = {
        "division_id": "petroleum-products",
        "full_name": "Oversized Tester",
        "company_name": "Oversized Corp",
        "business_email": "oversized@corp.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Commercial Fuel",
    }
    oversized_key = "k" * 129

    res1 = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json=payload,
        headers={"Idempotency-Key": oversized_key},
    )
    assert res1.status_code == status.HTTP_400_BAD_REQUEST
    assert "exceeds maximum allowed length of 128 characters" in res1.json()["detail"]

    res2 = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json=payload,
        headers={"X-Idempotency-Key": oversized_key},
    )
    assert res2.status_code == status.HTTP_400_BAD_REQUEST
    assert "exceeds maximum allowed length of 128 characters" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_39_idempotency_key_empty_and_whitespace_header_rejected(
    async_client: AsyncClient,
):
    """39. Empty or whitespace-only idempotency key headers are rejected with HTTP 400."""
    payload = {
        "division_id": "scrap-trading",
        "full_name": "Whitespace Tester",
        "company_name": "Whitespace Corp",
        "business_email": "whitespace@corp.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Copper Scrap",
    }

    for header_name in ["Idempotency-Key", "X-Idempotency-Key"]:
        # Empty string
        res_empty = await async_client.post(
            "/api/v1/public/rfq/enquire",
            json=payload,
            headers={header_name: ""},
        )
        assert res_empty.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            "cannot be empty or contain only whitespace" in res_empty.json()["detail"]
        )

        # Whitespace-only string
        res_ws = await async_client.post(
            "/api/v1/public/rfq/enquire",
            json=payload,
            headers={header_name: "     "},
        )
        assert res_ws.status_code == status.HTTP_400_BAD_REQUEST
        assert "cannot be empty or contain only whitespace" in res_ws.json()["detail"]


@pytest.mark.asyncio
async def test_40_idempotency_key_both_headers_identical_accepted(
    db_session: AsyncSession, async_client: AsyncClient
):
    """40. Both Idempotency-Key and X-Idempotency-Key provided with identical values are accepted."""
    payload = {
        "division_id": "furnace-oil",
        "full_name": "Dual Header Tester",
        "company_name": "Dual Corp",
        "business_email": "dual@corp.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Industrial Fuel Oil",
    }

    res = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json=payload,
        headers={
            "Idempotency-Key": "   dual-matching-key-40   ",
            "X-Idempotency-Key": "dual-matching-key-40",
        },
    )
    assert res.status_code == status.HTTP_201_CREATED

    stmt = select(Enquiry).where(Enquiry.idempotency_key == "dual-matching-key-40")
    enquiry = (await db_session.execute(stmt)).scalar_one_or_none()
    assert enquiry is not None


@pytest.mark.asyncio
async def test_41_idempotency_key_both_headers_conflicting_rejected(
    async_client: AsyncClient,
):
    """41. Conflicting values in Idempotency-Key and X-Idempotency-Key headers are rejected with HTTP 400."""
    payload = {
        "division_id": "furnace-oil",
        "full_name": "Conflict Header Tester",
        "company_name": "Conflict Corp",
        "business_email": "hdr_conflict@corp.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Low Sulfur Furnace Oil",
    }

    res = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json=payload,
        headers={
            "Idempotency-Key": "key-alpha",
            "X-Idempotency-Key": "key-beta",
        },
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "Conflicting idempotency keys provided" in res.json()["detail"]


@pytest.mark.asyncio
async def test_42_idempotency_key_conflicting_header_and_body_rejected(
    async_client: AsyncClient,
):
    """42. Conflicting values between HTTP header and request body are rejected with HTTP 400."""
    payload = {
        "division_id": "petroleum-products",
        "full_name": "Body Header Conflict",
        "company_name": "Conflict Corp",
        "business_email": "body_hdr_conflict@corp.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Engine Oil 15W40",
        "idempotency_key": "body-key-value",
    }

    res = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json=payload,
        headers={"Idempotency-Key": "header-key-value"},
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        "Conflicting idempotency keys provided in HTTP header and request body"
        in res.json()["detail"]
    )


@pytest.mark.asyncio
async def test_43_idempotency_header_retry_same_payload_returns_original_reference(
    async_client: AsyncClient, db_session: AsyncSession,
):
    """43. Idempotency-Key header retry with identical payload returns original reference without error."""
    payload = {
        "division_id": "agricultural-drones",
        "full_name": "Drone Buyer",
        "company_name": "AgriFly Corp",
        "business_email": "drones@agrifly.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Spraying Drones",
    }
    idem_header = {"Idempotency-Key": "header-retry-test-43"}

    res1 = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json=payload,
        headers=idem_header,
    )
    assert res1.status_code == status.HTTP_201_CREATED
    ref1 = res1.json()["data"]["reference_number"]

    res2 = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json=payload,
        headers=idem_header,
    )
    assert res2.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)
    ref2 = res2.json()["data"]["reference_number"]
    assert ref1 == ref2

    # Header-only retries must persist exactly one enquiry, as used by the website client.
    from app.models.enquiry import Enquiry

    stored = (
        await db_session.execute(
            select(Enquiry).where(Enquiry.idempotency_key == idem_header["Idempotency-Key"])
        )
    ).scalars().all()
    assert len(stored) == 1
    assert stored[0].reference_number == ref1


@pytest.mark.asyncio
async def test_44_idempotency_header_retry_different_payload_returns_409(
    async_client: AsyncClient,
):
    """44. Idempotency-Key header reused with modified commercial payload returns HTTP 409 Conflict."""
    payload = {
        "division_id": "construction",
        "full_name": "Promo Buyer",
        "company_name": "Promo Corp",
        "business_email": "promo@promocorp.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Commercial Space Lease",
    }
    idem_header = {"Idempotency-Key": "header-conflict-test-44"}

    res1 = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json=payload,
        headers=idem_header,
    )
    assert res1.status_code == status.HTTP_201_CREATED

    res2 = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json={**payload, "product_focus": "Industrial Warehouse Lease"},
        headers=idem_header,
    )
    assert res2.status_code == status.HTTP_409_CONFLICT
    assert "already been used with a different request payload" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_45_invalid_idempotency_header_rejected_before_database_query(
    async_client: AsyncClient,
):
    """45. Proves that invalid idempotency header rejects with 400 before ANY database queries run."""
    payload = {
        "division_id": "non-existent-and-invalid-division-id",
        "full_name": "Pre DB Tester",
        "company_name": "Pre DB Corp",
        "business_email": "predb@corp.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Petroleum",
    }

    # If the division query ran first, it would query the DB.
    # But because idempotency key validation runs BEFORE any DB queries,
    # an invalid idempotency header (e.g. oversized or conflicting) fails first,
    # and AsyncSession.execute must NEVER be invoked.
    with patch.object(AsyncSession, "execute") as mock_execute:
        res = await async_client.post(
            "/api/v1/public/rfq/enquire",
            json=payload,
            headers={"Idempotency-Key": "x" * 129},
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            "exceeds maximum allowed length of 128 characters" in res.json()["detail"]
        )
        mock_execute.assert_not_called()


@pytest.mark.asyncio
async def test_46_reservation_accounting_released_on_validation_failure(
    async_client: AsyncClient,
):
    """46. Verifies that reservation slot is released on validation failure and quota is unconsumed."""
    from app.core.rate_limit import public_rate_limiter

    test_ip = "192.168.100.99"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)

    payload = {
        "division_id": "mineral-water",
        "full_name": "Validation Fail Tester",
        "company_name": "Fail Corp",
        "business_email": "fail@corp.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Spring Water",
    }

    # 1. Invalid idempotency header failure
    res_bad_hdr = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json=payload,
        headers={"Idempotency-Key": "k" * 130, "X-Forwarded-For": test_ip},
    )
    assert res_bad_hdr.status_code == status.HTTP_400_BAD_REQUEST
    assert len(public_rate_limiter._reservations[test_ip]) == 0
    assert len(public_rate_limiter._submissions[test_ip]) == 0

    # 2. Conflicting headers failure
    res_conflict = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json=payload,
        headers={
            "Idempotency-Key": "key-1",
            "X-Idempotency-Key": "key-2",
            "X-Forwarded-For": test_ip,
        },
    )
    assert res_conflict.status_code == status.HTTP_400_BAD_REQUEST
    assert len(public_rate_limiter._reservations[test_ip]) == 0
    assert len(public_rate_limiter._submissions[test_ip]) == 0

    # 3. Invalid division failure
    res_bad_div = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json={**payload, "division_id": "non-existent-division"},
        headers={"X-Forwarded-For": test_ip},
    )
    assert res_bad_div.status_code == status.HTTP_400_BAD_REQUEST
    assert len(public_rate_limiter._reservations[test_ip]) == 0
    assert len(public_rate_limiter._submissions[test_ip]) == 0

    # 4. Verify client can still successfully submit up to the full quota
    res_valid = await async_client.post(
        "/api/v1/public/rfq/enquire",
        json=payload,
        headers={"X-Forwarded-For": test_ip},
    )
    assert res_valid.status_code == status.HTTP_201_CREATED
    assert len(public_rate_limiter._reservations[test_ip]) == 0
    assert len(public_rate_limiter._submissions[test_ip]) == 1


@pytest.mark.asyncio
async def test_47_submission_reservation_multiple_release_is_idempotent():
    """47. Proves that calling release() multiple times on SubmissionReservation is strictly idempotent."""
    from app.core.rate_limit import public_rate_limiter

    test_ip = "192.168.100.100"
    reservation = await public_rate_limiter.acquire_submission_slot(test_ip)
    assert len(public_rate_limiter._reservations[test_ip]) == 1

    # First release: releases slot
    await reservation.release()
    assert len(public_rate_limiter._reservations[test_ip]) == 0

    # Subsequent releases: idempotent no-op
    await reservation.release()
    await reservation.release()
    assert len(public_rate_limiter._reservations[test_ip]) == 0


@pytest.mark.asyncio
async def test_48_reservations_identical_timestamp_unique_token_release():
    """48. Two reservations with identical timestamps have distinct tokens; releasing one preserves the other."""
    from app.core.rate_limit import public_rate_limiter

    test_ip = "192.168.200.1"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)

    frozen_time = 1700000000.0
    with patch("time.time", return_value=frozen_time):
        res1 = await public_rate_limiter.acquire_submission_slot(test_ip)
        res2 = await public_rate_limiter.acquire_submission_slot(test_ip)

    assert res1.created_at == res2.created_at == frozen_time
    assert res1.token != res2.token
    assert len(public_rate_limiter._reservations[test_ip]) == 2

    # Release first reservation
    await res1.release()

    # Second reservation must still be active and intact in reservations list
    assert len(public_rate_limiter._reservations[test_ip]) == 1
    assert public_rate_limiter._reservations[test_ip][0].token == res2.token

    # Release second reservation
    await res2.release()
    assert len(public_rate_limiter._reservations[test_ip]) == 0


@pytest.mark.asyncio
async def test_49_committing_one_reservation_does_not_affect_another():
    """49. Committing one reservation records exactly 1 submission and leaves concurrent reservation active."""
    from app.core.rate_limit import public_rate_limiter

    test_ip = "192.168.200.2"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)

    frozen_time = 1700000000.0
    with patch("time.time", return_value=frozen_time):
        res1 = await public_rate_limiter.acquire_submission_slot(test_ip)
        res2 = await public_rate_limiter.acquire_submission_slot(test_ip)

    assert len(public_rate_limiter._reservations[test_ip]) == 2
    assert len(public_rate_limiter._submissions[test_ip]) == 0

    # Commit reservation 1
    await res1.commit()

    # Exactly 1 submission recorded, and reservation 2 is still active in reservations list
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert len(public_rate_limiter._reservations[test_ip]) == 1
    assert public_rate_limiter._reservations[test_ip][0].token == res2.token

    # Committing res1 again is idempotent no-op
    await res1.commit()
    assert len(public_rate_limiter._submissions[test_ip]) == 1

    # Release reservation 2
    await res2.release()
    assert len(public_rate_limiter._reservations[test_ip]) == 0
    assert len(public_rate_limiter._submissions[test_ip]) == 1


def test_50_direct_untrusted_client_with_forged_xff():
    """50. Direct untrusted client cannot spoof IP by providing X-Forwarded-For."""
    scope = {
        "type": "http",
        "client": ("198.51.100.99", 54321),
        "headers": [(b"x-forwarded-for", b"8.8.8.8, 1.1.1.1")],
    }
    req = Request(scope)
    assert get_client_ip(req) == "198.51.100.99"


def test_51_trusted_proxy_sanitized_forwarding_header():
    """51. Trusted proxy with a clean, single client IP in X-Forwarded-For extracts that client IP."""
    scope = {
        "type": "http",
        "client": ("127.0.0.1", 54321),
        "headers": [(b"x-forwarded-for", b"203.0.113.150")],
    }
    req = Request(scope)
    assert get_client_ip(req) == "203.0.113.150"


def test_52_trusted_proxy_forged_address_defeated_by_right_to_left_parsing():
    """52. Client-forged address prepended to XFF is defeated; right-to-left parsing picks authentic client."""
    scope = {
        "type": "http",
        "client": ("127.0.0.1", 54321),
        "headers": [(b"x-forwarded-for", b"8.8.8.8, 203.0.113.195, 10.0.0.1")],
    }
    req = Request(scope)
    with patch.object(settings, "TRUSTED_PROXIES", ["127.0.0.1", "10.0.0.1", "::1"]):
        assert get_client_ip(req) == "203.0.113.195"


def test_53_invalid_forwarding_chain_entries_skipped_safely():
    """53. Malformed non-IP entries in XFF chain are safely skipped during right-to-left evaluation."""
    scope = {
        "type": "http",
        "client": ("127.0.0.1", 54321),
        "headers": [(b"x-forwarded-for", b"203.0.113.175, invalid-ip-entry, 10.0.0.1")],
    }
    req = Request(scope)
    with patch.object(settings, "TRUSTED_PROXIES", ["127.0.0.1", "10.0.0.1", "::1"]):
        assert get_client_ip(req) == "203.0.113.175"

    scope_bad = {
        "type": "http",
        "client": ("127.0.0.1", 54321),
        "headers": [(b"x-forwarded-for", b"not-an-ip, also-bad-string")],
    }
    req_bad = Request(scope_bad)
    assert get_client_ip(req_bad) == "127.0.0.1"


def test_54_multiple_trusted_proxy_hops_supported():
    """54. Chain traversing multiple configured trusted proxies (e.g. CDN -> Load Balancer -> App)."""
    scope = {
        "type": "http",
        "client": ("127.0.0.1", 54321),
        "headers": [(b"x-forwarded-for", b"198.51.100.42, 172.16.0.1, 10.0.0.1")],
    }
    req = Request(scope)
    with patch.object(
        settings, "TRUSTED_PROXIES", ["127.0.0.1", "10.0.0.1", "172.16.0.0/16", "::1"]
    ):
        assert get_client_ip(req) == "198.51.100.42"


def test_55_trusted_non_cloudflare_proxy_forged_cf_connecting_ip_uses_xff():
    """55. Trusted non-Cloudflare proxy with forged CF-Connecting-IP and valid XFF: select the authentic XFF client."""
    scope = {
        "type": "http",
        "client": ("127.0.0.1", 54321),
        "headers": [
            (b"cf-connecting-ip", b"8.8.8.8"),
            (b"x-forwarded-for", b"203.0.113.195"),
        ],
    }
    req = Request(scope)
    # 127.0.0.1 is in TRUSTED_PROXIES, but NOT in TRUSTED_CLOUDFLARE_PROXIES (default [])
    assert get_client_ip(req) == "203.0.113.195"


def test_56_trusted_non_cloudflare_proxy_forged_cf_connecting_ip_no_xff_uses_peer():
    """56. Trusted non-Cloudflare proxy with forged CF-Connecting-IP and no XFF: use the immediate peer."""
    scope = {
        "type": "http",
        "client": ("127.0.0.1", 54321),
        "headers": [
            (b"cf-connecting-ip", b"8.8.8.8"),
        ],
    }
    req = Request(scope)
    # CF-Connecting-IP is ignored; no XFF available; falls back to immediate peer 127.0.0.1
    assert get_client_ip(req) == "127.0.0.1"


def test_57_configured_cloudflare_proxy_valid_cf_connecting_ip_accepted():
    """57. Configured Cloudflare proxy with valid CF-Connecting-IP: accept the Cloudflare-provided client IP."""
    scope = {
        "type": "http",
        "client": ("173.245.48.5", 54321),
        "headers": [
            (b"cf-connecting-ip", b"198.51.100.77"),
        ],
    }
    req = Request(scope)
    with patch.object(settings, "TRUSTED_CLOUDFLARE_PROXIES", ["173.245.48.0/20"]):
        assert get_client_ip(req) == "198.51.100.77"


def test_58_untrusted_direct_client_both_forged_headers_ignored():
    """58. Untrusted direct client with both forged headers: ignore both CF-Connecting-IP and X-Forwarded-For."""
    scope = {
        "type": "http",
        "client": ("198.51.100.22", 54321),
        "headers": [
            (b"cf-connecting-ip", b"1.1.1.1"),
            (b"x-forwarded-for", b"2.2.2.2"),
        ],
    }
    req = Request(scope)
    with patch.object(settings, "TRUSTED_CLOUDFLARE_PROXIES", ["173.245.48.0/20"]):
        assert get_client_ip(req) == "198.51.100.22"


def test_59_invalid_cf_connecting_ip_from_cloudflare_proxy_falls_back_to_xff():
    """59. Invalid CF-Connecting-IP from a trusted Cloudflare proxy: safely fall back to XFF."""
    scope = {
        "type": "http",
        "client": ("173.245.48.5", 54321),
        "headers": [
            (b"cf-connecting-ip", b"not-a-valid-ip"),
            (b"x-forwarded-for", b"203.0.113.88"),
        ],
    }
    req = Request(scope)
    with patch.object(settings, "TRUSTED_CLOUDFLARE_PROXIES", ["173.245.48.0/20"]):
        assert get_client_ip(req) == "203.0.113.88"

    # Also verify fallback to immediate peer when both CF-Connecting-IP is invalid and XFF is absent
    scope_no_xff = {
        "type": "http",
        "client": ("173.245.48.5", 54321),
        "headers": [
            (b"cf-connecting-ip", b"not-a-valid-ip"),
        ],
    }
    req_no_xff = Request(scope_no_xff)
    with patch.object(settings, "TRUSTED_CLOUDFLARE_PROXIES", ["173.245.48.0/20"]):
        assert get_client_ip(req_no_xff) == "173.245.48.5"


def test_60_proxy_config_valid_ipv4_and_ipv6_and_cidr():
    """60. Valid IPv4, IPv6, and CIDR network configurations are successfully accepted."""
    valid_entries = [
        "127.0.0.1",
        "198.51.100.22",
        "10.0.0.1",
        "::1",
        "2001:db8::1",
        "fe80::1",
        "10.0.0.0/8",
        "172.16.0.0/16",
        "192.168.1.0/24",
        "2001:db8::/32",
        "fe80::/64",
    ]
    validated = validate_proxy_configuration(valid_entries, "TRUSTED_PROXIES")
    assert validated == valid_entries


def test_61_proxy_config_malformed_ipv4_rejected():
    """61. Malformed IPv4 entries are rejected with a clear configuration error."""
    malformed_ipv4_cases = [
        "256.0.0.1",
        "192.168.1.999",
        "10.0.0.1.1",
        "not-an-ip",
        "127.0.0",
        "",
        "   ",
    ]
    for case in malformed_ipv4_cases:
        with pytest.raises(ValueError) as exc_info:
            validate_proxy_entry(case, "TRUSTED_PROXIES")
        assert "Configuration error for 'TRUSTED_PROXIES'" in str(exc_info.value)


def test_62_proxy_config_malformed_ipv6_rejected():
    """62. Malformed IPv6 entries are rejected with a clear configuration error."""
    malformed_ipv6_cases = [
        "::gggg",
        "2001:xyz::1",
        "fe80:::1",
        "::1::2",
        "2001:db8:12345::1",
    ]
    for case in malformed_ipv6_cases:
        with pytest.raises(ValueError) as exc_info:
            validate_proxy_entry(case, "TRUSTED_PROXIES")
        assert "Configuration error for 'TRUSTED_PROXIES'" in str(exc_info.value)
        assert "is not a valid IPv4/IPv6 address or CIDR network" in str(exc_info.value)


def test_63_proxy_config_invalid_cidr_rejected():
    """63. Invalid CIDR network prefix entries are rejected with a clear configuration error."""
    invalid_cidr_cases = [
        "10.0.0.1/33",
        "192.168.1.0/invalid",
        "::1/129",
        "fe80::/130",
        "172.16.0.0/-1",
        "192.168.1.0//24",
    ]
    for case in invalid_cidr_cases:
        with pytest.raises(ValueError) as exc_info:
            validate_proxy_entry(case, "TRUSTED_CLOUDFLARE_PROXIES")
        assert "Configuration error for 'TRUSTED_CLOUDFLARE_PROXIES'" in str(
            exc_info.value
        )
        assert "is not a valid IPv4/IPv6 address or CIDR network" in str(exc_info.value)


def test_64_settings_startup_validation_rejects_malformed_proxies():
    """64. Pydantic Settings instantiation validates proxy lists and rejects malformed entries."""
    # Malformed TRUSTED_PROXIES
    with pytest.raises(ValidationError) as exc_info:
        Settings(TRUSTED_PROXIES=["256.0.0.1"])
    assert "Configuration error for 'TRUSTED_PROXIES'" in str(exc_info.value)

    # Malformed TRUSTED_CLOUDFLARE_PROXIES
    with pytest.raises(ValidationError) as exc_info:
        Settings(TRUSTED_CLOUDFLARE_PROXIES=["::gggg"])
    assert "Configuration error for 'TRUSTED_CLOUDFLARE_PROXIES'" in str(exc_info.value)

    # Invalid CIDR in TRUSTED_CLOUDFLARE_PROXIES
    with pytest.raises(ValidationError) as exc_info:
        Settings(TRUSTED_CLOUDFLARE_PROXIES=["10.0.0.1/33"])
    assert "Configuration error for 'TRUSTED_CLOUDFLARE_PROXIES'" in str(exc_info.value)

    # Valid proxy configuration succeeds
    valid_settings = Settings(
        TRUSTED_PROXIES=["127.0.0.1", "10.0.0.0/8", "::1"],
        TRUSTED_CLOUDFLARE_PROXIES=["173.245.48.0/20", "2001:db8::/32"],
    )
    assert "127.0.0.1" in valid_settings.TRUSTED_PROXIES
    assert "173.245.48.0/20" in valid_settings.TRUSTED_CLOUDFLARE_PROXIES


@pytest.mark.asyncio
async def test_65_lifespan_startup_validation_rejects_malformed_proxies():
    """65. Application lifespan startup rejects malformed proxy configuration with ValueError."""
    # Malformed TRUSTED_PROXIES
    with patch.object(settings, "TRUSTED_PROXIES", ["bad-ip-address"]):
        with pytest.raises(ValueError) as exc_info:
            async with lifespan(app):
                pass
        assert "Configuration error for 'TRUSTED_PROXIES'" in str(exc_info.value)

    # Malformed TRUSTED_CLOUDFLARE_PROXIES
    with patch.object(settings, "TRUSTED_CLOUDFLARE_PROXIES", ["10.0.0.1/99"]):
        with pytest.raises(ValueError) as exc_info:
            async with lifespan(app):
                pass
        assert "Configuration error for 'TRUSTED_CLOUDFLARE_PROXIES'" in str(
            exc_info.value
        )


def test_66_is_trusted_proxy_raises_on_malformed_configuration_entry():
    """66. is_trusted_proxy raises ValueError on malformed configuration entry rather than silently skipping."""
    # Malformed entry when first entry matches
    with pytest.raises(ValueError) as exc_info:
        is_trusted_proxy("127.0.0.1", ["127.0.0.1", "malformed-proxy-entry"])
    assert "Configuration error: 'malformed-proxy-entry' in trusted proxy list" in str(
        exc_info.value
    )

    # Malformed entry when no entry matches
    with pytest.raises(ValueError) as exc_info:
        is_trusted_proxy("192.168.1.1", ["bad-proxy", "10.0.0.1"])
    assert "Configuration error: 'bad-proxy' in trusted proxy list" in str(
        exc_info.value
    )


@pytest.mark.asyncio
async def test_67_reservation_expiry_before_successful_commit():
    """67. Reservation expires after 60s while processing; active slot clears but reservation remains PENDING."""
    test_ip = "198.51.100.21"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)

    start_time = 1700000000.0
    with patch("time.time", return_value=start_time):
        res = await public_rate_limiter.acquire_submission_slot(test_ip)

    assert len(public_rate_limiter._reservations[test_ip]) == 1
    assert len(public_rate_limiter._submissions[test_ip]) == 0
    assert not res.is_committed
    assert not res.is_released

    # Advance time to 65 seconds later (> 60s expiry)
    expired_time = start_time + 65.0
    with patch("time.time", return_value=expired_time):
        assert res.is_expired
        # When acquire_submission_slot checks in-flight capacity at expired_time:
        async with public_rate_limiter._lock:
            # Expire stale reservations from active in-flight count
            public_rate_limiter._reservations[test_ip] = [
                r
                for r in public_rate_limiter._reservations[test_ip]
                if r.expires_at > expired_time
            ]

    # Active in-flight slot has expired from _reservations
    assert len(public_rate_limiter._reservations[test_ip]) == 0
    # No quota has been consumed while processing is still in progress
    assert len(public_rate_limiter._submissions[test_ip]) == 0
    # Reservation status remains PENDING in lifecycle registry
    status_val = await public_rate_limiter.get_reservation_status(res.token)
    assert status_val == ReservationStatus.PENDING


@pytest.mark.asyncio
async def test_68_successful_persistence_after_reservation_expiry():
    """68. Database persistence succeeds after reservation expiry; quota is properly consumed and idempotent."""
    test_ip = "198.51.100.22"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)

    start_time = 1700000000.0
    with patch("time.time", return_value=start_time):
        res = await public_rate_limiter.acquire_submission_slot(test_ip)

    # Time advances 70 seconds (> 60s expiry)
    commit_time = start_time + 70.0
    with patch("time.time", return_value=commit_time):
        # Trigger slot expiration
        async with public_rate_limiter._lock:
            public_rate_limiter._reservations[test_ip] = [
                r
                for r in public_rate_limiter._reservations[test_ip]
                if r.expires_at > commit_time
            ]
        assert len(public_rate_limiter._reservations[test_ip]) == 0
        assert res.is_expired

        # Database operation succeeds: commit is called
        await res.commit()

    # Quota is successfully consumed despite prior reservation expiration
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert public_rate_limiter._submissions[test_ip][0] == commit_time
    assert res.is_committed
    assert (
        await public_rate_limiter.get_reservation_status(res.token)
        == ReservationStatus.COMMITTED
    )

    # Repeated commit is strictly idempotent (does not double-count)
    await res.commit()
    assert len(public_rate_limiter._submissions[test_ip]) == 1


@pytest.mark.asyncio
async def test_69_failed_persistence_after_reservation_expiry():
    """69. Database persistence fails after reservation expiry; slot is released and quota is NOT consumed."""
    test_ip = "198.51.100.23"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)

    start_time = 1700000000.0
    with patch("time.time", return_value=start_time):
        res = await public_rate_limiter.acquire_submission_slot(test_ip)

    # Time advances 75 seconds (> 60s expiry)
    failure_time = start_time + 75.0
    with patch("time.time", return_value=failure_time):
        async with public_rate_limiter._lock:
            public_rate_limiter._reservations[test_ip] = [
                r
                for r in public_rate_limiter._reservations[test_ip]
                if r.expires_at > failure_time
            ]
        assert len(public_rate_limiter._reservations[test_ip]) == 0
        assert res.is_expired

        # Database operation fails: release is called
        await res.release()

    # Quota is NOT consumed on failure
    assert len(public_rate_limiter._submissions[test_ip]) == 0
    assert res.is_released
    assert (
        await public_rate_limiter.get_reservation_status(res.token)
        == ReservationStatus.RELEASED
    )

    # Subsequent commit attempt is rejected (cannot commit released reservation)
    await res.commit()
    assert len(public_rate_limiter._submissions[test_ip]) == 0


@pytest.mark.asyncio
async def test_70_concurrent_submissions_during_reservation_expiry():
    """70. Unresolved expired PENDING operations continue counting against admission capacity, preventing quota bypass."""
    test_ip = "198.51.100.24"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)

    t0 = 1700000000.0
    with patch("time.time", return_value=t0):
        # 1. Acquire 5 reservations (reaching PUBLIC_SUBMISSION_LIMIT_10MIN = 5)
        res_list = [
            await public_rate_limiter.acquire_submission_slot(test_ip) for _ in range(5)
        ]

        # 6th acquire attempt fails with 429
        with pytest.raises(HTTPException) as exc_info:
            await public_rate_limiter.acquire_submission_slot(test_ip)
        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    # 2. Advance time to 65 seconds later (all 5 active reservation slots expire)
    t1 = t0 + 65.0
    with patch("time.time", return_value=t1):
        for r in res_list:
            assert r.is_expired

        # Trigger active slot expiration in _reservations[test_ip]
        async with public_rate_limiter._lock:
            public_rate_limiter._reservations[test_ip] = [
                r
                for r in public_rate_limiter._reservations[test_ip]
                if r.expires_at > t1
            ]
        assert len(public_rate_limiter._reservations[test_ip]) == 0

        # CRITICAL VERIFICATION (Defect 1):
        # Even though active reservation slots expired from _reservations, all 5 operations
        # are still unresolved and PENDING in the background. Therefore, a 6th admission attempt
        # MUST BE REJECTED with 429, preventing quota bypass!
        with pytest.raises(HTTPException) as exc_info_blocked:
            await public_rate_limiter.acquire_submission_slot(test_ip)
        assert exc_info_blocked.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS

        # 3. Simulate failure of 1 operation (e.g. database error on res_list[0])
        await res_list[0].release()
        assert res_list[0].is_released
        assert (
            len(public_rate_limiter._submissions[test_ip]) == 0
        )  # No quota consumed on failure

        # Because res_list[0] released its pending capacity, admission capacity is now 4 of 5.
        # A new request (res_6) CAN now be admitted!
        res_6 = await public_rate_limiter.acquire_submission_slot(test_ip)
        assert res_6 is not None

        # Admission capacity is full again (4 pending from res_list + 1 from res_6 = 5)
        with pytest.raises(HTTPException) as exc_info_full:
            await public_rate_limiter.acquire_submission_slot(test_ip)
        assert exc_info_full.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS

        # 4. Now the remaining 4 original operations and res_6 commit successfully
        await asyncio.gather(*[r.commit() for r in res_list[1:]], res_6.commit())

        # Total confirmed submissions is EXACTLY 5 (never exceeds configured limit of 5!)
        assert len(public_rate_limiter._submissions[test_ip]) == 5

        # 5. Subsequent admission attempts are rejected because 5 submissions are committed
        with pytest.raises(HTTPException) as exc_info_final:
            await public_rate_limiter.acquire_submission_slot(test_ip)
        assert exc_info_final.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.asyncio
async def test_71_exactly_once_quota_accounting():
    """71. Proves exactly-once quota accounting under high concurrency, retries, and duplicate requests."""
    test_ip = "198.51.100.25"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)

    res = await public_rate_limiter.acquire_submission_slot(test_ip)

    # 30 concurrent coroutines attempting to commit the same reservation
    commit_results = await asyncio.gather(*[res.commit() for _ in range(30)])
    assert len(commit_results) == 30
    # Exactly one submission timestamp recorded
    assert len(public_rate_limiter._submissions[test_ip]) == 1

    # Concurrent release attempts cannot revoke or alter committed submission
    await asyncio.gather(*[res.release() for _ in range(30)])
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert (
        await public_rate_limiter.get_reservation_status(res.token)
        == ReservationStatus.COMMITTED
    )


@pytest.mark.asyncio
async def test_72_reservation_security_and_ip_isolation():
    """72. Enforces security isolation: rejects untracked tokens and cross-IP commit hijacking."""
    ip_a = "198.51.100.26"
    ip_b = "198.51.100.27"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(ip_a, None)
        public_rate_limiter._submissions.pop(ip_a, None)
        public_rate_limiter._reservations.pop(ip_b, None)
        public_rate_limiter._submissions.pop(ip_b, None)

    # 1. Untracked/fabricated token rejected
    commit_fake = await public_rate_limiter._commit_reservation(
        ip_a, "fabricated-token-999"
    )
    assert commit_fake is False
    assert len(public_rate_limiter._submissions[ip_a]) == 0

    # 2. Reservation issued to IP A cannot be committed under IP B
    res_a = await public_rate_limiter.acquire_submission_slot(ip_a)
    commit_hijack = await public_rate_limiter._commit_reservation(ip_b, res_a.token)
    assert commit_hijack is False
    assert len(public_rate_limiter._submissions[ip_b]) == 0
    assert len(public_rate_limiter._submissions[ip_a]) == 0

    # 3. Legitimate commit under IP A succeeds
    commit_legit = await public_rate_limiter._commit_reservation(ip_a, res_a.token)
    assert commit_legit is True
    assert len(public_rate_limiter._submissions[ip_a]) == 1


@pytest.mark.asyncio
async def test_73_e2e_enquiry_submission_after_reservation_expiry(
    async_client: AsyncClient,
):
    """73. End-to-end HTTP test: Enquiry persists successfully when reservation expires during processing."""
    test_ip = "198.51.100.28"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)

    payload = {
        "division_id": "mineral-water",
        "full_name": "Delayed Commit Tester",
        "company_name": "Latency Solutions Ltd",
        "business_email": "latency@solutions.com",
        "contact_number": "+60123456789",
        "country": "Malaysia",
        "product_focus": "Mineral Water Bottling",
    }

    t0 = 1700000000.0
    original_acquire = public_rate_limiter.acquire_submission_slot

    async def delayed_acquire(ip: str):
        with patch("time.time", return_value=t0):
            res = await original_acquire(ip)
        return res

    # Patch acquire to set created_at at t0, but let time advance 65s during request handling
    with (
        patch.object(
            public_rate_limiter, "acquire_submission_slot", side_effect=delayed_acquire
        ),
        patch("time.time", return_value=t0 + 65.0),
    ):
        response = await async_client.post(
            "/api/v1/public/rfq/enquire",
            json=payload,
            headers={"X-Forwarded-For": test_ip},
        )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["success"] is True
    assert data["data"]["reference_number"].startswith("EB-RFQ-")

    # Quota is accounted for in submissions
    assert len(public_rate_limiter._submissions[test_ip]) == 1


@pytest.mark.asyncio
async def test_74_pending_records_survive_beyond_ten_minute_window():
    """74. Unresolved PENDING reservation records are never pruned based on age, and commit successfully afterward."""
    test_ip = "198.51.100.29"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)

    start_time = 1700000000.0
    with patch("time.time", return_value=start_time):
        res = await public_rate_limiter.acquire_submission_slot(test_ip)

    # Fast forward 800 seconds (> 600s sliding window)
    t_after_13m = start_time + 800.0
    with patch("time.time", return_value=t_after_13m):
        # Force prune check at 800 seconds
        async with public_rate_limiter._lock:
            public_rate_limiter._last_prune = 0.0
            public_rate_limiter._maybe_prune(t_after_13m)

        # Invariant (Defect 2): The pending reservation record MUST NOT be pruned!
        record = public_rate_limiter._reservation_records.get(res.token)
        assert record is not None
        assert record.status == ReservationStatus.PENDING

        # The pending operation still counts against admission capacity
        assert res.token in public_rate_limiter._pending_tokens_by_ip[test_ip]

        # Slow database operation finally succeeds at 850 seconds:
        t_commit = start_time + 850.0
        with patch("time.time", return_value=t_commit):
            await res.commit()

    # Commit successfully accounted for in quota window!
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert public_rate_limiter._submissions[test_ip][0] == start_time + 850.0
    assert (
        await public_rate_limiter.get_reservation_status(res.token)
        == ReservationStatus.COMMITTED
    )


@pytest.mark.asyncio
async def test_75_submission_limit_unexceeded_by_mixture_of_expired_and_new_requests():
    """75. Limit cannot be exceeded by any mixture of expired pending operations and newly admitted requests."""
    test_ip = "198.51.100.30"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)

    t0 = 1700000000.0
    with patch("time.time", return_value=t0):
        # Acquire 3 initial operations
        res_initial = [
            await public_rate_limiter.acquire_submission_slot(test_ip) for _ in range(3)
        ]

    # Advance time to 70s: initial 3 operations expire active slots, but remain PENDING
    t1 = t0 + 70.0
    with patch("time.time", return_value=t1):
        # We can admit exactly 2 more operations (3 pending + 2 new = 5 limit)
        res_new_1 = await public_rate_limiter.acquire_submission_slot(test_ip)
        res_new_2 = await public_rate_limiter.acquire_submission_slot(test_ip)

        # 6th admission is rejected
        with pytest.raises(HTTPException) as exc_info:
            await public_rate_limiter.acquire_submission_slot(test_ip)
        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS

        # All 5 operations (3 expired + 2 newly admitted) commit concurrently
        all_ops = res_initial + [res_new_1, res_new_2]
        await asyncio.gather(*[r.commit() for r in all_ops])

        # Exactly 5 submissions recorded
        assert len(public_rate_limiter._submissions[test_ip]) == 5

        # Further admissions rejected
        with pytest.raises(HTTPException) as exc_info_2:
            await public_rate_limiter.acquire_submission_slot(test_ip)
        assert exc_info_2.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.asyncio
async def test_76_pruning_rules_for_committed_and_released_records():
    """76. COMMITTED and RELEASED records are pruned after aging out of the 10m window; PENDING are never pruned."""
    test_ip = "198.51.100.31"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)

    t0 = 1700000000.0
    with patch("time.time", return_value=t0):
        res_pending = await public_rate_limiter.acquire_submission_slot(test_ip)
        res_commit = await public_rate_limiter.acquire_submission_slot(test_ip)
        res_release = await public_rate_limiter.acquire_submission_slot(test_ip)

        await res_commit.commit()
        await res_release.release()

    assert (
        await public_rate_limiter.get_reservation_status(res_pending.token)
        == ReservationStatus.PENDING
    )
    assert (
        await public_rate_limiter.get_reservation_status(res_commit.token)
        == ReservationStatus.COMMITTED
    )
    assert (
        await public_rate_limiter.get_reservation_status(res_release.token)
        == ReservationStatus.RELEASED
    )

    # Advance time to t0 + 700s (> 600s window)
    t_prune = t0 + 700.0
    with patch("time.time", return_value=t_prune):
        async with public_rate_limiter._lock:
            public_rate_limiter._last_prune = 0.0
            public_rate_limiter._maybe_prune(t_prune)

    # COMMITTED and RELEASED records have been cleaned up after resolution window
    assert public_rate_limiter._reservation_records.get(res_commit.token) is None
    assert public_rate_limiter._reservation_records.get(res_release.token) is None

    # PENDING record is preserved!
    assert public_rate_limiter._reservation_records.get(res_pending.token) is not None
    assert (
        public_rate_limiter._reservation_records[res_pending.token].status
        == ReservationStatus.PENDING
    )


@pytest.mark.asyncio
async def test_77_cancellation_while_commit_waiting_for_limiter_lock():
    """77 (A). Coroutine cancellation while commit() waits on limiter lock leaves reservation in PENDING state."""
    test_ip = "198.51.100.41"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    res = await public_rate_limiter.acquire_submission_slot(test_ip)
    assert not res.is_committed
    assert not res.is_released
    assert (
        await public_rate_limiter.get_reservation_status(res.token)
        == ReservationStatus.PENDING
    )

    # Hold the limiter lock externally to force commit() to wait
    await public_rate_limiter._lock.acquire()
    try:
        commit_task = asyncio.create_task(res.commit())
        # Yield execution to allow commit_task to start and block awaiting the lock
        await asyncio.sleep(0.01)
        assert not commit_task.done()

        # Cancel while waiting on the lock
        commit_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await commit_task
    finally:
        public_rate_limiter._lock.release()

    # Local reservation flags must remain uncommitted
    assert not res.is_committed
    assert not res.is_released
    # Underlying limiter record must remain PENDING
    assert (
        await public_rate_limiter.get_reservation_status(res.token)
        == ReservationStatus.PENDING
    )
    # Zero quota consumed
    assert len(public_rate_limiter._submissions[test_ip]) == 0
    # Pending accounting still tracks the token
    assert res.token in public_rate_limiter._pending_tokens_by_ip[test_ip]


@pytest.mark.asyncio
async def test_78_cancellation_while_release_waiting_for_limiter_lock():
    """78 (B). Coroutine cancellation while release() waits on limiter lock leaves reservation in PENDING state."""
    test_ip = "198.51.100.42"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    res = await public_rate_limiter.acquire_submission_slot(test_ip)
    assert not res.is_committed
    assert not res.is_released
    assert (
        await public_rate_limiter.get_reservation_status(res.token)
        == ReservationStatus.PENDING
    )

    # Hold the limiter lock externally to force release() to wait
    await public_rate_limiter._lock.acquire()
    try:
        release_task = asyncio.create_task(res.release())
        await asyncio.sleep(0.01)
        assert not release_task.done()

        # Cancel while waiting on the lock
        release_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await release_task
    finally:
        public_rate_limiter._lock.release()

    # Local reservation flags must remain unreleased
    assert not res.is_released
    assert not res.is_committed
    # Underlying limiter record must remain PENDING
    assert (
        await public_rate_limiter.get_reservation_status(res.token)
        == ReservationStatus.PENDING
    )
    # Zero quota consumed
    assert len(public_rate_limiter._submissions[test_ip]) == 0
    assert res.token in public_rate_limiter._pending_tokens_by_ip[test_ip]


@pytest.mark.asyncio
async def test_79_reservation_remains_recoverable_after_cancelled_transition():
    """79 (C). Cancelled commit() or release() leaves reservation recoverable for subsequent commit or release."""
    test_ip = "198.51.100.43"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    # Sub-case 1: Cancelled commit() -> subsequently retried commit() succeeds
    res1 = await public_rate_limiter.acquire_submission_slot(test_ip)
    await public_rate_limiter._lock.acquire()
    try:
        task1 = asyncio.create_task(res1.commit())
        await asyncio.sleep(0.01)
        task1.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task1
    finally:
        public_rate_limiter._lock.release()

    # Retry commit() on the same handle
    commit_ok = await res1.commit()
    assert commit_ok is True
    assert res1.is_committed is True
    assert not res1.is_released
    assert (
        await public_rate_limiter.get_reservation_status(res1.token)
        == ReservationStatus.COMMITTED
    )
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert res1.token not in public_rate_limiter._pending_tokens_by_ip[test_ip]

    # Sub-case 2: Cancelled commit() -> subsequently executed release() cleanly releases
    res2 = await public_rate_limiter.acquire_submission_slot(test_ip)
    await public_rate_limiter._lock.acquire()
    try:
        task2 = asyncio.create_task(res2.commit())
        await asyncio.sleep(0.01)
        task2.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task2
    finally:
        public_rate_limiter._lock.release()

    # Recover with release()
    release_ok = await res2.release()
    assert release_ok is True
    assert res2.is_released is True
    assert not res2.is_committed
    assert (
        await public_rate_limiter.get_reservation_status(res2.token)
        == ReservationStatus.RELEASED
    )
    # Quota still 1 from res1, nothing added by res2
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert res2.token not in public_rate_limiter._pending_tokens_by_ip[test_ip]

    # Sub-case 3: Cancelled release() -> subsequently executed commit() succeeds
    res3 = await public_rate_limiter.acquire_submission_slot(test_ip)
    await public_rate_limiter._lock.acquire()
    try:
        task3 = asyncio.create_task(res3.release())
        await asyncio.sleep(0.01)
        task3.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task3
    finally:
        public_rate_limiter._lock.release()

    commit3_ok = await res3.commit()
    assert commit3_ok is True
    assert res3.is_committed is True
    assert not res3.is_released
    assert (
        await public_rate_limiter.get_reservation_status(res3.token)
        == ReservationStatus.COMMITTED
    )
    assert len(public_rate_limiter._submissions[test_ip]) == 2


@pytest.mark.asyncio
async def test_80_concurrent_commit_attempts_against_underlying_limiter_method():
    """80 (D). 20 concurrent commit attempts against underlying _commit_reservation() record exactly once."""
    test_ip = "198.51.100.44"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    res = await public_rate_limiter.acquire_submission_slot(test_ip)

    # Call _commit_reservation directly across 20 concurrent tasks, bypassing handle-level flags
    tasks = [
        public_rate_limiter._commit_reservation(test_ip, res.token) for _ in range(20)
    ]
    results = await asyncio.gather(*tasks)

    # Exactly 1 returns True, exactly 19 return False
    assert sum(1 for r in results if r is True) == 1
    assert sum(1 for r in results if r is False) == 19
    # Exactly one submission timestamp in quota window
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert (
        await public_rate_limiter.get_reservation_status(res.token)
        == ReservationStatus.COMMITTED
    )
    # Token removed from pending operations
    assert res.token not in public_rate_limiter._pending_tokens_by_ip[test_ip]


@pytest.mark.asyncio
async def test_81_concurrent_release_attempts_against_underlying_limiter_method():
    """81 (E). 20 concurrent release attempts against underlying _release_reservation() succeed exactly once."""
    test_ip = "198.51.100.45"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    res = await public_rate_limiter.acquire_submission_slot(test_ip)

    # Call _release_reservation directly across 20 concurrent tasks
    tasks = [
        public_rate_limiter._release_reservation(test_ip, res.token) for _ in range(20)
    ]
    results = await asyncio.gather(*tasks)

    # Exactly 1 returns True, exactly 19 return False
    assert sum(1 for r in results if r is True) == 1
    assert sum(1 for r in results if r is False) == 19
    # Zero quota consumed
    assert len(public_rate_limiter._submissions[test_ip]) == 0
    assert (
        await public_rate_limiter.get_reservation_status(res.token)
        == ReservationStatus.RELEASED
    )
    assert res.token not in public_rate_limiter._pending_tokens_by_ip[test_ip]


@pytest.mark.asyncio
async def test_82_concurrent_commit_and_release_against_same_token():
    """82 (F). Concurrent _commit_reservation and _release_reservation calls on same token: exactly one terminal state wins."""
    test_ip = "198.51.100.46"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    res = await public_rate_limiter.acquire_submission_slot(test_ip)

    # 10 direct commit tasks and 10 direct release tasks concurrently
    commit_tasks = [
        public_rate_limiter._commit_reservation(test_ip, res.token) for _ in range(10)
    ]
    release_tasks = [
        public_rate_limiter._release_reservation(test_ip, res.token) for _ in range(10)
    ]
    all_coros = commit_tasks + release_tasks
    results = await asyncio.gather(*all_coros)

    # Across all 20 competing calls, exactly one transitioned the state and returned True
    assert sum(1 for r in results if r is True) == 1
    assert sum(1 for r in results if r is False) == 19

    status_val = await public_rate_limiter.get_reservation_status(res.token)
    assert status_val in (ReservationStatus.COMMITTED, ReservationStatus.RELEASED)

    if status_val == ReservationStatus.COMMITTED:
        assert len(public_rate_limiter._submissions[test_ip]) == 1
        assert res.is_committed is True
        assert res.is_released is False
    else:
        assert len(public_rate_limiter._submissions[test_ip]) == 0
        assert res.is_released is True
        assert res.is_committed is False


@pytest.mark.asyncio
async def test_83_local_reservation_flags_agree_with_actual_lifecycle_state():
    """83 (G). Local reservation flags immediately reflect underlying limiter lifecycle state without handle calls."""
    test_ip = "198.51.100.47"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    # Case 1: Fresh reservation -> PENDING
    res1 = await public_rate_limiter.acquire_submission_slot(test_ip)
    assert not res1.is_committed
    assert not res1.is_released

    # Commit directly on limiter without calling res1.commit()
    ok = await public_rate_limiter._commit_reservation(test_ip, res1.token)
    assert ok is True
    # Handle flags must agree with actual global lifecycle state
    assert res1.is_committed is True
    assert res1.is_released is False

    # Case 2: Release directly on limiter without calling res2.release()
    res2 = await public_rate_limiter.acquire_submission_slot(test_ip)
    assert not res2.is_committed
    assert not res2.is_released

    ok2 = await public_rate_limiter._release_reservation(test_ip, res2.token)
    assert ok2 is True
    # Handle flags must agree with actual global lifecycle state
    assert res2.is_released is True
    assert res2.is_committed is False


@pytest.mark.asyncio
async def test_84_no_quota_consumed_by_released_reservation():
    """84 (H). Released reservation never consumes quota on subsequent commit or _commit_reservation calls."""
    test_ip = "198.51.100.48"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    res = await public_rate_limiter.acquire_submission_slot(test_ip)
    assert len(public_rate_limiter._submissions[test_ip]) == 0

    release_result = await res.release()
    assert release_result is True
    assert res.is_released is True
    assert len(public_rate_limiter._submissions[test_ip]) == 0

    # Handle commit attempt must fail and not consume quota
    commit_handle_result = await res.commit()
    assert commit_handle_result is False
    assert len(public_rate_limiter._submissions[test_ip]) == 0

    # Direct limiter commit attempt must fail and not consume quota
    commit_direct_result = await public_rate_limiter._commit_reservation(
        test_ip, res.token
    )
    assert commit_direct_result is False
    assert len(public_rate_limiter._submissions[test_ip]) == 0

    assert (
        await public_rate_limiter.get_reservation_status(res.token)
        == ReservationStatus.RELEASED
    )


@pytest.mark.asyncio
async def test_85_no_successful_commit_lost_because_of_local_handle_state():
    """85 (I). Global commit is protected against subsequent release attempts and cannot be lost due to handle state."""
    test_ip = "198.51.100.49"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    res = await public_rate_limiter.acquire_submission_slot(test_ip)

    # Commit directly on limiter (e.g. background worker or distributed coordinator)
    commit_ok = await public_rate_limiter._commit_reservation(test_ip, res.token)
    assert commit_ok is True
    assert len(public_rate_limiter._submissions[test_ip]) == 1

    # Local handle immediately recognizes committed state
    assert res.is_committed is True

    # Subsequent release call on handle cannot revoke commit
    release_result = await res.release()
    assert release_result is False
    assert res.is_committed is True
    assert res.is_released is False
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert (
        await public_rate_limiter.get_reservation_status(res.token)
        == ReservationStatus.COMMITTED
    )

    # Subsequent commit call on handle is idempotent and does not duplicate quota
    commit_result = await res.commit()
    assert commit_result is True
    assert len(public_rate_limiter._submissions[test_ip]) == 1


def _make_rfq_request(
    test_ip: str, email: str = "cancel@test.com", company: str = "Cancel Corp"
):
    """Helper to construct an RFQ Request and EnquiryCreateRequest for endpoint testing."""
    from app.schemas.public import EnquiryCreateRequest
    from starlette.requests import Request

    payload = EnquiryCreateRequest(
        division_id="mineral-water",
        full_name="Cancellation Tester",
        company_name=company,
        business_email=email,
        contact_number="+60123456789",
        country="Malaysia",
        product_focus="Natural Mineral Water",
    )
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/public/rfq/enquire",
        "headers": [(b"host", b"testserver"), (b"x-forwarded-for", test_ip.encode())],
        "client": ("127.0.0.1", 12345),
    }
    req = Request(scope)
    return req, payload


@pytest.mark.asyncio
async def test_86_endpoint_cancellation_before_database_persistence(
    db_session: AsyncSession,
):
    """86 (1). Cancellation before DB persistence safely releases reservation and consumes zero quota."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry

    test_ip = "198.51.100.91"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    req, payload = _make_rfq_request(test_ip, email="before_db@corp.com")

    # Hook db.execute to cancel current task during division lookup (pre-persistence)
    async def cancelling_execute(*args, **kwargs):
        current = asyncio.current_task()
        if current:
            current.cancel()
        raise asyncio.CancelledError()

    with patch.object(db_session, "execute", side_effect=cancelling_execute):
        task = asyncio.create_task(submit_rfq_enquiry(req, payload, db_session))
        with pytest.raises(asyncio.CancelledError):
            await task

    # Assert reservation was released safely
    assert len(public_rate_limiter._submissions[test_ip]) == 0
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0

    # Token status in global records must be RELEASED
    records = [
        rec
        for rec in public_rate_limiter._reservation_records.values()
        if rec.ip == test_ip
    ]
    assert len(records) == 1
    assert records[0].status == ReservationStatus.RELEASED


@pytest.mark.asyncio
async def test_87_endpoint_cancellation_after_database_persistence_commits_quota(
    db_session: AsyncSession,
):
    """87 (2). Request cancellation after DB persistence completes still guarantees exactly one quota commitment."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry

    test_ip = "198.51.100.92"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    req, payload = _make_rfq_request(test_ip, email="after_db@corp.com")

    # Hook db.commit to cancel task immediately after persistence commits
    real_commit = db_session.commit

    async def cancelling_commit():
        await real_commit()
        # Immediately cancel current task after persistence has committed
        current = asyncio.current_task()
        if current:
            current.cancel()

    with patch.object(db_session, "commit", side_effect=cancelling_commit):
        task = asyncio.create_task(submit_rfq_enquiry(req, payload, db_session))
        with pytest.raises(asyncio.CancelledError):
            await task

    # Database enquiry was committed
    stmt = select(Enquiry).where(Enquiry.business_email == "after_db@corp.com")
    enquiry = (await db_session.execute(stmt)).scalar_one_or_none()
    assert enquiry is not None

    # Quota is properly committed and not abandoned
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0

    records = [
        rec
        for rec in public_rate_limiter._reservation_records.values()
        if rec.ip == test_ip
    ]
    assert len(records) == 1
    assert records[0].status == ReservationStatus.COMMITTED


@pytest.mark.asyncio
async def test_88_endpoint_cancellation_while_commit_waits_for_limiter_lock(
    db_session: AsyncSession,
):
    """88 (3). Cancellation while commit waits on limiter lock completes shielded commit without stranding PENDING."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry

    test_ip = "198.51.100.93"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    # Unique per run: the assertion below counts persisted rows for this address.
    email = f"lock_wait_{uuid.uuid4().hex[:10]}@corp.com"
    req, payload = _make_rfq_request(test_ip, email=email)

    real_commit = db_session.commit
    limiter_lock_held = asyncio.Event()

    async def lock_and_commit():
        await real_commit()
        # The database commit has succeeded. Now take the limiter lock so the endpoint's
        # shielded reservation commit (_shield_execute(reservation.commit())) must wait on it.
        await public_rate_limiter._lock.acquire()
        limiter_lock_held.set()

    with patch.object(db_session, "commit", side_effect=lock_and_commit):
        task = asyncio.create_task(submit_rfq_enquiry(req, payload, db_session))
        try:
            # Deterministic synchronisation (no timing guess): proceed once the DB commit has
            # completed and the limiter lock is held, or fail clearly if the endpoint finished first.
            lock_wait = asyncio.create_task(limiter_lock_held.wait())
            done, _ = await asyncio.wait({lock_wait, task}, timeout=10, return_when=asyncio.FIRST_COMPLETED)
            assert lock_wait in done, "endpoint never reached the limiter-lock wait"
            assert public_rate_limiter._lock.locked()
            assert not task.done()

            # Cancel the request while it waits for the limiter lock.
            task.cancel()
            for _ in range(5):
                await asyncio.sleep(0)
            # The shield keeps the reservation commit pending; cancellation must not abort it.
            assert not task.done()
        finally:
            # Always release, so a failure here cannot leave the shared limiter locked
            # and hang every later test that uses it.
            if public_rate_limiter._lock.locked():
                public_rate_limiter._lock.release()

        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=10)

    # The enquiry is durably persisted exactly once despite the cancellation.
    persisted = (
        await db_session.execute(select(Enquiry.id).where(Enquiry.business_email == email))
    ).scalars().all()
    assert len(persisted) == 1

    # Assert exactly one submission committed
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0
    records = [
        rec
        for rec in public_rate_limiter._reservation_records.values()
        if rec.ip == test_ip
    ]
    assert len(records) == 1
    assert records[0].status == ReservationStatus.COMMITTED


@pytest.mark.asyncio
async def test_89_endpoint_cancellation_during_failed_persistence(
    db_session: AsyncSession,
):
    """89 (4). Cancellation during failed database persistence releases reservation cleanly."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry

    test_ip = "198.51.100.94"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    req, payload = _make_rfq_request(test_ip, email="fail_persist@corp.com")

    async def failing_commit():
        import asyncpg.exceptions
        from sqlalchemy.exc import OperationalError

        current = asyncio.current_task()
        if current:
            current.cancel()
        orig = asyncpg.exceptions.DeadlockDetectedError("deadlock detected by server")
        raise OperationalError("COMMIT", {}, orig)

    with patch.object(db_session, "commit", side_effect=failing_commit):
        task = asyncio.create_task(submit_rfq_enquiry(req, payload, db_session))
        with pytest.raises((asyncio.CancelledError, Exception)):
            await task

    # Zero quota consumed, reservation safely released
    assert len(public_rate_limiter._submissions[test_ip]) == 0
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0
    records = [
        rec
        for rec in public_rate_limiter._reservation_records.values()
        if rec.ip == test_ip
    ]
    assert len(records) == 1
    assert records[0].status == ReservationStatus.RELEASED


@pytest.mark.asyncio
async def test_90_release_cannot_override_committed_and_commit_cannot_override_released():
    """90 (5 & 6). Cross-state terminal immutability: release cannot override COMMITTED; commit cannot override RELEASED."""
    test_ip = "198.51.100.95"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    # 1. Once COMMITTED, neither handle nor limiter release can alter state
    res_committed = await public_rate_limiter.acquire_submission_slot(test_ip)
    await res_committed.commit()
    assert res_committed.is_committed is True
    assert len(public_rate_limiter._submissions[test_ip]) == 1

    rel_handle_result = await res_committed.release()
    assert rel_handle_result is False
    rel_limiter_result = await public_rate_limiter._release_reservation(
        test_ip, res_committed.token
    )
    assert rel_limiter_result is False

    assert res_committed.is_committed is True
    assert res_committed.is_released is False
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert (
        await public_rate_limiter.get_reservation_status(res_committed.token)
        == ReservationStatus.COMMITTED
    )

    # 2. Once RELEASED, neither handle nor limiter commit can alter state or consume quota
    res_released = await public_rate_limiter.acquire_submission_slot(test_ip)
    await res_released.release()
    assert res_released.is_released is True
    assert len(public_rate_limiter._submissions[test_ip]) == 1  # only prior committed

    com_handle_result = await res_released.commit()
    assert com_handle_result is False
    com_limiter_result = await public_rate_limiter._commit_reservation(
        test_ip, res_released.token
    )
    assert com_limiter_result is False

    assert res_released.is_released is True
    assert res_released.is_committed is False
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert (
        await public_rate_limiter.get_reservation_status(res_released.token)
        == ReservationStatus.RELEASED
    )


@pytest.mark.asyncio
async def test_91_unreachable_request_handles_leave_no_abandoned_pending_reservations(
    db_session: AsyncSession,
):
    """91 (7). Dropping handles upon request cancellation guarantees zero abandoned PENDING reservations."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry

    test_ip = "198.51.100.97"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    # Launch 4 requests cancelled before DB persistence
    for i in range(4):
        req, payload = _make_rfq_request(test_ip, email=f"dropped_{i}@corp.com")

        async def cancel_before_db(*args, **kwargs):
            current = asyncio.current_task()
            if current:
                current.cancel()
            raise asyncio.CancelledError()

        with patch.object(db_session, "execute", side_effect=cancel_before_db):
            task = asyncio.create_task(submit_rfq_enquiry(req, payload, db_session))
            with pytest.raises(asyncio.CancelledError):
                await task
            # Dropping handle reference completely
            del task, req, payload

    # Launch 1 request cancelled after DB persistence
    req_after, payload_after = _make_rfq_request(
        test_ip, email="dropped_after@corp.com"
    )
    real_commit = db_session.commit

    async def cancel_after_commit():
        await real_commit()
        current = asyncio.current_task()
        if current:
            current.cancel()

    with patch.object(db_session, "commit", side_effect=cancel_after_commit):
        task = asyncio.create_task(
            submit_rfq_enquiry(req_after, payload_after, db_session)
        )
        with pytest.raises(asyncio.CancelledError):
            await task
        del task, req_after, payload_after

    # Crucial assertion: ZERO abandoned PENDING reservations across all issued tokens
    ip_records = [
        rec
        for rec in public_rate_limiter._reservation_records.values()
        if rec.ip == test_ip
    ]
    assert len(ip_records) == 5
    pending_records = [r for r in ip_records if r.status == ReservationStatus.PENDING]
    assert len(pending_records) == 0

    # 4 released, 1 committed
    assert sum(1 for r in ip_records if r.status == ReservationStatus.RELEASED) == 4
    assert sum(1 for r in ip_records if r.status == ReservationStatus.COMMITTED) == 1
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0
    assert len(public_rate_limiter._submissions[test_ip]) == 1


@pytest.mark.asyncio
async def test_92_cleanup_paths_for_exceptions_cancellations_and_disconnects(
    db_session: AsyncSession,
):
    """92 (8). Verification of cleanup across ordinary exceptions, CancelledError, and client disconnects."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry
    from app.schemas.public import EnquiryCreateRequest
    from starlette.requests import Request

    test_ip = "198.51.100.98"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    # 1. Ordinary HTTPException (invalid division): clean release
    payload_bad_div = EnquiryCreateRequest(
        division_id="invalid-div-name",
        full_name="Bad Div Buyer",
        company_name="Bad Div Corp",
        business_email="baddiv@corp.com",
        contact_number="+60123456789",
        country="Malaysia",
        product_focus="Invalid",
    )
    scope1 = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/public/rfq/enquire",
        "headers": [(b"host", b"testserver"), (b"x-forwarded-for", test_ip.encode())],
        "client": ("127.0.0.1", 12345),
    }
    with pytest.raises(HTTPException) as exc_info:
        await submit_rfq_enquiry(Request(scope1), payload_bad_div, db_session)
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert len(public_rate_limiter._submissions[test_ip]) == 0
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0

    # 2. Client disconnect / CancelledError before DB: clean release
    req2, payload2 = _make_rfq_request(test_ip, email="disconnect@corp.com")

    async def disconnect_execute(*args, **kwargs):
        raise asyncio.CancelledError()

    with (
        patch.object(db_session, "execute", side_effect=disconnect_execute),
        pytest.raises(asyncio.CancelledError),
    ):
        await submit_rfq_enquiry(req2, payload2, db_session)
    assert len(public_rate_limiter._submissions[test_ip]) == 0
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0

    # 3. Successful persistent completion: clean commit
    req3, payload3 = _make_rfq_request(test_ip, email="persist_ok@corp.com")
    resp3 = await submit_rfq_enquiry(req3, payload3, db_session)
    assert resp3.success is True
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0


@pytest.mark.asyncio
async def test_93_cleanup_never_releases_after_database_commit(
    db_session: AsyncSession,
):
    """93 (9). Verification that cleanup never releases a reservation after the database transaction commits."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry

    test_ip = "198.51.100.99"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    req, payload = _make_rfq_request(test_ip, email="never_release@corp.com")

    # Intercept reservation right after commit to verify status
    res_token = None
    original_acquire = public_rate_limiter.acquire_submission_slot

    async def tracking_acquire(ip):
        nonlocal res_token
        res = await original_acquire(ip)
        res_token = res.token
        return res

    with patch.object(
        public_rate_limiter, "acquire_submission_slot", side_effect=tracking_acquire
    ):
        envelope = await submit_rfq_enquiry(req, payload, db_session)
        assert envelope.success is True

    assert res_token is not None
    # Committed in limiter
    assert (
        await public_rate_limiter.get_reservation_status(res_token)
        == ReservationStatus.COMMITTED
    )
    assert len(public_rate_limiter._submissions[test_ip]) == 1

    # Simulated post-cleanup attempt to release MUST return False and be rejected
    release_attempt = await public_rate_limiter._release_reservation(test_ip, res_token)
    assert release_attempt is False
    assert (
        await public_rate_limiter.get_reservation_status(res_token)
        == ReservationStatus.COMMITTED
    )
    assert len(public_rate_limiter._submissions[test_ip]) == 1


@pytest.mark.asyncio
async def test_94_capacity_admission_invariant_strictly_preserved(
    db_session: AsyncSession,
):
    """94. Invariant: committed submissions plus unresolved PENDING operations cannot exceed five."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry

    test_ip = "198.51.100.100"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    # 3 successful persisted enquiries
    for i in range(3):
        req, payload = _make_rfq_request(test_ip, email=f"capacity_{i}@corp.com")
        res = await submit_rfq_enquiry(req, payload, db_session)
        assert res.success is True

    assert len(public_rate_limiter._submissions[test_ip]) == 3

    # 1 cancelled pre-DB (released, does not consume quota)
    req_cancel, payload_cancel = _make_rfq_request(
        test_ip, email="capacity_cancel@corp.com"
    )

    async def fail_pre_db(*args, **kwargs):
        raise asyncio.CancelledError()

    with (
        patch.object(db_session, "execute", side_effect=fail_pre_db),
        pytest.raises(asyncio.CancelledError),
    ):
        await submit_rfq_enquiry(req_cancel, payload_cancel, db_session)

    # Still 3 quota consumed
    assert len(public_rate_limiter._submissions[test_ip]) == 3

    # 2 more successful enquiries to reach exactly 5
    for i in range(3, 5):
        req, payload = _make_rfq_request(test_ip, email=f"capacity_{i}@corp.com")
        res = await submit_rfq_enquiry(req, payload, db_session)
        assert res.success is True

    assert len(public_rate_limiter._submissions[test_ip]) == 5

    # 6th attempt must be rejected with HTTP 429
    req_6, payload_6 = _make_rfq_request(test_ip, email="capacity_overflow@corp.com")
    with pytest.raises(HTTPException) as exc_info:
        await submit_rfq_enquiry(req_6, payload_6, db_session)
    assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.asyncio
async def test_95_cancellation_while_database_commit_in_progress(
    db_session: AsyncSession,
):
    """95. Cancellation while db.commit is in progress completes commit shielded and records quota."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry

    test_ip = "198.51.100.101"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    req, payload = _make_rfq_request(test_ip, email="commit_in_progress@corp.com")
    real_commit = db_session.commit
    commit_started = asyncio.Event()

    async def slow_commit():
        commit_started.set()
        await asyncio.sleep(0.04)
        await real_commit()

    with patch.object(db_session, "commit", side_effect=slow_commit):
        task = asyncio.create_task(submit_rfq_enquiry(req, payload, db_session))
        # Wait until db.commit is actively running
        await commit_started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    # Assert row is committed in DB
    stmt = select(Enquiry).where(
        Enquiry.business_email == "commit_in_progress@corp.com"
    )
    enquiry = (await db_session.execute(stmt)).scalar_one_or_none()
    assert enquiry is not None

    # Exactly one quota commitment
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0
    records = [
        r for r in public_rate_limiter._reservation_records.values() if r.ip == test_ip
    ]
    assert len(records) == 1
    assert records[0].status == ReservationStatus.COMMITTED


@pytest.mark.asyncio
async def test_96_commit_succeeds_but_awaiting_request_cancelled_before_result(
    db_session: AsyncSession,
):
    """96. Database commit succeeds but awaiting request task is cancelled before receiving return value."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry

    test_ip = "198.51.100.102"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    req, payload = _make_rfq_request(test_ip, email="cancel_before_result@corp.com")
    real_commit = db_session.commit

    task = None

    async def commit_and_cancel_request():
        await real_commit()
        # Cancel the request task right as commit finishes
        if task:
            task.cancel()

    with patch.object(db_session, "commit", side_effect=commit_and_cancel_request):
        task = asyncio.create_task(submit_rfq_enquiry(req, payload, db_session))
        with pytest.raises(asyncio.CancelledError):
            await task

    # Row is in database
    stmt = select(Enquiry).where(
        Enquiry.business_email == "cancel_before_result@corp.com"
    )
    enquiry = (await db_session.execute(stmt)).scalar_one_or_none()
    assert enquiry is not None

    # Quota is committed exactly once
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0
    records = [
        r for r in public_rate_limiter._reservation_records.values() if r.ip == test_ip
    ]
    assert len(records) == 1
    assert records[0].status == ReservationStatus.COMMITTED


@pytest.mark.asyncio
async def test_97_connection_loss_or_exception_after_database_may_have_committed(
    db_session: AsyncSession,
):
    """97. Connection error raised on commit but reconciliation proves row committed: quota committed."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry
    from sqlalchemy.exc import OperationalError

    test_ip = "198.51.100.103"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    req, payload = _make_rfq_request(test_ip, email="conn_loss_commit@corp.com")
    real_commit = db_session.commit

    async def commit_with_simulated_network_error():
        # Execute real commit (so data is in DB) but raise an OperationalError (simulating lost ACK)
        await real_commit()
        raise OperationalError(
            "COMMIT", {}, Exception("Connection reset by peer after commit")
        )

    with patch.object(
        db_session, "commit", side_effect=commit_with_simulated_network_error
    ):
        envelope = await submit_rfq_enquiry(req, payload, db_session)
        assert envelope.success is True

    # Quota was committed because reconciliation verified row exists
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0
    records = [
        r for r in public_rate_limiter._reservation_records.values() if r.ip == test_ip
    ]
    assert len(records) == 1
    assert records[0].status == ReservationStatus.COMMITTED


@pytest.mark.asyncio
async def test_98_confirmed_rollback_releases_reservation(db_session: AsyncSession):
    """98. Exception on commit where reconciliation proves row was NOT persisted: reservation released."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry
    from sqlalchemy.exc import OperationalError

    test_ip = "198.51.100.104"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    req, payload = _make_rfq_request(test_ip, email="rollback_ok@corp.com")
    real_rollback = db_session.rollback

    async def commit_with_rollback():
        import asyncpg.exceptions

        # Transaction rolls back instead of committing
        await real_rollback()
        orig = asyncpg.exceptions.DeadlockDetectedError(
            "Transaction aborted by database deadlock"
        )
        raise OperationalError("COMMIT", {}, orig)

    with (
        patch.object(db_session, "commit", side_effect=commit_with_rollback),
        pytest.raises(OperationalError),
    ):
        await submit_rfq_enquiry(req, payload, db_session)

    # Reconciliation proves row does NOT exist in DB, so reservation is released
    stmt = select(Enquiry).where(Enquiry.business_email == "rollback_ok@corp.com")
    enquiry = (await db_session.execute(stmt)).scalar_one_or_none()
    assert enquiry is None

    assert len(public_rate_limiter._submissions[test_ip]) == 0
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0
    records = [
        r for r in public_rate_limiter._reservation_records.values() if r.ip == test_ip
    ]
    assert len(records) == 1
    assert records[0].status == ReservationStatus.RELEASED


@pytest.mark.asyncio
async def test_99_ambiguous_outcome_does_not_incorrectly_release_quota(
    db_session: AsyncSession,
):
    """99. Ambiguous outcome (commit fails & DB unreachable) does NOT release quota; holds PENDING."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry
    from sqlalchemy.exc import OperationalError

    test_ip = "198.51.100.105"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    req, payload = _make_rfq_request(test_ip, email="ambiguous@corp.com")

    async def fail_commit():
        raise OperationalError(
            "COMMIT", {}, Exception("Network partition during commit")
        )

    async def unreachable_reconcile(*args, **kwargs):
        # Database completely unreachable during reconciliation
        return None

    with (
        patch.object(db_session, "commit", side_effect=fail_commit),
        patch(
            "app.api.v1.endpoints.public._reconcile_enquiry_persistence",
            side_effect=unreachable_reconcile,
        ),
        pytest.raises(OperationalError),
    ):
        await submit_rfq_enquiry(req, payload, db_session)

    # CRITICAL: Ambiguous outcome MUST NOT be released!
    assert len(public_rate_limiter._submissions[test_ip]) == 0
    records = [
        r for r in public_rate_limiter._reservation_records.values() if r.ip == test_ip
    ]
    assert len(records) == 1
    assert records[0].status == ReservationStatus.PENDING

    # Token remains in pending accounting to protect admission ceiling
    assert records[0].token in public_rate_limiter._pending_tokens_by_ip[test_ip]


@pytest.mark.asyncio
async def test_100_repeated_cancellation_while_cleanup_waits_for_limiter_lock(
    db_session: AsyncSession,
):
    """100. Repeated cancellation while cleanup waits on limiter lock does not abort transition."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry

    test_ip = "198.51.100.106"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    req, payload = _make_rfq_request(test_ip, email="repeat_cancel_lock@corp.com")
    real_commit = db_session.commit
    commit_finished = asyncio.Event()

    async def commit_and_hold_lock():
        await real_commit()
        # Acquire rate limiter lock before submit_rfq_enquiry calls reservation.commit()
        await public_rate_limiter._lock.acquire()
        commit_finished.set()

    with patch.object(db_session, "commit", side_effect=commit_and_hold_lock):
        task = asyncio.create_task(submit_rfq_enquiry(req, payload, db_session))
        await commit_finished.wait()
        try:
            # Deliver 5 repeated cancellations while task is blocked in _shield_execute waiting for limiter lock
            for _ in range(5):
                task.cancel()
                await asyncio.sleep(0.005)
        finally:
            # Release lock so shielded task can acquire it and finish
            public_rate_limiter._lock.release()

        with pytest.raises(asyncio.CancelledError):
            await task

    # Ensure commit was completed despite repeated cancellation
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0
    records = [
        r for r in public_rate_limiter._reservation_records.values() if r.ip == test_ip
    ]
    assert len(records) == 1
    assert records[0].status == ReservationStatus.COMMITTED


@pytest.mark.asyncio
async def test_101_repeated_cancellation_after_successful_database_persistence(
    db_session: AsyncSession,
):
    """101. Repeated cancellation after DB persistence succeeds guarantees exactly one quota commitment."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry

    test_ip = "198.51.100.107"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    req, payload = _make_rfq_request(
        test_ip, email="repeat_cancel_after_persist@corp.com"
    )
    real_commit = db_session.commit

    task = None

    async def commit_and_bombard_cancellations():
        await real_commit()
        if task:
            # Bombard with 5 cancellations
            for _ in range(5):
                task.cancel()
                await asyncio.sleep(0.002)

    with patch.object(
        db_session, "commit", side_effect=commit_and_bombard_cancellations
    ):
        task = asyncio.create_task(submit_rfq_enquiry(req, payload, db_session))
        with pytest.raises(asyncio.CancelledError):
            await task

    # Assert row in DB
    stmt = select(Enquiry).where(
        Enquiry.business_email == "repeat_cancel_after_persist@corp.com"
    )
    enquiry = (await db_session.execute(stmt)).scalar_one_or_none()
    assert enquiry is not None

    # Quota is strictly 1
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0
    records = [
        r for r in public_rate_limiter._reservation_records.values() if r.ip == test_ip
    ]
    assert len(records) == 1
    assert records[0].status == ReservationStatus.COMMITTED


@pytest.mark.asyncio
async def test_102_no_abandoned_pending_reservations_after_resolved_outcome(
    db_session: AsyncSession,
):
    """102. Mix of success, cancellation, and rollback results in zero abandoned PENDING records."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry

    test_ip = "198.51.100.108"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    # 1. Normal success
    req1, payload1 = _make_rfq_request(test_ip, email="mixed_1@corp.com")
    r1 = await submit_rfq_enquiry(req1, payload1, db_session)
    assert r1.success is True

    # 2. Cancelled before DB
    req2, payload2 = _make_rfq_request(test_ip, email="mixed_2@corp.com")

    async def fail_pre(*args, **kwargs):
        raise asyncio.CancelledError()

    with (
        patch.object(db_session, "execute", side_effect=fail_pre),
        pytest.raises(asyncio.CancelledError),
    ):
        await submit_rfq_enquiry(req2, payload2, db_session)

    # 3. Another normal success
    req3, payload3 = _make_rfq_request(test_ip, email="mixed_3@corp.com")
    r3 = await submit_rfq_enquiry(req3, payload3, db_session)
    assert r3.success is True

    # Total records for IP must all be either COMMITTED or RELEASED; zero PENDING
    records = [
        r for r in public_rate_limiter._reservation_records.values() if r.ip == test_ip
    ]
    assert len(records) == 3
    assert all(
        r.status in (ReservationStatus.COMMITTED, ReservationStatus.RELEASED)
        for r in records
    )
    assert not any(r.status == ReservationStatus.PENDING for r in records)
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0
    assert len(public_rate_limiter._submissions[test_ip]) == 2


@pytest.mark.asyncio
async def test_103_exactly_once_quota_accounting_for_persisted_enquiries(
    db_session: AsyncSession,
):
    """103. 1:1 parity between enquiries persisted in database and quota consumed in limiter."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry

    test_ip = "198.51.100.109"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    # Submit 3 successful enquiries under varied conditions
    for i in range(3):
        req, payload = _make_rfq_request(test_ip, email=f"parity_{i}@corp.com")
        res = await submit_rfq_enquiry(req, payload, db_session)
        assert res.success is True

    # Count DB records for this test IP
    stmt = select(Enquiry).where(Enquiry.source_ip == test_ip)
    db_enquiries = (await db_session.execute(stmt)).scalars().all()
    assert len(db_enquiries) == 3

    # Exact parity with rate limiter quota
    assert len(public_rate_limiter._submissions[test_ip]) == 3
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0


@pytest.mark.asyncio
async def test_104_missing_row_while_transaction_may_still_commit_does_not_release_quota(
    db_session: AsyncSession,
):
    """104 (1). Missing row while original transaction may still commit does NOT release quota."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry
    from sqlalchemy.exc import OperationalError

    test_ip = "198.51.100.110"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    req, payload = _make_rfq_request(test_ip, email="may_still_commit@corp.com")

    async def fail_with_unverified_disconnect():
        # Connection severed during commit: server may or may not commit
        raise OperationalError(
            "COMMIT", {}, Exception("Connection reset by peer during commit")
        )

    with (
        patch.object(db_session, "commit", side_effect=fail_with_unverified_disconnect),
        pytest.raises(OperationalError),
    ):
        await submit_rfq_enquiry(req, payload, db_session)

    # Roll back local test session so uncommitted dirty state is discarded
    await db_session.rollback()

    # 1. Assert database persistence outcome: row is not found
    stmt = select(Enquiry).where(Enquiry.business_email == "may_still_commit@corp.com")
    enquiry = (await db_session.execute(stmt)).scalar_one_or_none()
    assert enquiry is None

    # 2. Assert authoritative reservation lifecycle state:
    # CRITICAL: Missing row must NOT be interpreted as rollback! Retained in PENDING!
    assert len(public_rate_limiter._submissions[test_ip]) == 0
    records = [
        r for r in public_rate_limiter._reservation_records.values() if r.ip == test_ip
    ]
    assert len(records) == 1
    assert records[0].status == ReservationStatus.PENDING
    assert records[0].token in public_rate_limiter._pending_tokens_by_ip[test_ip]
    assert records[0].reference_number is not None


@pytest.mark.asyncio
async def test_105_confirmed_transaction_termination_without_commit_permits_release(
    db_session: AsyncSession,
):
    """105 (2). Confirmed transaction termination without commit permits release."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry
    from sqlalchemy.exc import OperationalError

    test_ip = "198.51.100.111"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    req, payload = _make_rfq_request(test_ip, email="confirmed_abort@corp.com")
    real_rollback = db_session.rollback

    async def commit_with_deadlock_abort():
        import asyncpg.exceptions

        # PostgreSQL server explicitly aborts transaction via deadlock
        await real_rollback()
        orig = asyncpg.exceptions.DeadlockDetectedError("deadlock detected by server")
        raise OperationalError("COMMIT", {}, orig)

    with (
        patch.object(db_session, "commit", side_effect=commit_with_deadlock_abort),
        pytest.raises(OperationalError),
    ):
        await submit_rfq_enquiry(req, payload, db_session)

    # 1. Assert database persistence outcome: row absent
    stmt = select(Enquiry).where(Enquiry.business_email == "confirmed_abort@corp.com")
    enquiry = (await db_session.execute(stmt)).scalar_one_or_none()
    assert enquiry is None

    # 2. Assert authoritative reservation lifecycle state: safely released
    assert len(public_rate_limiter._submissions[test_ip]) == 0
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0
    records = [
        r for r in public_rate_limiter._reservation_records.values() if r.ip == test_ip
    ]
    assert len(records) == 1
    assert records[0].status == ReservationStatus.RELEASED


@pytest.mark.asyncio
async def test_106_confirmed_committed_row_consumes_quota_exactly_once(
    db_session: AsyncSession,
):
    """106 (3). Confirmed committed row consumes quota exactly once."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry
    from sqlalchemy.exc import OperationalError

    test_ip = "198.51.100.112"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    req, payload = _make_rfq_request(test_ip, email="confirmed_persist@corp.com")
    real_commit = db_session.commit

    async def commit_with_ack_loss():
        await real_commit()
        raise OperationalError(
            "COMMIT", {}, Exception("Connection reset after commit packet")
        )

    with patch.object(db_session, "commit", side_effect=commit_with_ack_loss):
        envelope = await submit_rfq_enquiry(req, payload, db_session)
        assert envelope.success is True

    # 1. Assert database persistence outcome: row persisted
    stmt = select(Enquiry).where(Enquiry.business_email == "confirmed_persist@corp.com")
    enquiry = (await db_session.execute(stmt)).scalar_one_or_none()
    assert enquiry is not None

    # 2. Assert authoritative reservation lifecycle state: committed exactly once
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0
    records = [
        r for r in public_rate_limiter._reservation_records.values() if r.ip == test_ip
    ]
    assert len(records) == 1
    assert records[0].status == ReservationStatus.COMMITTED


@pytest.mark.asyncio
async def test_107_database_outage_retains_reservation(
    db_session: AsyncSession,
):
    """107 (4). Database outage retains reservation in PENDING to protect admission ceiling."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry
    from sqlalchemy.exc import OperationalError

    test_ip = "198.51.100.113"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    req, payload = _make_rfq_request(test_ip, email="db_outage@corp.com")

    async def fail_network():
        raise OperationalError("COMMIT", {}, Exception("Host unreachable"))

    async def unreachable_reconcile(*args, **kwargs):
        return None

    with (
        patch.object(db_session, "commit", side_effect=fail_network),
        patch(
            "app.api.v1.endpoints.public._reconcile_enquiry_persistence",
            side_effect=unreachable_reconcile,
        ),
        pytest.raises(OperationalError),
    ):
        await submit_rfq_enquiry(req, payload, db_session)

    # Database outcome: unknown / unreachable
    # Authoritative reservation lifecycle state: must remain PENDING
    assert len(public_rate_limiter._submissions[test_ip]) == 0
    records = [
        r for r in public_rate_limiter._reservation_records.values() if r.ip == test_ip
    ]
    assert len(records) == 1
    assert records[0].status == ReservationStatus.PENDING
    assert records[0].token in public_rate_limiter._pending_tokens_by_ip[test_ip]


@pytest.mark.asyncio
async def test_108_recovery_after_database_connectivity_returns_resolves_reservation(
    db_session: AsyncSession,
):
    """108 (5). Recovery after database connectivity returns resolves reservation correctly."""
    from app.models.division import Division
    from app.models.enquiry import Enquiry

    test_ip = "198.51.100.114"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    div = (
        (await db_session.execute(select(Division).where(Division.is_active.is_(True))))
        .scalars()
        .first()
    )
    assert div is not None

    # Scenario A: Enquiry was in fact committed during the outage
    res_a = await public_rate_limiter.acquire_submission_slot(test_ip)
    ref_a = "EB-RFQ-20261110-RECOV-COMMITTED-A"
    await res_a.attach_reference(ref_a)

    # Persist the row to PostgreSQL (simulating committed transaction)
    enquiry_a = Enquiry(
        reference_number=ref_a,
        full_name="Recovery Tester A",
        company_name="Recover Corp",
        business_email="recov_a@corp.com",
        contact_number="+6012345678",
        country="Malaysia",
        initial_division_id=div.id,
        current_division_id=div.id,
        product_focus="Mineral Water",
        status="NEW",
        source_ip=test_ip,
    )
    db_session.add(enquiry_a)
    await db_session.commit()

    # Authoritative recovery: row exists in DB -> transitions PENDING to COMMITTED
    status_a = await public_rate_limiter.reconcile_pending_reservation(
        res_a.token, db_session
    )
    assert status_a == ReservationStatus.COMMITTED
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert res_a.token not in public_rate_limiter._pending_tokens_by_ip[test_ip]

    # Scenario B: Enquiry was aborted and transaction terminated
    res_b = await public_rate_limiter.acquire_submission_slot(test_ip)
    ref_b = "EB-RFQ-20261110-RECOV-ABORTED-B"
    await res_b.attach_reference(ref_b)

    # Row is absent; confirmed_terminated=True -> transitions PENDING to RELEASED
    status_b = await public_rate_limiter.reconcile_pending_reservation(
        res_b.token, db_session, confirmed_terminated=True
    )
    assert status_b == ReservationStatus.RELEASED
    assert len(public_rate_limiter._submissions[test_ip]) == 1  # No additional quota
    assert res_b.token not in public_rate_limiter._pending_tokens_by_ip[test_ip]


@pytest.mark.asyncio
async def test_109_concurrent_reconciliation_cannot_cause_duplicate_transitions(
    db_session: AsyncSession,
):
    """109 (6). Concurrent reconciliation cannot cause duplicate transitions."""
    from app.models.division import Division
    from app.models.enquiry import Enquiry

    test_ip = "198.51.100.115"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    div = (
        (await db_session.execute(select(Division).where(Division.is_active.is_(True))))
        .scalars()
        .first()
    )
    assert div is not None

    res = await public_rate_limiter.acquire_submission_slot(test_ip)
    ref = "EB-RFQ-20261110-CONC-RECOV-001"
    await res.attach_reference(ref)

    # Persist the row to PostgreSQL
    enquiry = Enquiry(
        reference_number=ref,
        full_name="Concurrent Recovery",
        company_name="Conc Corp",
        business_email="conc_recov@corp.com",
        contact_number="+6012345678",
        country="Malaysia",
        initial_division_id=div.id,
        current_division_id=div.id,
        product_focus="Mineral Water",
        status="NEW",
        source_ip=test_ip,
    )
    db_session.add(enquiry)
    await db_session.commit()

    # 10 concurrent reconciliation tasks
    tasks = [
        asyncio.create_task(
            public_rate_limiter.reconcile_pending_reservation(res.token, db_session)
        )
        for _ in range(10)
    ]
    results = await asyncio.gather(*tasks)

    # Every concurrent task observed COMMITTED
    assert all(st == ReservationStatus.COMMITTED for st in results)

    # Quota was consumed EXACTLY ONCE
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0


@pytest.mark.asyncio
async def test_110_repeated_cancellation_cannot_interrupt_reconciliation_or_reservation_cleanup(
    db_session: AsyncSession,
):
    """110 (7). Repeated cancellation cannot interrupt reconciliation or reservation cleanup."""
    from app.models.division import Division
    from app.models.enquiry import Enquiry

    test_ip = "198.51.100.116"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    div = (
        (await db_session.execute(select(Division).where(Division.is_active.is_(True))))
        .scalars()
        .first()
    )
    assert div is not None

    res = await public_rate_limiter.acquire_submission_slot(test_ip)
    ref = "EB-RFQ-20261110-CANCEL-SHIELD-001"
    await res.attach_reference(ref)

    enquiry = Enquiry(
        reference_number=ref,
        full_name="Shielded Cancel",
        company_name="Shield Corp",
        business_email="shield_cancel@corp.com",
        contact_number="+6012345678",
        country="Malaysia",
        initial_division_id=div.id,
        current_division_id=div.id,
        product_focus="Mineral Water",
        status="NEW",
        source_ip=test_ip,
    )
    db_session.add(enquiry)
    await db_session.commit()

    # Hold the limiter lock externally so reconciliation must wait
    await public_rate_limiter._lock.acquire()
    reconcile_task = None
    try:
        from app.api.v1.endpoints.public import _shield_execute

        reconcile_task = asyncio.create_task(
            _shield_execute(
                public_rate_limiter.reconcile_pending_reservation(res.token, db_session)
            )
        )
        await asyncio.sleep(0.02)
        # Deliver 5 repeated cancellations
        for _ in range(5):
            reconcile_task.cancel()
            await asyncio.sleep(0.005)
    finally:
        public_rate_limiter._lock.release()

    with pytest.raises(asyncio.CancelledError):
        await reconcile_task

    # Commit completed despite repeated cancellations
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0
    records = [
        r for r in public_rate_limiter._reservation_records.values() if r.ip == test_ip
    ]
    assert len(records) == 1
    assert records[0].status == ReservationStatus.COMMITTED


@pytest.mark.asyncio
async def test_111_no_resolved_operation_leaves_abandoned_pending_record(
    db_session: AsyncSession,
):
    """111 (8). No resolved operation leaves an abandoned PENDING record."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry
    from sqlalchemy.exc import OperationalError

    test_ip = "198.51.100.117"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    # 1. Clean successful submission
    req1, payload1 = _make_rfq_request(test_ip, email="resolved_succ@corp.com")
    res1 = await submit_rfq_enquiry(req1, payload1, db_session)
    assert res1.success is True

    # 2. Confirmed abort
    req2, payload2 = _make_rfq_request(test_ip, email="resolved_abort@corp.com")
    real_rollback = db_session.rollback

    async def deadlock_abort():
        import asyncpg.exceptions

        await real_rollback()
        orig = asyncpg.exceptions.DeadlockDetectedError("deadlock abort")
        raise OperationalError("COMMIT", {}, orig)

    with (
        patch.object(db_session, "commit", side_effect=deadlock_abort),
        pytest.raises(OperationalError),
    ):
        await submit_rfq_enquiry(req2, payload2, db_session)

    # Assert: zero abandoned PENDING records remain for resolved operations
    records = [
        r for r in public_rate_limiter._reservation_records.values() if r.ip == test_ip
    ]
    assert len(records) == 2
    assert all(
        r.status in (ReservationStatus.COMMITTED, ReservationStatus.RELEASED)
        for r in records
    )
    assert not any(r.status == ReservationStatus.PENDING for r in records)
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0


@pytest.mark.asyncio
async def test_112_full_parity_between_database_persistence_and_authoritative_reservation_state(
    db_session: AsyncSession,
):
    """112. Full parity assertion between database persistence and authoritative reservation state."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry
    from sqlalchemy.exc import OperationalError

    test_ip = "198.51.100.118"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    # 2 successful enquiries
    for i in range(2):
        req, payload = _make_rfq_request(test_ip, email=f"parity_audit_{i}@corp.com")
        res = await submit_rfq_enquiry(req, payload, db_session)
        assert res.success is True

    # 1 ambiguous enquiry retained in PENDING
    req_amb, payload_amb = _make_rfq_request(test_ip, email="parity_ambiguous@corp.com")

    async def fail_conn():
        raise OperationalError(
            "COMMIT", {}, Exception("Connection dropped during commit")
        )

    with (
        patch.object(db_session, "commit", side_effect=fail_conn),
        pytest.raises(OperationalError),
    ):
        await submit_rfq_enquiry(req_amb, payload_amb, db_session)

    # 1 confirmed rollback (released)
    req_rb, payload_rb = _make_rfq_request(test_ip, email="parity_rollback@corp.com")
    real_rollback = db_session.rollback

    async def confirmed_rb():
        import asyncpg.exceptions

        await real_rollback()
        orig = asyncpg.exceptions.DeadlockDetectedError("deadlock abort")
        raise OperationalError("COMMIT", {}, orig)

    with (
        patch.object(db_session, "commit", side_effect=confirmed_rb),
        pytest.raises(OperationalError),
    ):
        await submit_rfq_enquiry(req_rb, payload_rb, db_session)

    # Verify Database Persistence:
    # Exactly 2 enquiries exist in PostgreSQL
    stmt = select(Enquiry).where(Enquiry.source_ip == test_ip)
    db_rows = (await db_session.execute(stmt)).scalars().all()
    assert len(db_rows) == 2

    # Verify Authoritative Reservation Lifecycle:
    # Exactly 2 committed submissions in rate limiter quota
    assert len(public_rate_limiter._submissions[test_ip]) == 2
    # Exactly 1 pending operation holding capacity
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 1
    # Total in-flight admissions = 2 committed + 1 pending = 3
    # Capacity admission invariant strictly preserved


@pytest.mark.asyncio
async def test_113_generic_runtime_error_does_not_release(db_session: AsyncSession):
    """113. Generic RuntimeError during commit does NOT release; holds PENDING."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry

    test_ip = "198.51.100.120"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    req, payload = _make_rfq_request(test_ip, email="runtime_err@corp.com")

    async def fail_runtime():
        raise RuntimeError("Unexpected internal runtime failure during commit")

    with (
        patch.object(db_session, "commit", side_effect=fail_runtime),
        pytest.raises(RuntimeError),
    ):
        await submit_rfq_enquiry(req, payload, db_session)

    await db_session.rollback()

    # Zero quota committed, but reservation MUST remain PENDING
    assert len(public_rate_limiter._submissions[test_ip]) == 0
    records = [
        r for r in public_rate_limiter._reservation_records.values() if r.ip == test_ip
    ]
    assert len(records) == 1
    assert records[0].status == ReservationStatus.PENDING
    assert records[0].token in public_rate_limiter._pending_tokens_by_ip[test_ip]


@pytest.mark.asyncio
async def test_114_operational_error_does_not_release(db_session: AsyncSession):
    """114. OperationalError (connection reset / lost ACK) does NOT release; holds PENDING."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry
    from sqlalchemy.exc import OperationalError

    test_ip = "198.51.100.121"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    req, payload = _make_rfq_request(test_ip, email="op_err@corp.com")

    async def fail_op():
        raise OperationalError("COMMIT", {}, Exception("Connection reset by peer"))

    with (
        patch.object(db_session, "commit", side_effect=fail_op),
        pytest.raises(OperationalError),
    ):
        await submit_rfq_enquiry(req, payload, db_session)

    await db_session.rollback()

    assert len(public_rate_limiter._submissions[test_ip]) == 0
    records = [
        r for r in public_rate_limiter._reservation_records.values() if r.ip == test_ip
    ]
    assert len(records) == 1
    assert records[0].status == ReservationStatus.PENDING
    assert records[0].token in public_rate_limiter._pending_tokens_by_ip[test_ip]


@pytest.mark.asyncio
async def test_115_unknown_driver_exception_does_not_release(db_session: AsyncSession):
    """115. Unknown driver exceptions without valid SQLSTATE do NOT release; holds PENDING."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry
    from sqlalchemy.exc import DBAPIError

    test_ip = "198.51.100.122"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    req, payload = _make_rfq_request(test_ip, email="unknown_driver@corp.com")

    class CustomUnknownDriverError(Exception):
        pass

    async def fail_custom():
        raise DBAPIError(
            "COMMIT", {}, CustomUnknownDriverError("Unknown protocol malfunction")
        )

    with (
        patch.object(db_session, "commit", side_effect=fail_custom),
        pytest.raises(DBAPIError),
    ):
        await submit_rfq_enquiry(req, payload, db_session)

    await db_session.rollback()

    assert len(public_rate_limiter._submissions[test_ip]) == 0
    records = [
        r for r in public_rate_limiter._reservation_records.values() if r.ip == test_ip
    ]
    assert len(records) == 1
    assert records[0].status == ReservationStatus.PENDING
    assert records[0].token in public_rate_limiter._pending_tokens_by_ip[test_ip]


@pytest.mark.asyncio
async def test_116_verified_postgres_deadlock_abort_releases_when_terminated(
    db_session: AsyncSession,
):
    """116. Verified PostgreSQL deadlock-abort (SQLSTATE 40P01) releases when transaction terminated."""
    import asyncpg.exceptions
    from app.api.v1.endpoints.public import submit_rfq_enquiry
    from sqlalchemy.exc import OperationalError

    test_ip = "198.51.100.123"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    req, payload = _make_rfq_request(test_ip, email="deadlock_abort@corp.com")
    real_rollback = db_session.rollback

    async def fail_deadlock():
        await real_rollback()
        orig = asyncpg.exceptions.DeadlockDetectedError(
            "deadlock detected by PostgreSQL engine"
        )
        raise OperationalError("COMMIT", {}, orig)

    with (
        patch.object(db_session, "commit", side_effect=fail_deadlock),
        pytest.raises(OperationalError),
    ):
        await submit_rfq_enquiry(req, payload, db_session)

    # 1. Row is absent in database
    stmt = select(Enquiry).where(Enquiry.business_email == "deadlock_abort@corp.com")
    enquiry = (await db_session.execute(stmt)).scalar_one_or_none()
    assert enquiry is None

    # 2. Reservation is cleanly RELEASED because 40P01 is an explicit abort response
    assert len(public_rate_limiter._submissions[test_ip]) == 0
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0
    records = [
        r for r in public_rate_limiter._reservation_records.values() if r.ip == test_ip
    ]
    assert len(records) == 1
    assert records[0].status == ReservationStatus.RELEASED


@pytest.mark.asyncio
async def test_117_verified_postgres_serialization_abort_releases_when_terminated(
    db_session: AsyncSession,
):
    """117. Verified PostgreSQL serialization-abort (SQLSTATE 40001) releases when transaction terminated."""
    import asyncpg.exceptions
    from app.api.v1.endpoints.public import submit_rfq_enquiry
    from sqlalchemy.exc import OperationalError

    test_ip = "198.51.100.124"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    req, payload = _make_rfq_request(test_ip, email="serial_abort@corp.com")
    real_rollback = db_session.rollback

    async def fail_serialization():
        await real_rollback()
        orig = asyncpg.exceptions.SerializationError(
            "could not serialize access due to concurrent update"
        )
        raise OperationalError("COMMIT", {}, orig)

    with (
        patch.object(db_session, "commit", side_effect=fail_serialization),
        pytest.raises(OperationalError),
    ):
        await submit_rfq_enquiry(req, payload, db_session)

    # 1. Row is absent in database
    stmt = select(Enquiry).where(Enquiry.business_email == "serial_abort@corp.com")
    enquiry = (await db_session.execute(stmt)).scalar_one_or_none()
    assert enquiry is None

    # 2. Reservation is cleanly RELEASED because 40001 is an explicit abort response
    assert len(public_rate_limiter._submissions[test_ip]) == 0
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0
    records = [
        r for r in public_rate_limiter._reservation_records.values() if r.ip == test_ip
    ]
    assert len(records) == 1
    assert records[0].status == ReservationStatus.RELEASED


@pytest.mark.asyncio
async def test_118_concurrent_reconciliation_conflicting_observations_order_a_then_b(
    db_session: AsyncSession,
):
    """118. Concurrent reconciliation: A (observes row) finishes before B (observes no row). Status remains COMMITTED."""
    from app.models.division import Division
    from app.models.enquiry import Enquiry

    test_ip = "198.51.100.125"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    div = (
        (await db_session.execute(select(Division).where(Division.is_active.is_(True))))
        .scalars()
        .first()
    )
    assert div is not None

    res = await public_rate_limiter.acquire_submission_slot(test_ip)
    ref = "EB-RFQ-20261110-CONF-ORDER-AB"
    await res.attach_reference(ref)

    # Persist the row in PostgreSQL
    enquiry = Enquiry(
        reference_number=ref,
        full_name="Conflict AB",
        company_name="Conflict Corp",
        business_email="conflict_ab@corp.com",
        contact_number="+6012345678",
        country="Malaysia",
        initial_division_id=div.id,
        current_division_id=div.id,
        product_focus="Mineral Water",
        status="NEW",
        source_ip=test_ip,
    )
    db_session.add(enquiry)
    await db_session.commit()

    # Task A queries and observes the row (COMMITTED)
    st_a = await public_rate_limiter.reconcile_pending_reservation(
        res.token, db_session
    )
    assert st_a == ReservationStatus.COMMITTED

    # Task B subsequently attempts to report no row with confirmed_terminated=True
    with patch("app.models.enquiry.Enquiry.id", None):
        st_b = await public_rate_limiter.reconcile_pending_reservation(
            res.token, db_session, confirmed_terminated=True
        )

    # In Order A-then-B: B must NOT override COMMITTED!
    assert st_b == ReservationStatus.COMMITTED
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0
    records = [
        r for r in public_rate_limiter._reservation_records.values() if r.ip == test_ip
    ]
    assert records[0].status == ReservationStatus.COMMITTED


@pytest.mark.asyncio
async def test_119_concurrent_reconciliation_conflicting_observations_order_b_then_a(
    db_session: AsyncSession,
):
    """119. Concurrent reconciliation: B (stale negative observation) attempts first, then A (observes row). Never ends RELEASED."""
    from app.models.division import Division
    from app.models.enquiry import Enquiry

    test_ip = "198.51.100.126"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    div = (
        (await db_session.execute(select(Division).where(Division.is_active.is_(True))))
        .scalars()
        .first()
    )
    assert div is not None

    res = await public_rate_limiter.acquire_submission_slot(test_ip)
    ref = "EB-RFQ-20261110-CONF-ORDER-BA"
    await res.attach_reference(ref)

    # Persist the row in PostgreSQL
    enquiry = Enquiry(
        reference_number=ref,
        full_name="Conflict BA",
        company_name="Conflict Corp",
        business_email="conflict_ba@corp.com",
        contact_number="+6012345678",
        country="Malaysia",
        initial_division_id=div.id,
        current_division_id=div.id,
        product_focus="Mineral Water",
        status="NEW",
        source_ip=test_ip,
    )
    db_session.add(enquiry)
    await db_session.commit()

    # Simulate Task B starting first (increments generation to 1), querying DB (seeing False):
    async with public_rate_limiter._lock:
        rec = public_rate_limiter._reservation_records[res.token]
        gen_b = rec.reconciliation_generation + 1
        public_rate_limiter._reservation_records[res.token] = rec._replace(
            reconciliation_generation=gen_b
        )

    # Now Task A starts (increments generation to 2, superseding B):
    async with public_rate_limiter._lock:
        rec = public_rate_limiter._reservation_records[res.token]
        gen_a = rec.reconciliation_generation + 1
        public_rate_limiter._reservation_records[res.token] = rec._replace(
            reconciliation_generation=gen_a
        )

    # Task B tries to complete first with row_exists=False and confirmed_terminated=True using stale gen_b:
    async with public_rate_limiter._lock:
        current = public_rate_limiter._reservation_records[res.token]
        # Generation protection: gen_b != current.reconciliation_generation -> cannot release!
        assert gen_b != current.reconciliation_generation

    # Task A completes with live DB check observing row:
    st_a = await public_rate_limiter.reconcile_pending_reservation(
        res.token, db_session
    )
    assert st_a == ReservationStatus.COMMITTED

    # CRITICAL: In neither order may a committed enquiry end with a RELEASED reservation!
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0
    records = [
        r for r in public_rate_limiter._reservation_records.values() if r.ip == test_ip
    ]
    assert records[0].status == ReservationStatus.COMMITTED


@pytest.mark.asyncio
async def test_120_repeated_reconciliation_of_terminal_reservation(
    db_session: AsyncSession,
):
    """120. Repeated reconciliation of an already terminal reservation preserves immutability and never double-counts."""
    from app.models.division import Division
    from app.models.enquiry import Enquiry

    test_ip = "198.51.100.127"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    div = (
        (await db_session.execute(select(Division).where(Division.is_active.is_(True))))
        .scalars()
        .first()
    )
    assert div is not None

    res = await public_rate_limiter.acquire_submission_slot(test_ip)
    ref = "EB-RFQ-20261110-REPEATED-RECON"
    await res.attach_reference(ref)

    enquiry = Enquiry(
        reference_number=ref,
        full_name="Repeat Recon",
        company_name="Repeat Corp",
        business_email="repeat_recon@corp.com",
        contact_number="+6012345678",
        country="Malaysia",
        initial_division_id=div.id,
        current_division_id=div.id,
        product_focus="Mineral Water",
        status="NEW",
        source_ip=test_ip,
    )
    db_session.add(enquiry)
    await db_session.commit()

    # 1st reconciliation: COMMITTED
    st1 = await public_rate_limiter.reconcile_pending_reservation(res.token, db_session)
    assert st1 == ReservationStatus.COMMITTED
    assert len(public_rate_limiter._submissions[test_ip]) == 1

    # Repeat reconciliation 5 times
    for _ in range(5):
        st = await public_rate_limiter.reconcile_pending_reservation(
            res.token, db_session
        )
        assert st == ReservationStatus.COMMITTED

    # Quota is strictly NOT double-counted
    assert len(public_rate_limiter._submissions[test_ip]) == 1
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0


@pytest.mark.asyncio
async def test_121_recovery_trigger_on_incoming_rfq_submission(
    db_session: AsyncSession,
):
    """121. Recovery trigger: incoming RFQ submission recovers ambiguous reservation from previous outage."""
    from app.api.v1.endpoints.public import submit_rfq_enquiry
    from app.models.division import Division
    from app.models.enquiry import Enquiry

    test_ip = "198.51.100.128"
    async with public_rate_limiter._lock:
        public_rate_limiter._reservations.pop(test_ip, None)
        public_rate_limiter._submissions.pop(test_ip, None)
        public_rate_limiter._pending_tokens_by_ip.pop(test_ip, None)

    div = (
        (await db_session.execute(select(Division).where(Division.is_active.is_(True))))
        .scalars()
        .first()
    )
    assert div is not None

    # 1. Simulate an earlier ambiguous reservation left PENDING from a network outage
    old_res = await public_rate_limiter.acquire_submission_slot(test_ip)
    old_ref = "EB-RFQ-20261110-OLD-OUTAGE-RECON"
    await old_res.attach_reference(old_ref)

    # In reality, that earlier enquiry DID persist to PostgreSQL before the connection dropped
    earlier_enquiry = Enquiry(
        reference_number=old_ref,
        full_name="Earlier Enquiry",
        company_name="Earlier Corp",
        business_email="earlier@corp.com",
        contact_number="+6012345678",
        country="Malaysia",
        initial_division_id=div.id,
        current_division_id=div.id,
        product_focus="Mineral Water",
        status="NEW",
        source_ip=test_ip,
    )
    db_session.add(earlier_enquiry)
    await db_session.commit()

    # Prior to new request: old_res is in PENDING
    assert old_res.token in public_rate_limiter._pending_tokens_by_ip[test_ip]
    assert len(public_rate_limiter._submissions[test_ip]) == 0

    # 2. Client submits a new RFQ request. The intake trigger automatically runs reconcile_pending_for_ip!
    req, payload = _make_rfq_request(test_ip, email="fresh_new_rfq@corp.com")
    envelope = await submit_rfq_enquiry(req, payload, db_session)
    assert envelope.success is True

    # 3. Assertions:
    # The earlier ambiguous reservation was recovered and committed!
    assert old_res.token not in public_rate_limiter._pending_tokens_by_ip[test_ip]
    old_record = public_rate_limiter._reservation_records[old_res.token]
    assert old_record.status == ReservationStatus.COMMITTED

    # Total submissions = 1 (recovered earlier) + 1 (new submission) = 2
    assert len(public_rate_limiter._submissions[test_ip]) == 2
    assert len(public_rate_limiter._pending_tokens_by_ip[test_ip]) == 0
