"""Pydantic Schemas for Public Division Inquiries and RFQ Ingestion.

Phase C13.3 — Corrective Pass:
Adheres strictly to C13-api-specification.md v2.1.0 and C13-security-design.md v2.1.0:
- Public division catalogue representation.
- Strict input validation, whitespace trimming, and HTML/script sanitization.
- Forbids extraneous/unexpected client fields (extra="forbid") to protect internal workflow state.
- Supports both snake_case and camelCase field aliases for seamless client compatibility.
- Safe parsing of commercial volume and quantities.
- Honeypot and CAPTCHA architecture hooks.
- Standard JSON:API envelope conventions.
"""

import re
from decimal import Decimal
from typing import Any

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)

SCRIPT_STYLE_REGEX = re.compile(r"(?is)<(script|style|iframe)[^>]*>.*?</\1>")
HTML_TAG_REGEX = re.compile(r"<[^>]*>")


def sanitize_text(text: str | None) -> str | None:
    """Strips executable script/style/iframe blocks and HTML tags from user input."""
    if text is None:
        return None
    # Strip entire script, style, and iframe blocks including contents
    cleaned = SCRIPT_STYLE_REGEX.sub("", text)
    # Strip any remaining HTML tags
    cleaned = HTML_TAG_REGEX.sub("", cleaned).strip()
    return cleaned if cleaned else None


class DivisionPublic(BaseModel):
    """Publicly exposed attributes of a commercial division."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique division slug (e.g. 'petroleum-products')")
    name: str = Field(..., description="Commercial division display name")
    sector: str = Field(..., description="Business sector designation")
    accent_color: str = Field(..., description="Corporate division hex color")
    manufacturer_attribution: str | None = Field(
        default=None,
        description="Verified manufacturer attribution, when one has been confirmed in writing",
    )
    disclaimer: str | None = Field(
        default=None,
        description="Statutory commercial disclaimer or limitation notice",
    )


class DivisionsResponseEnvelope(BaseModel):
    """Envelope for public division catalogue endpoint."""

    success: bool = True
    data: list[DivisionPublic]


class EnquiryCreateRequest(BaseModel):
    """Public Trade Enquiry (RFQ) submission payload.

    Accepts both snake_case and camelCase field aliases.
    Strictly forbids unexpected fields (extra="forbid") to prevent clients from attempting
    to inject internal enquiry status, reference numbers, or administrative assignments.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    division_id: str = Field(
        ...,
        validation_alias=AliasChoices("division_id", "divisionId"),
        min_length=2,
        max_length=50,
        description="Target commercial division identifier",
    )
    full_name: str = Field(
        ...,
        validation_alias=AliasChoices("full_name", "fullName"),
        min_length=2,
        max_length=150,
        description="Submitter contact full name",
    )
    company_name: str = Field(
        ...,
        validation_alias=AliasChoices("company_name", "companyName"),
        min_length=2,
        max_length=200,
        description="Registered corporate entity name",
    )
    business_email: EmailStr = Field(
        ...,
        validation_alias=AliasChoices("business_email", "businessEmail"),
        max_length=255,
        description="Corporate business email address",
    )
    contact_number: str | None = Field(
        default=None,
        validation_alias=AliasChoices("contact_number", "contactNumber"),
        min_length=6,
        max_length=50,
        description="Optional direct corporate telephone or mobile number",
    )
    country: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Country of incorporation or operation",
    )
    product_focus: str = Field(
        ...,
        validation_alias=AliasChoices("product_focus", "productFocus"),
        min_length=2,
        max_length=255,
        description="Specific product, grade, or commodity required",
    )
    quantity: Decimal | None = Field(
        default=None,
        ge=0,
        description="Procurement volume or batch quantity",
    )
    unit_of_measurement: str | None = Field(
        default=None,
        validation_alias=AliasChoices("unit_of_measurement", "unitOfMeasurement"),
        max_length=50,
        description="Commercial unit (e.g. Metric Tonnes, Barrels, Units)",
    )
    specifications: str | None = Field(
        default=None,
        max_length=4000,
        description="Technical specifications, standards, or grade parameters",
    )
    additional_notes: str | None = Field(
        default=None,
        validation_alias=AliasChoices("additional_notes", "additionalNotes"),
        max_length=4000,
        description="Logistical details, timeline, or commercial terms",
    )
    preferred_incoterm: str | None = Field(
        default=None,
        validation_alias=AliasChoices("preferred_incoterm", "preferredIncoterm"),
        max_length=10,
        description="Incoterms 2020 preference (e.g. FOB, CIF, CFR)",
    )
    target_destination_port: str | None = Field(
        default=None,
        validation_alias=AliasChoices("target_destination_port", "targetDestinationPort"),
        max_length=150,
        description="Target destination port or discharge terminal",
    )

    # Backwards compatibility fields present in website form interface
    requirements: str | None = Field(
        default=None,
        max_length=4000,
        description="Optional requirements (legacy frontend compatibility)",
    )
    message: str | None = Field(
        default=None,
        max_length=4000,
        description="Optional message (legacy frontend compatibility)",
    )

    # Idempotency Controls (Phase C13.3 Final Corrective Pass)
    idempotency_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("idempotency_key", "idempotencyKey"),
        min_length=1,
        max_length=128,
        description="Client-generated unique token ensuring safe idempotent retries",
    )

    # Anti-Abuse Hooks (C13-security-design.md Section 4.3)
    website_url_hp: str | None = Field(
        default=None,
        validation_alias=AliasChoices("website_url_hp", "websiteUrlHp", "website", "website_url"),
        max_length=255,
        description="Honeypot field visually hidden in UI. Must be empty for legitimate requests.",
    )
    captcha_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("captcha_token", "captchaToken"),
        max_length=2048,
        description="Optional Cloudflare Turnstile token for edge anti-bot integration.",
    )

    @field_validator("quantity", mode="before")
    @classmethod
    def parse_quantity(cls, v: Any) -> Decimal | None:
        """Parses numeric, string-encoded, or empty quantities safely."""
        if v is None or v == "":
            return None
        if isinstance(v, (int, float, Decimal)):
            return Decimal(str(v))
        if isinstance(v, str):
            cleaned = v.strip().replace(",", "")
            if not cleaned:
                return None
            try:
                val = Decimal(cleaned)
                if val < 0:
                    raise ValueError("Quantity cannot be negative.")
                return val
            except (ValueError, ArithmeticError):
                raise ValueError(f"Quantity '{v}' is not a valid numeric value.") from None
        return None

    @field_validator("full_name", "company_name", "country", "product_focus", mode="before")
    @classmethod
    def sanitize_required_strings(cls, v: str) -> str:
        if isinstance(v, str):
            cleaned = sanitize_text(v)
            if not cleaned:
                raise ValueError("Field cannot be empty or contain only whitespace/HTML.")
            return cleaned
        return v

    @field_validator("contact_number", mode="before")
    @classmethod
    def normalize_optional_contact_number(cls, v: Any) -> str | None:
        """Treat omitted or blank phone numbers as optional; validate nonblank values."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator(
        "specifications",
        "additional_notes",
        "unit_of_measurement",
        "preferred_incoterm",
        "target_destination_port",
        "requirements",
        "message",
        mode="before",
    )
    @classmethod
    def sanitize_optional_strings(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            return sanitize_text(v)
        return v


class EnquiryResponseData(BaseModel):
    """Enquiry submission confirmation payload."""

    reference_number: str = Field(
        ...,
        description="Official unique tracking reference (EB-RFQ-YYYYMMDD-XXXX)",
    )
    status: str = Field(default="NEW", description="Initial workflow status")
    message: str = Field(..., description="Confirmation dispatch message")


class EnquiryResponseEnvelope(BaseModel):
    """Envelope for public RFQ ingestion endpoint."""

    success: bool = True
    data: EnquiryResponseData
