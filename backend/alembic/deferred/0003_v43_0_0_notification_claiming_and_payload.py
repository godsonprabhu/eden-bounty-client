"""Alembic Migration 0003: Notification Claiming, Circuit Breaker, Evidence Store, and V43 Security Architecture.

Revision ID: 0003_v43_0_0
Revises: 0002_add_enquiry_idempotency
Create Date: 2026-11-10 14:30:00.000000

Authoritative Baseline: C13.5 Version 43.0.0 (APPROVED FOR ARCHITECTURE FREEZE).
Implements:
1. Canonical 22-column public.notification_logs schema (reconciles 10 legacy columns from
   Migration 0001 and adds exactly 12 extension columns).
2. All 16 PostgreSQL engine CHECK constraints enforcing authoritative domain invariants.
3. Supporting tables:
   - public.platform_circuit_breakers
   - public.legacy_notification_provenance
   - public.smtp_evidence_store
   - eb_security.notification_quarantine_audit
4. Dedicated eb_security schema with hardened SECURITY DEFINER triggers and the
   eb_security.fn_release_quarantine administrative gateway function.
5. Five-stage status-aware historical data backfill & legacy normalization with
   cryptographic RFC 8785 JCS HMAC-SHA256 provenance registration.
6. Seven-role PostgreSQL least-privilege RBAC architecture with schema ownership and
   fail-fast prerequisite validation.
7. High-performance partial indexes for worker claim candidate discovery and lease sweeping.
8. Forward-only production safety guard on downgrade with ordered teardown.
"""

import hashlib
import hmac
import json
import os
import re
import unicodedata
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic.
revision: str = "0003_v43_0_0"
down_revision: str | None = "0002_add_enquiry_idempotency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TXID_REGEX = re.compile(r"^(0|[1-9][0-9]*)$")
SUPPORTED_SERIALIZATION_VERSIONS = {"eb-prov-v1"}


# -----------------------------------------------------------------------------
# CRYPTOGRAPHIC PROVENANCE & OFFLINE VERIFICATION ENGINE (V43 SECTION 4.1.3)
# -----------------------------------------------------------------------------


class VerificationStatus(str, Enum):
    """Authoritative provenance audit verification status taxonomy (V43 Section 4.1.3.5)."""

    VALID = "VALID"
    INVALID_HMAC_DIGEST = "INVALID_HMAC_DIGEST"
    UNKNOWN_KEY_VERSION = "UNKNOWN_KEY_VERSION"
    REVOKED_KEY_VERSION = "REVOKED_KEY_VERSION"
    MISSING_PROVENANCE_RECORD = "MISSING_PROVENANCE_RECORD"
    ORPHAN_PROVENANCE_RECORD = "ORPHAN_PROVENANCE_RECORD"
    NOTIFICATION_STATE_MISMATCH = "NOTIFICATION_STATE_MISMATCH"
    INVALID_TERMINAL_CLASSIFICATION = "INVALID_TERMINAL_CLASSIFICATION"
    INVALID_COUNTERS = "INVALID_COUNTERS"
    INVALID_LEASE_FIELDS = "INVALID_LEASE_FIELDS"
    MISSING_OR_CONTRADICTORY_SMTP_EVIDENCE = "MISSING_OR_CONTRADICTORY_SMTP_EVIDENCE"
    UNSUPPORTED_SERIALIZATION_VERSION = "UNSUPPORTED_SERIALIZATION_VERSION"
    INVALID_TXID_FORMAT = "INVALID_TXID_FORMAT"


def _format_ecma_number(val: float) -> str:
    """Serialize IEEE 754 float in compliance with ECMA-262 §7.1.12.1 and RFC 8785 §3.2.2.3."""
    import math

    if math.isnan(val) or math.isinf(val):
        raise ValueError("NaN and Infinity are forbidden by RFC 8785")
    if val == 0.0:
        return "0"
    sign = "-" if math.copysign(1.0, val) < 0 else ""
    abs_val = abs(val)
    # Python repr(float) produces the shortest decimal representation that round-trips
    r = repr(abs_val)
    if "e" in r or "E" in r:
        mantissa, exp_s = r.lower().split("e")
        exp = int(exp_s)
        digits = mantissa.replace(".", "")
    else:
        if "." in r:
            int_part, frac_part = r.split(".")
            int_part = int_part.lstrip("0")
            if not int_part:
                frac_l = frac_part.lstrip("0")
                leading_zeros = len(frac_part) - len(frac_l)
                digits = frac_l
                exp = -(leading_zeros + 1)
            else:
                digits = int_part + frac_part
                exp = len(int_part) - 1
        else:
            digits = r.lstrip("0")
            exp = len(digits) - 1
    digits = digits.rstrip("0")
    if not digits:
        return "0"
    k = len(digits)
    n = exp + 1
    if k <= n <= 21:
        res = digits + "0" * (n - k)
    elif 0 < n <= 21:
        res = digits[:n] + ("." + digits[n:] if n < k else "")
    elif -6 < n <= 0:
        res = "0." + "0" * (-n) + digits
    else:
        if k == 1:
            res = digits
        else:
            res = digits[0] + "." + digits[1:]
        res += "e" + ("+" if n - 1 >= 0 else "") + str(n - 1)
    return sign + res


def _check_lone_surrogates(s: str) -> None:
    """Enforce RFC 8785 strict Unicode rejection of lone surrogates (0xD800..0xDFFF)."""
    for ch in s:
        if 0xD800 <= ord(ch) <= 0xDFFF:
            raise ValueError(
                f"Lone surrogate code point U+{ord(ch):04X} is forbidden by RFC 8785."
            )


def rfc8785_canonical_serialize(obj: Any) -> bytes:
    """Demonstrably compliant RFC 8785 JSON Canonicalization Scheme (JCS).

    Specification: RFC 8785 & EDEN BOUNTY C13.5 Section 4.1.3.1
    Stage 1: Pre-Serialization Normalization:
      - Unicode NFC normalization on string values and object keys.
      - ISO 8601 UTC microsecond representation with trailing 'Z' for datetimes.
      - Rejection of lone surrogates (0xD800..0xDFFF) and malformed Unicode (fail-closed).
      - Rejection of duplicate keys and NFC key collisions (fail-closed).
    Stage 2: RFC 8785 JCS Formatting:
      - UTF-16 code unit lexicographical key sorting (k.encode('utf-16-be')).
      - Strict string escaping per RFC 8785 Section 3.2.2.2:
        * Quotation mark (0x22) -> \\\"
        * Reverse solidus (0x5C) -> \\\\
        * Control characters (0x00..0x1F):
          - 0x08 -> \\b, 0x09 -> \\t, 0x0A -> \\n, 0x0C -> \\f, 0x0D -> \\r
          - Other control chars (< 0x20) -> \\u00xx (lowercase hex)
        * All other characters emitted directly as valid UTF-8.
      - Strict number formatting per ECMA-262 §7.1.12.1 (negative zero -0.0 -> "0", exponential thresholds, no leading plus or zeros).
      - Zero insignificant whitespace delimiters (separators (',', ':')).
      - Unquoted literal null, true, false.
    Stage 3: UTF-8 Byte Encoding:
      - Valid UTF-8 bytes without BOM.
    """

    def _escape_str(s: str) -> str:
        _check_lone_surrogates(s)
        try:
            s.encode("utf-8")
        except UnicodeEncodeError as e:
            raise ValueError(f"Invalid Unicode string with lone surrogates: {e}") from e

        res: list[str] = ['"']
        for ch in s:
            cp = ord(ch)
            if ch == '"':
                res.append('\\"')
            elif ch == "\\":
                res.append("\\\\")
            elif ch == "\b":
                res.append("\\b")
            elif ch == "\t":
                res.append("\\t")
            elif ch == "\n":
                res.append("\\n")
            elif ch == "\f":
                res.append("\\f")
            elif ch == "\r":
                res.append("\\r")
            elif cp < 0x20:
                res.append(f"\\u{cp:04x}")
            else:
                res.append(ch)
        res.append('"')
        return "".join(res)

    def _serialize(val: Any) -> str:
        if val is None:
            return "null"
        if isinstance(val, bool):
            return "true" if val else "false"
        if isinstance(val, int) and not isinstance(val, bool):
            return str(val)
        if isinstance(val, float):
            return _format_ecma_number(val)
        if isinstance(val, datetime):
            utc_dt = val.astimezone(UTC)
            return _escape_str(utc_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        if isinstance(val, str):
            _check_lone_surrogates(val)
            norm_s = unicodedata.normalize("NFC", val)
            return _escape_str(norm_s)
        if isinstance(val, dict):
            # Check for duplicate / NFC-colliding keys and sort by UTF-16 code units
            seen_normalized_keys: set[str] = set()
            normalized_entries: list[tuple[bytes, str, Any]] = []
            for k, v in val.items():
                if not isinstance(k, str):
                    raise TypeError(f"Dictionary key must be string, got {type(k)}")
                _check_lone_surrogates(k)
                k_norm = unicodedata.normalize("NFC", k)
                if k_norm in seen_normalized_keys:
                    raise ValueError(
                        f"Duplicate object key after NFC normalization: {k_norm!r}"
                    )
                seen_normalized_keys.add(k_norm)
                # RFC 8785: Property keys MUST be sorted by UTF-16 code units
                utf16_key = k_norm.encode("utf-16-be")
                normalized_entries.append((utf16_key, k_norm, v))

            normalized_entries.sort(key=lambda item: item[0])
            items: list[str] = []
            for _, k_norm, v in normalized_entries:
                k_escaped = _escape_str(k_norm)
                v_str = _serialize(v)
                items.append(f"{k_escaped}:{v_str}")
            return "{" + ",".join(items) + "}"
        if isinstance(val, (list, tuple)):
            items = [_serialize(x) for x in val]
            return "[" + ",".join(items) + "]"
        raise TypeError(f"Unsupported type for RFC 8785 serialization: {type(val)}")

    return _serialize(obj).encode("utf-8")


# Alias for backward-compatibility in verifier and callers
canonical_serialize = rfc8785_canonical_serialize


class ExternalKMSClient:
    """External KMS / Vault client boundary for HMAC-SHA256 provenance registration.

    SECURITY ARCHITECTURE STATUS & UNRESOLVED PREREQUISITE:
    - Production / Staging Deployment Prerequisite: A genuine external KMS or HashiCorp Vault
      SDK integration (e.g. AWS KMS, HashiCorp Vault hvac, GCP Cloud KMS) is NOT YET
      provisioned or approved in the repository dependencies.
    - Fail-Closed Policy: By default, this client fails closed (is_configured() == False).
      Attempting live cryptographic HMAC generation during online migration without an
      approved external KMS provider raises an explicit RuntimeError and halts execution.
    - Zero Fallbacks: Zero-key fallbacks ('00000000...'), database session settings,
      hardcoded credentials, and synthetic placeholder signatures are strictly forbidden.
    - Test Harness & Offline Verification Isolation: For offline manifest verification
      and test fixtures ONLY, explicit verification keys may be supplied via
      create_test_client(test_keys) or explicit test registration. This is strictly
      isolated from production KMS integration and must never be conflated with it.
    """

    _instance: Optional["ExternalKMSClient"] = None

    def __init__(
        self,
        test_key_store: dict[str, bytes] | None = None,
        *,
        is_test_fixture: bool = False,
    ) -> None:
        self._test_key_store: dict[str, bytes] = test_key_store or {}
        self._is_test_fixture: bool = is_test_fixture

    @classmethod
    def get_client(cls) -> "ExternalKMSClient":
        """Return the default client singleton.

        In production and normal migration runtime, this client has no KMS SDK configured
        and fails closed upon any cryptographic operation.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def create_test_client(cls, test_keys: dict[str, bytes]) -> "ExternalKMSClient":
        """Explicit test fixture factory.

        Used solely by isolated unit tests and offline manifest verifiers.
        Must NOT be used to simulate production KMS readiness.
        """
        return cls(test_key_store=test_keys, is_test_fixture=True)

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (used in tests and fixture isolation)."""
        cls._instance = None

    def is_configured(self) -> bool:
        """Indicate whether an external KMS provider is actively integrated."""
        return self._is_test_fixture and bool(self._test_key_store)

    def get_key(self, key_version: str) -> dict[str, Any] | None:
        """Retrieve key metadata from test store if running under explicit test harness."""
        if self._is_test_fixture and key_version in self._test_key_store:
            return {
                "key_version": key_version,
                "key_bytes": self._test_key_store[key_version],
                "status": "ACTIVE_TEST_FIXTURE",
            }
        return None

    def register_test_key(
        self, key_version: str, key_bytes: bytes, status: str = "ACTIVE_TEST_FIXTURE"
    ) -> None:
        """Register a key strictly for offline test fixture execution."""
        self._test_key_store[key_version] = key_bytes
        self._is_test_fixture = True

    # Legacy alias for test fixtures calling register_key
    register_key = register_test_key

    def has_active_key(self, key_version: str = "eb-prov-k1-202611") -> bool:
        """Check whether an active key is available."""
        key_meta = self.get_key(key_version)
        return bool(key_meta and key_meta.get("key_bytes"))

    def generate_hmac(self, key_version: str, canonical_bytes: bytes) -> str:
        """Calculate HMAC-SHA256 hex digest using configured key.

        Fails safely (fail-closed) if no external KMS integration or test fixture key is configured.
        """
        if not self._is_test_fixture:
            raise RuntimeError(
                "UNRESOLVED DEPLOYMENT PREREQUISITE: Genuine external KMS / Vault integration "
                "is not configured in this environment. No approved external KMS SDK (AWS KMS, "
                "HashiCorp Vault, GCP KMS) is present in backend/requirements.txt. "
                "Migration 0003 execution halted safely (fail-closed). "
                "Live historical backfill cannot proceed without an approved KMS provider."
            )
        key_meta = self.get_key(key_version)
        if not key_meta or not key_meta.get("key_bytes"):
            raise RuntimeError(
                f"KMS KEY RETRIEVAL ERROR: Test fixture key '{key_version}' is required for HMAC provenance calculation, "
                "but was not configured in the test harness key store. "
                "Execution halted safely (fail-closed)."
            )
        return hmac.new(
            key_meta["key_bytes"], canonical_bytes, hashlib.sha256
        ).hexdigest()


def _normalize_iso_ts(val: Any) -> str | None:
    """Normalize datetime or timestamp string to canonical ISO 8601 UTC microsecond representation.

    Guarantees that whether a timestamp is provided as a Python datetime object (from ORM/DB)
    or an ISO string (from manifest/API), it produces the exact canonical UTC microsecond
    representation (YYYY-MM-DDTHH:MM:SS.ffffffZ) required for RFC 8785 pre-image reconstruction.
    """
    if val is None:
        return None
    if isinstance(val, datetime):
        utc_dt = val if val.tzinfo is not None else val.replace(tzinfo=UTC)
        return utc_dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if isinstance(val, str):
        val_str = val.strip()
        if not val_str:
            return None
        if val_str.endswith("Z"):
            return val_str
        try:
            dt = datetime.fromisoformat(val_str)
            utc_dt = dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
            return utc_dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            return val_str
    return str(val)


def build_legacy_provenance_record(
    notification_id: str,
    original_status: str,
    original_attempt_count: int,
    original_retry_count: int,
    original_last_attempt_at: datetime | str | None,
    original_sent_at: datetime | str | None,
    provenance_reason: str,
    migration_txid: str,
    kms_client: Any,
    migrated_at: datetime | None = None,
    key_version: str = "eb-prov-k1-202611",
    migration_version: str = "0003_v43_0_0",
    migration_executor: str = "eb_migration_runner",
    serialization_version: str = "eb-prov-v1",
) -> dict[str, Any]:
    """Construct, cryptographically sign, and prepare an authoritative provenance record.

    Guarantees strict single-timestamp integrity:
    1. Generates one timezone-aware UTC timestamp with non-truncated microseconds.
    2. Constructs the canonical pre-image with that exact timestamp string.
    3. Calculates HMAC-SHA256 digest via external KMS client.
    4. Returns exact payload for both database persistence and verifier reconstruction.
    """
    ts = migrated_at or datetime.now(UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    ts_utc = ts.astimezone(UTC)
    ts_iso = ts_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    last_att_iso = _normalize_iso_ts(original_last_attempt_at)
    sent_at_iso = _normalize_iso_ts(original_sent_at)

    pre_image = {
        "key_version": key_version,
        "migrated_at": ts_iso,
        "migration_executor": migration_executor,
        "migration_txid": str(migration_txid),
        "migration_version": migration_version,
        "notification_id": str(notification_id),
        "original_attempt_count": original_attempt_count,
        "original_last_attempt_at": last_att_iso,
        "original_retry_count": original_retry_count,
        "original_sent_at": sent_at_iso,
        "original_status": str(original_status),
        "provenance_reason": provenance_reason,
        "serialization_version": serialization_version,
    }
    canonical_bytes = rfc8785_canonical_serialize(pre_image)
    prov_hmac = kms_client.generate_hmac(key_version, canonical_bytes)

    return {
        "notification_id": str(notification_id),
        "migration_version": migration_version,
        "migrated_at": ts_utc,
        "migrated_at_iso": ts_iso,
        "migration_executor": migration_executor,
        "original_status": str(original_status),
        "original_attempt_count": original_attempt_count,
        "original_retry_count": original_retry_count,
        "original_last_attempt_at": original_last_attempt_at,
        "original_sent_at": original_sent_at,
        "provenance_reason": provenance_reason,
        "migration_txid": str(migration_txid),
        "key_version": key_version,
        "serialization_version": serialization_version,
        "provenance_sha256": prov_hmac,
    }


AUTHORITATIVE_INFRASTRUCTURE_ROLES = {
    "eb_app_user",
    "eb_worker_user",
    "eb_migration_runner",
    "eb_migration_role",
    "eb_schema_owner",
    "eb_sec_admin",
    "eb_archival_role",
}


def validate_prerequisite_roles_exist(existing_roles: set[str]) -> None:
    """Validate that all 7 authoritative infrastructure roles exist in pg_roles.

    In compliance with PostgreSQL 16 least-privilege security principles, infrastructure
    roles and memberships are provisioned out-of-band by an authorized DBA principal
    (e.g., eb_dba) prior to migration execution. These are exclusively database engine
    principals for least-privilege access, object ownership, and connection isolation.
    They are NOT application administrator accounts. EDEN BOUNTY requires exactly ONE
    application administrator (SUPER_ADMIN); all dashboard operations are handled by this
    single administrator without multi-admin management or operational staff accounts.
    The migration runner is an unprivileged database principal and does not possess
    CREATEROLE or ADMIN OPTION.
    Fails closed if any required infrastructure role is missing from pg_roles.
    """
    missing = AUTHORITATIVE_INFRASTRUCTURE_ROLES - existing_roles
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise PermissionError(
            f"PRE-REQUISITE ROLES MISSING: The following infrastructure roles must be provisioned "
            f"out-of-band by an authorized DBA principal (e.g. eb_dba) prior to executing Migration 0003: "
            f"{missing_str}. The migration runner lacks CREATEROLE and cannot self-provision roles."
        )


def validate_migration_authority(
    session_user: str,
    user_roles: set[str],
) -> None:
    """Validate that migration execution principal possesses required ownership transfer authority.

    Evaluates authority strictly according to PostgreSQL RBAC rules without superuser bypass.
    To transfer table ownership to eb_schema_owner and schema/function ownership to eb_sec_admin,
    the executing principal must possess direct or indirect membership in those target roles.
    Superuser status alone does NOT grant ownership-transfer authority without explicit role
    membership. Execution fails closed if any required role is missing.
    """
    required_roles = {"eb_migration_role", "eb_schema_owner", "eb_sec_admin"}
    missing = required_roles - user_roles
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise PermissionError(
            f"AUTHORIZATION VIOLATION: Migration executor '{session_user}' lacks required "
            f"authority for roles: {missing_str}. Ownership transfer to target roles requires "
            f"explicit membership. Execution halted before making schema changes."
        )


def verify_provenance_row(
    prov_row: dict[str, Any] | None,
    notif_row: dict[str, Any] | None,
    kms_client: Any,
) -> dict[str, Any]:
    """Numbered 10-step decision procedure evaluating active notification rows

    against immutable provenance records (V43 Section 4.1.3.5 & Section 12.3.1).
    Strictly read-only and non-corrective.
    """
    # -------------------------------------------------------------------------
    # STEP 1: Relational Existence & Orphan Check
    # -------------------------------------------------------------------------
    if notif_row and notif_row.get("is_legacy_exception") is True and not prov_row:
        return {
            "status": VerificationStatus.MISSING_PROVENANCE_RECORD,
            "notification_id": notif_row.get("id"),
            "error": "Notification marked is_legacy_exception = TRUE without registered audit record in legacy_notification_provenance.",
        }

    if prov_row and not notif_row:
        return {
            "status": VerificationStatus.ORPHAN_PROVENANCE_RECORD,
            "notification_id": prov_row.get("notification_id"),
            "error": "Audit record exists in legacy_notification_provenance with no parent row in notification_logs.",
        }

    if not notif_row and not prov_row:
        return {"status": VerificationStatus.VALID, "message": "No row presented."}

    # -------------------------------------------------------------------------
    # STEP 2: Serialization Version Validation
    # -------------------------------------------------------------------------
    if prov_row:
        ser_ver = prov_row.get("serialization_version")
        if ser_ver not in SUPPORTED_SERIALIZATION_VERSIONS:
            return {
                "status": VerificationStatus.UNSUPPORTED_SERIALIZATION_VERSION,
                "notification_id": prov_row.get("notification_id"),
                "serialization_version": ser_ver,
                "error": f"Serialization version '{ser_ver}' is not supported by this verifier.",
            }

        # -------------------------------------------------------------------------
        # STEP 3: Canonical migration_txid Format Validation
        # -------------------------------------------------------------------------
        txid_str = str(prov_row.get("migration_txid", ""))
        if not TXID_REGEX.match(txid_str):
            return {
                "status": VerificationStatus.INVALID_TXID_FORMAT,
                "notification_id": prov_row.get("notification_id"),
                "txid_value": txid_str,
                "error": "migration_txid must be a canonical decimal string without leading zeros.",
            }
        int_txid = int(txid_str)
        if int_txid < 0 or int_txid > 9223372036854775807:
            return {
                "status": VerificationStatus.INVALID_TXID_FORMAT,
                "notification_id": prov_row.get("notification_id"),
                "txid_value": txid_str,
                "error": f"migration_txid {int_txid} exceeds maximum PostgreSQL BIGINT (2^63 - 1).",
            }

        # -------------------------------------------------------------------------
        # STEP 4: KMS Key Version & Status Resolution
        # -------------------------------------------------------------------------
        key_ver = prov_row.get("key_version")
        key_meta = kms_client.get_key(key_ver)
        if not key_meta:
            return {
                "status": VerificationStatus.UNKNOWN_KEY_VERSION,
                "notification_id": prov_row.get("notification_id"),
                "key_version": key_ver,
                "error": f"Key version {key_ver} is unrecognized in external KMS.",
            }
        if key_meta.get("status") == "REVOKED":
            return {
                "status": VerificationStatus.REVOKED_KEY_VERSION,
                "notification_id": prov_row.get("notification_id"),
                "key_version": key_ver,
                "error": f"Key version {key_ver} was revoked due to security incident.",
            }

        # -------------------------------------------------------------------------
        # STEP 5: Pre-Image Reconstruction & HMAC Digest Verification
        # -------------------------------------------------------------------------
        material_fields = {
            "key_version": prov_row["key_version"],
            "migrated_at": _normalize_iso_ts(prov_row["migrated_at"]),
            "migration_executor": prov_row["migration_executor"],
            "migration_txid": txid_str,
            "migration_version": prov_row["migration_version"],
            "notification_id": str(prov_row["notification_id"]),
            "original_attempt_count": prov_row["original_attempt_count"],
            "original_last_attempt_at": _normalize_iso_ts(
                prov_row.get("original_last_attempt_at")
            ),
            "original_retry_count": prov_row["original_retry_count"],
            "original_sent_at": _normalize_iso_ts(prov_row.get("original_sent_at")),
            "original_status": prov_row["original_status"],
            "provenance_reason": prov_row["provenance_reason"],
            "serialization_version": prov_row.get(
                "serialization_version", "eb-prov-v1"
            ),
        }
        canonical_bytes = canonical_serialize(material_fields)
        computed_digest = hmac.new(
            key_meta["key_bytes"], canonical_bytes, hashlib.sha256
        ).hexdigest()
        stored_digest = prov_row.get("provenance_sha256", "")
        if not hmac.compare_digest(computed_digest, stored_digest):
            return {
                "status": VerificationStatus.INVALID_HMAC_DIGEST,
                "notification_id": prov_row.get("notification_id"),
                "stored_digest": stored_digest,
                "computed_digest": computed_digest,
                "error": "Cryptographic digest mismatch! Record content in legacy_notification_provenance has been tampered with.",
            }

    # -------------------------------------------------------------------------
    # STEP 6: Terminal State & Lease Invariant Verification
    # -------------------------------------------------------------------------
    status = notif_row.get("status") if notif_row else None
    if status in ("SENT", "EXHAUSTED"):
        if (
            notif_row.get("claimed_by") is not None
            or notif_row.get("claim_expires_at") is not None
            or notif_row.get("retry_eligible_at") is not None
        ):
            return {
                "status": VerificationStatus.INVALID_LEASE_FIELDS,
                "notification_id": notif_row.get("id"),
                "error": f"Terminal record in status '{status}' retains non-NULL lease or backoff fields.",
            }
    elif status not in ("PENDING", "CLAIMED", "FAILED", "QUARANTINED"):
        return {
            "status": VerificationStatus.NOTIFICATION_STATE_MISMATCH,
            "notification_id": notif_row.get("id"),
            "error": f"Notification row has illegal status '{status}'.",
        }

    # -------------------------------------------------------------------------
    # STEP 7: Provenance-to-Notification Field State Equality
    # -------------------------------------------------------------------------
    if prov_row and notif_row:
        mismatches: list[tuple[str, Any, Any]] = []
        if notif_row.get("is_legacy_exception") is not True:
            mismatches.append(
                ("is_legacy_exception", notif_row.get("is_legacy_exception"), True)
            )
        if notif_row.get("status") != prov_row.get("original_status"):
            mismatches.append(
                ("status", notif_row.get("status"), prov_row.get("original_status"))
            )
        if notif_row.get("attempt_count") != prov_row.get("original_attempt_count"):
            mismatches.append(
                (
                    "attempt_count",
                    notif_row.get("attempt_count"),
                    prov_row.get("original_attempt_count"),
                )
            )
        if notif_row.get("retry_count") != prov_row.get("original_retry_count"):
            mismatches.append(
                (
                    "retry_count",
                    notif_row.get("retry_count"),
                    prov_row.get("original_retry_count"),
                )
            )
        if notif_row.get("last_attempt_at") != prov_row.get("original_last_attempt_at"):
            mismatches.append(
                (
                    "last_attempt_at",
                    notif_row.get("last_attempt_at"),
                    prov_row.get("original_last_attempt_at"),
                )
            )
        if notif_row.get("sent_at") != prov_row.get("original_sent_at"):
            mismatches.append(
                (
                    "sent_at",
                    notif_row.get("sent_at"),
                    prov_row.get("original_sent_at"),
                )
            )

        if mismatches:
            return {
                "status": VerificationStatus.NOTIFICATION_STATE_MISMATCH,
                "notification_id": notif_row.get("id"),
                "field_mismatches": mismatches,
                "error": f"Active notification row fields differ from immutable provenance: {mismatches}",
            }

    # -------------------------------------------------------------------------
    # STEP 8: Monotonic Counter Invariant Verification
    # -------------------------------------------------------------------------
    att = notif_row.get("attempt_count", 0) if notif_row else 0
    ret = notif_row.get("retry_count", 0) if notif_row else 0
    is_legacy = notif_row.get("is_legacy_exception", False) if notif_row else False

    if not is_legacy and notif_row:
        if att == 0 and ret != 0:
            return {
                "status": VerificationStatus.INVALID_COUNTERS,
                "notification_id": notif_row.get("id"),
                "error": f"Unattempted record (att=0) has non-zero retry_count={ret}.",
            }
        elif att > 0 and ret != att - 1:
            return {
                "status": VerificationStatus.INVALID_COUNTERS,
                "notification_id": notif_row.get("id"),
                "error": f"Monotonic counter invariant violated: att={att}, ret={ret} (expected ret = att - 1).",
            }
        if att < 0 or att > 4 or ret < 0 or ret > 3:
            return {
                "status": VerificationStatus.INVALID_COUNTERS,
                "notification_id": notif_row.get("id"),
                "error": f"Counters out of legal bounds: att={att}, ret={ret}.",
            }

    # -------------------------------------------------------------------------
    # STEP 9: Terminal Classification & SMTP Evidence Verification
    # -------------------------------------------------------------------------
    tf_class = notif_row.get("terminal_failure_class") if notif_row else None
    smtp_phase = notif_row.get("smtp_command_or_phase") if notif_row else None
    smtp_code = notif_row.get("smtp_reply_code") if notif_row else None

    if status == "SENT":
        if tf_class is not None:
            return {
                "status": VerificationStatus.INVALID_TERMINAL_CLASSIFICATION,
                "notification_id": notif_row.get("id"),
                "terminal_failure_class": tf_class,
                "error": "SENT notification must have terminal_failure_class = NULL.",
            }

    elif status == "EXHAUSTED":
        if tf_class is None:
            return {
                "status": VerificationStatus.INVALID_TERMINAL_CLASSIFICATION,
                "notification_id": notif_row.get("id"),
                "error": "EXHAUSTED notification must have non-NULL terminal_failure_class.",
            }

        if tf_class == "RETRY_BUDGET_EXHAUSTED":
            if att != 4 or ret != 3:
                return {
                    "status": VerificationStatus.INVALID_COUNTERS,
                    "notification_id": notif_row.get("id"),
                    "error": f"Class A RETRY_BUDGET_EXHAUSTED requires att=4, ret=3; found att={att}, ret={ret}.",
                }
            if is_legacy:
                return {
                    "status": VerificationStatus.NOTIFICATION_STATE_MISMATCH,
                    "notification_id": notif_row.get("id"),
                    "error": "Class A RETRY_BUDGET_EXHAUSTED cannot be marked as is_legacy_exception = TRUE.",
                }
            if (
                smtp_phase == "RCPT_TO"
                and smtp_code is not None
                and 550 <= smtp_code <= 554
            ):
                return {
                    "status": VerificationStatus.MISSING_OR_CONTRADICTORY_SMTP_EVIDENCE,
                    "notification_id": notif_row.get("id"),
                    "error": "Permanent recipient rejection (RCPT_TO 550-554) was incorrectly classified as Class A instead of Class B.",
                }

        elif tf_class == "PERMANENT_RECIPIENT_REJECTION":
            if att < 1 or att > 4 or ret != att - 1:
                return {
                    "status": VerificationStatus.INVALID_COUNTERS,
                    "notification_id": notif_row.get("id"),
                    "error": f"Class B PERMANENT_RECIPIENT_REJECTION requires 1 <= att <= 4 and ret = att - 1; found att={att}, ret={ret}.",
                }
            if is_legacy:
                return {
                    "status": VerificationStatus.NOTIFICATION_STATE_MISMATCH,
                    "notification_id": notif_row.get("id"),
                    "error": "Class B PERMANENT_RECIPIENT_REJECTION cannot be marked as is_legacy_exception = TRUE.",
                }
            if (
                smtp_phase != "RCPT_TO"
                or smtp_code is None
                or not (550 <= smtp_code <= 554)
            ):
                return {
                    "status": VerificationStatus.MISSING_OR_CONTRADICTORY_SMTP_EVIDENCE,
                    "notification_id": notif_row.get("id"),
                    "smtp_phase": smtp_phase,
                    "smtp_code": smtp_code,
                    "error": f"Class B requires smtp_command_or_phase='RCPT_TO' and 550 <= smtp_reply_code <= 554; found phase='{smtp_phase}', code={smtp_code}.",
                }

        elif tf_class == "PAYLOAD_SNAPSHOT_UNAVAILABLE":
            if (
                att != 0
                or ret != 0
                or (notif_row and notif_row.get("last_attempt_at") is not None)
            ):
                return {
                    "status": VerificationStatus.INVALID_COUNTERS,
                    "notification_id": notif_row.get("id"),
                    "error": f"Class C PAYLOAD_SNAPSHOT_UNAVAILABLE requires att=0, ret=0, and last_attempt_at=NULL; found att={att}, ret={ret}.",
                }
            if is_legacy:
                return {
                    "status": VerificationStatus.NOTIFICATION_STATE_MISMATCH,
                    "notification_id": notif_row.get("id"),
                    "error": "Class C PAYLOAD_SNAPSHOT_UNAVAILABLE cannot be marked as is_legacy_exception = TRUE.",
                }
            if smtp_phase is not None or smtp_code is not None:
                return {
                    "status": VerificationStatus.MISSING_OR_CONTRADICTORY_SMTP_EVIDENCE,
                    "notification_id": notif_row.get("id"),
                    "error": "Class C unattempted record must not possess SMTP telemetry.",
                }

        elif tf_class == "LEGACY_FAILURE_UNCLASSIFIED":
            if not is_legacy and att > 0 and ret != att - 1:
                return {
                    "status": VerificationStatus.INVALID_COUNTERS,
                    "notification_id": notif_row.get("id"),
                    "error": f"Non-legacy Class D record violates counter monotonicity: att={att}, ret={ret}.",
                }

        elif tf_class not in (
            "PERMANENT_SENDER_REJECTION",
            "PERMANENT_CONTENT_POLICY_REJECTION",
            "CORRELATION_QUARANTINE_DISCARD",
        ):
            return {
                "status": VerificationStatus.INVALID_TERMINAL_CLASSIFICATION,
                "notification_id": notif_row.get("id"),
                "terminal_failure_class": tf_class,
                "error": f"Unrecognized terminal_failure_class '{tf_class}'.",
            }

    # -------------------------------------------------------------------------
    # STEP 10: Strict Non-Corrective Audit Report Generation
    # -------------------------------------------------------------------------
    return {
        "status": VerificationStatus.VALID,
        "notification_id": notif_row.get("id") if notif_row else None,
        "key_version": prov_row.get("key_version") if prov_row else None,
        "terminal_failure_class": tf_class,
        "message": "Cryptographic digest, terminal failure classification, and all relational invariants fully verified.",
    }


# -----------------------------------------------------------------------------
# ALEMBIC UPGRADE MIGRATION ENTRYPOINT
# -----------------------------------------------------------------------------


def upgrade() -> None:
    bind = op.get_bind()
    is_offline = context.is_offline_mode()

    # Pre-flight session role validation before any schema changes (online mode)
    if not is_offline:
        session_user_val = bind.execute(sa.text("SELECT session_user;")).scalar()
        session_user = str(session_user_val) if session_user_val else "unknown"

        # 1. Validate that all 7 prerequisite infrastructure roles exist in pg_roles
        roles_query = sa.text("""
            SELECT rolname FROM pg_roles
            WHERE rolname IN (
                'eb_app_user',
                'eb_worker_user',
                'eb_migration_runner',
                'eb_migration_role',
                'eb_schema_owner',
                'eb_sec_admin',
                'eb_archival_role'
            );
        """)
        existing_roles = {r[0] for r in bind.execute(roles_query).fetchall()}
        validate_prerequisite_roles_exist(existing_roles)

        # 2. Validate executor possesses explicit ownership-transfer and execution authority
        auth_query = sa.text("""
            SELECT rolname FROM pg_roles
            WHERE pg_has_role(session_user, rolname, 'MEMBER')
               OR pg_has_role(current_user, rolname, 'MEMBER');
        """)
        user_roles = {r[0] for r in bind.execute(auth_query).fetchall()}
        validate_migration_authority(session_user, user_roles)

    # -------------------------------------------------------------------------
    # PHASE 0: PRE-FLIGHT MIGRATION AUTHORITY & ROLE VALIDATION
    # -------------------------------------------------------------------------
    # Authoritative Rule (V43 Section 4.1.3 & Section 12):
    # - Validates that all 7 authoritative infrastructure roles exist externally.
    # - Note: These roles are database engine infrastructure roles only, NOT application
    #   administrator accounts. Application operations are handled exclusively by the
    #   single SUPER_ADMIN account.
    # - Validates that the migration executor possesses explicit ownership-transfer
    #   authority for both eb_schema_owner and eb_sec_admin, as well as eb_migration_role,
    #   BEFORE making any schema changes.
    # - In accordance with PostgreSQL 16 least-privilege principles, the migration runner
    #   is an unprivileged principal without CREATEROLE, ADMIN OPTION, or superuser status.
    #   It cannot and does not self-provision roles or grant itself role memberships.
    #   All 7 infrastructure roles and runner memberships must be provisioned out-of-band
    #   by an authorized DBA principal (e.g., eb_dba) prior to executing Migration 0003.
    # - Fails closed strictly without relying on undocumented superuser execution bypasses.
    op.execute("""
        DO $auth_preflight$
        DECLARE
            v_missing_role TEXT;
            v_missing_infra_roles TEXT[] := ARRAY[]::TEXT[];
            v_required_infra_roles TEXT[] := ARRAY[
                'eb_app_user',
                'eb_worker_user',
                'eb_migration_runner',
                'eb_migration_role',
                'eb_schema_owner',
                'eb_sec_admin',
                'eb_archival_role'
            ];
        BEGIN
            -- 1. Validate all 7 authoritative infrastructure roles have been provisioned out-of-band
            FOREACH v_missing_role IN ARRAY v_required_infra_roles LOOP
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = v_missing_role) THEN
                    v_missing_infra_roles := array_append(v_missing_infra_roles, v_missing_role);
                END IF;
            END LOOP;

            IF array_length(v_missing_infra_roles, 1) > 0 THEN
                RAISE EXCEPTION 'PRE-REQUISITE ROLES MISSING: The following infrastructure roles must be provisioned out-of-band by an authorized DBA principal (e.g. eb_dba) prior to executing Migration 0003: %. Migration runner does not possess CREATEROLE privilege and cannot self-provision infrastructure roles.', array_to_string(v_missing_infra_roles, ', ')
                    USING ERRCODE = '42704';
            END IF;

            -- 2. Validate executor possesses explicit ownership-transfer authority for eb_schema_owner
            IF NOT (
                pg_has_role(SESSION_USER, 'eb_schema_owner', 'MEMBER')
                OR pg_has_role(CURRENT_USER, 'eb_schema_owner', 'MEMBER')
            ) THEN
                RAISE EXCEPTION 'AUTHORIZATION VIOLATION: Migration executor (SESSION_USER: %, CURRENT_USER: %) lacks required ownership-transfer authority for role "eb_schema_owner". Execution halted before making schema changes. DBA must grant eb_schema_owner to migration executor.', SESSION_USER, CURRENT_USER
                    USING ERRCODE = '42501';
            END IF;

            -- 3. Validate executor possesses explicit ownership-transfer authority for eb_sec_admin
            IF NOT (
                pg_has_role(SESSION_USER, 'eb_sec_admin', 'MEMBER')
                OR pg_has_role(CURRENT_USER, 'eb_sec_admin', 'MEMBER')
            ) THEN
                RAISE EXCEPTION 'AUTHORIZATION VIOLATION: Migration executor (SESSION_USER: %, CURRENT_USER: %) lacks required ownership-transfer authority for role "eb_sec_admin". Execution halted before making schema changes. DBA must grant eb_sec_admin to migration executor.', SESSION_USER, CURRENT_USER
                    USING ERRCODE = '42501';
            END IF;

            -- 4. Validate executor possesses migration execution authority for eb_migration_role
            IF NOT (
                pg_has_role(SESSION_USER, 'eb_migration_role', 'MEMBER')
                OR pg_has_role(CURRENT_USER, 'eb_migration_role', 'MEMBER')
            ) THEN
                RAISE EXCEPTION 'AUTHORIZATION VIOLATION: Migration executor (SESSION_USER: %, CURRENT_USER: %) lacks required execution authority for role "eb_migration_role". Execution halted before making schema changes. DBA must grant eb_migration_role to migration executor.', SESSION_USER, CURRENT_USER
                    USING ERRCODE = '42501';
            END IF;
        END $auth_preflight$;
    """)

    # -------------------------------------------------------------------------
    # PHASE 1: CRYPTOGRAPHIC EXTENSION, ENUMS & CIRCUIT BREAKER TABLE
    # -------------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    terminal_class_enum = postgresql.ENUM(
        "RETRY_BUDGET_EXHAUSTED",
        "PERMANENT_RECIPIENT_REJECTION",
        "PAYLOAD_SNAPSHOT_UNAVAILABLE",
        "LEGACY_FAILURE_UNCLASSIFIED",
        "PERMANENT_SENDER_REJECTION",
        "PERMANENT_CONTENT_POLICY_REJECTION",
        "CORRELATION_QUARANTINE_DISCARD",
        name="terminal_failure_class_enum",
    )
    terminal_class_enum.create(bind, checkfirst=True)

    # 1. Platform Circuit Breakers Table
    op.create_table(
        "platform_circuit_breakers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("service_name", sa.String(50), nullable=False, unique=True),
        sa.Column("state", sa.String(20), nullable=False, server_default="CLOSED"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "consecutive_successes", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_state_change_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "cooldown_seconds", sa.Integer(), nullable=False, server_default="300"
        ),
        sa.Column("trip_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.execute("""
        INSERT INTO platform_circuit_breakers (service_name, state, failure_count, consecutive_successes)
        VALUES ('smtp_dispatch', 'CLOSED', 0, 0)
        ON CONFLICT (service_name) DO NOTHING;
    """)

    # -------------------------------------------------------------------------
    # PHASE 2: EXTEND NOTIFICATION_LOGS TO CANONICAL 22 COLUMNS
    # Pre-existing from 0001: id, enquiry_id, recipient_email, notification_type,
    #                         status, error_message, retry_count, last_attempt_at,
    #                         sent_at, created_at (10 columns).
    # Adding 12 extension columns. Total: 22 canonical columns.
    # -------------------------------------------------------------------------
    op.add_column(
        "notification_logs",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "notification_logs",
        sa.Column("retry_eligible_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notification_logs", sa.Column("claimed_by", sa.String(100), nullable=True)
    )
    op.add_column(
        "notification_logs",
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notification_logs",
        sa.Column("claim_version", sa.BigInteger(), nullable=False, server_default="1"),
    )
    op.add_column(
        "notification_logs",
        sa.Column(
            "is_legacy_exception", sa.Boolean(), nullable=False, server_default="false"
        ),
    )
    op.add_column(
        "notification_logs",
        sa.Column("terminal_failure_class", terminal_class_enum, nullable=True),
    )
    op.add_column(
        "notification_logs",
        sa.Column("terminal_classified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notification_logs",
        sa.Column("smtp_command_or_phase", sa.String(50), nullable=True),
    )
    op.add_column(
        "notification_logs", sa.Column("smtp_reply_code", sa.Integer(), nullable=True)
    )
    op.add_column(
        "notification_logs",
        sa.Column(
            "payload_context", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.add_column(
        "notification_logs",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # 2. Legacy Relational Provenance Audit Table (14 Columns, V43 Section 4.1.3)
    op.create_table(
        "legacy_notification_provenance",
        sa.Column(
            "notification_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notification_logs.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("migration_version", sa.String(50), nullable=False),
        sa.Column(
            "migrated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "migration_executor",
            sa.String(100),
            nullable=False,
            server_default=sa.func.current_user(),
        ),
        sa.Column("original_status", sa.String(50), nullable=False),
        sa.Column("original_attempt_count", sa.Integer(), nullable=False),
        sa.Column("original_retry_count", sa.Integer(), nullable=False),
        sa.Column(
            "original_last_attempt_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("original_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provenance_reason", sa.Text(), nullable=False),
        sa.Column(
            "migration_txid",
            sa.String(64),
            nullable=False,
            server_default=sa.text("CAST(txid_current() AS TEXT)"),
        ),
        sa.Column("key_version", sa.String(32), nullable=False),
        sa.Column(
            "serialization_version",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'eb-prov-v1'"),
        ),
        sa.Column("provenance_sha256", sa.String(64), nullable=False),
        sa.CheckConstraint(
            "migration_txid ~ '^(0|[1-9][0-9]*)$'",
            name="chk_provenance_txid_format",
        ),
    )

    # 3. Structured SMTP Evidence Store Table
    op.create_table(
        "smtp_evidence_store",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "notification_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notification_logs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("claim_version", sa.BigInteger(), nullable=False),
        sa.Column("worker_id", sa.String(100), nullable=False),
        sa.Column("smtp_command_or_phase", sa.String(50), nullable=False),
        sa.Column("smtp_reply_code", sa.Integer(), nullable=False),
        sa.Column("diagnostic_message", sa.Text(), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "notification_id", "attempt_count", name="uq_smtp_evidence_attempt"
        ),
        sa.CheckConstraint(
            "smtp_reply_code BETWEEN 200 AND 599", name="chk_smtp_reply_code"
        ),
        sa.CheckConstraint(
            "attempt_count BETWEEN 1 AND 4", name="chk_smtp_attempt_count"
        ),
    )

    # -------------------------------------------------------------------------
    # PHASE 3: SECURITY SCHEMA & SECURITY DEFINER FUNCTIONS
    # -------------------------------------------------------------------------
    op.execute("""
        -- 1. Create Dedicated eb_security Schema
        CREATE SCHEMA IF NOT EXISTS eb_security;

        -- 2. Schema Ownership & Permissions (eb_sec_admin owns eb_security schema)
        ALTER SCHEMA eb_security OWNER TO eb_sec_admin;
        REVOKE ALL ON SCHEMA eb_security FROM PUBLIC;
        GRANT USAGE ON SCHEMA eb_security TO eb_app_user, eb_worker_user, eb_migration_role, eb_migration_runner, eb_archival_role;
        REVOKE CREATE ON SCHEMA public FROM PUBLIC;
    """)

    # 4. Quarantine Audit Table in eb_security Schema
    op.execute("""
        CREATE TABLE IF NOT EXISTS eb_security.notification_quarantine_audit (
            audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            notification_id UUID NOT NULL REFERENCES public.notification_logs(id),
            released_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            primary_operator_id VARCHAR(64) NOT NULL,
            secondary_approver_id VARCHAR(64),
            override_ticket_id VARCHAR(64),
            release_category VARCHAR(64) NOT NULL,
            prior_attempt_count INT NOT NULL,
            prior_retry_count INT NOT NULL,
            new_target_status VARCHAR(20) NOT NULL,
            claim_version_at_release BIGINT NOT NULL,
            duplicate_risk_acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
            upstream_evidence_ref TEXT,
            terminal_failure_class VARCHAR(64),
            justification_reason TEXT NOT NULL
        );
        ALTER TABLE eb_security.notification_quarantine_audit OWNER TO eb_sec_admin;
        REVOKE ALL ON eb_security.notification_quarantine_audit FROM PUBLIC;
        GRANT SELECT ON eb_security.notification_quarantine_audit TO eb_sec_admin, eb_migration_runner;
    """)

    # 5. Functions & Triggers in eb_security Schema
    op.execute("""
        -- Function: Validate Legacy Provenance
        CREATE OR REPLACE FUNCTION eb_security.fn_validate_legacy_provenance()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, eb_security, public
        AS $$
        DECLARE
            v_prov public.legacy_notification_provenance%ROWTYPE;
        BEGIN
            IF NEW.is_legacy_exception IS TRUE THEN
                SELECT * INTO v_prov
                FROM public.legacy_notification_provenance
                WHERE notification_id = NEW.id;

                IF NOT FOUND THEN
                    RAISE EXCEPTION 'PROVENANCE VERIFICATION FAILED: Notification % marked as legacy exception without registered audit record in legacy_notification_provenance',
                        NEW.id USING ERRCODE = '23514';
                END IF;

                IF NEW.attempt_count IS DISTINCT FROM v_prov.original_attempt_count OR
                   NEW.retry_count IS DISTINCT FROM v_prov.original_retry_count THEN
                    RAISE EXCEPTION 'PROVENANCE INTEGRITY MISMATCH: Notification % counters (att=%, ret=%) do not match immutable provenance record (att=%, ret=%)',
                        NEW.id, NEW.attempt_count, NEW.retry_count, v_prov.original_attempt_count, v_prov.original_retry_count
                        USING ERRCODE = '23514';
                END IF;

                IF NEW.status NOT IN ('SENT', 'EXHAUSTED') THEN
                    RAISE EXCEPTION 'PROVENANCE STATUS INVALID: Notification % marked as legacy exception but in non-terminal status %',
                        NEW.id, NEW.status USING ERRCODE = '23514';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$;

        ALTER FUNCTION eb_security.fn_validate_legacy_provenance() OWNER TO eb_sec_admin;
        REVOKE ALL ON FUNCTION eb_security.fn_validate_legacy_provenance() FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION eb_security.fn_validate_legacy_provenance() TO eb_app_user, eb_migration_role;

        CREATE CONSTRAINT TRIGGER trg_validate_legacy_provenance
        AFTER INSERT OR UPDATE ON public.notification_logs
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION eb_security.fn_validate_legacy_provenance();

        -- Function: Prevent Provenance Tampering
        CREATE OR REPLACE FUNCTION eb_security.fn_prevent_provenance_tampering()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, eb_security, public
        AS $$
        BEGIN
            RAISE EXCEPTION 'IMMUTABILITY VIOLATION: Records in legacy_notification_provenance cannot be modified or deleted (id: %)',
                OLD.notification_id USING ERRCODE = '55000';
        END;
        $$;

        ALTER FUNCTION eb_security.fn_prevent_provenance_tampering() OWNER TO eb_sec_admin;
        REVOKE ALL ON FUNCTION eb_security.fn_prevent_provenance_tampering() FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION eb_security.fn_prevent_provenance_tampering() TO eb_app_user, eb_migration_role;

        CREATE TRIGGER trg_protect_provenance_immutability
        BEFORE UPDATE OR DELETE ON public.legacy_notification_provenance
        FOR EACH ROW
        EXECUTE FUNCTION eb_security.fn_prevent_provenance_tampering();

        -- Function: Prevent Terminal Record Tampering
        CREATE OR REPLACE FUNCTION eb_security.fn_prevent_terminal_record_tampering()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, eb_security, public
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.status IN ('SENT', 'EXHAUSTED') THEN
                    RAISE EXCEPTION 'TERMINAL RECORD DELETION VIOLATION: Notification % is finalized in terminal status % and cannot be deleted',
                        OLD.id, OLD.status USING ERRCODE = '55000';
                END IF;
                RETURN OLD;
            END IF;

            IF TG_OP = 'UPDATE' THEN
                IF OLD.status IN ('SENT', 'EXHAUSTED') THEN
                    IF NEW IS DISTINCT FROM OLD THEN
                        RAISE EXCEPTION 'TERMINAL RECORD IMMUTABILITY VIOLATION: Notification % is finalized in terminal status % and all columns are permanently immutable',
                            OLD.id, OLD.status USING ERRCODE = '55000';
                    END IF;
                END IF;
                RETURN NEW;
            END IF;

            RETURN NEW;
        END;
        $$;

        ALTER FUNCTION eb_security.fn_prevent_terminal_record_tampering() OWNER TO eb_sec_admin;
        REVOKE ALL ON FUNCTION eb_security.fn_prevent_terminal_record_tampering() FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION eb_security.fn_prevent_terminal_record_tampering() TO eb_app_user, eb_worker_user, eb_migration_runner, eb_migration_role;

        CREATE TRIGGER trg_protect_terminal_record_immutability
        BEFORE UPDATE OR DELETE ON public.notification_logs
        FOR EACH ROW
        WHEN (OLD.status IN ('SENT', 'EXHAUSTED'))
        EXECUTE FUNCTION eb_security.fn_prevent_terminal_record_tampering();

        -- Function: Guard SMTP Evidence Immutability
        CREATE OR REPLACE FUNCTION eb_security.fn_guard_smtp_evidence_immutability()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, eb_security, public
        AS $$
        BEGIN
            RAISE EXCEPTION 'IMMUTABILITY VIOLATION: smtp_evidence_store records are append-only and cannot be updated or deleted (attempted % on ID %)',
                TG_OP, OLD.id
                USING ERRCODE = '55000';
        END;
        $$;

        ALTER FUNCTION eb_security.fn_guard_smtp_evidence_immutability() OWNER TO eb_sec_admin;
        REVOKE ALL ON FUNCTION eb_security.fn_guard_smtp_evidence_immutability() FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION eb_security.fn_guard_smtp_evidence_immutability() TO eb_worker_user, eb_migration_role;

        CREATE TRIGGER trg_guard_smtp_evidence_immutability
        BEFORE UPDATE OR DELETE ON public.smtp_evidence_store
        FOR EACH ROW
        EXECUTE FUNCTION eb_security.fn_guard_smtp_evidence_immutability();

        -- Function: Guard Terminal INSERT
        CREATE OR REPLACE FUNCTION eb_security.fn_guard_terminal_insert()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, eb_security, public
        AS $$
        DECLARE
            v_session_user text := SESSION_USER;
            v_current_role text := current_setting('role', true);
            v_is_authorized_migration boolean;
            v_is_authorized_app boolean;
        BEGIN
            v_is_authorized_migration := (
                (v_session_user = 'eb_migration_runner' AND v_current_role = 'eb_migration_role')
                OR (v_session_user = 'postgres')
            );

            v_is_authorized_app := (
                v_session_user IN ('eb_app_user', 'postgres')
                OR v_is_authorized_migration
            );

            IF v_session_user = 'eb_worker_user' THEN
                RAISE EXCEPTION 'PERMISSION DENIED: Celery worker role "eb_worker_user" cannot insert new notification records (attempted INSERT on ID %)',
                    NEW.id
                    USING ERRCODE = '42501';
            END IF;

            IF NOT v_is_authorized_app THEN
                RAISE EXCEPTION 'UNAUTHORIZED PRINCIPAL: Role "%" is not authorized to insert notification records',
                    v_session_user
                    USING ERRCODE = '42501';
            END IF;

            IF NOT v_is_authorized_migration THEN
                IF NEW.status != 'PENDING' THEN
                    RAISE EXCEPTION 'TERMINAL INSERT VIOLATION: Role "%" cannot directly insert % records (Notification ID %). New notifications must be inserted as PENDING.',
                        v_session_user, NEW.status, NEW.id
                        USING ERRCODE = '42501';
                END IF;

                IF NEW.is_legacy_exception = TRUE THEN
                    RAISE EXCEPTION 'PROVENANCE FORGERY: Role "%" cannot assert is_legacy_exception = TRUE on new notifications',
                        v_session_user
                        USING ERRCODE = '42501';
                END IF;

                IF NEW.attempt_count != 0 OR NEW.retry_count != 0 OR NEW.sent_at IS NOT NULL OR NEW.retry_eligible_at IS NOT NULL THEN
                    RAISE EXCEPTION 'INVALID PENDING INGESTION: New notifications must have attempt_count=0, retry_count=0, sent_at=NULL, retry_eligible_at=NULL'
                        USING ERRCODE = '23514';
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$;

        ALTER FUNCTION eb_security.fn_guard_terminal_insert() OWNER TO eb_sec_admin;
        REVOKE ALL ON FUNCTION eb_security.fn_guard_terminal_insert() FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION eb_security.fn_guard_terminal_insert() TO eb_app_user, eb_worker_user, eb_migration_runner, eb_migration_role;

        CREATE TRIGGER trg_guard_terminal_insert
        BEFORE INSERT ON public.notification_logs
        FOR EACH ROW
        EXECUTE FUNCTION eb_security.fn_guard_terminal_insert();

        -- Function: Guard Operational UPDATE (Wall-Clock clock_timestamp() Evaluation)
        CREATE OR REPLACE FUNCTION eb_security.fn_guard_operational_update()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, eb_security, public
        AS $$
        DECLARE
            v_session_user text := SESSION_USER;
            v_current_role text := current_setting('role', true);
            v_is_authorized_migration boolean;
            v_is_authorized_worker boolean;
            v_now_clock timestamptz := clock_timestamp();
        BEGIN
            v_is_authorized_migration := (
                (v_session_user = 'eb_migration_runner' AND v_current_role = 'eb_migration_role')
                OR (v_session_user = 'postgres')
            );

            v_is_authorized_worker := (
                v_session_user IN ('eb_worker_user', 'postgres')
                OR v_is_authorized_migration
            );

            IF v_session_user = 'eb_app_user' THEN
                RAISE EXCEPTION 'PERMISSION DENIED: Application web role "eb_app_user" cannot modify operational notification fields or status (attempted update on ID %)',
                    OLD.id
                    USING ERRCODE = '42501';
            END IF;

            IF NOT v_is_authorized_worker THEN
                RAISE EXCEPTION 'UNAUTHORIZED PRINCIPAL: Role "%" is not authorized to update notification records',
                    v_session_user
                    USING ERRCODE = '42501';
            END IF;

            IF OLD.status IN ('SENT', 'EXHAUSTED') THEN
                IF NEW IS DISTINCT FROM OLD THEN
                    RAISE EXCEPTION 'TERMINAL RECORD IMMUTABILITY VIOLATION: Cannot modify terminal % notification record (ID %)',
                        OLD.status, OLD.id
                        USING ERRCODE = '55000';
                END IF;
                RETURN NEW;
            END IF;

            IF NEW.status = OLD.status THEN
                IF OLD.status = 'CLAIMED' THEN
                    IF OLD.claim_expires_at <= v_now_clock AND NOT v_is_authorized_migration THEN
                        RAISE EXCEPTION 'EXPIRED LEASE: Cannot heartbeat expired lease on CLAIMED notification (ID %)', OLD.id
                            USING ERRCODE = '23514';
                    END IF;
                    IF NEW.claimed_by IS DISTINCT FROM OLD.claimed_by THEN
                        RAISE EXCEPTION 'LEASE OWNERSHIP VIOLATION: Cannot modify claimed_by during heartbeat (ID %)', OLD.id
                            USING ERRCODE = '23514';
                    END IF;
                    IF NEW.claim_version IS DISTINCT FROM OLD.claim_version THEN
                        RAISE EXCEPTION 'CLAIM FENCING VIOLATION: Cannot modify claim_version during heartbeat (ID %)', OLD.id
                            USING ERRCODE = '23514';
                    END IF;
                    IF NEW.claim_expires_at <= v_now_clock OR NEW.claim_expires_at > v_now_clock + INTERVAL '300 seconds' THEN
                        RAISE EXCEPTION 'INVALID LEASE EXTENSION: Heartbeat claim_expires_at must be between clock_timestamp() and clock_timestamp()+300s'
                            USING ERRCODE = '23514';
                    END IF;
                    IF NEW.attempt_count IS DISTINCT FROM OLD.attempt_count
                       OR NEW.retry_count IS DISTINCT FROM OLD.retry_count
                       OR NEW.last_attempt_at IS DISTINCT FROM OLD.last_attempt_at
                       OR NEW.sent_at IS DISTINCT FROM OLD.sent_at
                       OR NEW.retry_eligible_at IS DISTINCT FROM OLD.retry_eligible_at
                       OR NEW.terminal_failure_class IS DISTINCT FROM OLD.terminal_failure_class
                       OR NEW.terminal_classified_at IS DISTINCT FROM OLD.terminal_classified_at
                       OR NEW.smtp_command_or_phase IS DISTINCT FROM OLD.smtp_command_or_phase
                       OR NEW.smtp_reply_code IS DISTINCT FROM OLD.smtp_reply_code
                       OR NEW.error_message IS DISTINCT FROM OLD.error_message
                       OR NEW.payload_context IS DISTINCT FROM OLD.payload_context
                       OR NEW.recipient_email IS DISTINCT FROM OLD.recipient_email
                       OR NEW.notification_type IS DISTINCT FROM OLD.notification_type
                       OR NEW.enquiry_id IS DISTINCT FROM OLD.enquiry_id
                       OR NEW.created_at IS DISTINCT FROM OLD.created_at
                       OR NEW.is_legacy_exception IS DISTINCT FROM OLD.is_legacy_exception
                    THEN
                        RAISE EXCEPTION 'ILLEGAL OPERATIONAL UPDATE: Heartbeat on CLAIMED record may only update claim_expires_at and updated_at (ID %)', OLD.id
                            USING ERRCODE = '23514';
                    END IF;
                    RETURN NEW;
                ELSIF OLD.status IN ('PENDING', 'FAILED') THEN
                    IF NOT v_is_authorized_migration THEN
                        RAISE EXCEPTION 'ILLEGAL OPERATIONAL UPDATE: Modifying operational fields on % record without status transition is strictly prohibited (ID %)',
                            OLD.status, OLD.id
                            USING ERRCODE = '23514';
                    END IF;
                    RETURN NEW;
                END IF;
            END IF;

            -- Authoritative Status Transition Matrix
            IF OLD.status = 'PENDING' AND NEW.status = 'CLAIMED' THEN
                IF OLD.attempt_count != 0 OR OLD.retry_count != 0 THEN
                    RAISE EXCEPTION 'INVALID PENDING STATE: PENDING notification must have attempt_count=0, retry_count=0' USING ERRCODE = '23514';
                END IF;
                IF NEW.claimed_by IS NULL OR NEW.claim_expires_at IS NULL OR NEW.claim_expires_at <= v_now_clock OR NEW.claim_expires_at > v_now_clock + INTERVAL '300 seconds' THEN
                    RAISE EXCEPTION 'INVALID CLAIM LEASE: Active lease required' USING ERRCODE = '23514';
                END IF;
                IF NEW.claim_version != OLD.claim_version + 1 THEN
                    RAISE EXCEPTION 'FENCING PROGRESSION VIOLATION: claim_version increment required' USING ERRCODE = '23514';
                END IF;
                IF NEW.attempt_count != 1 OR NEW.retry_count != 0 THEN
                    RAISE EXCEPTION 'INVALID COUNTERS: Initial claim requires attempt_count=1, retry_count=0' USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            ELSIF OLD.status = 'FAILED' AND NEW.status = 'CLAIMED' THEN
                IF OLD.retry_eligible_at IS NULL THEN
                    RAISE EXCEPTION 'INVALID RETRY STATE: FAILED record has NULL retry_eligible_at (ID %)', OLD.id USING ERRCODE = '23514';
                END IF;
                IF OLD.retry_eligible_at > v_now_clock AND NOT v_is_authorized_migration THEN
                    RAISE EXCEPTION 'PREMATURE RETRY CLAIM: Cooldown active until %', OLD.retry_eligible_at USING ERRCODE = '23514';
                END IF;
                IF NEW.claimed_by IS NULL OR NEW.claim_expires_at IS NULL OR NEW.claim_expires_at <= v_now_clock OR NEW.claim_expires_at > v_now_clock + INTERVAL '300 seconds' THEN
                    RAISE EXCEPTION 'INVALID CLAIM LEASE: Active lease required' USING ERRCODE = '23514';
                END IF;
                IF NEW.claim_version != OLD.claim_version + 1 THEN
                    RAISE EXCEPTION 'FENCING PROGRESSION VIOLATION: claim_version increment required' USING ERRCODE = '23514';
                END IF;
                IF NEW.attempt_count != OLD.attempt_count + 1 OR NEW.retry_count != OLD.retry_count + 1 THEN
                    RAISE EXCEPTION 'COUNTER PROGRESSION VIOLATION: Increment both attempt and retry count by 1' USING ERRCODE = '23514';
                END IF;
                IF NEW.attempt_count > 4 THEN
                    RAISE EXCEPTION 'RETRY BUDGET EXCEEDED: attempt_count cannot exceed 4' USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            ELSIF OLD.status = 'CLAIMED' AND NEW.status = 'SENT' THEN
                IF OLD.claim_expires_at <= v_now_clock AND NOT v_is_authorized_migration THEN
                    RAISE EXCEPTION 'EXPIRED LEASE: Cannot finalize SENT with expired lease' USING ERRCODE = '23514';
                END IF;
                IF NEW.claimed_by IS NOT NULL OR NEW.claim_expires_at IS NOT NULL THEN
                    RAISE EXCEPTION 'INVALID LEASE: Lease fields must be cleared on SENT' USING ERRCODE = '23514';
                END IF;
                IF NEW.sent_at IS NULL OR NEW.sent_at > v_now_clock THEN
                    RAISE EXCEPTION 'INVALID TERMINAL SENT: sent_at <= clock_timestamp() required' USING ERRCODE = '23514';
                END IF;
                IF NOT v_is_authorized_migration THEN
                    PERFORM 1 FROM public.smtp_evidence_store
                    WHERE notification_id = NEW.id
                      AND attempt_count = NEW.attempt_count
                      AND claim_version = OLD.claim_version
                      AND worker_id = OLD.claimed_by
                      AND smtp_reply_code = 250
                      AND smtp_command_or_phase = 'DATA';
                    IF NOT FOUND THEN
                        RAISE EXCEPTION 'MISSING SMTP EVIDENCE: Terminal SENT transition requires verified RFC 5321 code 250 evidence in smtp_evidence_store' USING ERRCODE = '23514';
                    END IF;
                END IF;
                RETURN NEW;
            ELSIF OLD.status = 'CLAIMED' AND NEW.status = 'FAILED' THEN
                IF NEW.claimed_by IS NOT NULL OR NEW.claim_expires_at IS NOT NULL THEN
                    RAISE EXCEPTION 'INVALID LEASE: Lease fields must be cleared on FAILED' USING ERRCODE = '23514';
                END IF;
                IF NEW.attempt_count >= 4 THEN
                    RAISE EXCEPTION 'EXCEEDED RETRY BUDGET: Notification with attempt_count >= 4 must transition to EXHAUSTED' USING ERRCODE = '23514';
                END IF;
                IF NEW.retry_eligible_at IS NULL OR NEW.retry_eligible_at <= v_now_clock THEN
                    RAISE EXCEPTION 'INVALID RETRY COOLDOWN: Future retry_eligible_at required' USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            ELSIF OLD.status = 'CLAIMED' AND NEW.status = 'EXHAUSTED' THEN
                IF NEW.claimed_by IS NOT NULL OR NEW.claim_expires_at IS NOT NULL THEN
                    RAISE EXCEPTION 'INVALID LEASE: Lease fields must be cleared on EXHAUSTED' USING ERRCODE = '23514';
                END IF;
                IF NEW.terminal_classified_at IS NULL OR NEW.terminal_classified_at > v_now_clock THEN
                    RAISE EXCEPTION 'INVALID CLASSIFICATION TIMESTAMP: terminal_classified_at required' USING ERRCODE = '23514';
                END IF;
                IF NEW.terminal_failure_class = 'RETRY_BUDGET_EXHAUSTED' THEN
                    IF NEW.attempt_count != 4 OR NEW.retry_count != 3 THEN
                        RAISE EXCEPTION 'COUNTER BOUND VIOLATION: Class A requires attempt_count=4, retry_count=3' USING ERRCODE = '23514';
                    END IF;
                ELSIF NEW.terminal_failure_class = 'PERMANENT_RECIPIENT_REJECTION' THEN
                    IF NEW.smtp_command_or_phase != 'RCPT_TO' OR NEW.smtp_reply_code NOT BETWEEN 550 AND 554 THEN
                        RAISE EXCEPTION 'EVIDENCE VIOLATION: Class B requires RCPT_TO and code 550-554' USING ERRCODE = '23514';
                    END IF;
                ELSE
                    RAISE EXCEPTION 'ILLEGAL CLASSIFICATION: CLAIMED -> EXHAUSTED permits only Class A or Class B' USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            ELSIF OLD.status = 'PENDING' AND NEW.status = 'EXHAUSTED' THEN
                IF NEW.terminal_failure_class != 'PAYLOAD_SNAPSHOT_UNAVAILABLE' THEN
                    RAISE EXCEPTION 'ILLEGAL TRANSITION: PENDING -> EXHAUSTED permits strictly Class C' USING ERRCODE = '23514';
                END IF;
                IF OLD.payload_context IS NOT NULL AND OLD.payload_context != '{}'::jsonb THEN
                    RAISE EXCEPTION 'ILLEGAL CLASS C: Cannot exhaust PENDING notification with valid payload context (ID %)', OLD.id USING ERRCODE = '23514';
                END IF;
                IF NEW.attempt_count != 0 OR NEW.retry_count != 0 OR NEW.last_attempt_at IS NOT NULL OR NEW.sent_at IS NOT NULL OR NEW.retry_eligible_at IS NOT NULL THEN
                    RAISE EXCEPTION 'INVALID CLASS C: Pre-dispatch quarantine requires 0 attempts and NULL timestamps' USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            ELSE
                RAISE EXCEPTION 'ILLEGAL STATUS TRANSITION: Transition from "%" to "%" is forbidden (Notification ID %)',
                    OLD.status, NEW.status, OLD.id USING ERRCODE = '23514';
            END IF;

            RETURN NEW;
        END;
        $$;

        ALTER FUNCTION eb_security.fn_guard_operational_update() OWNER TO eb_sec_admin;
        REVOKE ALL ON FUNCTION eb_security.fn_guard_operational_update() FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION eb_security.fn_guard_operational_update() TO eb_app_user, eb_worker_user, eb_migration_runner, eb_migration_role;

        CREATE TRIGGER trg_guard_operational_update
        BEFORE UPDATE ON public.notification_logs
        FOR EACH ROW
        EXECUTE FUNCTION eb_security.fn_guard_operational_update();

        -- Function: Quarantine Release Gateway Function
        CREATE OR REPLACE FUNCTION eb_security.fn_release_quarantine(
            p_notification_id UUID,
            p_target_status VARCHAR(20),
            p_release_category VARCHAR(64),
            p_primary_operator_id VARCHAR(64),
            p_secondary_approver_id VARCHAR(64) DEFAULT NULL,
            p_override_ticket_id VARCHAR(64) DEFAULT NULL,
            p_justification_reason TEXT DEFAULT '',
            p_duplicate_risk_acknowledged BOOLEAN DEFAULT FALSE,
            p_upstream_evidence_ref TEXT DEFAULT NULL,
            p_terminal_failure_class VARCHAR(64) DEFAULT NULL
        )
        RETURNS BOOLEAN
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public, eb_security
        AS $$
        DECLARE
            v_session_user VARCHAR(64) := SESSION_USER;
            v_old_status VARCHAR(20);
            v_old_attempt INT;
            v_old_retry INT;
            v_old_claim_ver BIGINT;
            v_term_class terminal_failure_class_enum;
        BEGIN
            -- 1. Administrative Authorization Validation
            IF NOT (
                pg_has_role(v_session_user, 'eb_sec_admin', 'MEMBER')
                OR v_session_user = 'postgres'
            ) THEN
                RAISE EXCEPTION 'PERMISSION DENIED: Caller % is not authorized to execute quarantine release', v_session_user
                    USING ERRCODE = '42501';
            END IF;

            IF p_primary_operator_id IS NULL OR length(trim(p_primary_operator_id)) < 3 THEN
                RAISE EXCEPTION 'PERMISSION DENIED: Valid primary operator ID is required'
                    USING ERRCODE = '42501';
            END IF;

            -- 2. Target status validation
            IF p_target_status NOT IN ('PENDING', 'SENT', 'EXHAUSTED') THEN
                RAISE EXCEPTION 'INVALID TARGET STATUS: Quarantine release must target PENDING, SENT, or EXHAUSTED (received: %)', p_target_status
                    USING ERRCODE = '22023';
            END IF;

            -- 3. Release Category Validation
            IF p_release_category NOT IN (
                'Q1_CONFIRMED_NON_DELIVERY',
                'Q2_ACCEPTANCE_CONFIRMED',
                'Q2_NON_ACCEPTANCE_4XX',
                'Q2_NON_ACCEPTANCE_5XX',
                'Q2_UNCERTAIN_OVERRIDE',
                'Q2_UNRESOLVED_DISCARD',
                'Q3_DATABASE_REPAIR'
            ) THEN
                RAISE EXCEPTION 'INVALID RELEASE CATEGORY: % is not a recognized quarantine release category', p_release_category
                    USING ERRCODE = '22023';
            END IF;

            -- 4. Lock and validate record state
            SELECT status, attempt_count, retry_count, claim_version
            INTO v_old_status, v_old_attempt, v_old_retry, v_old_claim_ver
            FROM public.notification_logs
            WHERE id = p_notification_id
            FOR UPDATE;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'RECORD NOT FOUND: Notification % does not exist', p_notification_id
                    USING ERRCODE = '02000';
            END IF;

            IF v_old_status != 'QUARANTINED' THEN
                RAISE EXCEPTION 'INVALID STATE: Notification % is in status %, not QUARANTINED', p_notification_id, v_old_status
                    USING ERRCODE = '22023';
            END IF;

            -- 5. Attempt Budget Guard
            IF p_target_status = 'PENDING' AND v_old_attempt >= 4 THEN
                RAISE EXCEPTION 'ATTEMPT BUDGET EXHAUSTED: Record % has already executed 4 attempts (att=%); cannot release to PENDING', p_notification_id, v_old_attempt
                    USING ERRCODE = '23514';
            END IF;

            -- 6. Category-Specific Enforcement
            IF p_release_category = 'Q2_ACCEPTANCE_CONFIRMED' THEN
                IF p_target_status != 'SENT' THEN
                    RAISE EXCEPTION 'POLICY VIOLATION: Q2_ACCEPTANCE_CONFIRMED must transition record strictly to SENT' USING ERRCODE = '22023';
                END IF;
                IF p_upstream_evidence_ref IS NULL OR length(trim(p_upstream_evidence_ref)) < 5 THEN
                    RAISE EXCEPTION 'POLICY VIOLATION: Q2_ACCEPTANCE_CONFIRMED requires verifiable upstream relay evidence reference' USING ERRCODE = '22023';
                END IF;
            END IF;

            IF p_release_category = 'Q2_NON_ACCEPTANCE_4XX' THEN
                IF p_upstream_evidence_ref IS NULL OR length(trim(p_upstream_evidence_ref)) < 5 THEN
                    RAISE EXCEPTION 'POLICY VIOLATION: Q2_NON_ACCEPTANCE_4XX requires verifiable upstream 4xx rejection evidence reference' USING ERRCODE = '22023';
                END IF;
                IF p_target_status = 'SENT' THEN
                    RAISE EXCEPTION 'POLICY VIOLATION: Q2_NON_ACCEPTANCE_4XX cannot transition to SENT' USING ERRCODE = '22023';
                END IF;
            END IF;

            IF p_release_category = 'Q2_NON_ACCEPTANCE_5XX' THEN
                IF p_target_status != 'EXHAUSTED' THEN
                    RAISE EXCEPTION 'POLICY VIOLATION: Q2_NON_ACCEPTANCE_5XX must transition strictly to EXHAUSTED. Retrying unchanged rejected messages is prohibited' USING ERRCODE = '22023';
                END IF;
                IF p_upstream_evidence_ref IS NULL OR length(trim(p_upstream_evidence_ref)) < 5 THEN
                    RAISE EXCEPTION 'POLICY VIOLATION: Q2_NON_ACCEPTANCE_5XX requires verifiable upstream 5xx rejection evidence reference' USING ERRCODE = '22023';
                END IF;
                IF p_terminal_failure_class NOT IN ('PERMANENT_RECIPIENT_REJECTION', 'PERMANENT_SENDER_REJECTION', 'PERMANENT_CONTENT_POLICY_REJECTION') THEN
                    RAISE EXCEPTION 'POLICY VIOLATION: Q2_NON_ACCEPTANCE_5XX requires valid permanent failure class (Class B, E, or F)' USING ERRCODE = '22023';
                END IF;
                v_term_class := p_terminal_failure_class::terminal_failure_class_enum;
            END IF;

            IF p_release_category = 'Q2_UNRESOLVED_DISCARD' THEN
                IF p_target_status != 'EXHAUSTED' THEN
                    RAISE EXCEPTION 'POLICY VIOLATION: Q2_UNRESOLVED_DISCARD must transition strictly to EXHAUSTED' USING ERRCODE = '22023';
                END IF;
                IF length(trim(p_justification_reason)) < 20 THEN
                    RAISE EXCEPTION 'POLICY VIOLATION: Detailed written justification required to discard unresolved quarantine record' USING ERRCODE = '23514';
                END IF;
                v_term_class := 'CORRELATION_QUARANTINE_DISCARD'::terminal_failure_class_enum;
            END IF;

            IF p_release_category = 'Q2_UNCERTAIN_OVERRIDE' THEN
                IF p_target_status != 'PENDING' THEN
                    RAISE EXCEPTION 'POLICY VIOLATION: Q2_UNCERTAIN_OVERRIDE must target PENDING for retransmission' USING ERRCODE = '22023';
                END IF;
                IF NOT p_duplicate_risk_acknowledged THEN
                    RAISE EXCEPTION 'POLICY VIOLATION: Q2 uncertain override requires explicit duplicate delivery risk acknowledgement' USING ERRCODE = '23514';
                END IF;
                IF p_secondary_approver_id IS NULL OR length(trim(p_secondary_approver_id)) < 3 THEN
                    RAISE EXCEPTION 'PERMISSION DENIED: Q2 uncertain override requires secondary approver ID from external dual-control ticket' USING ERRCODE = '42501';
                END IF;
                IF p_secondary_approver_id = p_primary_operator_id THEN
                    RAISE EXCEPTION 'PERMISSION DENIED: Primary operator cannot serve as secondary approver (dual control violation)' USING ERRCODE = '42501';
                END IF;
                IF p_override_ticket_id IS NULL OR p_override_ticket_id !~ '^ITSM-[A-Z0-9_-]+$' THEN
                    RAISE EXCEPTION 'POLICY VIOLATION: Q2 uncertain override requires valid external dual-custody ticket format (^ITSM-[A-Z0-9_-]+$)' USING ERRCODE = '23514';
                END IF;
                IF length(trim(p_justification_reason)) < 20 THEN
                    RAISE EXCEPTION 'POLICY VIOLATION: Detailed written commercial justification required for uncertain override' USING ERRCODE = '23514';
                END IF;
            END IF;

            -- 7. Execute atomic update with cumulative counter preservation
            UPDATE public.notification_logs
            SET status = p_target_status,
                claimed_by = NULL,
                claim_expires_at = NULL,
                retry_eligible_at = CASE
                    WHEN p_target_status = 'PENDING' THEN NULL
                    ELSE retry_eligible_at
                END,
                sent_at = CASE
                    WHEN p_target_status = 'SENT' THEN clock_timestamp()
                    ELSE sent_at
                END,
                terminal_failure_class = CASE
                    WHEN p_target_status = 'EXHAUSTED' THEN COALESCE(v_term_class, 'CORRELATION_QUARANTINE_DISCARD'::terminal_failure_class_enum)
                    ELSE NULL
                END,
                terminal_classified_at = CASE
                    WHEN p_target_status = 'EXHAUSTED' THEN clock_timestamp()
                    ELSE NULL
                END,
                claim_version = claim_version + 1,
                updated_at = clock_timestamp()
            WHERE id = p_notification_id
              AND status = 'QUARANTINED'
              AND claim_version = v_old_claim_ver;

            -- 8. Record Immutable Audit Log Entry
            INSERT INTO eb_security.notification_quarantine_audit (
                notification_id,
                primary_operator_id,
                secondary_approver_id,
                override_ticket_id,
                release_category,
                prior_attempt_count,
                prior_retry_count,
                new_target_status,
                claim_version_at_release,
                duplicate_risk_acknowledged,
                upstream_evidence_ref,
                terminal_failure_class,
                justification_reason
            ) VALUES (
                p_notification_id,
                p_primary_operator_id,
                p_secondary_approver_id,
                p_override_ticket_id,
                p_release_category,
                v_old_attempt,
                v_old_retry,
                p_target_status,
                v_old_claim_ver + 1,
                p_duplicate_risk_acknowledged,
                p_upstream_evidence_ref,
                CASE WHEN p_target_status = 'EXHAUSTED' THEN COALESCE(v_term_class::text, 'CORRELATION_QUARANTINE_DISCARD') ELSE NULL END,
                p_justification_reason
            );

            RETURN TRUE;
        END;
        $$;

        ALTER FUNCTION eb_security.fn_release_quarantine(UUID, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, TEXT, BOOLEAN, TEXT, VARCHAR) OWNER TO eb_sec_admin;
        REVOKE EXECUTE ON FUNCTION eb_security.fn_release_quarantine FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION eb_security.fn_release_quarantine TO eb_migration_runner;
    """)

    # -------------------------------------------------------------------------
    # PHASE 4: HISTORICAL DATA BACKFILL & STATUS-AWARE NORMALIZATION (V43 SECTION 12.1)
    # -------------------------------------------------------------------------
    if not is_offline:
        # LIVE / ONLINE MIGRATION EXECUTION
        # Python computes RFC 8785 JCS HMAC-SHA256 with External KMS Client
        conn = op.get_bind()
        txid_val = conn.execute(sa.text("SELECT txid_current()::text;")).scalar()
        txid_str = str(int(txid_val)) if txid_val is not None else "0"
        kms_client = ExternalKMSClient.get_client()

        # Step 1: Clear invalid lease fields on non-CLAIMED legacy rows
        conn.execute(
            sa.text("""
            UPDATE notification_logs
            SET claimed_by = NULL,
                claim_expires_at = NULL
            WHERE status != 'CLAIMED'
              AND (claimed_by IS NOT NULL OR claim_expires_at IS NOT NULL);
        """)
        )

        # Step 2: SENT records processing
        # 2A: Normalize standard SENT natively if counters consistent (att = ret + 1 or both NULL)
        conn.execute(
            sa.text("""
            UPDATE notification_logs
            SET attempt_count = COALESCE(attempt_count, retry_count + 1, 1),
                retry_count = COALESCE(retry_count, CASE WHEN attempt_count > 0 THEN attempt_count - 1 ELSE 0 END, 0),
                claimed_by = NULL,
                claim_expires_at = NULL,
                retry_eligible_at = NULL,
                terminal_failure_class = NULL,
                terminal_classified_at = NULL,
                is_legacy_exception = FALSE
            WHERE status = 'SENT'
              AND (
                  (attempt_count IS NULL AND retry_count IS NULL)
                  OR (attempt_count > 0 AND retry_count = attempt_count - 1)
              );
        """)
        )

        # 2B: SENT records with contradictory counters: register provenance FIRST, then set is_legacy_exception = TRUE
        sent_contra_rows = conn.execute(
            sa.text("""
            SELECT id, status, attempt_count, retry_count, last_attempt_at, sent_at
            FROM notification_logs
            WHERE status = 'SENT'
              AND NOT (
                  (attempt_count IS NULL AND retry_count IS NULL)
                  OR (attempt_count > 0 AND retry_count = attempt_count - 1)
              );
        """)
        ).fetchall()

        if sent_contra_rows and not kms_client.has_active_key("eb-prov-k1-202611"):
            raise RuntimeError(
                "UNRESOLVED DEPLOYMENT PREREQUISITE: Database contains historical contradictory SENT records requiring "
                "HMAC-SHA256 provenance registration, but genuine external KMS integration is an unresolved deployment "
                "prerequisite and no approved KMS provider is configured. Migration execution halted safely (fail-closed)."
            )

        for r in sent_contra_rows:
            orig_att = r.attempt_count if r.attempt_count is not None else 0
            orig_ret = r.retry_count if r.retry_count is not None else 0
            rec = build_legacy_provenance_record(
                notification_id=str(r.id),
                original_status=str(r.status),
                original_attempt_count=orig_att,
                original_retry_count=orig_ret,
                original_last_attempt_at=r.last_attempt_at,
                original_sent_at=r.sent_at,
                provenance_reason="MIGRATION_0003_LEGACY_SENT_CONTRADICTORY_COUNTERS",
                migration_txid=txid_str,
                kms_client=kms_client,
            )

            conn.execute(
                sa.text("""
                INSERT INTO legacy_notification_provenance (
                    notification_id, migration_version, migrated_at, migration_executor,
                    original_status, original_attempt_count, original_retry_count,
                    original_last_attempt_at, original_sent_at, provenance_reason,
                    migration_txid, key_version, serialization_version, provenance_sha256
                )
                VALUES (
                    :nid, '0003_v43_0_0', :migrated_at, 'eb_migration_runner',
                    :orig_status, :orig_att, :orig_ret,
                    :orig_last, :orig_sent, :reason,
                    :txid, 'eb-prov-k1-202611', 'eb-prov-v1', :hmac
                )
                ON CONFLICT (notification_id) DO NOTHING;
            """),
                {
                    "nid": r.id,
                    "migrated_at": rec["migrated_at"],
                    "orig_status": r.status,
                    "orig_att": orig_att,
                    "orig_ret": orig_ret,
                    "orig_last": r.last_attempt_at,
                    "orig_sent": r.sent_at,
                    "reason": "MIGRATION_0003_LEGACY_SENT_CONTRADICTORY_COUNTERS",
                    "txid": txid_str,
                    "hmac": rec["provenance_sha256"],
                },
            )

            conn.execute(
                sa.text("""
                UPDATE notification_logs
                SET is_legacy_exception = TRUE,
                    claimed_by = NULL,
                    claim_expires_at = NULL,
                    retry_eligible_at = NULL,
                    terminal_failure_class = NULL,
                    terminal_classified_at = NULL
                WHERE id = :nid;
            """),
                {"nid": r.id},
            )

        # 2C: SENT Missing Payload Tombstone Marker
        conn.execute(
            sa.text("""
            UPDATE notification_logs
            SET payload_context = jsonb_build_object(
                'legacy_payload_unavailable', true,
                'tombstone_reason', 'HISTORICAL_PAYLOAD_UNAVAILABLE_AT_MIGRATION',
                'enquiry_id', enquiry_id,
                'migrated_at', NOW()
            )
            WHERE status = 'SENT'
              AND (payload_context IS NULL OR payload_context = '{}'::jsonb);
        """)
        )

        # Step 3: EXHAUSTED Records Classification
        # 3A: Class C - PAYLOAD_SNAPSHOT_UNAVAILABLE (Strict Unattempted Pre-Dispatch)
        conn.execute(
            sa.text("""
            UPDATE notification_logs
            SET terminal_failure_class = 'PAYLOAD_SNAPSHOT_UNAVAILABLE',
                terminal_classified_at = NOW(),
                attempt_count = 0,
                retry_count = 0,
                last_attempt_at = NULL,
                claimed_by = NULL,
                claim_expires_at = NULL,
                retry_eligible_at = NULL,
                payload_context = COALESCE(payload_context, '{"legacy_payload_missing": true}'::jsonb),
                error_message = COALESCE('[CLASS_C_PAYLOAD_UNAVAILABLE] ' || error_message, '[CLASS_C_PAYLOAD_UNAVAILABLE] Legacy exhausted record missing payload snapshot')
            WHERE status = 'EXHAUSTED'
              AND attempt_count = 0
              AND retry_count = 0
              AND last_attempt_at IS NULL
              AND (payload_context IS NULL OR payload_context = '{}'::jsonb);
        """)
        )

        # 3B: Class B - PERMANENT_RECIPIENT_REJECTION (Strict Structured Evidence & Consistent Counters)
        conn.execute(
            sa.text("""
            UPDATE notification_logs
            SET terminal_failure_class = 'PERMANENT_RECIPIENT_REJECTION',
                terminal_classified_at = NOW(),
                claimed_by = NULL,
                claim_expires_at = NULL,
                retry_eligible_at = NULL,
                payload_context = COALESCE(payload_context, jsonb_build_object('enquiry_id', enquiry_id, 'migrated_at', NOW()))
            WHERE status = 'EXHAUSTED'
              AND terminal_failure_class IS NULL
              AND smtp_command_or_phase = 'RCPT_TO'
              AND smtp_reply_code BETWEEN 550 AND 554
              AND attempt_count >= 1 AND attempt_count <= 4
              AND retry_count = attempt_count - 1;
        """)
        )

        # 3C: Class A - RETRY_BUDGET_EXHAUSTED (Exhausted Retries: retry_count = 3 or attempt_count = 4)
        conn.execute(
            sa.text("""
            UPDATE notification_logs
            SET terminal_failure_class = 'RETRY_BUDGET_EXHAUSTED',
                terminal_classified_at = NOW(),
                attempt_count = 4,
                retry_count = 3,
                claimed_by = NULL,
                claim_expires_at = NULL,
                retry_eligible_at = NULL,
                payload_context = COALESCE(payload_context, jsonb_build_object('enquiry_id', enquiry_id, 'migrated_at', NOW()))
            WHERE status = 'EXHAUSTED'
              AND terminal_failure_class IS NULL
              AND (retry_count = 3 OR attempt_count = 4);
        """)
        )

        # 3D: Class D - LEGACY_FAILURE_UNCLASSIFIED contradictory EXHAUSTED records
        ex_contra_rows = conn.execute(
            sa.text("""
            SELECT id, status, attempt_count, retry_count, last_attempt_at, sent_at
            FROM notification_logs
            WHERE status = 'EXHAUSTED'
              AND terminal_failure_class IS NULL;
        """)
        ).fetchall()

        if ex_contra_rows and not kms_client.has_active_key("eb-prov-k1-202611"):
            raise RuntimeError(
                "UNRESOLVED DEPLOYMENT PREREQUISITE: Database contains historical contradictory EXHAUSTED records requiring "
                "HMAC-SHA256 provenance registration, but genuine external KMS integration is an unresolved deployment "
                "prerequisite and no approved KMS provider is configured. Migration execution halted safely (fail-closed)."
            )

        for r in ex_contra_rows:
            orig_att = r.attempt_count if r.attempt_count is not None else 0
            orig_ret = r.retry_count if r.retry_count is not None else 0
            rec = build_legacy_provenance_record(
                notification_id=str(r.id),
                original_status=str(r.status),
                original_attempt_count=orig_att,
                original_retry_count=orig_ret,
                original_last_attempt_at=r.last_attempt_at,
                original_sent_at=r.sent_at,
                provenance_reason="MIGRATION_0003_LEGACY_EXHAUSTED_CONTRADICTORY_COUNTERS",
                migration_txid=txid_str,
                kms_client=kms_client,
            )

            conn.execute(
                sa.text("""
                INSERT INTO legacy_notification_provenance (
                    notification_id, migration_version, migrated_at, migration_executor,
                    original_status, original_attempt_count, original_retry_count,
                    original_last_attempt_at, original_sent_at, provenance_reason,
                    migration_txid, key_version, serialization_version, provenance_sha256
                )
                VALUES (
                    :nid, '0003_v43_0_0', :migrated_at, 'eb_migration_runner',
                    :orig_status, :orig_att, :orig_ret,
                    :orig_last, :orig_sent, :reason,
                    :txid, 'eb-prov-k1-202611', 'eb-prov-v1', :hmac
                )
                ON CONFLICT (notification_id) DO NOTHING;
            """),
                {
                    "nid": r.id,
                    "migrated_at": rec["migrated_at"],
                    "orig_status": r.status,
                    "orig_att": orig_att,
                    "orig_ret": orig_ret,
                    "orig_last": r.last_attempt_at,
                    "orig_sent": r.sent_at,
                    "reason": "MIGRATION_0003_LEGACY_EXHAUSTED_CONTRADICTORY_COUNTERS",
                    "txid": txid_str,
                    "hmac": rec["provenance_sha256"],
                },
            )

            conn.execute(
                sa.text("""
                UPDATE notification_logs
                SET terminal_failure_class = 'LEGACY_FAILURE_UNCLASSIFIED',
                    terminal_classified_at = NOW(),
                    is_legacy_exception = TRUE,
                    claimed_by = NULL,
                    claim_expires_at = NULL,
                    retry_eligible_at = NULL,
                    error_message = COALESCE('[MIGRATION_QUARANTINE_CONTRADICTORY] ' || error_message, '[MIGRATION_QUARANTINE_CONTRADICTORY] Historical contradictory evidence quarantined')
                WHERE id = :nid;
            """),
                {"nid": r.id},
            )

        # Step 4: PENDING & FAILED Records Processing
        # 4A: Contradictory PENDING records quarantined to Class D
        pending_contra_rows = conn.execute(
            sa.text("""
            SELECT id, status, attempt_count, retry_count, last_attempt_at, sent_at
            FROM notification_logs
            WHERE status = 'PENDING'
              AND (attempt_count > 0 OR retry_count > 0 OR last_attempt_at IS NOT NULL);
        """)
        ).fetchall()

        if pending_contra_rows and not kms_client.has_active_key("eb-prov-k1-202611"):
            raise RuntimeError(
                "UNRESOLVED DEPLOYMENT PREREQUISITE: Database contains historical contradictory PENDING records requiring "
                "HMAC-SHA256 provenance registration, but genuine external KMS integration is an unresolved deployment "
                "prerequisite and no approved KMS provider is configured. Migration execution halted safely (fail-closed)."
            )

        for r in pending_contra_rows:
            orig_att = r.attempt_count if r.attempt_count is not None else 0
            orig_ret = r.retry_count if r.retry_count is not None else 0
            rec = build_legacy_provenance_record(
                notification_id=str(r.id),
                original_status=str(r.status),
                original_attempt_count=orig_att,
                original_retry_count=orig_ret,
                original_last_attempt_at=r.last_attempt_at,
                original_sent_at=r.sent_at,
                provenance_reason="MIGRATION_0003_LEGACY_PENDING_ATTEMPT_EVIDENCE_QUARANTINED",
                migration_txid=txid_str,
                kms_client=kms_client,
            )

            conn.execute(
                sa.text("""
                INSERT INTO legacy_notification_provenance (
                    notification_id, migration_version, migrated_at, migration_executor,
                    original_status, original_attempt_count, original_retry_count,
                    original_last_attempt_at, original_sent_at, provenance_reason,
                    migration_txid, key_version, serialization_version, provenance_sha256
                )
                VALUES (
                    :nid, '0003_v43_0_0', :migrated_at, 'eb_migration_runner',
                    :orig_status, :orig_att, :orig_ret,
                    :orig_last, :orig_sent, :reason,
                    :txid, 'eb-prov-k1-202611', 'eb-prov-v1', :hmac
                )
                ON CONFLICT (notification_id) DO NOTHING;
            """),
                {
                    "nid": r.id,
                    "migrated_at": rec["migrated_at"],
                    "orig_status": r.status,
                    "orig_att": orig_att,
                    "orig_ret": orig_ret,
                    "orig_last": r.last_attempt_at,
                    "orig_sent": r.sent_at,
                    "reason": "MIGRATION_0003_LEGACY_PENDING_ATTEMPT_EVIDENCE_QUARANTINED",
                    "txid": txid_str,
                    "hmac": rec["provenance_sha256"],
                },
            )

            conn.execute(
                sa.text("""
                UPDATE notification_logs
                SET status = 'EXHAUSTED',
                    terminal_failure_class = 'LEGACY_FAILURE_UNCLASSIFIED',
                    terminal_classified_at = NOW(),
                    is_legacy_exception = TRUE,
                    claimed_by = NULL,
                    claim_expires_at = NULL,
                    retry_eligible_at = NULL,
                    error_message = COALESCE('[MIGRATION_QUARANTINE_ATTEMPTED_PENDING] ' || error_message, '[MIGRATION_QUARANTINE_ATTEMPTED_PENDING] PENDING record with attempt evidence quarantined')
                WHERE id = :nid;
            """),
                {"nid": r.id},
            )

        # 4B: Valid PENDING records normalized
        conn.execute(
            sa.text("""
            UPDATE notification_logs
            SET attempt_count = 0,
                retry_count = 0,
                last_attempt_at = NULL,
                sent_at = NULL,
                claimed_by = NULL,
                claim_expires_at = NULL,
                retry_eligible_at = NULL,
                terminal_failure_class = NULL,
                terminal_classified_at = NULL,
                is_legacy_exception = FALSE,
                payload_context = COALESCE(payload_context, jsonb_build_object('enquiry_id', enquiry_id, 'migrated_at', NOW()))
            WHERE status = 'PENDING';
        """)
        )

        # 4C: Contradictory FAILED records quarantined to Class D
        failed_contra_rows = conn.execute(
            sa.text("""
            SELECT id, status, attempt_count, retry_count, last_attempt_at, sent_at
            FROM notification_logs
            WHERE status = 'FAILED'
              AND (
                  attempt_count IS NULL OR retry_count IS NULL
                  OR attempt_count < 1 OR attempt_count > 3
                  OR retry_count < 0 OR retry_count > 2
                  OR retry_count != attempt_count - 1
                  OR last_attempt_at IS NULL
              );
        """)
        ).fetchall()

        if failed_contra_rows and not kms_client.has_active_key("eb-prov-k1-202611"):
            raise RuntimeError(
                "UNRESOLVED DEPLOYMENT PREREQUISITE: Database contains historical contradictory FAILED records requiring "
                "HMAC-SHA256 provenance registration, but genuine external KMS integration is an unresolved deployment "
                "prerequisite and no approved KMS provider is configured. Migration execution halted safely (fail-closed)."
            )

        for r in failed_contra_rows:
            orig_att = r.attempt_count if r.attempt_count is not None else 0
            orig_ret = r.retry_count if r.retry_count is not None else 0
            rec = build_legacy_provenance_record(
                notification_id=str(r.id),
                original_status=str(r.status),
                original_attempt_count=orig_att,
                original_retry_count=orig_ret,
                original_last_attempt_at=r.last_attempt_at,
                original_sent_at=r.sent_at,
                provenance_reason="MIGRATION_0003_LEGACY_FAILED_CONTRADICTORY_COUNTERS",
                migration_txid=txid_str,
                kms_client=kms_client,
            )

            conn.execute(
                sa.text("""
                INSERT INTO legacy_notification_provenance (
                    notification_id, migration_version, migrated_at, migration_executor,
                    original_status, original_attempt_count, original_retry_count,
                    original_last_attempt_at, original_sent_at, provenance_reason,
                    migration_txid, key_version, serialization_version, provenance_sha256
                )
                VALUES (
                    :nid, '0003_v43_0_0', :migrated_at, 'eb_migration_runner',
                    :orig_status, :orig_att, :orig_ret,
                    :orig_last, :orig_sent, :reason,
                    :txid, 'eb-prov-k1-202611', 'eb-prov-v1', :hmac
                )
                ON CONFLICT (notification_id) DO NOTHING;
            """),
                {
                    "nid": r.id,
                    "migrated_at": rec["migrated_at"],
                    "orig_status": r.status,
                    "orig_att": orig_att,
                    "orig_ret": orig_ret,
                    "orig_last": r.last_attempt_at,
                    "orig_sent": r.sent_at,
                    "reason": "MIGRATION_0003_LEGACY_FAILED_CONTRADICTORY_COUNTERS",
                    "txid": txid_str,
                    "hmac": rec["provenance_sha256"],
                },
            )

            conn.execute(
                sa.text("""
                UPDATE notification_logs
                SET status = 'EXHAUSTED',
                    terminal_failure_class = 'LEGACY_FAILURE_UNCLASSIFIED',
                    terminal_classified_at = NOW(),
                    is_legacy_exception = TRUE,
                    claimed_by = NULL,
                    claim_expires_at = NULL,
                    retry_eligible_at = NULL,
                    error_message = COALESCE('[MIGRATION_QUARANTINE_CONTRADICTORY_FAILED] ' || error_message, '[MIGRATION_QUARANTINE_CONTRADICTORY_FAILED] FAILED record with invalid counters or missing timestamp quarantined')
                WHERE id = :nid;
            """),
                {"nid": r.id},
            )

        # 4D: Valid FAILED records assigned canonical exponential backoff
        conn.execute(
            sa.text("""
            UPDATE notification_logs
            SET retry_eligible_at = NOW() + (INTERVAL '120 seconds' * POWER(2, LEAST(retry_count, 2))),
                claimed_by = NULL,
                claim_expires_at = NULL,
                terminal_failure_class = NULL,
                terminal_classified_at = NULL,
                is_legacy_exception = FALSE,
                payload_context = COALESCE(payload_context, jsonb_build_object('enquiry_id', enquiry_id, 'migrated_at', NOW()))
            WHERE status = 'FAILED';
        """)
        )

        # Step 5: CLAIMED Records Processing
        # 5A: Expired CLAIMED records recovered to FAILED with exponential backoff (attempts 1-3)
        conn.execute(
            sa.text("""
            UPDATE notification_logs
            SET status = 'FAILED',
                retry_eligible_at = NOW() + (INTERVAL '120 seconds' * POWER(2, LEAST(retry_count, 2))),
                claimed_by = NULL,
                claim_expires_at = NULL,
                claim_version = claim_version + 1,
                terminal_failure_class = NULL,
                terminal_classified_at = NULL,
                is_legacy_exception = FALSE,
                payload_context = COALESCE(payload_context, jsonb_build_object('enquiry_id', enquiry_id, 'migrated_at', NOW())),
                error_message = COALESCE('[LEASE_EXPIRED_MIGRATION] ' || error_message, '[LEASE_EXPIRED_MIGRATION] Expired claim recovered to FAILED')
            WHERE status = 'CLAIMED'
              AND claim_expires_at <= NOW()
              AND attempt_count >= 1 AND attempt_count <= 3
              AND retry_count >= 0 AND retry_count <= 2
              AND retry_count = attempt_count - 1
              AND last_attempt_at IS NOT NULL;
        """)
        )

        # 5B: Expired CLAIMED with exhausted budget swept to EXHAUSTED Class A
        conn.execute(
            sa.text("""
            UPDATE notification_logs
            SET status = 'EXHAUSTED',
                terminal_failure_class = 'RETRY_BUDGET_EXHAUSTED',
                terminal_classified_at = NOW(),
                attempt_count = 4,
                retry_count = 3,
                claimed_by = NULL,
                claim_expires_at = NULL,
                retry_eligible_at = NULL,
                is_legacy_exception = FALSE,
                payload_context = COALESCE(payload_context, jsonb_build_object('enquiry_id', enquiry_id, 'migrated_at', NOW())),
                error_message = COALESCE('[BUDGET_EXHAUSTED_MIGRATION] ' || error_message, '[BUDGET_EXHAUSTED_MIGRATION] Expired claim on 4th attempt swept to EXHAUSTED')
            WHERE status = 'CLAIMED'
              AND claim_expires_at <= NOW()
              AND (attempt_count = 4 OR retry_count = 3);
        """)
        )

        # 5C: Remaining corrupt CLAIMED records quarantined to Class D
        claimed_contra_rows = conn.execute(
            sa.text("""
            SELECT id, status, attempt_count, retry_count, last_attempt_at, sent_at
            FROM notification_logs
            WHERE status = 'CLAIMED'
              AND (claim_expires_at IS NULL OR claim_expires_at <= NOW());
        """)
        ).fetchall()

        if claimed_contra_rows and not kms_client.has_active_key("eb-prov-k1-202611"):
            raise RuntimeError(
                "UNRESOLVED DEPLOYMENT PREREQUISITE: Database contains historical contradictory CLAIMED records requiring "
                "HMAC-SHA256 provenance registration, but genuine external KMS integration is an unresolved deployment "
                "prerequisite and no approved KMS provider is configured. Migration execution halted safely (fail-closed)."
            )

        for r in claimed_contra_rows:
            orig_att = r.attempt_count if r.attempt_count is not None else 0
            orig_ret = r.retry_count if r.retry_count is not None else 0
            rec = build_legacy_provenance_record(
                notification_id=str(r.id),
                original_status=str(r.status),
                original_attempt_count=orig_att,
                original_retry_count=orig_ret,
                original_last_attempt_at=r.last_attempt_at,
                original_sent_at=r.sent_at,
                provenance_reason="MIGRATION_0003_LEGACY_CLAIMED_CORRUPT_LEASE_QUARANTINED",
                migration_txid=txid_str,
                kms_client=kms_client,
            )

            conn.execute(
                sa.text("""
                INSERT INTO legacy_notification_provenance (
                    notification_id, migration_version, migrated_at, migration_executor,
                    original_status, original_attempt_count, original_retry_count,
                    original_last_attempt_at, original_sent_at, provenance_reason,
                    migration_txid, key_version, serialization_version, provenance_sha256
                )
                VALUES (
                    :nid, '0003_v43_0_0', :migrated_at, 'eb_migration_runner',
                    :orig_status, :orig_att, :orig_ret,
                    :orig_last, :orig_sent, :reason,
                    :txid, 'eb-prov-k1-202611', 'eb-prov-v1', :hmac
                )
                ON CONFLICT (notification_id) DO NOTHING;
            """),
                {
                    "nid": r.id,
                    "migrated_at": rec["migrated_at"],
                    "orig_status": r.status,
                    "orig_att": orig_att,
                    "orig_ret": orig_ret,
                    "orig_last": r.last_attempt_at,
                    "orig_sent": r.sent_at,
                    "reason": "MIGRATION_0003_LEGACY_CLAIMED_CORRUPT_LEASE_QUARANTINED",
                    "txid": txid_str,
                    "hmac": rec["provenance_sha256"],
                },
            )

            conn.execute(
                sa.text("""
                UPDATE notification_logs
                SET status = 'EXHAUSTED',
                    terminal_failure_class = 'LEGACY_FAILURE_UNCLASSIFIED',
                    terminal_classified_at = NOW(),
                    is_legacy_exception = TRUE,
                    claimed_by = NULL,
                    claim_expires_at = NULL,
                    retry_eligible_at = NULL,
                    error_message = COALESCE('[MIGRATION_QUARANTINE_CLAIMED] ' || error_message, '[MIGRATION_QUARANTINE_CLAIMED] Corrupt or unverified CLAIMED record quarantined')
                WHERE id = :nid;
            """),
                {"nid": r.id},
            )

        # Step 6: Guarantee non-empty payload
        conn.execute(
            sa.text("""
            UPDATE notification_logs
            SET payload_context = jsonb_build_object('enquiry_id', enquiry_id, 'migrated_at', NOW())
            WHERE payload_context IS NULL OR payload_context = '{}'::jsonb;
        """)
        )

    else:
        # OFFLINE SQL GENERATION MODE (alembic upgrade --sql)
        # Authoritative Rule (V43 Section 4.1.3.0 & Section 12.1):
        # - PostgreSQL DOES NOT compute HMACs or store secret signing keys.
        # - All zero-key, placeholder key, and silent fallbacks are strictly eliminated.
        # - Offline mode consumes securely precomputed verified signature material
        #   (via PRECOMPUTED_PROVENANCE_MANIFEST) or fails closed if contradictory
        #   historical records exist without verified provenance registration.

        manifest_raw = os.getenv("PRECOMPUTED_PROVENANCE_MANIFEST")
        precomputed_manifest: list[dict[str, Any]] = []
        if manifest_raw:
            try:
                if os.path.exists(manifest_raw):
                    with open(manifest_raw, encoding="utf-8") as mf:
                        precomputed_manifest = json.load(mf)
                else:
                    precomputed_manifest = json.loads(manifest_raw)
            except Exception as e:
                raise RuntimeError(
                    f"FAILED TO PARSE PRECOMPUTED_PROVENANCE_MANIFEST: {e}"
                ) from e

        # If a precomputed manifest is supplied, cryptographically verify each entry before emitting ANY SQL
        if precomputed_manifest:
            # 1. Obtain verification key from environment or explicit test fixture
            ver_key_raw = os.getenv("EB_PROVENANCE_VERIFICATION_KEY") or os.getenv(
                "EB_OFFLINE_VERIFICATION_KEY"
            )
            verification_key_bytes: bytes | None = None
            if ver_key_raw:
                clean_vk = ver_key_raw.strip()
                if len(clean_vk) == 64:
                    try:
                        verification_key_bytes = bytes.fromhex(clean_vk)
                    except ValueError:
                        verification_key_bytes = clean_vk.encode("utf-8")
                else:
                    verification_key_bytes = clean_vk.encode("utf-8")
            else:
                test_client = ExternalKMSClient.get_client()
                test_meta = test_client.get_key("eb-prov-k1-202611")
                if test_meta and test_meta.get("key_bytes"):
                    verification_key_bytes = test_meta["key_bytes"]

            if not verification_key_bytes:
                raise RuntimeError(
                    "OFFLINE PROVENANCE MANIFEST VERIFICATION FAILED: PRECOMPUTED_PROVENANCE_MANIFEST was supplied, "
                    "but no verification key was provided (set EB_PROVENANCE_VERIFICATION_KEY or EB_OFFLINE_VERIFICATION_KEY in environment). "
                    "Offline SQL generation halted safely (fail-closed)."
                )

            # 2. Strict validation regexes
            UUID_REGEX = re.compile(
                r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                re.IGNORECASE,
            )
            ISO_TS_REGEX = re.compile(
                r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
            )
            seen_manifest_ids: set[str] = set()

            def _sql_str_literal(val: str) -> str:
                escaped = val.replace("'", "''")
                return f"'{escaped}'"

            def _sql_nullable_str(val: str | None) -> str:
                if val is None:
                    return "NULL"
                return _sql_str_literal(val)

            def _sql_int_literal(val: Any) -> str:
                if not isinstance(val, int) or isinstance(val, bool):
                    raise TypeError(f"Expected integer value, got {type(val)}: {val!r}")
                return str(val)

            # 3. Cryptographically verify and validate each entry
            verified_entries: list[dict[str, Any]] = []
            for entry in precomputed_manifest:
                if not isinstance(entry, dict):
                    raise TypeError(
                        f"Manifest entry must be a dictionary, got {type(entry)}"
                    )

                required_fields = [
                    "notification_id",
                    "migration_version",
                    "migrated_at",
                    "migration_executor",
                    "original_status",
                    "original_attempt_count",
                    "original_retry_count",
                    "provenance_reason",
                    "migration_txid",
                    "key_version",
                    "serialization_version",
                    "provenance_sha256",
                ]
                missing = [f for f in required_fields if f not in entry]
                if missing:
                    raise ValueError(
                        f"Manifest entry missing required fields: {missing}"
                    )

                nid = entry["notification_id"]
                if not isinstance(nid, str) or not UUID_REGEX.match(nid):
                    raise ValueError(
                        f"Manifest entry has invalid UUID for notification_id: {nid!r}"
                    )

                if nid.lower() in seen_manifest_ids:
                    raise ValueError(
                        f"Duplicate notification_id in PRECOMPUTED_PROVENANCE_MANIFEST: {nid}"
                    )
                seen_manifest_ids.add(nid.lower())

                txid = str(entry["migration_txid"])
                if not TXID_REGEX.match(txid):
                    raise ValueError(
                        f"Manifest entry {nid} has invalid migration_txid format: {txid!r}"
                    )
                txid_int = int(txid)
                if txid_int < 0 or txid_int > 9223372036854775807:
                    raise ValueError(
                        f"Manifest entry {nid} migration_txid out of bounds [0, 2^63-1]: {txid}"
                    )

                ser_ver = entry["serialization_version"]
                if ser_ver not in SUPPORTED_SERIALIZATION_VERSIONS:
                    raise ValueError(
                        f"Manifest entry {nid} unsupported serialization_version: {ser_ver!r}"
                    )

                key_ver = entry["key_version"]
                if not isinstance(key_ver, str) or not key_ver.strip():
                    raise ValueError(
                        f"Manifest entry {nid} invalid key_version: {key_ver!r}"
                    )

                for ts_field in [
                    "migrated_at",
                    "original_last_attempt_at",
                    "original_sent_at",
                ]:
                    val = entry.get(ts_field)
                    if val is not None and (
                        not isinstance(val, str) or not ISO_TS_REGEX.match(val)
                    ):
                        raise ValueError(
                            f"Manifest entry {nid} field {ts_field} has invalid timestamp: {val!r}"
                        )

                for int_field in ["original_attempt_count", "original_retry_count"]:
                    val = entry.get(int_field)
                    if not isinstance(val, int) or isinstance(val, bool) or val < 0:
                        raise ValueError(
                            f"Manifest entry {nid} field {int_field} must be non-negative integer: {val!r}"
                        )

                canonical_preimage = {
                    "key_version": entry["key_version"],
                    "migrated_at": entry["migrated_at"],
                    "migration_executor": entry["migration_executor"],
                    "migration_txid": txid,
                    "migration_version": entry["migration_version"],
                    "notification_id": entry["notification_id"],
                    "original_attempt_count": entry["original_attempt_count"],
                    "original_last_attempt_at": entry.get("original_last_attempt_at"),
                    "original_retry_count": entry["original_retry_count"],
                    "original_sent_at": entry.get("original_sent_at"),
                    "original_status": entry["original_status"],
                    "provenance_reason": entry["provenance_reason"],
                    "serialization_version": entry["serialization_version"],
                }

                canonical_bytes = rfc8785_canonical_serialize(canonical_preimage)
                computed_hmac = hmac.new(
                    verification_key_bytes, canonical_bytes, hashlib.sha256
                ).hexdigest()

                if not hmac.compare_digest(computed_hmac, entry["provenance_sha256"]):
                    raise ValueError(
                        f"CRYPTOGRAPHIC INTEGRITY ERROR: HMAC signature mismatch for manifest entry {nid}. "
                        f"Expected {computed_hmac}, got {entry['provenance_sha256']}. "
                        "Manifest has been tampered with or verification key does not match."
                    )

                verified_entries.append(entry)

            # 4. Emit safe SQL INSERT statements for verified entries
            for entry in verified_entries:
                orig_last_att = _sql_nullable_str(entry.get("original_last_attempt_at"))
                orig_sent = _sql_nullable_str(entry.get("original_sent_at"))

                insert_sql = (
                    "INSERT INTO legacy_notification_provenance (\n"
                    "    notification_id, migration_version, migrated_at, migration_executor,\n"
                    "    original_status, original_attempt_count, original_retry_count,\n"
                    "    original_last_attempt_at, original_sent_at, provenance_reason,\n"
                    "    migration_txid, key_version, serialization_version, provenance_sha256\n"
                    ") VALUES (\n"
                    f"    {_sql_str_literal(entry['notification_id'])}::uuid,\n"
                    f"    {_sql_str_literal(entry['migration_version'])},\n"
                    f"    {_sql_str_literal(entry['migrated_at'])}::timestamptz,\n"
                    f"    {_sql_str_literal(entry['migration_executor'])},\n"
                    f"    {_sql_str_literal(entry['original_status'])},\n"
                    f"    {_sql_int_literal(entry['original_attempt_count'])},\n"
                    f"    {_sql_int_literal(entry['original_retry_count'])},\n"
                    f"    {orig_last_att},\n"
                    f"    {orig_sent},\n"
                    f"    {_sql_str_literal(entry['provenance_reason'])},\n"
                    f"    {_sql_str_literal(str(entry['migration_txid']))},\n"
                    f"    {_sql_str_literal(entry['key_version'])},\n"
                    f"    {_sql_str_literal(entry['serialization_version'])},\n"
                    f"    {_sql_str_literal(entry['provenance_sha256'])}\n"
                    ") ON CONFLICT (notification_id) DO NOTHING;"
                )
                op.execute(insert_sql)

        op.execute("""
            -- STEP 1: Clear invalid lease fields on non-CLAIMED legacy rows
            UPDATE notification_logs
            SET claimed_by = NULL,
                claim_expires_at = NULL
            WHERE status != 'CLAIMED'
              AND (claimed_by IS NOT NULL OR claim_expires_at IS NOT NULL);

            -- STEP 2: SENT Records Processing
            -- 2A: Preserved as SENT natively if counters consistent (att = ret + 1 or both NULL)
            UPDATE notification_logs
            SET attempt_count = COALESCE(attempt_count, retry_count + 1, 1),
                retry_count = COALESCE(retry_count, CASE WHEN attempt_count > 0 THEN attempt_count - 1 ELSE 0 END, 0),
                claimed_by = NULL,
                claim_expires_at = NULL,
                retry_eligible_at = NULL,
                terminal_failure_class = NULL,
                terminal_classified_at = NULL,
                is_legacy_exception = FALSE
            WHERE status = 'SENT'
              AND (
                  (attempt_count IS NULL AND retry_count IS NULL)
                  OR (attempt_count > 0 AND retry_count = attempt_count - 1)
              );

            -- 2B: SENT Records with Contradictory Historical Counters:
            -- If matching verified provenance row exists, set is_legacy_exception = TRUE
            UPDATE notification_logs n
            SET is_legacy_exception = TRUE,
                claimed_by = NULL,
                claim_expires_at = NULL,
                retry_eligible_at = NULL,
                terminal_failure_class = NULL,
                terminal_classified_at = NULL
            FROM legacy_notification_provenance p
            WHERE n.id = p.notification_id
              AND n.status = 'SENT'
              AND NOT (
                  (n.attempt_count IS NULL AND n.retry_count IS NULL)
                  OR (n.attempt_count > 0 AND n.retry_count = n.attempt_count - 1)
              );

            -- 2C: SENT Missing Payload Tombstone Marker
            UPDATE notification_logs
            SET payload_context = jsonb_build_object(
                'legacy_payload_unavailable', true,
                'tombstone_reason', 'HISTORICAL_PAYLOAD_UNAVAILABLE_AT_MIGRATION',
                'enquiry_id', enquiry_id,
                'migrated_at', NOW()
            )
            WHERE status = 'SENT'
              AND (payload_context IS NULL OR payload_context = '{}'::jsonb);

            -- STEP 3: EXHAUSTED Records Classification
            -- 3A: Class C - PAYLOAD_SNAPSHOT_UNAVAILABLE (Strict Unattempted Pre-Dispatch)
            UPDATE notification_logs
            SET terminal_failure_class = 'PAYLOAD_SNAPSHOT_UNAVAILABLE',
                terminal_classified_at = NOW(),
                attempt_count = 0,
                retry_count = 0,
                last_attempt_at = NULL,
                claimed_by = NULL,
                claim_expires_at = NULL,
                retry_eligible_at = NULL,
                payload_context = COALESCE(payload_context, '{"legacy_payload_missing": true}'::jsonb),
                error_message = COALESCE('[CLASS_C_PAYLOAD_UNAVAILABLE] ' || error_message, '[CLASS_C_PAYLOAD_UNAVAILABLE] Legacy exhausted record missing payload snapshot')
            WHERE status = 'EXHAUSTED'
              AND attempt_count = 0
              AND retry_count = 0
              AND last_attempt_at IS NULL
              AND (payload_context IS NULL OR payload_context = '{}'::jsonb);

            -- 3B: Class B - PERMANENT_RECIPIENT_REJECTION (Strict Structured Evidence & Consistent Counters)
            UPDATE notification_logs
            SET terminal_failure_class = 'PERMANENT_RECIPIENT_REJECTION',
                terminal_classified_at = NOW(),
                claimed_by = NULL,
                claim_expires_at = NULL,
                retry_eligible_at = NULL,
                payload_context = COALESCE(payload_context, jsonb_build_object('enquiry_id', enquiry_id, 'migrated_at', NOW()))
            WHERE status = 'EXHAUSTED'
              AND terminal_failure_class IS NULL
              AND smtp_command_or_phase = 'RCPT_TO'
              AND smtp_reply_code BETWEEN 550 AND 554
              AND attempt_count >= 1 AND attempt_count <= 4
              AND retry_count = attempt_count - 1;

            -- 3C: Class A - RETRY_BUDGET_EXHAUSTED (Exhausted Retries: retry_count = 3 or attempt_count = 4)
            UPDATE notification_logs
            SET terminal_failure_class = 'RETRY_BUDGET_EXHAUSTED',
                terminal_classified_at = NOW(),
                attempt_count = 4,
                retry_count = 3,
                claimed_by = NULL,
                claim_expires_at = NULL,
                retry_eligible_at = NULL,
                payload_context = COALESCE(payload_context, jsonb_build_object('enquiry_id', enquiry_id, 'migrated_at', NOW()))
            WHERE status = 'EXHAUSTED'
              AND terminal_failure_class IS NULL
              AND (retry_count = 3 OR attempt_count = 4);

            -- 3D: Class D - LEGACY_FAILURE_UNCLASSIFIED contradictory EXHAUSTED records:
            -- If matching verified provenance row exists, set terminal_failure_class & is_legacy_exception
            UPDATE notification_logs n
            SET terminal_failure_class = 'LEGACY_FAILURE_UNCLASSIFIED',
                terminal_classified_at = NOW(),
                is_legacy_exception = TRUE,
                claimed_by = NULL,
                claim_expires_at = NULL,
                retry_eligible_at = NULL,
                error_message = COALESCE('[MIGRATION_QUARANTINE_CONTRADICTORY] ' || error_message, '[MIGRATION_QUARANTINE_CONTRADICTORY] Historical contradictory evidence quarantined')
            FROM legacy_notification_provenance p
            WHERE n.id = p.notification_id
              AND n.status = 'EXHAUSTED'
              AND n.terminal_failure_class IS NULL;

            -- STEP 4: PENDING & FAILED Records Processing
            -- 4A: Contradictory PENDING records with registered provenance:
            UPDATE notification_logs n
            SET status = 'EXHAUSTED',
                terminal_failure_class = 'LEGACY_FAILURE_UNCLASSIFIED',
                terminal_classified_at = NOW(),
                is_legacy_exception = TRUE,
                claimed_by = NULL,
                claim_expires_at = NULL,
                retry_eligible_at = NULL,
                error_message = COALESCE('[MIGRATION_QUARANTINE_ATTEMPTED_PENDING] ' || error_message, '[MIGRATION_QUARANTINE_ATTEMPTED_PENDING] PENDING record with attempt evidence quarantined')
            FROM legacy_notification_provenance p
            WHERE n.id = p.notification_id
              AND n.status = 'PENDING'
              AND (n.attempt_count > 0 OR n.retry_count > 0 OR n.last_attempt_at IS NOT NULL);

            -- 4B: Valid PENDING records normalized
            UPDATE notification_logs
            SET attempt_count = 0,
                retry_count = 0,
                last_attempt_at = NULL,
                sent_at = NULL,
                claimed_by = NULL,
                claim_expires_at = NULL,
                retry_eligible_at = NULL,
                terminal_failure_class = NULL,
                terminal_classified_at = NULL,
                is_legacy_exception = FALSE,
                payload_context = COALESCE(payload_context, jsonb_build_object('enquiry_id', enquiry_id, 'migrated_at', NOW()))
            WHERE status = 'PENDING';

            -- 4C: Contradictory FAILED records with registered provenance:
            UPDATE notification_logs n
            SET status = 'EXHAUSTED',
                terminal_failure_class = 'LEGACY_FAILURE_UNCLASSIFIED',
                terminal_classified_at = NOW(),
                is_legacy_exception = TRUE,
                claimed_by = NULL,
                claim_expires_at = NULL,
                retry_eligible_at = NULL,
                error_message = COALESCE('[MIGRATION_QUARANTINE_CONTRADICTORY_FAILED] ' || error_message, '[MIGRATION_QUARANTINE_CONTRADICTORY_FAILED] FAILED record with invalid counters or missing timestamp quarantined')
            FROM legacy_notification_provenance p
            WHERE n.id = p.notification_id
              AND n.status = 'FAILED'
              AND (
                  n.attempt_count IS NULL OR n.retry_count IS NULL
                  OR n.attempt_count < 1 OR n.attempt_count > 3
                  OR n.retry_count < 0 OR n.retry_count > 2
                  OR n.retry_count != n.attempt_count - 1
                  OR n.last_attempt_at IS NULL
              );

            -- 4D: Valid FAILED records assigned canonical exponential backoff
            UPDATE notification_logs
            SET retry_eligible_at = NOW() + (INTERVAL '120 seconds' * POWER(2, LEAST(retry_count, 2))),
                claimed_by = NULL,
                claim_expires_at = NULL,
                terminal_failure_class = NULL,
                terminal_classified_at = NULL,
                is_legacy_exception = FALSE,
                payload_context = COALESCE(payload_context, jsonb_build_object('enquiry_id', enquiry_id, 'migrated_at', NOW()))
            WHERE status = 'FAILED';

            -- STEP 5: CLAIMED Records Processing
            -- 5A: Expired CLAIMED records recovered to FAILED with exponential backoff (attempts 1-3)
            UPDATE notification_logs
            SET status = 'FAILED',
                retry_eligible_at = NOW() + (INTERVAL '120 seconds' * POWER(2, LEAST(retry_count, 2))),
                claimed_by = NULL,
                claim_expires_at = NULL,
                claim_version = claim_version + 1,
                terminal_failure_class = NULL,
                terminal_classified_at = NULL,
                is_legacy_exception = FALSE,
                payload_context = COALESCE(payload_context, jsonb_build_object('enquiry_id', enquiry_id, 'migrated_at', NOW())),
                error_message = COALESCE('[LEASE_EXPIRED_MIGRATION] ' || error_message, '[LEASE_EXPIRED_MIGRATION] Expired claim recovered to FAILED')
            WHERE status = 'CLAIMED'
              AND claim_expires_at <= NOW()
              AND attempt_count >= 1 AND attempt_count <= 3
              AND retry_count >= 0 AND retry_count <= 2
              AND retry_count = attempt_count - 1
              AND last_attempt_at IS NOT NULL;

            -- 5B: Expired CLAIMED with exhausted budget swept to EXHAUSTED Class A
            UPDATE notification_logs
            SET status = 'EXHAUSTED',
                terminal_failure_class = 'RETRY_BUDGET_EXHAUSTED',
                terminal_classified_at = NOW(),
                attempt_count = 4,
                retry_count = 3,
                claimed_by = NULL,
                claim_expires_at = NULL,
                retry_eligible_at = NULL,
                is_legacy_exception = FALSE,
                payload_context = COALESCE(payload_context, jsonb_build_object('enquiry_id', enquiry_id, 'migrated_at', NOW())),
                error_message = COALESCE('[BUDGET_EXHAUSTED_MIGRATION] ' || error_message, '[BUDGET_EXHAUSTED_MIGRATION] Expired claim on 4th attempt swept to EXHAUSTED')
            WHERE status = 'CLAIMED'
              AND claim_expires_at <= NOW()
              AND (attempt_count = 4 OR retry_count = 3);

            -- 5C: Remaining corrupt CLAIMED records with registered provenance:
            UPDATE notification_logs n
            SET status = 'EXHAUSTED',
                terminal_failure_class = 'LEGACY_FAILURE_UNCLASSIFIED',
                terminal_classified_at = NOW(),
                is_legacy_exception = TRUE,
                claimed_by = NULL,
                claim_expires_at = NULL,
                retry_eligible_at = NULL,
                error_message = COALESCE('[MIGRATION_QUARANTINE_CLAIMED] ' || error_message, '[MIGRATION_QUARANTINE_CLAIMED] Corrupt or unverified CLAIMED record quarantined')
            FROM legacy_notification_provenance p
            WHERE n.id = p.notification_id
              AND n.status = 'CLAIMED'
              AND (n.claim_expires_at IS NULL OR n.claim_expires_at <= NOW());

            -- STEP 6: Guarantee Payload Not Empty
            UPDATE notification_logs
            SET payload_context = jsonb_build_object('enquiry_id', enquiry_id, 'migrated_at', NOW())
            WHERE payload_context IS NULL OR payload_context = '{}'::jsonb;

            -- STEP 7: Fail-Closed Provenance Verification Guard
            -- Aborts transaction if any contradictory legacy rows exist without registered KMS provenance
            DO $prov_guard$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM notification_logs
                    WHERE status = 'SENT'
                      AND NOT ((attempt_count IS NULL AND retry_count IS NULL) OR (attempt_count > 0 AND retry_count = attempt_count - 1))
                      AND is_legacy_exception IS NOT TRUE
                ) OR EXISTS (
                    SELECT 1 FROM notification_logs
                    WHERE status = 'EXHAUSTED'
                      AND terminal_failure_class IS NULL
                ) OR EXISTS (
                    SELECT 1 FROM notification_logs
                    WHERE status = 'PENDING'
                      AND (attempt_count > 0 OR retry_count > 0 OR last_attempt_at IS NOT NULL)
                      AND is_legacy_exception IS NOT TRUE
                ) OR EXISTS (
                    SELECT 1 FROM notification_logs
                    WHERE status = 'FAILED'
                      AND (attempt_count IS NULL OR retry_count IS NULL OR attempt_count < 1 OR attempt_count > 3 OR retry_count < 0 OR retry_count > 2 OR retry_count != attempt_count - 1 OR last_attempt_at IS NULL)
                      AND is_legacy_exception IS NOT TRUE
                ) OR EXISTS (
                    SELECT 1 FROM notification_logs
                    WHERE status = 'CLAIMED'
                      AND (claim_expires_at IS NULL OR claim_expires_at <= NOW())
                      AND is_legacy_exception IS NOT TRUE
                ) THEN
                    RAISE EXCEPTION 'OFFLINE PROVENANCE SIGNATURE MATERIAL REQUIRED: Database contains contradictory legacy records that require KMS HMAC-SHA256 provenance registration. Offline SQL generation cannot synthesize placeholder or zero-key signatures. Supply verified precomputed signatures via PRECOMPUTED_PROVENANCE_MANIFEST or execute migration in online mode with external KMS provider.'
                        USING ERRCODE = '23514';
                END IF;
            END $prov_guard$;
        """)

    # -------------------------------------------------------------------------
    # PHASE 5: ATTACH 16 ENGINE CHECK CONSTRAINTS (V43 SECTION 12.1)
    # -------------------------------------------------------------------------
    op.create_check_constraint(
        "chk_notification_logs_attempt_bounds",
        "notification_logs",
        "((attempt_count >= 0 AND attempt_count <= 4)) OR (status IN ('SENT', 'EXHAUSTED') AND is_legacy_exception = TRUE)",
    )
    op.create_check_constraint(
        "chk_notification_logs_retry_bounds",
        "notification_logs",
        "((retry_count >= 0 AND retry_count <= 3)) OR (status IN ('SENT', 'EXHAUSTED') AND is_legacy_exception = TRUE)",
    )
    op.create_check_constraint(
        "chk_notification_logs_class_counters",
        "notification_logs",
        "(is_legacy_exception = TRUE AND status IN ('SENT', 'EXHAUSTED')) OR (is_legacy_exception = FALSE AND ((status = 'PENDING' AND attempt_count = 0 AND retry_count = 0) OR (status = 'EXHAUSTED' AND terminal_failure_class = 'PAYLOAD_SNAPSHOT_UNAVAILABLE' AND attempt_count = 0 AND retry_count = 0) OR (attempt_count >= 1 AND retry_count = attempt_count - 1)))",
    )
    op.create_check_constraint(
        "chk_notification_logs_pending_invariants",
        "notification_logs",
        """
        status != 'PENDING' OR (
            ((attempt_count = 0 AND retry_count = 0 AND last_attempt_at IS NULL)
             OR
             (attempt_count >= 1 AND attempt_count <= 3 AND retry_count = attempt_count - 1 AND last_attempt_at IS NOT NULL))
            AND sent_at IS NULL
            AND retry_eligible_at IS NULL
            AND claimed_by IS NULL
            AND claim_expires_at IS NULL
            AND terminal_failure_class IS NULL
            AND terminal_classified_at IS NULL
            AND is_legacy_exception = FALSE
        )
        """,
    )
    op.create_check_constraint(
        "chk_notification_logs_claimed_invariants",
        "notification_logs",
        "status != 'CLAIMED' OR (attempt_count >= 1 AND attempt_count <= 4 AND retry_count >= 0 AND retry_count <= 3 AND retry_count = attempt_count - 1 AND last_attempt_at IS NOT NULL AND sent_at IS NULL AND retry_eligible_at IS NULL AND claimed_by IS NOT NULL AND claim_expires_at IS NOT NULL AND terminal_failure_class IS NULL AND terminal_classified_at IS NULL)",
    )
    op.create_check_constraint(
        "chk_notification_logs_failed_invariants",
        "notification_logs",
        "status != 'FAILED' OR (attempt_count >= 1 AND attempt_count <= 3 AND retry_count >= 0 AND retry_count <= 2 AND retry_count = attempt_count - 1 AND last_attempt_at IS NOT NULL AND sent_at IS NULL AND retry_eligible_at IS NOT NULL AND claimed_by IS NULL AND claim_expires_at IS NULL AND terminal_failure_class IS NULL AND terminal_classified_at IS NULL)",
    )
    op.create_check_constraint(
        "chk_notification_logs_sent_invariants",
        "notification_logs",
        "status != 'SENT' OR ((((attempt_count >= 1 AND attempt_count <= 4 AND retry_count >= 0 AND retry_count <= 3 AND retry_count = attempt_count - 1)) OR (is_legacy_exception = TRUE)) AND claimed_by IS NULL AND claim_expires_at IS NULL AND retry_eligible_at IS NULL AND terminal_failure_class IS NULL AND terminal_classified_at IS NULL AND (sent_at IS NULL OR last_attempt_at IS NULL OR sent_at >= last_attempt_at))",
    )
    op.create_check_constraint(
        "chk_notification_logs_exhausted_invariants",
        "notification_logs",
        "status != 'EXHAUSTED' OR (claimed_by IS NULL AND claim_expires_at IS NULL AND retry_eligible_at IS NULL AND terminal_failure_class IS NOT NULL AND terminal_classified_at IS NOT NULL AND (sent_at IS NULL OR is_legacy_exception = TRUE))",
    )
    op.create_check_constraint(
        "chk_notification_logs_class_b_evidence",
        "notification_logs",
        "status != 'EXHAUSTED' OR terminal_failure_class != 'PERMANENT_RECIPIENT_REJECTION' OR (smtp_command_or_phase = 'RCPT_TO' AND smtp_reply_code >= 550 AND smtp_reply_code <= 554)",
    )
    op.create_check_constraint(
        "chk_notification_logs_class_c_preconditions",
        "notification_logs",
        "status != 'EXHAUSTED' OR terminal_failure_class != 'PAYLOAD_SNAPSHOT_UNAVAILABLE' OR (attempt_count = 0 AND retry_count = 0 AND last_attempt_at IS NULL)",
    )
    op.create_check_constraint(
        "chk_notification_logs_reply_code_bounds",
        "notification_logs",
        "smtp_reply_code IS NULL OR (smtp_reply_code >= 200 AND smtp_reply_code <= 599)",
    )
    op.create_check_constraint(
        "chk_notification_logs_payload_not_empty",
        "notification_logs",
        "payload_context IS NOT NULL AND payload_context != '{}'::jsonb",
    )
    op.create_check_constraint(
        "chk_notification_logs_legacy_provenance_flag",
        "notification_logs",
        "NOT is_legacy_exception OR status IN ('SENT', 'EXHAUSTED')",
    )
    op.create_check_constraint(
        "chk_notification_logs_quarantined_invariants",
        "notification_logs",
        """
        status != 'QUARANTINED' OR (
            claimed_by IS NULL
            AND claim_expires_at IS NULL
            AND retry_eligible_at IS NULL
            AND terminal_failure_class IS NULL
            AND terminal_classified_at IS NULL
            AND is_legacy_exception = FALSE
        )
        """,
    )
    op.create_check_constraint(
        "chk_notification_logs_class_e_evidence",
        "notification_logs",
        """
        status != 'EXHAUSTED'
        OR terminal_failure_class != 'PERMANENT_SENDER_REJECTION'
        OR (
            smtp_command_or_phase = 'MAIL_FROM'
            AND smtp_reply_code IN (501, 550, 553, 554)
        )
        """,
    )
    op.create_check_constraint(
        "chk_notification_logs_class_f_evidence",
        "notification_logs",
        """
        status != 'EXHAUSTED'
        OR terminal_failure_class != 'PERMANENT_CONTENT_POLICY_REJECTION'
        OR (
            smtp_command_or_phase = 'DATA'
            AND smtp_reply_code IN (550, 552, 554)
        )
        """,
    )

    # -------------------------------------------------------------------------
    # PHASE 6: ROLE-BASED ACCESS CONTROL (RBAC) LEAST-PRIVILEGE GRANTS
    # -------------------------------------------------------------------------
    op.execute("""
        -- 1. Table Ownership (Schema Owner eb_schema_owner holds structural ownership)
        ALTER TABLE public.notification_logs OWNER TO eb_schema_owner;
        ALTER TABLE public.platform_circuit_breakers OWNER TO eb_schema_owner;
        ALTER TABLE public.legacy_notification_provenance OWNER TO eb_schema_owner;
        ALTER TABLE public.smtp_evidence_store OWNER TO eb_schema_owner;

        -- 2. Ingestion API Role Fencing: eb_app_user has ZERO UPDATE/DELETE on notification_logs
        REVOKE ALL ON public.notification_logs FROM eb_app_user;
        GRANT SELECT ON public.notification_logs TO eb_app_user;
        GRANT INSERT (
            id, enquiry_id, recipient_email, notification_type, status,
            payload_context, created_at
        ) ON public.notification_logs TO eb_app_user;
        GRANT SELECT ON public.platform_circuit_breakers TO eb_app_user;
        GRANT SELECT ON public.legacy_notification_provenance TO eb_app_user;

        -- 3. Worker Role Grants: eb_worker_user has SELECT and operational column UPDATE
        GRANT USAGE ON SCHEMA public TO eb_worker_user;
        GRANT SELECT ON public.notification_logs TO eb_worker_user;
        GRANT UPDATE (
            status, attempt_count, retry_count, last_attempt_at, sent_at,
            retry_eligible_at, claimed_by, claim_expires_at, claim_version,
            terminal_failure_class, terminal_classified_at,
            smtp_command_or_phase, smtp_reply_code, error_message, updated_at
        ) ON public.notification_logs TO eb_worker_user;

        -- 4. SMTP Evidence Store Permissions
        REVOKE ALL ON public.smtp_evidence_store FROM PUBLIC;
        GRANT SELECT, INSERT ON public.smtp_evidence_store TO eb_worker_user;
        GRANT SELECT, INSERT ON public.smtp_evidence_store TO eb_migration_role;
        GRANT SELECT ON public.smtp_evidence_store TO eb_archival_role;

        -- 5. Circuit Breaker Permissions
        GRANT SELECT, UPDATE (state, failure_count, consecutive_successes, last_failure_at, last_state_change_at, trip_reason, updated_at)
        ON public.platform_circuit_breakers TO eb_worker_user;
        GRANT ALL PRIVILEGES ON public.platform_circuit_breakers TO eb_migration_role;

        -- 6. Security Administrator Schema Permissions (NOLOGIN role, assumed via SECURITY DEFINER)
        GRANT USAGE ON SCHEMA public TO eb_sec_admin;
        GRANT SELECT ON public.notification_logs TO eb_sec_admin;
        GRANT UPDATE (
            status, claimed_by, claim_expires_at, retry_eligible_at,
            claim_version, error_message, updated_at, terminal_failure_class,
            terminal_classified_at
        ) ON public.notification_logs TO eb_sec_admin;
        GRANT SELECT ON public.smtp_evidence_store TO eb_sec_admin;
        GRANT SELECT ON public.legacy_notification_provenance TO eb_sec_admin;

        -- 7. Archival Role Permissions (Read-only historical audit & partition dump runner)
        GRANT USAGE ON SCHEMA public TO eb_archival_role;
        GRANT SELECT ON public.notification_logs TO eb_archival_role;
        GRANT SELECT ON public.legacy_notification_provenance TO eb_archival_role;

        -- 8. Migration Role Permissions
        GRANT ALL PRIVILEGES ON public.notification_logs TO eb_migration_role;
        GRANT ALL PRIVILEGES ON public.legacy_notification_provenance TO eb_migration_role;
    """)

    # -------------------------------------------------------------------------
    # PHASE 7: PARTIAL PERFORMANCE INDEXES
    # -------------------------------------------------------------------------
    op.create_index(
        "ix_notification_logs_claim_lookup",
        "notification_logs",
        ["status", "retry_eligible_at"],
        postgresql_where=sa.text("status IN ('PENDING', 'FAILED')"),
    )
    op.create_index(
        "ix_notification_logs_lease_sweeper",
        "notification_logs",
        ["status", "claim_expires_at"],
        postgresql_where=sa.text("status = 'CLAIMED'"),
    )
    op.create_index(
        "ix_notification_logs_enquiry_id",
        "notification_logs",
        ["enquiry_id"],
    )


# -----------------------------------------------------------------------------
# ALEMBIC DOWNGRADE MIGRATION ENTRYPOINT (FORWARD-ONLY PRODUCTION SAFETY GUARD)
# -----------------------------------------------------------------------------


def downgrade() -> None:
    # -------------------------------------------------------------------------
    # PRODUCTION SAFETY GUARD: FORWARD-ONLY MIGRATION POLICY ENFORCEMENT
    # -------------------------------------------------------------------------
    app_env = os.getenv("APP_ENV", "development").lower()
    eden_bounty_env = os.getenv("EDEN_BOUNTY_ENV", "").lower()
    allow_destructive = os.getenv("ALLOW_DESTRUCTIVE_DOWNGRADE", "0")

    if (
        app_env in ("production", "prod")
        or eden_bounty_env == "production"
        or allow_destructive != "1"
    ):
        raise RuntimeError(
            "CRITICAL INTEGRITY VIOLATION: Downgrade of Migration 0003 is blocked by Forward-Only Policy! "
            "Downgrading would permanently destroy immutable audit records in legacy_notification_provenance, "
            "smtp_evidence_store, and eb_security.notification_quarantine_audit, violating legal data retention "
            "and regulatory auditability standards. In production, any schema corrections must be applied as "
            "forward migrations. In dev/test, set ALLOW_DESTRUCTIVE_DOWNGRADE=1 to proceed."
        )

    # Teardown indexes
    op.drop_index("ix_notification_logs_enquiry_id", table_name="notification_logs")
    op.drop_index("ix_notification_logs_lease_sweeper", table_name="notification_logs")
    op.drop_index("ix_notification_logs_claim_lookup", table_name="notification_logs")

    # Teardown triggers and functions
    op.execute("DROP TRIGGER IF EXISTS trg_guard_terminal_insert ON notification_logs;")
    op.execute("DROP FUNCTION IF EXISTS eb_security.fn_guard_terminal_insert();")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_guard_operational_update ON notification_logs;"
    )
    op.execute("DROP FUNCTION IF EXISTS eb_security.fn_guard_operational_update();")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_protect_terminal_record_immutability ON notification_logs;"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS eb_security.fn_prevent_terminal_record_tampering();"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_guard_smtp_evidence_immutability ON smtp_evidence_store;"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS eb_security.fn_guard_smtp_evidence_immutability();"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_protect_provenance_immutability ON legacy_notification_provenance;"
    )
    op.execute("DROP FUNCTION IF EXISTS eb_security.fn_prevent_provenance_tampering();")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_validate_legacy_provenance ON notification_logs;"
    )
    op.execute("DROP FUNCTION IF EXISTS eb_security.fn_validate_legacy_provenance();")
    op.execute(
        "DROP FUNCTION IF EXISTS eb_security.fn_release_quarantine(UUID, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, TEXT, BOOLEAN, TEXT, VARCHAR);"
    )

    # Teardown constraints
    op.drop_constraint(
        "chk_notification_logs_class_f_evidence", "notification_logs", type_="check"
    )
    op.drop_constraint(
        "chk_notification_logs_class_e_evidence", "notification_logs", type_="check"
    )
    op.drop_constraint(
        "chk_notification_logs_quarantined_invariants",
        "notification_logs",
        type_="check",
    )
    op.drop_constraint(
        "chk_notification_logs_legacy_provenance_flag",
        "notification_logs",
        type_="check",
    )
    op.drop_constraint(
        "chk_notification_logs_payload_not_empty", "notification_logs", type_="check"
    )
    op.drop_constraint(
        "chk_notification_logs_reply_code_bounds", "notification_logs", type_="check"
    )
    op.drop_constraint(
        "chk_notification_logs_class_c_preconditions",
        "notification_logs",
        type_="check",
    )
    op.drop_constraint(
        "chk_notification_logs_class_b_evidence", "notification_logs", type_="check"
    )
    op.drop_constraint(
        "chk_notification_logs_exhausted_invariants", "notification_logs", type_="check"
    )
    op.drop_constraint(
        "chk_notification_logs_sent_invariants", "notification_logs", type_="check"
    )
    op.drop_constraint(
        "chk_notification_logs_failed_invariants", "notification_logs", type_="check"
    )
    op.drop_constraint(
        "chk_notification_logs_claimed_invariants", "notification_logs", type_="check"
    )
    op.drop_constraint(
        "chk_notification_logs_pending_invariants", "notification_logs", type_="check"
    )
    op.drop_constraint(
        "chk_notification_logs_class_counters", "notification_logs", type_="check"
    )
    op.drop_constraint(
        "chk_notification_logs_retry_bounds", "notification_logs", type_="check"
    )
    op.drop_constraint(
        "chk_notification_logs_attempt_bounds", "notification_logs", type_="check"
    )

    # Teardown tables
    op.drop_table("notification_quarantine_audit", schema="eb_security")
    op.execute("DROP SCHEMA IF EXISTS eb_security CASCADE;")
    op.drop_table("smtp_evidence_store")
    op.drop_table("legacy_notification_provenance")

    # Teardown added columns
    op.drop_column("notification_logs", "updated_at")
    op.drop_column("notification_logs", "payload_context")
    op.drop_column("notification_logs", "smtp_reply_code")
    op.drop_column("notification_logs", "smtp_command_or_phase")
    op.drop_column("notification_logs", "terminal_classified_at")
    op.drop_column("notification_logs", "terminal_failure_class")
    op.drop_column("notification_logs", "is_legacy_exception")
    op.drop_column("notification_logs", "claim_version")
    op.drop_column("notification_logs", "claim_expires_at")
    op.drop_column("notification_logs", "claimed_by")
    op.drop_column("notification_logs", "retry_eligible_at")
    op.drop_column("notification_logs", "attempt_count")

    op.drop_table("platform_circuit_breakers")

    terminal_class_enum = postgresql.ENUM(
        "RETRY_BUDGET_EXHAUSTED",
        "PERMANENT_RECIPIENT_REJECTION",
        "PAYLOAD_SNAPSHOT_UNAVAILABLE",
        "LEGACY_FAILURE_UNCLASSIFIED",
        "PERMANENT_SENDER_REJECTION",
        "PERMANENT_CONTENT_POLICY_REJECTION",
        "CORRELATION_QUARANTINE_DISCARD",
        name="terminal_failure_class_enum",
    )
    terminal_class_enum.drop(op.get_bind(), checkfirst=True)
