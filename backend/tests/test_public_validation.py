"""Database-independent validation tests for public RFQ request payloads."""

import pytest
from app.api.v1.endpoints.public import compute_payload_hash
from app.schemas.public import EnquiryCreateRequest
from pydantic import ValidationError


def valid_payload() -> dict[str, str]:
    return {
        "division_id": "petroleum-products",
        "full_name": "Buyer Contact",
        "company_name": "Buyer Corporation",
        "business_email": "buyer@example.com",
        "country": "Malaysia",
        "product_focus": "Fuel Oil",
    }


def test_contact_number_can_be_omitted_or_blank() -> None:
    without_phone = EnquiryCreateRequest.model_validate(valid_payload())
    blank_phone = EnquiryCreateRequest.model_validate(
        {**valid_payload(), "contact_number": "   "}
    )

    assert without_phone.contact_number is None
    assert blank_phone.contact_number is None
    assert compute_payload_hash(without_phone) == compute_payload_hash(blank_phone)


def test_supplied_contact_number_is_preserved() -> None:
    payload = {**valid_payload(), "contact_number": "+60 12 345 6789"}
    assert EnquiryCreateRequest.model_validate(payload).contact_number == "+60 12 345 6789"


def test_supplied_contact_number_still_requires_six_characters() -> None:
    with pytest.raises(ValidationError):
        EnquiryCreateRequest.model_validate(
            {**valid_payload(), "contact_number": "+1234"}
        )
