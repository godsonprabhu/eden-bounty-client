"""In-process Sliding-Window Rate Limiting and Anti-Abuse Controls.

Phase C13.3 — Final Corrective Pass:
- Immediate Proxy Verification: Trust X-Forwarded-For ONLY when the immediate connection
  originates from an explicitly configured trusted proxy (TRUSTED_PROXIES).
  CF-Connecting-IP is independently segregated and trusted ONLY when the immediate
  peer is verified against explicit Cloudflare proxy ranges (TRUSTED_CLOUDFLARE_PROXIES).
- External Spoof Protection: Disregards forwarded headers from untrusted clients.
- Rate Limit Segregation:
  * Public requests: 10 requests per minute per IP (e.g. GET /divisions, POST /rfq/enquire).
  * RFQ submissions: Maximum 5 submissions per IP per 10-minute sliding window.
- Atomic Submission Reservation: Prevents check/record concurrency races by reserving
  in-flight submission slots and committing them only upon successful persistence.
- Zero Redis dependency: In-memory timestamp deques with periodic garbage pruning.

IMPORTANT ARCHITECTURAL NOTE:
This rate limiter is strictly in-process and in-memory. It requires running a single
worker process (WORKERS=1). If scaling horizontally to multiple replicas or multiple
Uvicorn workers, rate limiting must be migrated to a centralized store (e.g. Redis)
or handled at the edge/reverse proxy layer (e.g. Cloudflare Rate Limiting or Nginx limit_req).
"""

import asyncio
import ipaddress
import secrets
import time
from collections import defaultdict
from enum import Enum
from typing import Any, Final, NamedTuple

from fastapi import HTTPException, Request, status

from app.core.config import settings


class ReservationStatus(str, Enum):
    """Lifecycle states of a submission rate-limit reservation."""

    PENDING = "PENDING"
    COMMITTED = "COMMITTED"
    RELEASED = "RELEASED"


class ReservationRecord(NamedTuple):
    """Internal lifecycle tracking record for an issued reservation."""

    token: str
    ip: str
    created_at: float
    expires_at: float
    status: ReservationStatus
    resolved_at: float | None = None
    reference_number: str | None = None
    reconciliation_generation: int = 0


class ReservationEntry(NamedTuple):
    """Immutable record of an in-flight submission reservation."""

    token: str
    created_at: float
    expires_at: float


def is_trusted_proxy(ip_str: str, trusted_proxies: list[str]) -> bool:
    """Verifies whether an IP address matches the list of trusted proxy hosts or CIDR subnets.

    Raises ValueError if any entry in `trusted_proxies` is not a valid IPv4/IPv6 address or CIDR network.
    Returns False if `ip_str` is not a valid IP address.
    """
    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    matched = False
    for trusted in trusted_proxies:
        try:
            if "/" in trusted:
                network = ipaddress.ip_network(trusted, strict=False)
                if not matched and ip_obj in network:
                    matched = True
            else:
                trusted_ip = ipaddress.ip_address(trusted)
                if not matched and ip_obj == trusted_ip:
                    matched = True
        except ValueError as e:
            raise ValueError(
                f"Configuration error: '{trusted}' in trusted proxy list is not a valid IPv4/IPv6 address or CIDR network."
            ) from e

    return matched


def get_client_ip(
    request: Request,
    trusted_proxies: list[str] | None = None,
    trusted_cloudflare_proxies: list[str] | None = None,
) -> str:
    """Extracts the client IP address securely using right-to-left forwarding-chain validation.

    Security Strategy:
    1. Immediate Peer Check: Forwarded headers (CF-Connecting-IP, X-Forwarded-For) are evaluated
       ONLY if the immediate socket peer (request.client.host) is recognized in `trusted_proxies`
       or `trusted_cloudflare_proxies`. Direct untrusted clients attempting to forge forwarding
       headers are ignored, returning the immediate peer IP immediately.
    2. Cloudflare Segregation: CF-Connecting-IP is trusted ONLY when the immediate peer is
       independently verified against `trusted_cloudflare_proxies`. A generic trusted reverse proxy
       (e.g. Nginx or internal balancer) in `trusted_proxies` that passes through a client-supplied
       CF-Connecting-IP header will NOT cause that header to be trusted.
    3. CF-Connecting-IP Validation: If the immediate peer matches `trusted_cloudflare_proxies`,
       the CF-Connecting-IP header is validated as a valid IP address. If valid, it is returned.
       If invalid/malformed, it safely falls back to X-Forwarded-For evaluation.
    4. Right-to-Left Forwarding Chain: For X-Forwarded-For, hops are parsed from right to left
       (closest upstream hops first). All trusted proxy hops (from both trusted lists) are stripped.
       The first untrusted IP encountered from the right is selected as the genuine client address.
       This prevents a client from spoofing its rate-limit identity by prepending arbitrary forged IPs.
    5. Fallback: If no valid untrusted address is found, falls back safely to immediate_ip.
    """
    if trusted_proxies is None:
        trusted_proxies = settings.TRUSTED_PROXIES
    if trusted_cloudflare_proxies is None:
        trusted_cloudflare_proxies = settings.TRUSTED_CLOUDFLARE_PROXIES

    immediate_ip = "127.0.0.1"
    if request.client and request.client.host:
        immediate_ip = request.client.host.strip()

    is_cf_trusted = is_trusted_proxy(immediate_ip, trusted_cloudflare_proxies)
    is_general_trusted = is_trusted_proxy(immediate_ip, trusted_proxies)

    # 1. If immediate peer is untrusted, ignore all forwarded headers completely
    if not (is_cf_trusted or is_general_trusted):
        return immediate_ip

    # 2. CF-Connecting-IP: trusted ONLY if immediate peer is verified against Cloudflare proxies
    if is_cf_trusted:
        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip:
            candidate = cf_ip.strip()
            try:
                ipaddress.ip_address(candidate)
                return candidate
            except ValueError:
                # Malformed CF-Connecting-IP: safely fall back to X-Forwarded-For
                pass

    # 3. X-Forwarded-For: right-to-left evaluation stripping all trusted proxy hops
    combined_trusted = list(trusted_proxies) + list(trusted_cloudflare_proxies)
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # X-Forwarded-For chain: [client_forged...], client, proxy1, proxy2, ...
        # Parse from right to left (most proximate upstream hops first).
        # Strip trusted proxy hops; select the first untrusted IP address.
        hops = [entry.strip() for entry in xff.split(",") if entry.strip()]
        for hop in reversed(hops):
            try:
                ipaddress.ip_address(hop)
            except ValueError:
                # Malformed entry in forwarding chain: skip safely
                continue

            if is_trusted_proxy(hop, combined_trusted):
                # Intermediate hop is a trusted proxy: strip and continue leftward
                continue

            # First untrusted address encountered from the right is the genuine client IP
            return hop

    return immediate_ip


class SubmissionReservation:
    """Represents an atomic in-flight reservation slot for an RFQ submission."""

    def __init__(
        self,
        limiter: "SlidingWindowRateLimiter",
        ip: str,
        token: str,
        created_at: float,
        expires_at: float,
    ) -> None:
        self._limiter = limiter
        self._ip = ip
        self._token = token
        self._created_at = created_at
        self._expires_at = expires_at
        self._committed = False
        self._released = False

    @property
    def token(self) -> str:
        return self._token

    @property
    def created_at(self) -> float:
        return self._created_at

    @property
    def expires_at(self) -> float:
        return self._expires_at

    @property
    def is_expired(self) -> bool:
        """Indicates whether this reservation's in-flight slot has exceeded its 60-second window."""
        return time.time() > self._expires_at

    @property
    def is_committed(self) -> bool:
        """Indicates whether the reservation has committed to the rate limiter."""
        if self._committed:
            return True
        record = self._limiter._reservation_records.get(self._token)
        if (
            record is not None
            and record.ip == self._ip
            and record.status == ReservationStatus.COMMITTED
        ):
            self._committed = True
            return True
        return False

    @property
    def is_released(self) -> bool:
        """Indicates whether the reservation has been released."""
        if self._released:
            return True
        record = self._limiter._reservation_records.get(self._token)
        if (
            record is not None
            and record.ip == self._ip
            and record.status == ReservationStatus.RELEASED
        ):
            self._released = True
            return True
        return False

    async def attach_reference(self, reference_number: str) -> None:
        """Associates an enquiry reference number with this in-flight reservation."""
        await self._limiter.attach_reference(self._token, reference_number)

    async def commit(self) -> bool:
        """Confirms the submission upon successful database persistence.

        Consumes submission quota even if the reservation expired during processing.
        Strictly idempotent and concurrency-safe.
        """
        if self.is_committed:
            return True
        if self.is_released:
            return False

        success = await self._limiter._commit_reservation(self._ip, self._token)
        if success or self.is_committed:
            self._committed = True
            return True
        return False

    async def release(self) -> bool:
        """Releases the reserved slot (e.g. on duplicate retry or failed write).

        Does not consume submission quota. Strictly idempotent.
        """
        if self.is_released:
            return True
        if self.is_committed:
            return False

        success = await self._limiter._release_reservation(self._ip, self._token)
        if success or self.is_released:
            self._released = True
            return True
        return False


class SlidingWindowRateLimiter:
    """Thread-safe, in-process sliding window rate limiter.

    Tracks timestamps per client IP for:
    - Global public request rate (10 requests / 60 seconds)
    - RFQ submission rate (5 submissions / 600 seconds)
    Supports atomic reservations to prevent check/record race conditions.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._submissions: dict[str, list[float]] = defaultdict(list)
        self._reservations: dict[str, list[ReservationEntry]] = defaultdict(list)
        self._reservation_records: dict[str, ReservationRecord] = {}
        self._pending_tokens_by_ip: dict[str, set[str]] = defaultdict(set)
        self._last_prune: float = time.time()
        self._prune_interval_seconds: Final[float] = 300.0  # 5 minutes

    async def check_request_rate_limit(self, request: Request) -> str:
        """Enforces the 10 requests / minute rate limit for public endpoints.

        Returns the resolved client IP.
        Raises HTTPException(429) if request rate is exceeded.
        """
        ip = get_client_ip(request)
        now = time.time()

        async with self._lock:
            self._maybe_prune(now)

            window_1m = now - 60.0
            recent_requests = [t for t in self._requests[ip] if t > window_1m]
            if len(recent_requests) >= settings.PUBLIC_RATE_LIMIT_PER_MINUTE:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please wait a minute before submitting again.",
                )

            # Record this request attempt
            recent_requests.append(now)
            self._requests[ip] = recent_requests

        return ip

    async def acquire_submission_slot(self, ip: str) -> SubmissionReservation:
        """Atomically checks and reserves an in-flight submission slot.

        Prevents check/record race conditions where concurrent requests could
        simultaneously exceed the submission quota before any write commits.
        """
        now = time.time()

        async with self._lock:
            self._maybe_prune(now)

            window_10m = now - 600.0
            # Expire stale reservations (> 60s) from active in-flight count
            self._reservations[ip] = [
                r for r in self._reservations[ip] if r.expires_at > now
            ]
            recent_submissions = [t for t in self._submissions[ip] if t > window_10m]

            # Outstanding unresolved operations: all PENDING records for this IP
            # (includes both active < 60s slots and ongoing > 60s operations)
            pending_operations = sum(
                1
                for token in self._pending_tokens_by_ip[ip]
                if (rec := self._reservation_records.get(token))
                and rec.status == ReservationStatus.PENDING
            )

            total_in_flight = len(recent_submissions) + pending_operations
            if total_in_flight >= settings.PUBLIC_SUBMISSION_LIMIT_10MIN:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Submission limit reached for this IP. Please wait before submitting additional enquiries.",
                )

            token = secrets.token_urlsafe(16)
            created_at = now
            expires_at = now + 60.0
            entry = ReservationEntry(
                token=token, created_at=created_at, expires_at=expires_at
            )
            self._reservations[ip].append(entry)

            self._reservation_records[token] = ReservationRecord(
                token=token,
                ip=ip,
                created_at=created_at,
                expires_at=expires_at,
                status=ReservationStatus.PENDING,
                resolved_at=None,
            )
            self._pending_tokens_by_ip[ip].add(token)

            return SubmissionReservation(
                limiter=self,
                ip=ip,
                token=token,
                created_at=created_at,
                expires_at=expires_at,
            )

    async def _commit_reservation(self, ip: str, token: str) -> bool:
        """Removes the reservation and records a confirmed submission.

        If the reservation expired during processing, this method still consumes
        quota upon successful persistence, preventing rate-limit accounting gaps.
        Guarantees exactly-once quota accounting under concurrent and repeated calls.
        """
        now = time.time()
        async with self._lock:
            # 1. Remove from active in-flight reservations if still present
            self._reservations[ip] = [
                r for r in self._reservations[ip] if r.token != token
            ]

            # 2. Check reservation lifecycle state
            record = self._reservation_records.get(token)
            if record is None:
                # Defensive fallback for untracked mock reservations
                return False

            if record.ip != ip:
                return False

            if record.status != ReservationStatus.PENDING:
                # Already committed or released: prevent double-counting
                return False

            # 3. Transition status to COMMITTED with resolution timestamp
            self._reservation_records[token] = record._replace(
                status=ReservationStatus.COMMITTED,
                resolved_at=now,
            )
            self._pending_tokens_by_ip[ip].discard(token)

            # 4. Record confirmed submission timestamp in quota window
            self._submissions[ip].append(now)
            return True

    async def _release_reservation(self, ip: str, token: str) -> bool:
        """Releases the reservation slot without consuming submission quota.

        Guarantees that failed persistence, validation errors, or duplicate
        submissions do not consume quota. Strictly idempotent.
        """
        now = time.time()
        async with self._lock:
            # 1. Remove from active in-flight reservations if still present
            self._reservations[ip] = [
                r for r in self._reservations[ip] if r.token != token
            ]

            # 2. Check reservation lifecycle state
            record = self._reservation_records.get(token)
            if record is None:
                return False

            if record.ip != ip:
                return False

            if record.status != ReservationStatus.PENDING:
                # Already committed or released
                return False

            # 3. Transition status to RELEASED with resolution timestamp
            self._reservation_records[token] = record._replace(
                status=ReservationStatus.RELEASED,
                resolved_at=now,
            )
            self._pending_tokens_by_ip[ip].discard(token)
            return True

    async def get_reservation_status(self, token: str) -> ReservationStatus | None:
        """Returns the current lifecycle status of a reservation token, or None if unknown."""
        async with self._lock:
            record = self._reservation_records.get(token)
            return record.status if record else None

    async def attach_reference(self, token: str, reference_number: str) -> None:
        """Associates an enquiry reference number with an active reservation for reconciliation."""
        async with self._lock:
            record = self._reservation_records.get(token)
            if record is not None:
                self._reservation_records[token] = record._replace(
                    reference_number=reference_number
                )

    async def reconcile_pending_reservation(
        self,
        token: str,
        db: Any,
        confirmed_terminated: bool = False,
    ) -> ReservationStatus:
        """Authoritatively reconciles an ambiguous PENDING reservation against PostgreSQL state.

        - If the enquiry row exists in PostgreSQL: commits the reservation and consumes quota exactly once.
        - If the enquiry row is absent:
          * If `confirmed_terminated` is True: releases the reservation without consuming quota,
            provided no newer reconciliation generation has superseded this observation.
          * If `confirmed_terminated` is False: retains the reservation in PENDING to prevent quota bypass.
        - If database is unreachable: retains the reservation in PENDING.
        """
        async with self._lock:
            record = self._reservation_records.get(token)
            if record is None:
                return ReservationStatus.RELEASED
            if record.status != ReservationStatus.PENDING:
                return record.status
            ref = record.reference_number
            ip = record.ip
            my_generation = record.reconciliation_generation + 1
            self._reservation_records[token] = record._replace(
                reconciliation_generation=my_generation
            )

        if not ref:
            # Cannot reconcile without an associated reference number
            return ReservationStatus.PENDING

        # Query database outside the limiter lock
        row_exists: bool | None = None
        try:
            from sqlalchemy import select
            from sqlalchemy.exc import SQLAlchemyError
            from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

            from app.models.enquiry import Enquiry

            bind = getattr(db, "bind", None)
            if bind is not None:
                session_factory = async_sessionmaker(
                    bind=bind,
                    class_=AsyncSession,
                    expire_on_commit=False,
                )
                async with session_factory() as check_session:
                    stmt = select(Enquiry.id).where(Enquiry.reference_number == ref)
                    res = await check_session.execute(stmt)
                    row_exists = res.scalar_one_or_none() is not None
            else:
                stmt = select(Enquiry.id).where(Enquiry.reference_number == ref)
                res = await db.execute(stmt)
                row_exists = res.scalar_one_or_none() is not None
        except (SQLAlchemyError, OSError, ConnectionError, TimeoutError, RuntimeError):
            row_exists = None

        async with self._lock:
            current_record = self._reservation_records.get(token)
            if current_record is None:
                return ReservationStatus.RELEASED
            if current_record.status != ReservationStatus.PENDING:
                # Terminal immutability: already COMMITTED or RELEASED
                return current_record.status

            if row_exists is True:
                # Positive observation: row exists in PostgreSQL. Commit authoritatively.
                self._reservations[ip] = [
                    r for r in self._reservations[ip] if r.token != token
                ]
                now = time.time()
                self._reservation_records[token] = current_record._replace(
                    status=ReservationStatus.COMMITTED,
                    resolved_at=now,
                )
                self._pending_tokens_by_ip[ip].discard(token)
                self._submissions[ip].append(now)
                return ReservationStatus.COMMITTED

            elif row_exists is False and confirmed_terminated:
                # Negative observation: check generation protection.
                # Stale results must NEVER override a newer reconciliation outcome!
                if current_record.reconciliation_generation != my_generation:
                    # Superseded by newer reconciliation session: do NOT release
                    return current_record.status

                self._reservations[ip] = [
                    r for r in self._reservations[ip] if r.token != token
                ]
                now = time.time()
                self._reservation_records[token] = current_record._replace(
                    status=ReservationStatus.RELEASED,
                    resolved_at=now,
                )
                self._pending_tokens_by_ip[ip].discard(token)
                return ReservationStatus.RELEASED

            else:
                # Retain in PENDING: row absent without confirmed termination, or DB unreachable
                return ReservationStatus.PENDING

    async def reconcile_pending_for_ip(self, ip: str, db: Any) -> int:
        """Opportunistically reconciles all pending reservations for `ip` using live `db` session.

        Triggered on incoming RFQ requests to recover ambiguous reservations before admission.
        Returns the number of reservations that transitioned to a terminal state.
        """
        async with self._lock:
            tokens = [
                token
                for token in list(self._pending_tokens_by_ip[ip])
                if (rec := self._reservation_records.get(token))
                and rec.status == ReservationStatus.PENDING
                and rec.reference_number is not None
            ]

        resolved = 0
        for token in tokens:
            st = await self.reconcile_pending_reservation(token, db)
            if st != ReservationStatus.PENDING:
                resolved += 1
        return resolved

    async def reconcile_all_pending(self, db: Any) -> dict[str, ReservationStatus]:
        """Reconciles all outstanding ambiguous reservations across all IPs using live `db` session."""
        async with self._lock:
            tokens = [
                token
                for token, rec in list(self._reservation_records.items())
                if rec.status == ReservationStatus.PENDING
                and rec.reference_number is not None
            ]

        results: dict[str, ReservationStatus] = {}
        for token in tokens:
            results[token] = await self.reconcile_pending_reservation(token, db)
        return results

    async def check_submission_rate_limit(self, ip: str) -> None:
        """Legacy check for submission rate limit."""
        now = time.time()
        async with self._lock:
            self._maybe_prune(now)
            window_10m = now - 600.0
            recent_submissions = [t for t in self._submissions[ip] if t > window_10m]
            pending_operations = sum(
                1
                for token in self._pending_tokens_by_ip[ip]
                if (rec := self._reservation_records.get(token))
                and rec.status == ReservationStatus.PENDING
            )
            if (
                len(recent_submissions) + pending_operations
                >= settings.PUBLIC_SUBMISSION_LIMIT_10MIN
            ):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Submission limit reached for this IP. Please wait before submitting additional enquiries.",
                )

    async def record_submission(self, ip: str) -> None:
        """Records a completed enquiry submission timestamp for the client IP."""
        now = time.time()
        async with self._lock:
            self._submissions[ip].append(now)

    async def record_successful_submission(self, ip: str) -> None:
        """Alias for record_submission."""
        await self.record_submission(ip)

    async def reset(self) -> None:
        """Clears all tracking state (used primarily in automated tests)."""
        async with self._lock:
            self._requests.clear()
            self._submissions.clear()
            self._reservations.clear()
            self._reservation_records.clear()
            self._pending_tokens_by_ip.clear()

    def _maybe_prune(self, now: float) -> None:
        """Periodically removes stale tracking entries to prevent memory growth.

        Safe cleanup rules:
        - NEVER prune unresolved PENDING records solely because of age.
        - Prune COMMITTED and RELEASED records once their resolution age
          exceeds the 10-minute sliding window (window_10m).
        """
        if now - self._last_prune < self._prune_interval_seconds:
            return

        window_10m = now - 600.0
        for ip in list(self._requests.keys()):
            self._requests[ip] = [t for t in self._requests[ip] if t > now - 60.0]
            if not self._requests[ip]:
                del self._requests[ip]

        for ip in list(self._submissions.keys()):
            self._submissions[ip] = [t for t in self._submissions[ip] if t > window_10m]
            if not self._submissions[ip]:
                del self._submissions[ip]

        for ip in list(self._reservations.keys()):
            self._reservations[ip] = [
                r for r in self._reservations[ip] if r.expires_at > now
            ]
            if not self._reservations[ip]:
                del self._reservations[ip]

        # Cleanup resolved reservation lifecycle records
        for token, record in list(self._reservation_records.items()):
            if record.status == ReservationStatus.PENDING:
                # Invariant: Never prune unresolved pending operations regardless of age
                continue
            resolution_time = (
                record.resolved_at
                if record.resolved_at is not None
                else record.created_at
            )
            if resolution_time <= window_10m:
                del self._reservation_records[token]

        for ip in list(self._pending_tokens_by_ip.keys()):
            # Synchronize pending tokens with active records
            self._pending_tokens_by_ip[ip] = {
                t
                for t in self._pending_tokens_by_ip[ip]
                if (rec := self._reservation_records.get(t))
                and rec.status == ReservationStatus.PENDING
            }
            if not self._pending_tokens_by_ip[ip]:
                del self._pending_tokens_by_ip[ip]

        self._last_prune = now


# Global rate limiter instance
public_rate_limiter = SlidingWindowRateLimiter()
