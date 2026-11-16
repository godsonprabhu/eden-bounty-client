"""Public Ingestion Endpoints for Commercial Divisions and Trade RFQ Enquiries.

Phase C13.3 — Final Corrective Pass:
Endpoints:
- GET  /api/v1/public/divisions
- POST /api/v1/public/rfq/enquire
"""

import asyncio
import hashlib
import json
import secrets
from datetime import UTC, datetime
from typing import Annotated, Any, Final

from app.api.deps import get_db
from app.core.rate_limit import public_rate_limiter
from app.models.division import Division
from app.models.enquiry import Enquiry
from app.schemas.public import (
    DivisionPublic,
    DivisionsResponseEnvelope,
    EnquiryCreateRequest,
    EnquiryResponseData,
    EnquiryResponseEnvelope,
)
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

router = APIRouter(prefix="/public", tags=["Public Ingestion"])


def generate_cryptographic_reference() -> str:
    """Generates a cryptographically secure random RFQ reference with >= 64 bits of entropy.

    Format: EB-RFQ-YYYYMMDD-XXXXXXXXXXXXXXXX (e.g. EB-RFQ-20261108-A1B2C3D4E5F67890).
    Uses secrets.token_hex(8) (CSPRNG) providing 64 bits of cryptographic entropy.
    Does NOT use database COUNT(*) to prevent concurrency bottlenecks and race conditions.
    Internal database IDs are never exposed.
    """
    date_str = datetime.now(UTC).strftime("%Y%m%d")
    suffix = secrets.token_hex(8).upper()
    return f"EB-RFQ-{date_str}-{suffix}"


def _normalize_optional(val: str | None) -> str | None:
    """Normalizes optional string fields: trims whitespace, maps empty strings to None."""
    if val is None:
        return None
    cleaned = val.strip()
    return cleaned if cleaned else None


def compute_payload_hash(payload: EnquiryCreateRequest) -> str:
    """Computes a deterministic SHA-256 fingerprint over all 13 canonical commercial fields.

    Builds a canonical dictionary containing all 13 commercial enquiry fields,
    normalizes values consistently, serializes using json.dumps with sorted keys
    and compact separators (',', ':'), and encodes as UTF-8 before calculating SHA-256.
    This eliminates delimiter ambiguity or field-shifting collisions.
    """
    canonical_dict: dict[str, str | None] = {
        "additional_notes": _normalize_optional(payload.additional_notes),
        "business_email": str(payload.business_email).strip().lower(),
        "company_name": payload.company_name.strip(),
        "contact_number": _normalize_optional(payload.contact_number),
        "country": payload.country.strip(),
        "division_id": payload.division_id.strip(),
        "full_name": payload.full_name.strip(),
        "preferred_incoterm": _normalize_optional(payload.preferred_incoterm),
        "product_focus": payload.product_focus.strip(),
        "quantity": str(payload.quantity) if payload.quantity is not None else None,
        "specifications": _normalize_optional(payload.specifications),
        "target_destination_port": _normalize_optional(payload.target_destination_port),
        "unit_of_measurement": _normalize_optional(payload.unit_of_measurement),
    }
    serialized_bytes = json.dumps(
        canonical_dict,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized_bytes).hexdigest()


def resolve_and_validate_idempotency_key(
    request: Request,
    payload: EnquiryCreateRequest,
) -> str | None:
    """Extracts, validates, and reconciles idempotency keys from headers and body.

    Supported sources:
    - `Idempotency-Key` HTTP header
    - `X-Idempotency-Key` HTTP header
    - Request body field (`payload.idempotency_key`)

    Validation rules:
    - Maximum length: 128 characters. Oversized keys are rejected with HTTP 400.
    - Empty or whitespace-only header values are rejected with HTTP 400.
    - If both headers are supplied:
      * Identical normalized values are accepted.
      * Conflicting values are rejected with HTTP 400.
    - If both a header and a body key are supplied:
      * Identical values are accepted.
      * Conflicting values are rejected with HTTP 400.
    - Returns the normalized key string, or None if no key was supplied.
    """
    raw_idem = request.headers.get("idempotency-key")
    raw_x_idem = request.headers.get("x-idempotency-key")

    header_candidates: list[tuple[str, str]] = []
    if raw_idem is not None:
        header_candidates.append(("Idempotency-Key", raw_idem))
    if raw_x_idem is not None:
        header_candidates.append(("X-Idempotency-Key", raw_x_idem))

    resolved_header_key: str | None = None

    if header_candidates:
        cleaned_headers: list[tuple[str, str]] = []
        for name, val in header_candidates:
            cleaned = val.strip()
            if not cleaned:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"'{name}' header cannot be empty or contain only whitespace.",
                )
            if len(cleaned) > 128:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"'{name}' header exceeds maximum allowed length of 128 characters.",
                )
            cleaned_headers.append((name, cleaned))

        if len(cleaned_headers) == 2 and cleaned_headers[0][1] != cleaned_headers[1][1]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conflicting idempotency keys provided in 'Idempotency-Key' and 'X-Idempotency-Key' headers.",
            )

        resolved_header_key = cleaned_headers[0][1]

    body_key = payload.idempotency_key.strip() if payload.idempotency_key else None

    if resolved_header_key and body_key:
        if resolved_header_key != body_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conflicting idempotency keys provided in HTTP header and request body.",
            )
        return resolved_header_key

    return resolved_header_key or body_key


# The exactly six canonical commercial divisions exposed publicly
PUBLIC_CANONICAL_SERVICES: Final[list[dict[str, str]]] = [
    {
        "id": "mineral-water",
        "name": "Mineral Water",
        "fallback_sector": "Commercial Division",
        "fallback_accent_color": "#0284C7",
    },
    {
        "id": "scrap-trading",
        "name": "Scrap Trading",
        "fallback_sector": "Commercial Division",
        "fallback_accent_color": "#10B981",
    },
    {
        "id": "construction",
        "name": "Construction / Building Promotion",
        "fallback_sector": "Commercial Division",
        "fallback_accent_color": "#F59E0B",
    },
    {
        "id": "petroleum-products",
        "name": "Petroleum Products",
        "fallback_sector": "Commercial Division",
        "fallback_accent_color": "#EF4444",
    },
    {
        "id": "furnace-oil",
        "name": "Furnace Oil",
        "fallback_sector": "Commercial Division",
        "fallback_accent_color": "#6366F1",
    },
    {
        "id": "agricultural-drones",
        "name": "Drone Solutions",
        "fallback_sector": "Commercial Division",
        "fallback_accent_color": "#00E5FF",
    },
]


@router.get(
    "/divisions",
    response_model=DivisionsResponseEnvelope,
    status_code=status.HTTP_200_OK,
    summary="List active commercial divisions",
)
async def list_public_divisions(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DivisionsResponseEnvelope:
    """Retrieves confirmed active commercial divisions for EDEN BOUNTY.

    Enforces public request rate limit (10 requests / minute per client IP).
    Exposes display names, theme accent colors, and sectors for the exactly six
    approved public services: Mineral Water, Scrap Trading, Construction /
    Building Promotion, Petroleum Products, Furnace Oil, and Drone Solutions.
    Excludes duplicate Building Promotions, withdrawn services (Shisha Tobacco,
    Axe Oil, Industrial Lubricants), internal EB-DIV codes, and unverified
    manufacturer attributions or legacy disclaimers.
    Zero internal administrative data is leaked.
    """
    await public_rate_limiter.check_request_rate_limit(request)

    canonical_ids = [s["id"] for s in PUBLIC_CANONICAL_SERVICES]
    stmt = (
        select(Division)
        .where(
            Division.id.in_(canonical_ids),
            Division.is_active.is_(True),
        )
    )
    result = await db.execute(stmt)
    db_divs = {div.id: div for div in result.scalars().all()}

    divisions: list[DivisionPublic] = []
    for s in PUBLIC_CANONICAL_SERVICES:
        db_div = db_divs.get(s["id"])
        if not db_div:
            continue
        divisions.append(
            DivisionPublic(
                id=s["id"],
                name=s["name"],
                sector=db_div.sector if db_div else s["fallback_sector"],
                accent_color=db_div.accent_color if db_div else s["fallback_accent_color"],
                manufacturer_attribution=None,
                disclaimer=None,
            )
        )

    return DivisionsResponseEnvelope(
        success=True,
        data=divisions,
    )


_ACTIVE_TASKS: set[asyncio.Task[Any]] = set()


async def _shield_execute(coro: Any) -> Any:
    """Executes a coroutine shielded from cancellation and awaits its completion.

    Resilient to arbitrary repeated cancellations:
    - Retains a strong reference to the background task in `_ACTIVE_TASKS`
      to prevent premature garbage collection.
    - Loops until `task.done()` is True, catching any subsequent CancelledError.
    - Verifies completion of the underlying operation.
    - Re-raises CancelledError only after completion if any cancellation was received.
    """
    task = asyncio.create_task(coro)
    _ACTIVE_TASKS.add(task)
    task.add_done_callback(_ACTIVE_TASKS.discard)

    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True

    if cancelled:
        raise asyncio.CancelledError()

    return task.result()


async def _reconcile_enquiry_persistence(
    db: AsyncSession,
    reference_number: str,
) -> bool | None:
    """Reconciles whether an enquiry with `reference_number` was persisted.

    Returns:
    - True: confirmed persisted in database.
    - False: confirmed NOT in database (confirmed rollback).
    - None: ambiguous / cannot verify (e.g. database unreachable).
    """
    try:
        bind = getattr(db, "bind", None)
        if bind is None:
            return None
        session_factory = async_sessionmaker(
            bind=bind,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with session_factory() as check_session:
            stmt = select(Enquiry.id).where(
                Enquiry.reference_number == reference_number
            )
            res = await check_session.execute(stmt)
            return res.scalar_one_or_none() is not None
    except (SQLAlchemyError, OSError, ConnectionError, TimeoutError, RuntimeError):
        return None


POSTGRES_CONFIRMED_ABORT_SQLSTATES: Final[frozenset[str]] = frozenset(
    {
        "40001",  # serialization_failure
        "40P01",  # deadlock_detected
        "40002",  # transaction_integrity_constraint_violation
        "25P02",  # in_failed_sql_transaction
        "23505",  # unique_violation
        "23503",  # foreign_key_violation
        "23514",  # check_violation
    }
)


def extract_sqlstate(exc: BaseException | None) -> str | None:
    """Extracts the structured 5-character SQLSTATE code from a database exception."""
    if exc is None:
        return None
    code = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
    if isinstance(code, str) and len(code) == 5:
        return code.upper()

    orig = getattr(exc, "orig", None)
    if orig is not None:
        orig_code = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
        if isinstance(orig_code, str) and len(orig_code) == 5:
            return orig_code.upper()

    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        cause_code = getattr(cause, "sqlstate", None) or getattr(cause, "pgcode", None)
        if isinstance(cause_code, str) and len(cause_code) == 5:
            return cause_code.upper()

    return None


@router.post(
    "/rfq/enquire",
    response_model=EnquiryResponseEnvelope,
    status_code=status.HTTP_201_CREATED,
    summary="Submit public corporate trade enquiry (RFQ)",
)
async def submit_rfq_enquiry(
    request: Request,
    payload: EnquiryCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EnquiryResponseEnvelope:
    """Ingests commercial trade inquiries from prospective corporate buyers worldwide.

    Enforces:
    - In-process sliding window rate limiting:
      * 10 requests / minute per IP on public routes.
      * Atomic in-flight reservation for 5 submissions / 10 minutes per IP.
    - Honeypot anti-bot silent rejection (website_url_hp).
    - Active commercial division verification against database master records.
    - Client-generated idempotency key support:
      * Identical payload retry returns existing enquiry reference without quota loss.
      * Same key with altered payload returns HTTP 409 Conflict.
      * Submissions without idempotency keys create distinct enquiries without field suppression.
    - 64-bit cryptographic entropy reference generation (EB-RFQ-YYYYMMDD-XXXXXXXXXXXXXXXX).
    - Transactional persistence using PostgreSQL savepoints with bounded retry on collision.
    - Accurate API confirmation messages (no unsupported claims of email dispatch).
    """
    # 1. Rate Limiting: check global request limit and acquire atomic submission slot
    client_ip = await public_rate_limiter.check_request_rate_limit(request)
    # Opportunistically recover any previously unresolved ambiguous reservations for this IP
    await public_rate_limiter.reconcile_pending_for_ip(client_ip, db)
    reservation = await public_rate_limiter.acquire_submission_slot(client_ip)

    persisted = False
    persistence_ambiguous = False
    try:
        # 2. Resolve and validate Idempotency Key immediately (before database access)
        idempotency_key = resolve_and_validate_idempotency_key(request, payload)
        req_hash = compute_payload_hash(payload) if idempotency_key else None

        # 3. Honeypot Anti-Bot Inspection (C13-security-design.md Section 4.3)
        if payload.website_url_hp and payload.website_url_hp.strip():
            await reservation.release()
            fake_ref = generate_cryptographic_reference()
            return EnquiryResponseEnvelope(
                success=True,
                data=EnquiryResponseData(
                    reference_number=fake_ref,
                    status="NEW",
                    message=f"Enquiry received and registered successfully. Reference {fake_ref}.",
                ),
            )

        # 4. Verify selected division exists and is active (database query)
        div_stmt = select(Division).where(
            Division.id == payload.division_id,
            Division.is_active.is_(True),
        )
        division = (await db.execute(div_stmt)).scalar_one_or_none()
        if not division:
            await reservation.release()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Commercial division '{payload.division_id}' is invalid or inactive. "
                    "Must be one of the verified active EDEN BOUNTY divisions."
                ),
            )

        normalized_email = str(payload.business_email).strip().lower()

        # 5. Check idempotency in database
        if idempotency_key:
            # Query existing submission with this idempotency key
            idem_stmt = select(Enquiry).where(
                Enquiry.idempotency_key == idempotency_key
            )
            existing_idem = (await db.execute(idem_stmt)).scalar_one_or_none()
            if existing_idem:
                # Same key and same payload: return original reference without consuming quota
                if existing_idem.request_payload_hash == req_hash:
                    await reservation.release()
                    return EnquiryResponseEnvelope(
                        success=True,
                        data=EnquiryResponseData(
                            reference_number=existing_idem.reference_number,
                            status=existing_idem.status,
                            message=f"Enquiry received and registered successfully. Reference {existing_idem.reference_number}.",
                        ),
                    )
                # Same key with different payload: reject with 409 Conflict
                await reservation.release()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Idempotency key '{idempotency_key}' has already been used with a different request payload.",
                )

        # 5. Persist to PostgreSQL with bounded collision retry & savepoint isolation
        user_agent = request.headers.get("user-agent")
        max_retries = 5
        assigned_ref = ""

        for attempt in range(max_retries):
            candidate_ref = generate_cryptographic_reference()
            await reservation.attach_reference(candidate_ref)
            try:
                async with db.begin_nested():  # SAVEPOINT in PostgreSQL
                    enquiry = Enquiry(
                        reference_number=candidate_ref,
                        idempotency_key=idempotency_key,
                        request_payload_hash=req_hash,
                        full_name=payload.full_name,
                        company_name=payload.company_name,
                        business_email=normalized_email,
                        contact_number=payload.contact_number,
                        country=payload.country,
                        initial_division_id=division.id,
                        current_division_id=division.id,
                        product_focus=payload.product_focus,
                        quantity=payload.quantity,
                        unit_of_measurement=payload.unit_of_measurement,
                        specifications=payload.specifications,
                        additional_notes=payload.additional_notes,
                        preferred_incoterm=payload.preferred_incoterm,
                        target_destination_port=payload.target_destination_port,
                        status="NEW",
                        source_ip=client_ip,
                        client_user_agent=user_agent,
                    )
                    db.add(enquiry)
                    await db.flush()

                # Savepoint succeeded without collision.
                # Commit root transaction shielded against request cancellation.
                commit_task = asyncio.create_task(db.commit())
                _ACTIVE_TASKS.add(commit_task)
                commit_task.add_done_callback(_ACTIVE_TASKS.discard)

                commit_cancelled = False
                while not commit_task.done():
                    try:
                        await asyncio.shield(commit_task)
                    except asyncio.CancelledError:
                        commit_cancelled = True
                    except (
                        SQLAlchemyError,
                        OSError,
                        ConnectionError,
                        TimeoutError,
                        RuntimeError,
                    ):
                        break

                if commit_task.cancelled():
                    # commit_task was cancelled directly: verify whether DB persisted
                    reconciled = await _reconcile_enquiry_persistence(db, candidate_ref)
                    if reconciled is True:
                        persisted = True
                        assigned_ref = candidate_ref
                        raise asyncio.CancelledError()
                    elif reconciled is False:
                        persisted = False
                        persistence_ambiguous = False
                        raise asyncio.CancelledError()
                    else:
                        persisted = False
                        persistence_ambiguous = True
                        raise asyncio.CancelledError()

                commit_exc = commit_task.exception()
                if commit_exc is None:
                    # Database commit succeeded definitively!
                    persisted = True
                    assigned_ref = candidate_ref
                    if commit_cancelled:
                        raise asyncio.CancelledError()
                    break

                # db.commit() raised an exception: do not assume rollback!
                # Attempt active persistence reconciliation
                reconciled = await _reconcile_enquiry_persistence(db, candidate_ref)
                if reconciled is True:
                    # Confirmed persisted despite commit exception!
                    persisted = True
                    assigned_ref = candidate_ref
                    if commit_cancelled:
                        raise asyncio.CancelledError()
                    break
                else:
                    # Row absent or DB unreachable:
                    # Determine whether PostgreSQL conclusively confirmed transaction termination
                    is_confirmed_abort = False
                    if commit_exc is not None:
                        sqlstate = extract_sqlstate(commit_exc)
                        if sqlstate in POSTGRES_CONFIRMED_ABORT_SQLSTATES:
                            is_confirmed_abort = True

                    if is_confirmed_abort and reconciled is False:
                        # Conclusively confirmed rollback in PostgreSQL: safely release
                        persisted = False
                        persistence_ambiguous = False
                        if commit_cancelled:
                            raise asyncio.CancelledError()
                        raise commit_exc
                    else:
                        # Original transaction may still commit: hold as AMBIGUOUS!
                        persisted = False
                        persistence_ambiguous = True
                        if commit_cancelled:
                            raise asyncio.CancelledError()
                        raise commit_exc
            except IntegrityError as exc:
                err_str = str(exc).lower()

                # If idempotency key collided under concurrent race condition:
                if idempotency_key and "idempotency_key" in err_str:
                    race_stmt = select(Enquiry).where(
                        Enquiry.idempotency_key == idempotency_key
                    )
                    existing_race = (await db.execute(race_stmt)).scalar_one_or_none()
                    if existing_race:
                        if existing_race.request_payload_hash == req_hash:
                            await reservation.release()
                            return EnquiryResponseEnvelope(
                                success=True,
                                data=EnquiryResponseData(
                                    reference_number=existing_race.reference_number,
                                    status=existing_race.status,
                                    message=f"Enquiry received and registered successfully. Reference {existing_race.reference_number}.",
                                ),
                            )
                        await reservation.release()
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=f"Idempotency key '{idempotency_key}' has already been used with a different request payload.",
                        ) from None

                # If reference_number collided (1 in 1.84e19 chance), retry next candidate
                if "reference_number" in err_str and attempt < max_retries - 1:
                    continue
                if "reference_number" in err_str:
                    await reservation.release()
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to generate a unique enquiry reference number after maximum retries.",
                    )
                raise

        if not assigned_ref:
            await reservation.release()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate a unique enquiry reference number after maximum retries.",
            )

        # 6. Commit submission reservation quota
        await _shield_execute(reservation.commit())

        return EnquiryResponseEnvelope(
            success=True,
            data=EnquiryResponseData(
                reference_number=assigned_ref,
                status="NEW",
                message=f"Enquiry received and registered successfully. Reference {assigned_ref}.",
            ),
        )

    finally:
        if persistence_ambiguous:
            # Ambiguous database outcome: do NOT release reservation; holds admission quota safely
            pass
        elif persisted:
            if not reservation.is_committed:
                try:
                    await _shield_execute(reservation.commit())
                except asyncio.CancelledError:
                    pass
        else:
            if not reservation.is_released:
                try:
                    await _shield_execute(reservation.release())
                except asyncio.CancelledError:
                    pass
