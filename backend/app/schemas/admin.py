"""Pydantic v2 schemas for Central Administrative Enquiry Management and Dashboard.

Phase C13.4 — Central Admin Dashboard & Enquiry Management.
Adheres strictly to C13.4-implementation-plan.md v3.1.0 and corporate architecture rules.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# 8 Approved Institutional Enquiry Lifecycle Statuses
VALID_STATUSES: set[str] = {
    "NEW",
    "UNDER_REVIEW",
    "ASSIGNED",
    "IN_COMMUNICATION",
    "QUOTATION_PENDING",
    "COMPLETED",
    "DECLINED",
    "ARCHIVED",
}

# Permitted Finite State Transition Matrix
PERMITTED_TRANSITIONS: dict[str, set[str]] = {
    "NEW": {"UNDER_REVIEW", "ASSIGNED", "DECLINED"},
    "UNDER_REVIEW": {"ASSIGNED", "IN_COMMUNICATION", "DECLINED"},
    "ASSIGNED": {"UNDER_REVIEW", "IN_COMMUNICATION", "QUOTATION_PENDING", "DECLINED"},
    "IN_COMMUNICATION": {"UNDER_REVIEW", "QUOTATION_PENDING", "COMPLETED", "DECLINED", "ARCHIVED"},
    "QUOTATION_PENDING": {"IN_COMMUNICATION", "COMPLETED", "DECLINED", "ARCHIVED"},
    "COMPLETED": {"ARCHIVED", "IN_COMMUNICATION", "QUOTATION_PENDING"},
    "DECLINED": {"ARCHIVED", "UNDER_REVIEW"},
    "ARCHIVED": {"UNDER_REVIEW"},
}

# Terminal status transitions requiring SUPER_ADMIN role authority
SUPER_ADMIN_REQUIRED_TRANSITIONS: set[tuple[str, str]] = {
    ("COMPLETED", "IN_COMMUNICATION"),
    ("COMPLETED", "QUOTATION_PENDING"),
    ("DECLINED", "UNDER_REVIEW"),
    ("ARCHIVED", "UNDER_REVIEW"),
}


# ==============================================================================
# Request Schemas
# ==============================================================================


class EnquiryAssignmentRequest(BaseModel):
    """Payload to assign or reassign an enquiry to a central administrator."""

    assigned_admin_id: UUID | None = Field(
        default=None,
        description="Target administrator ID to assign, or null to unassign",
    )
    assignment_rationale: str | None = Field(
        default=None,
        max_length=1000,
        description="Administrative rationale for assignment or transfer",
    )


class EnquiryStatusUpdateRequest(BaseModel):
    """Payload to advance or update an enquiry lifecycle status."""

    new_status: str = Field(..., description="Target lifecycle status identifier")
    change_reason: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Mandatory administrative rationale for the status transition",
    )

    @field_validator("new_status")
    @classmethod
    def validate_status_identifier(cls, v: str) -> str:
        clean = v.strip().upper() if isinstance(v, str) else v
        if clean not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{v}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}"
            )
        return clean

    @field_validator("change_reason")
    @classmethod
    def validate_change_reason_text(cls, v: str) -> str:
        clean = v.strip() if isinstance(v, str) else ""
        if len(clean) < 3:
            raise ValueError("change_reason must contain at least 3 non-whitespace characters")
        if len(clean) > 1000:
            raise ValueError("change_reason cannot exceed 1000 characters")
        return clean


class EnquiryNoteCreateRequest(BaseModel):
    """Payload to append an internal operational follow-up note."""

    note_text: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Internal trade desk or operational note content",
    )

    @field_validator("note_text")
    @classmethod
    def validate_note_content(cls, v: str) -> str:
        clean = v.strip() if isinstance(v, str) else ""
        if not clean:
            raise ValueError("note_text cannot be empty or whitespace only")
        if len(clean) > 4000:
            raise ValueError("note_text cannot exceed 4000 characters")
        return clean


# ==============================================================================
# Shared & Sub-Entity Summaries
# ==============================================================================


class AdminAssignedUserSummary(BaseModel):
    """Compact identity representation for assigned administrators and authors."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: EmailStr
    job_title: str | None = None


class AdminAssigneeSummary(BaseModel):
    """Data-minimized representation of active administrators for assignment selector."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Administrator identifier for assignment")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    email: EmailStr = Field(..., description="Corporate administrator email address")
    job_title: str | None = Field(default=None, description="Job title or designation")
    roles: list[str] = Field(default_factory=list, description="Assigned administrative roles")


class AdminAssigneesEnvelope(BaseModel):
    """Response envelope for active administrators directory."""

    success: bool = True
    data: list[AdminAssigneeSummary]


class DivisionSummary(BaseModel):
    """Commercial division summary representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    accent_color: str | None = None


class PaginationMetadata(BaseModel):
    """Standardized pagination information."""

    page: int
    limit: int
    total_items: int
    total_pages: int


# ==============================================================================
# Overview & Metrics Schemas
# ==============================================================================


class DivisionMetricItem(BaseModel):
    """Enquiry volume metric per commercial trading division."""

    division_id: str
    code: str
    name: str
    count: int
    is_active: bool = True


class AdminOverviewMetrics(BaseModel):
    """High-level commercial enquiry volume metrics for dashboard."""

    total_enquiries: int
    by_status: dict[str, int]
    by_division: list[DivisionMetricItem]
    unassigned_count: int
    today_count: int


class AdminOverviewEnvelope(BaseModel):
    """Response envelope for dashboard metrics."""

    success: bool = True
    data: AdminOverviewMetrics


# ==============================================================================
# Enquiry List Schemas
# ==============================================================================


class EnquiryListItem(BaseModel):
    """Data-minimized representation of an enquiry for tabular display.

    SEC-02 Privacy Hardening: Submitter personal contact name and email address
    are strictly excluded from the list schema and JSON payload. Contact details
    remain accessible solely through the authenticated dossier endpoint.
    """

    id: UUID
    reference_number: str
    created_at: datetime
    company_name: str
    country: str
    division_id: str
    division_name: str
    product_focus: str
    status: str
    assigned_admin: AdminAssignedUserSummary | None = None


class EnquirySearchRequest(BaseModel):
    """Encrypted JSON body payload for privacy-preserving repository queries.

    SEC-01 Privacy Hardening: Carries search terms and filter criteria within
    the encrypted HTTP POST body, preventing search term leakage into browser
    URLs, browser history, reverse proxy logs, and server access logs.
    """

    page: int = Field(default=1, ge=1, description="Page index (1-based)")
    limit: int = Field(default=25, ge=1, le=100, description="Items per page")
    division_id: str | None = Field(default=None, description="Filter by commercial division")
    status: str | None = Field(default=None, description="Filter by lifecycle status")
    assigned_admin_id: str | None = Field(
        default=None, description="Filter by handling admin UUID, or 'unassigned'"
    )
    search: str | None = Field(
        default=None, description="Search company, contact name, email, or reference number"
    )
    sort_by: str = Field(
        default="created_at",
        description="Field to sort by: created_at, reference_number, company_name, status",
    )
    sort_order: str = Field(default="desc", description="Sort order: asc or desc")
    created_from: datetime | None = Field(
        default=None,
        description="Filter enquiries created on or after this UTC timestamp (inclusive start)",
    )
    created_to: datetime | None = Field(
        default=None,
        description="Filter enquiries created before this UTC timestamp (exclusive end)",
    )


class EnquiryListResponseData(BaseModel):
    """Paginated collection of enquiries."""

    items: list[EnquiryListItem]
    pagination: PaginationMetadata


class EnquiryListEnvelope(BaseModel):
    """Response envelope for enquiries query."""

    success: bool = True
    data: EnquiryListResponseData


# ==============================================================================
# Enquiry Detail & Timeline Schemas
# ==============================================================================


class EnquiryAssignmentHistoryItem(BaseModel):
    """Chronological record of an administrator assignment transition."""

    id: UUID
    previous_admin: AdminAssignedUserSummary | None = None
    new_admin: AdminAssignedUserSummary | None = None
    assigned_by_admin: AdminAssignedUserSummary
    assignment_rationale: str | None = None
    assigned_at: datetime


class EnquiryStatusHistoryItem(BaseModel):
    """Chronological record of a lifecycle status transition."""

    id: UUID
    old_status: str
    new_status: str
    change_reason: str | None = None
    changed_by_admin: AdminAssignedUserSummary
    created_at: datetime


class EnquiryNoteItem(BaseModel):
    """Internal operational note record."""

    id: UUID
    author_admin: AdminAssignedUserSummary
    note_text: str
    is_internal_only: bool = True
    created_at: datetime


class EnquiryNoteResponseEnvelope(BaseModel):
    """Response envelope for note creation."""

    success: bool = True
    data: EnquiryNoteItem


class EnquiryDetailResponseData(BaseModel):
    """Complete enquiry dossier including submitter snapshot, specifications, and timelines."""

    # Submitter Contact Snapshot
    full_name: str
    company_name: str
    business_email: EmailStr
    contact_number: str | None
    country: str

    # Commercial Requirements Snapshot
    initial_division: DivisionSummary
    current_division: DivisionSummary
    product_focus: str
    quantity: Decimal | None = None
    unit_of_measurement: str | None = None
    specifications: str | None = None
    additional_notes: str | None = None
    preferred_incoterm: str | None = None
    target_destination_port: str | None = None

    # Status & Assignment Routing
    id: UUID
    reference_number: str
    status: str
    assigned_admin: AdminAssignedUserSummary | None = None

    # Timestamps (UTC)
    created_at: datetime
    updated_at: datetime

    # Timelines
    assignments: list[EnquiryAssignmentHistoryItem] = Field(default_factory=list)
    status_history: list[EnquiryStatusHistoryItem] = Field(default_factory=list)
    notes: list[EnquiryNoteItem] = Field(default_factory=list)


class EnquiryDetailEnvelope(BaseModel):
    """Response envelope for detailed enquiry dossier."""

    success: bool = True
    data: EnquiryDetailResponseData


# ==============================================================================
# Audit Log Schemas (Super Admin Only)
# ==============================================================================


class AuditLogListItem(BaseModel):
    """Immutable operational and security audit record."""

    id: int
    timestamp: datetime
    actor_admin_id: UUID | None = None
    actor_email: str | None = None
    ip_address: str | None = None
    action: str
    entity_table: str
    entity_id: UUID
    old_state: dict[str, Any] | None = None
    new_state: dict[str, Any] | None = None
    client_user_agent: str | None = None


class AuditLogListResponseData(BaseModel):
    """Paginated collection of audit logs."""

    items: list[AuditLogListItem]
    pagination: PaginationMetadata


class AuditLogListEnvelope(BaseModel):
    """Response envelope for audit logs query."""

    success: bool = True
    data: AuditLogListResponseData


# ==============================================================================
# Dashboard Activity Feed Schemas (Stage 3)
# ==============================================================================


class DashboardActivityItem(BaseModel):
    """Data-minimized operational activity item derived from audit logs."""

    id: str = Field(..., description="Unique audit event ID as string")
    event_type: str = Field(..., description="STATUS_CHANGED | ENQUIRY_ASSIGNED | ENQUIRY_UNASSIGNED")
    reference_number: str = Field(..., description="Enquiry reference number")
    division_name: str = Field(..., description="Commercial division display name")
    description: str = Field(..., description="Neutral administrative description of the action")
    actor_name: str = Field(..., description="Administrator name or actor email")
    timestamp: datetime = Field(..., description="UTC event timestamp")


class DashboardActivityEnvelope(BaseModel):
    """Response envelope for dashboard activity feed."""

    success: bool = True
    data: list[DashboardActivityItem]
