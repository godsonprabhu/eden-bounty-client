"""Central Administrator API Endpoints for Enquiry Management and Operations.

Phase C13.4 — Central Admin Dashboard & Enquiry Management.
Adheres strictly to C13.4-implementation-plan.md v3.1.0:
- Single centralized operations team across all 10 commercial divisions.
- Strict division preservation (no administrative division reassignment).
- Authoritative finite status transition matrix with mandatory change reason.
- Terminal status reopening restricted strictly to SUPER_ADMIN.
- Atomic database transactions with row-level locks on mutations.
- Synchronous application-level append-only audit logging.
- Data minimization on administrative directory.
"""

import math
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from app.api.deps import (
    get_current_user,
    get_db,
    require_admin_user,
    require_super_admin,
    verify_csrf_token,
)
from app.models.admin import AdminUser
from app.models.audit import AuditLog
from app.models.division import Division
from app.models.enquiry import (
    Enquiry,
    EnquiryAssignment,
    EnquiryNote,
    EnquiryStatusHistory,
)
from app.schemas.admin import (
    PERMITTED_TRANSITIONS,
    SUPER_ADMIN_REQUIRED_TRANSITIONS,
    VALID_STATUSES,
    AdminAssignedUserSummary,
    AdminAssigneesEnvelope,
    AdminAssigneeSummary,
    AdminOverviewEnvelope,
    AdminOverviewMetrics,
    AuditLogListEnvelope,
    AuditLogListItem,
    AuditLogListResponseData,
    DashboardActivityEnvelope,
    DashboardActivityItem,
    DivisionMetricItem,
    DivisionSummary,
    EnquiryAssignmentHistoryItem,
    EnquiryAssignmentRequest,
    EnquiryDetailEnvelope,
    EnquiryDetailResponseData,
    EnquiryListEnvelope,
    EnquiryListItem,
    EnquiryListResponseData,
    EnquiryNoteCreateRequest,
    EnquiryNoteItem,
    EnquiryNoteResponseEnvelope,
    EnquirySearchRequest,
    EnquiryStatusHistoryItem,
    EnquiryStatusUpdateRequest,
    PaginationMetadata,
)
from app.services.audit import record_audit_log
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi import status as http_status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/admin", tags=["Admin Operations"])


# ==============================================================================
# Helper Functions
# ==============================================================================


async def _build_admin_lookup(
    db: AsyncSession, admin_ids: set[UUID | None]
) -> dict[UUID, AdminAssignedUserSummary]:
    """Efficiently queries and maps administrator summaries for a set of admin IDs."""
    clean_ids = {uid for uid in admin_ids if uid is not None}
    if not clean_ids:
        return {}

    stmt = select(AdminUser).where(AdminUser.id.in_(clean_ids))
    result = await db.execute(stmt)
    admins = result.scalars().all()

    return {
        admin.id: AdminAssignedUserSummary(
            id=admin.id,
            name=f"{admin.first_name} {admin.last_name}".strip(),
            email=admin.email,
            job_title=admin.job_title,
        )
        for admin in admins
    }


async def _load_full_enquiry_dossier(
    db: AsyncSession, enquiry_id: UUID
) -> EnquiryDetailEnvelope:
    """Loads complete enquiry dossier including timelines and resolved administrator details."""
    stmt = (
        select(Enquiry)
        .options(
            selectinload(Enquiry.initial_division),
            selectinload(Enquiry.current_division),
            selectinload(Enquiry.assigned_admin),
            selectinload(Enquiry.assignments),
            selectinload(Enquiry.status_history),
            selectinload(Enquiry.notes),
        )
        .where(Enquiry.id == enquiry_id, Enquiry.deleted_at.is_(None))
    )
    result = await db.execute(stmt)
    enquiry = result.scalar_one_or_none()

    if not enquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enquiry not found",
        )

    # Gather all referenced admin IDs across timelines
    admin_ids: set[UUID | None] = {enquiry.assigned_admin_id}
    for a in enquiry.assignments:
        admin_ids.add(a.previous_admin_id)
        admin_ids.add(a.new_admin_id)
        admin_ids.add(a.assigned_by_admin_id)
    for s in enquiry.status_history:
        admin_ids.add(s.changed_by_admin_id)
    for n in enquiry.notes:
        admin_ids.add(n.admin_user_id)

    admin_lookup = await _build_admin_lookup(db, admin_ids)

    # Construct assignment timeline items
    assignment_items = [
        EnquiryAssignmentHistoryItem(
            id=a.id,
            previous_admin=admin_lookup.get(a.previous_admin_id),
            new_admin=admin_lookup.get(a.new_admin_id),
            assigned_by_admin=admin_lookup.get(
                a.assigned_by_admin_id,
                AdminAssignedUserSummary(
                    id=a.assigned_by_admin_id,
                    name="System / Administrator",
                    email="admin@edenbounty.org",
                ),
            ),
            assignment_rationale=a.assignment_rationale,
            assigned_at=a.assigned_at,
        )
        for a in enquiry.assignments
    ]

    # Construct status history items
    status_items = [
        EnquiryStatusHistoryItem(
            id=s.id,
            old_status=s.old_status,
            new_status=s.new_status,
            change_reason=s.change_reason,
            changed_by_admin=admin_lookup.get(
                s.changed_by_admin_id,
                AdminAssignedUserSummary(
                    id=s.changed_by_admin_id,
                    name="System / Administrator",
                    email="admin@edenbounty.org",
                ),
            ),
            created_at=s.created_at,
        )
        for s in enquiry.status_history
    ]

    # Construct internal notes items
    note_items = [
        EnquiryNoteItem(
            id=n.id,
            author_admin=admin_lookup.get(
                n.admin_user_id,
                AdminAssignedUserSummary(
                    id=n.admin_user_id,
                    name="System / Administrator",
                    email="admin@edenbounty.org",
                ),
            ),
            note_text=n.note_text,
            is_internal_only=n.is_internal_only,
            created_at=n.created_at,
        )
        for n in enquiry.notes
    ]

    assigned_admin_summary = (
        admin_lookup.get(enquiry.assigned_admin_id)
        if enquiry.assigned_admin_id
        else None
    )

    dossier = EnquiryDetailResponseData(
        full_name=enquiry.full_name,
        company_name=enquiry.company_name,
        business_email=enquiry.business_email,
        contact_number=enquiry.contact_number,
        country=enquiry.country,
        initial_division=DivisionSummary(
            id=enquiry.initial_division.id,
            code=enquiry.initial_division.code,
            name=enquiry.initial_division.name,
            accent_color=enquiry.initial_division.accent_color,
        ),
        current_division=DivisionSummary(
            id=enquiry.current_division.id,
            code=enquiry.current_division.code,
            name=enquiry.current_division.name,
            accent_color=enquiry.current_division.accent_color,
        ),
        product_focus=enquiry.product_focus,
        quantity=enquiry.quantity,
        unit_of_measurement=enquiry.unit_of_measurement,
        specifications=enquiry.specifications,
        additional_notes=enquiry.additional_notes,
        preferred_incoterm=enquiry.preferred_incoterm,
        target_destination_port=enquiry.target_destination_port,
        id=enquiry.id,
        reference_number=enquiry.reference_number,
        status=enquiry.status,
        assigned_admin=assigned_admin_summary,
        created_at=enquiry.created_at,
        updated_at=enquiry.updated_at,
        assignments=assignment_items,
        status_history=status_items,
        notes=note_items,
    )

    return EnquiryDetailEnvelope(success=True, data=dossier)


# ==============================================================================
# Endpoint 1: Dashboard Overview & Volume Metrics
# ==============================================================================


@router.get(
    "/dashboard/overview",
    response_model=AdminOverviewEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Retrieve commercial pipeline overview and volume metrics",
    dependencies=[Depends(require_admin_user)],
)
async def get_dashboard_overview(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminOverviewEnvelope:
    """Aggregates pipeline counts by status, division, unassigned count, and daily volume."""
    # 1. Total active enquiries
    total_enquiries = (
        await db.scalar(
            select(func.count(Enquiry.id)).where(Enquiry.deleted_at.is_(None))
        )
        or 0
    )

    # 2. Counts grouped by status (initialize all 8 approved statuses to 0)
    status_counts: dict[str, int] = {st: 0 for st in VALID_STATUSES}
    stmt_status = (
        select(Enquiry.status, func.count(Enquiry.id))
        .where(Enquiry.deleted_at.is_(None))
        .group_by(Enquiry.status)
    )
    status_rows = (await db.execute(stmt_status)).all()
    for st, count in status_rows:
        if st in status_counts:
            status_counts[st] = count

    # 3. Counts grouped by division (load canonical divisions to guarantee representation)
    stmt_divs = select(Division).order_by(Division.code.asc())
    divisions = (await db.execute(stmt_divs)).scalars().all()

    stmt_div_counts = (
        select(Enquiry.current_division_id, func.count(Enquiry.id))
        .where(Enquiry.deleted_at.is_(None))
        .group_by(Enquiry.current_division_id)
    )
    div_counts_map = dict((await db.execute(stmt_div_counts)).all())

    division_metrics: list[DivisionMetricItem] = [
        DivisionMetricItem(
            division_id=div.id,
            code=div.code,
            name=div.name,
            count=div_counts_map.get(div.id, 0),
            is_active=div.is_active,
        )
        for div in divisions
    ]

    # 4. Unassigned urgent enquiries count
    unassigned_count = (
        await db.scalar(
            select(func.count(Enquiry.id)).where(
                Enquiry.deleted_at.is_(None),
                Enquiry.assigned_admin_id.is_(None),
            )
        )
        or 0
    )

    # 5. Today's enquiries volume (UTC start of day)
    now_utc = datetime.now(UTC)
    today_start = datetime(
        now_utc.year, now_utc.month, now_utc.day, 0, 0, 0, tzinfo=UTC
    )
    today_count = (
        await db.scalar(
            select(func.count(Enquiry.id)).where(
                Enquiry.deleted_at.is_(None),
                Enquiry.created_at >= today_start,
            )
        )
        or 0
    )

    return AdminOverviewEnvelope(
        success=True,
        data=AdminOverviewMetrics(
            total_enquiries=total_enquiries,
            by_status=status_counts,
            by_division=division_metrics,
            unassigned_count=unassigned_count,
            today_count=today_count,
        ),
    )


# ==============================================================================
# Endpoint 1B: Dashboard Operational Activity Feed (Stage 3)
# ==============================================================================


@router.get(
    "/dashboard/activity",
    response_model=DashboardActivityEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Retrieve operational activity feed from audit records",
    dependencies=[Depends(require_admin_user)],
)
async def get_dashboard_activity(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=10, ge=1, le=50, description="Maximum activity items to return"),
) -> DashboardActivityEnvelope:
    """Returns recent non-sensitive operational activity derived from audit logs.

    Reuses existing audit_logs records (STATUS_CHANGED, ENQUIRY_ASSIGNED).
    Excludes internal note content (NOTE_ADDED) and customer personal information.
    Accessible to both SUPER_ADMIN and OPERATIONS_ADMIN.
    """
    stmt = (
        select(
            AuditLog.id,
            AuditLog.action,
            AuditLog.timestamp,
            AuditLog.actor_email,
            AuditLog.old_state,
            AuditLog.new_state,
            Enquiry.reference_number,
            Division.name.label("division_name"),
            AdminUser.first_name.label("actor_first_name"),
            AdminUser.last_name.label("actor_last_name"),
        )
        .join(
            Enquiry,
            (AuditLog.entity_id == Enquiry.id)
            & (AuditLog.entity_table == "enquiries")
            & Enquiry.deleted_at.is_(None),
        )
        .join(Division, Enquiry.current_division_id == Division.id)
        .outerjoin(AdminUser, AuditLog.actor_admin_id == AdminUser.id)
        .where(AuditLog.action.in_(["STATUS_CHANGED", "ENQUIRY_ASSIGNED"]))
        .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    # Pre-fetch target admin names for assignment actions
    target_admin_ids: set[UUID] = set()
    for row in rows:
        if row.action == "ENQUIRY_ASSIGNED" and row.new_state and isinstance(row.new_state, dict):
            target_id = row.new_state.get("assigned_admin_id")
            if target_id:
                try:
                    target_admin_ids.add(UUID(target_id))
                except (ValueError, TypeError):
                    pass

    target_admin_lookup: dict[UUID, str] = {}
    if target_admin_ids:
        target_stmt = select(AdminUser.id, AdminUser.first_name, AdminUser.last_name).where(
            AdminUser.id.in_(target_admin_ids)
        )
        target_res = await db.execute(target_stmt)
        for t_id, t_first, t_last in target_res.all():
            target_admin_lookup[t_id] = f"{t_first} {t_last}".strip()

    items: list[DashboardActivityItem] = []
    for row in rows:
        # Determine actor display name
        if row.actor_first_name or row.actor_last_name:
            actor_name = f"{row.actor_first_name or ''} {row.actor_last_name or ''}".strip()
        elif row.actor_email:
            actor_name = row.actor_email
        else:
            actor_name = "Central Operations"

        # Determine neutral description and event_type
        if row.action == "STATUS_CHANGED":
            event_type = "STATUS_CHANGED"
            old_st = row.old_state.get("status", "Unknown") if isinstance(row.old_state, dict) else "Unknown"
            new_st = row.new_state.get("status", "Unknown") if isinstance(row.new_state, dict) else "Unknown"
            description = f"Status updated from {old_st} to {new_st}"
        elif row.action == "ENQUIRY_ASSIGNED":
            new_assignee_id = (
                row.new_state.get("assigned_admin_id")
                if isinstance(row.new_state, dict)
                else None
            )
            if new_assignee_id:
                event_type = "ENQUIRY_ASSIGNED"
                try:
                    target_uuid = UUID(new_assignee_id)
                    target_name = target_admin_lookup.get(target_uuid, "Administrator")
                except (ValueError, TypeError):
                    target_name = "Administrator"
                description = f"Enquiry assigned to {target_name}"
            else:
                event_type = "ENQUIRY_UNASSIGNED"
                description = "Enquiry unassigned (returned to central triage)"
        else:
            event_type = row.action
            description = f"Operational action: {row.action}"

        items.append(
            DashboardActivityItem(
                id=str(row.id),
                event_type=event_type,
                reference_number=row.reference_number,
                division_name=row.division_name,
                description=description,
                actor_name=actor_name,
                timestamp=row.timestamp,
            )
        )

    return DashboardActivityEnvelope(success=True, data=items)



# ==============================================================================
# Endpoint 2: Filterable, Paginated Enquiries Collection
# ==============================================================================


@router.get(
    "/rfqs",
    response_model=EnquiryListEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Filterable and paginated commercial enquiry collection",
    dependencies=[Depends(require_admin_user)],
)
async def list_enquiries(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1, description="Page index (1-based)"),
    limit: int = Query(default=25, ge=1, le=100, description="Items per page"),
    division_id: str | None = Query(default=None, description="Filter by commercial division"),
    status: str | None = Query(default=None, description="Filter by lifecycle status"),
    assigned_admin_id: str | None = Query(
        default=None,
        description="Filter by handling admin UUID, or 'unassigned'",
    ),
    search: str | None = Query(
        default=None,
        description="Search company, contact name, email, or reference number",
    ),
    sort_by: str = Query(
        default="created_at",
        description="Field to sort by: created_at, reference_number, company_name, status",
    ),
    sort_order: str = Query(default="desc", description="Sort order: asc or desc"),
    created_from: Annotated[
        datetime | None,
        Query(description="Filter enquiries created on or after this UTC timestamp (inclusive start)"),
    ] = None,
    created_to: Annotated[
        datetime | None,
        Query(description="Filter enquiries created before this UTC timestamp (exclusive end)"),
    ] = None,
) -> EnquiryListEnvelope:
    """Returns a filterable, paginated repository of commercial RFQ submissions."""
    return await _execute_enquiries_query(
        db=db,
        page=page,
        limit=limit,
        division_id=division_id,
        status_filter=status,
        assigned_admin_id=assigned_admin_id,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        created_from=created_from,
        created_to=created_to,
    )


@router.post(
    "/rfqs/search",
    response_model=EnquiryListEnvelope,
    status_code=http_status.HTTP_200_OK,
    summary="Privacy-preserving repository search with encrypted JSON request body",
    dependencies=[Depends(require_admin_user), Depends(verify_csrf_token)],
)
async def search_enquiries(
    payload: EnquirySearchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EnquiryListEnvelope:
    """Performs privacy-preserving repository search via POST request body.

    SEC-01 Privacy Hardening:
    - Search terms and filter criteria are delivered within an encrypted JSON request body.
    - Zero query string parameters logged in web server, proxy, or backend access logs.
    - Full administrator authentication (HttpOnly session cookie) and CSRF protection enforced.
    - Server-side filtering, multi-field search, pagination, and sorting preserved.
    """
    return await _execute_enquiries_query(
        db=db,
        page=payload.page,
        limit=payload.limit,
        division_id=payload.division_id,
        status_filter=payload.status,
        assigned_admin_id=payload.assigned_admin_id,
        search=payload.search,
        sort_by=payload.sort_by,
        sort_order=payload.sort_order,
        created_from=payload.created_from,
        created_to=payload.created_to,
    )


async def _execute_enquiries_query(
    db: AsyncSession,
    page: int,
    limit: int,
    division_id: str | None,
    status_filter: str | None,
    assigned_admin_id: str | None,
    search: str | None,
    sort_by: str,
    sort_order: str,
    created_from: datetime | None,
    created_to: datetime | None,
) -> EnquiryListEnvelope:
    """Shared query executor for commercial RFQ enquiries repository."""
    if created_from is not None and created_to is not None:
        cf = created_from if created_from.tzinfo is not None else created_from.replace(tzinfo=UTC)
        ct = created_to if created_to.tzinfo is not None else created_to.replace(tzinfo=UTC)
        if cf > ct:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="created_from timestamp cannot be later than created_to timestamp",
            )

    base_conditions = [Enquiry.deleted_at.is_(None)]

    if created_from is not None:
        cf = created_from if created_from.tzinfo is not None else created_from.replace(tzinfo=UTC)
        base_conditions.append(Enquiry.created_at >= cf)

    if created_to is not None:
        ct = created_to if created_to.tzinfo is not None else created_to.replace(tzinfo=UTC)
        base_conditions.append(Enquiry.created_at < ct)

    if division_id:
        base_conditions.append(Enquiry.current_division_id == division_id.strip())

    if status_filter:
        clean_status = status_filter.strip().upper()
        if clean_status in VALID_STATUSES:
            base_conditions.append(Enquiry.status == clean_status)

    if assigned_admin_id:
        clean_assignee = assigned_admin_id.strip()
        if clean_assignee.lower() == "unassigned":
            base_conditions.append(Enquiry.assigned_admin_id.is_(None))
        else:
            try:
                target_uuid = UUID(clean_assignee)
                base_conditions.append(Enquiry.assigned_admin_id == target_uuid)
            except ValueError:
                # Malformed UUID ignores filter or returns empty
                base_conditions.append(Enquiry.assigned_admin_id.is_(None))

    if search and search.strip():
        term = f"%{search.strip()}%"
        base_conditions.append(
            or_(
                Enquiry.reference_number.ilike(term),
                Enquiry.company_name.ilike(term),
                Enquiry.full_name.ilike(term),
                Enquiry.business_email.ilike(term),
            )
        )

    # 1. Total items count query
    count_stmt = select(func.count(Enquiry.id)).where(*base_conditions)
    total_items = (await db.scalar(count_stmt)) or 0
    total_pages = math.ceil(total_items / limit) if total_items > 0 else 1

    # 2. Sorting selection
    sort_column = Enquiry.created_at
    if sort_by == "reference_number":
        sort_column = Enquiry.reference_number
    elif sort_by == "company_name":
        sort_column = Enquiry.company_name
    elif sort_by == "status":
        sort_column = Enquiry.status

    order_expr = (
        sort_column.asc() if sort_order.lower() == "asc" else sort_column.desc()
    )

    offset = (page - 1) * limit
    stmt = (
        select(Enquiry)
        .options(
            selectinload(Enquiry.current_division),
            selectinload(Enquiry.assigned_admin),
        )
        .where(*base_conditions)
        .order_by(order_expr)
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(stmt)
    enquiries = result.scalars().all()

    items: list[EnquiryListItem] = []
    for enq in enquiries:
        assigned_summary = (
            AdminAssignedUserSummary(
                id=enq.assigned_admin.id,
                name=f"{enq.assigned_admin.first_name} {enq.assigned_admin.last_name}".strip(),
                email=enq.assigned_admin.email,
                job_title=enq.assigned_admin.job_title,
            )
            if enq.assigned_admin
            else None
        )

        # SEC-02 Data Minimization: contact_name and business_email are strictly omitted
        items.append(
            EnquiryListItem(
                id=enq.id,
                reference_number=enq.reference_number,
                created_at=enq.created_at,
                company_name=enq.company_name,
                country=enq.country,
                division_id=enq.current_division_id,
                division_name=enq.current_division.name,
                product_focus=enq.product_focus,
                status=enq.status,
                assigned_admin=assigned_summary,
            )
        )

    return EnquiryListEnvelope(
        success=True,
        data=EnquiryListResponseData(
            items=items,
            pagination=PaginationMetadata(
                page=page,
                limit=limit,
                total_items=total_items,
                total_pages=total_pages,
            ),
        ),
    )


# ==============================================================================
# Endpoint 3: Enquiry Detail Dossier
# ==============================================================================


@router.get(
    "/rfqs/{id}",
    response_model=EnquiryDetailEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Retrieve full commercial enquiry dossier and timeline",
    dependencies=[Depends(require_admin_user)],
)
async def get_enquiry_detail(
    id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EnquiryDetailEnvelope:
    """Returns complete submitter dossier, specifications, assignment timeline, and notes."""
    return await _load_full_enquiry_dossier(db, id)


# ==============================================================================
# Endpoint 4: Central Operations Assignment (Division Locked)
# ==============================================================================


@router.post(
    "/rfqs/{id}/assign",
    response_model=EnquiryDetailEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Assign or reassign enquiry to central operations administrator",
    dependencies=[Depends(require_admin_user), Depends(verify_csrf_token)],
)
async def assign_enquiry(
    id: UUID,
    payload: EnquiryAssignmentRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AdminUser, Depends(get_current_user)],
) -> EnquiryDetailEnvelope:
    """Assigns or transfers an enquiry between authorized central administrators.

    Rules:
    - Customer's original division (current_division_id) is strictly preserved and cannot be altered.
    - enquiry_assignments.new_division_id receives current_division_id to satisfy column constraints.
    - If enquiry is in 'NEW' status, it auto-transitions to 'ASSIGNED' upon assignment.
    - All entity updates, history creation, and audit logging commit atomically.
    """
    # 1. Acquire row-level lock on enquiry
    stmt = (
        select(Enquiry)
        .where(Enquiry.id == id, Enquiry.deleted_at.is_(None))
        .with_for_update()
    )
    result = await db.execute(stmt)
    enquiry = result.scalar_one_or_none()

    if not enquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enquiry not found",
        )

    # 2. Validate target assignee exists and is active if assigned_admin_id provided
    if payload.assigned_admin_id is not None:
        stmt_admin = select(AdminUser).where(
            AdminUser.id == payload.assigned_admin_id,
            AdminUser.is_active == True,
            AdminUser.deleted_at.is_(None),
        )
        target_admin = (await db.execute(stmt_admin)).scalar_one_or_none()
        if not target_admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target administrator does not exist or is inactive",
            )

    prev_admin_id = enquiry.assigned_admin_id
    new_admin_id = payload.assigned_admin_id

    # 3. Create EnquiryAssignment record (preserving current_division_id)
    assignment = EnquiryAssignment(
        enquiry_id=enquiry.id,
        previous_division_id=enquiry.current_division_id,
        new_division_id=enquiry.current_division_id,
        previous_admin_id=prev_admin_id,
        new_admin_id=new_admin_id,
        assigned_by_admin_id=current_user.id,
        assignment_rationale=payload.assignment_rationale,
    )
    db.add(assignment)

    # 4. Update enquiry handling administrator
    enquiry.assigned_admin_id = new_admin_id

    # 5. Auto-transition from NEW to ASSIGNED if allocating to an administrator
    if enquiry.status == "NEW" and new_admin_id is not None:
        enquiry.status = "ASSIGNED"
        status_hist = EnquiryStatusHistory(
            enquiry_id=enquiry.id,
            old_status="NEW",
            new_status="ASSIGNED",
            change_reason="Auto-transitioned on administrative assignment",
            changed_by_admin_id=current_user.id,
        )
        db.add(status_hist)

    # 6. Record synchronous audit log
    await record_audit_log(
        session=db,
        actor_admin=current_user,
        action="ENQUIRY_ASSIGNED",
        entity_table="enquiries",
        entity_id=enquiry.id,
        old_state={"assigned_admin_id": str(prev_admin_id) if prev_admin_id else None},
        new_state={
            "assigned_admin_id": str(new_admin_id) if new_admin_id else None,
            "assignment_rationale": payload.assignment_rationale,
        },
        request=request,
    )

    await db.commit()

    return await _load_full_enquiry_dossier(db, enquiry.id)


# ==============================================================================
# Endpoint 5: Lifecycle Status Transition
# ==============================================================================


@router.patch(
    "/rfqs/{id}/status",
    response_model=EnquiryDetailEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Transition enquiry lifecycle status with mandatory rationale",
    dependencies=[Depends(require_admin_user), Depends(verify_csrf_token)],
)
async def update_enquiry_status(
    id: UUID,
    payload: EnquiryStatusUpdateRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AdminUser, Depends(get_current_user)],
) -> EnquiryDetailEnvelope:
    """Transitions the enquiry status according to the authoritative transition matrix."""
    # 1. Acquire row-level lock
    stmt = (
        select(Enquiry)
        .where(Enquiry.id == id, Enquiry.deleted_at.is_(None))
        .with_for_update()
    )
    result = await db.execute(stmt)
    enquiry = result.scalar_one_or_none()

    if not enquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enquiry not found",
        )

    old_status = enquiry.status
    new_status = payload.new_status

    # 2. Reject same-status progression
    if old_status == new_status:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Enquiry is already in status '{old_status}'",
        )

    # 3. Check permitted transitions matrix
    allowed = PERMITTED_TRANSITIONS.get(old_status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Status transition from '{old_status}' to '{new_status}' is not permitted. "
                f"Allowed transitions: {sorted(allowed)}"
            ),
        )

    # 4. Check terminal status reopening permissions (SUPER_ADMIN required)
    user_roles = {r.id for r in current_user.roles}
    if (
        (old_status, new_status) in SUPER_ADMIN_REQUIRED_TRANSITIONS
        and "SUPER_ADMIN" not in user_roles
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Reopening a '{old_status}' enquiry requires SUPER_ADMIN authority.",
        )

    # 5. Insert status history record
    history_entry = EnquiryStatusHistory(
        enquiry_id=enquiry.id,
        old_status=old_status,
        new_status=new_status,
        change_reason=payload.change_reason,
        changed_by_admin_id=current_user.id,
    )
    db.add(history_entry)

    # 6. Apply status mutation to enquiry
    enquiry.status = new_status

    # 7. Record synchronous audit log
    await record_audit_log(
        session=db,
        actor_admin=current_user,
        action="STATUS_CHANGED",
        entity_table="enquiries",
        entity_id=enquiry.id,
        old_state={"status": old_status},
        new_state={
            "status": new_status,
            "change_reason": payload.change_reason,
        },
        request=request,
    )

    await db.commit()

    return await _load_full_enquiry_dossier(db, enquiry.id)


# ==============================================================================
# Endpoint 6: Internal Operational Notes
# ==============================================================================


@router.post(
    "/rfqs/{id}/notes",
    response_model=EnquiryNoteResponseEnvelope,
    status_code=status.HTTP_201_CREATED,
    summary="Append internal operational note to enquiry",
    dependencies=[Depends(require_admin_user), Depends(verify_csrf_token)],
)
async def add_enquiry_note(
    id: UUID,
    payload: EnquiryNoteCreateRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AdminUser, Depends(get_current_user)],
) -> EnquiryNoteResponseEnvelope:
    """Appends an internal operational follow-up note. Never exposed through public APIs."""
    stmt = select(Enquiry).where(Enquiry.id == id, Enquiry.deleted_at.is_(None))
    enquiry = (await db.execute(stmt)).scalar_one_or_none()

    if not enquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enquiry not found",
        )

    # 1. Create EnquiryNote
    note = EnquiryNote(
        enquiry_id=enquiry.id,
        admin_user_id=current_user.id,
        note_text=payload.note_text,
        is_internal_only=True,
    )
    db.add(note)
    await db.flush()

    # 2. Record synchronous audit log
    await record_audit_log(
        session=db,
        actor_admin=current_user,
        action="NOTE_ADDED",
        entity_table="enquiry_notes",
        entity_id=note.id,
        old_state=None,
        new_state={
            "enquiry_id": str(enquiry.id),
            "is_internal_only": True,
        },
        request=request,
    )

    await db.commit()

    return EnquiryNoteResponseEnvelope(
        success=True,
        data=EnquiryNoteItem(
            id=note.id,
            author_admin=AdminAssignedUserSummary(
                id=current_user.id,
                name=f"{current_user.first_name} {current_user.last_name}".strip(),
                email=current_user.email,
                job_title=current_user.job_title,
            ),
            note_text=note.note_text,
            is_internal_only=note.is_internal_only,
            created_at=note.created_at,
        ),
    )


# ==============================================================================
# Endpoint 7: Active Administrators Directory (Data-Minimized)
# ==============================================================================


@router.get(
    "/administrators",
    response_model=AdminAssigneesEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Retrieve active central administrators for assignment directory",
    dependencies=[Depends(require_admin_user)],
)
async def list_administrators(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminAssigneesEnvelope:
    """Returns active central administrators. Excludes credentials, sessions, and tokens."""
    stmt = (
        select(AdminUser)
        .options(selectinload(AdminUser.roles))
        .where(AdminUser.is_active == True, AdminUser.deleted_at.is_(None))
        .order_by(AdminUser.first_name.asc(), AdminUser.last_name.asc())
    )
    result = await db.execute(stmt)
    admins = result.scalars().all()

    assignees = [
        AdminAssigneeSummary(
            id=admin.id,
            first_name=admin.first_name,
            last_name=admin.last_name,
            email=admin.email,
            job_title=admin.job_title,
            roles=[r.id for r in admin.roles],
        )
        for admin in admins
    ]

    return AdminAssigneesEnvelope(success=True, data=assignees)


# ==============================================================================
# Endpoint 8: Audit Log Inspection (SUPER_ADMIN strictly)
# ==============================================================================


@router.get(
    "/audit-logs",
    response_model=AuditLogListEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Inspect application-level audit ledger (SUPER_ADMIN strictly)",
    dependencies=[Depends(require_super_admin)],
)
async def list_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1, description="Page index (1-based)"),
    limit: int = Query(default=50, ge=1, le=100, description="Items per page"),
    action: str | None = Query(default=None, description="Filter by action identifier"),
    entity_table: str | None = Query(default=None, description="Filter by affected entity table"),
) -> AuditLogListEnvelope:
    """Returns a paginated list of immutable operational audit logs. Restricted to SUPER_ADMIN."""
    base_conditions = []
    if action and action.strip():
        base_conditions.append(AuditLog.action == action.strip())
    if entity_table and entity_table.strip():
        base_conditions.append(AuditLog.entity_table == entity_table.strip())

    count_stmt = select(func.count(AuditLog.id))
    if base_conditions:
        count_stmt = count_stmt.where(*base_conditions)
    total_items = (await db.scalar(count_stmt)) or 0
    total_pages = math.ceil(total_items / limit) if total_items > 0 else 1

    offset = (page - 1) * limit
    stmt = (
        select(AuditLog)
        .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
    )
    if base_conditions:
        stmt = stmt.where(*base_conditions)

    result = await db.execute(stmt)
    logs = result.scalars().all()

    items = [
        AuditLogListItem(
            id=entry.id,
            timestamp=entry.timestamp,
            actor_admin_id=entry.actor_admin_id,
            actor_email=entry.actor_email,
            ip_address=str(entry.ip_address) if entry.ip_address else None,
            action=entry.action,
            entity_table=entry.entity_table,
            entity_id=entry.entity_id,
            old_state=entry.old_state,
            new_state=entry.new_state,
            client_user_agent=entry.client_user_agent,
        )
        for entry in logs
    ]

    return AuditLogListEnvelope(
        success=True,
        data=AuditLogListResponseData(
            items=items,
            pagination=PaginationMetadata(
                page=page,
                limit=limit,
                total_items=total_items,
                total_pages=total_pages,
            ),
        ),
    )
