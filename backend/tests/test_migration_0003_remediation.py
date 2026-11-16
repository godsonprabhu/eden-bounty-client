"""Focused Test Suite for C13.5 Step 5.1.3 Migration 0003 Remediation.

Authoritative Baseline: C13.5 Version 43.0.0 (APPROVED FOR ARCHITECTURE FREEZE).
Validates all 4 remediated defect areas in Migration 0003:
1. Defect 1: External KMS / Vault integration boundary & fail-closed unresolved prerequisite.
2. Defect 2: RFC 8785 JSON Canonicalization Scheme (JCS) compliance & Appendix B vectors.
3. Defect 3: Offline provenance manifest cryptographic verification & safe SQL emission.
4. Defect 4: Seven-role PostgreSQL RBAC matrix and least-privilege table grants.

Execution Boundary:
- Pure static / offline validation only (ZERO database connections, ZERO DDL execution).
"""

import hashlib
import hmac
import importlib.util
import json
import os
import struct
import subprocess
from datetime import UTC, datetime
from typing import Any

import pytest

# Load Migration 0003 module statically without database execution
# 0003 lives outside the active graph (alembic/deferred/); offline SQL is generated with the
# tooling-only config that also loads that directory.
DEFERRED_ALEMBIC_INI = "alembic/deferred/alembic.deferred.ini"
MIGRATION_PATH = os.path.abspath(
    "backend/alembic/deferred/0003_v43_0_0_notification_claiming_and_payload.py"
)
spec = importlib.util.spec_from_file_location("mig0003", MIGRATION_PATH)
mig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mig)

TEST_VERIFICATION_KEY = b"test-secret-key-32-bytes-long!!!"


# =============================================================================
# DEFECT 1: KMS INTEGRATION & UNRESOLVED PREREQUISITE FAIL-CLOSED TESTS
# =============================================================================


class TestDefect1KMSIntegration:
    """Validate external KMS client boundaries and fail-closed security guarantees."""

    def test_kms_sdk_absence_in_requirements(self) -> None:
        """Confirm that no approved KMS SDK is installed, documenting the prerequisite."""
        req_path = os.path.abspath("backend/requirements.txt")
        with open(req_path, encoding="utf-8") as f:
            reqs = f.read().lower()
        assert "boto3" not in reqs
        assert "hvac" not in reqs
        assert "google-cloud-kms" not in reqs
        assert "azure-keyvault" not in reqs

    def test_default_client_fails_closed_without_kms(self) -> None:
        """Default ExternalKMSClient has no KMS configured and fails closed."""
        mig.ExternalKMSClient.reset_instance()
        client = mig.ExternalKMSClient.get_client()
        assert not client.is_configured()
        assert not client.has_active_key("eb-prov-k1-202611")

        with pytest.raises(RuntimeError) as exc_info:
            client.generate_hmac("eb-prov-k1-202611", b"canonical_payload")
        assert "UNRESOLVED DEPLOYMENT PREREQUISITE" in str(exc_info.value)
        assert "backend/requirements.txt" in str(exc_info.value)

    def test_test_harness_client_isolation(self) -> None:
        """Explicit test client allows isolated verification without mocking production."""
        test_client = mig.ExternalKMSClient.create_test_client(
            {"eb-prov-k1-202611": TEST_VERIFICATION_KEY}
        )
        assert test_client.is_configured()
        assert test_client.has_active_key("eb-prov-k1-202611")

        digest = test_client.generate_hmac("eb-prov-k1-202611", b"test_payload")
        expected = hmac.new(
            TEST_VERIFICATION_KEY, b"test_payload", hashlib.sha256
        ).hexdigest()
        assert digest == expected

    def test_test_client_missing_key_version_fails_closed(self) -> None:
        """Test client raises fail-closed error if specific key version is not registered."""
        test_client = mig.ExternalKMSClient.create_test_client(
            {"other-version": TEST_VERIFICATION_KEY}
        )
        with pytest.raises(RuntimeError) as exc_info:
            test_client.generate_hmac("eb-prov-k1-202611", b"payload")
        assert "KMS KEY RETRIEVAL ERROR" in str(exc_info.value)


# =============================================================================
# DEFECT 2: RFC 8785 CANONICALIZATION & APPENDIX B VECTORS
# =============================================================================


class TestDefect2RFC8785Canonicalization:
    """Validate RFC 8785 JSON Canonicalization Scheme (JCS) compliance."""

    def test_appendix_b_number_samples(self) -> None:
        """Verify IEEE 754 number formatting against exact RFC 8785 Appendix B vectors."""
        appendix_b_vectors = [
            ("0000000000000000", "0"),  # Positive zero
            ("8000000000000000", "0"),  # Negative zero normalizes to "0"
            ("0000000000000001", "5e-324"),  # Min subnormal positive
            ("8000000000000001", "-5e-324"),  # Min subnormal negative
            ("7fefffffffffffff", "1.7976931348623157e+308"),  # Max double
            ("444b1ae4d6e2ef4f", "999999999999999900000"),  # Large int boundary
            ("444b1ae4d6e2ef50", "1e+21"),  # Exponent transition
            ("3eb0c6f7a0b5ed8c", "9.999999999999997e-7"),  # Small fraction boundary
            ("3eb0c6f7a0b5ed8d", "0.000001"),  # Decimal fraction transition
        ]
        for hex_bits, expected_repr in appendix_b_vectors:
            val = struct.unpack("!d", bytes.fromhex(hex_bits))[0]
            out = mig._format_ecma_number(val)
            assert out == expected_repr, (
                f"Appendix B mismatch for {hex_bits}: got {out}, expected {expected_repr}"
            )

    def test_canonical_provenance_vector_1(self) -> None:
        """Vector 1: SENT record with contradictory counters."""
        v1 = {
            "key_version": "eb-prov-k1-202611",
            "migrated_at": "2026-11-10T00:00:00.000000Z",
            "migration_executor": "eb_migration_runner",
            "migration_txid": "10001",
            "migration_version": "0003_v26_0_0",
            "notification_id": "00000000-0000-0000-0000-000000000001",
            "original_attempt_count": 0,
            "original_last_attempt_at": "2026-11-09T12:00:00.000000Z",
            "original_retry_count": 0,
            "original_sent_at": "2026-11-09T12:00:05.000000Z",
            "original_status": "SENT",
            "provenance_reason": "MIGRATION_0003_LEGACY_SENT_CONTRADICTORY_COUNTERS",
            "serialization_version": "eb-prov-v1",
        }
        b1 = mig.rfc8785_canonical_serialize(v1)
        digest = hmac.new(TEST_VERIFICATION_KEY, b1, hashlib.sha256).hexdigest()
        assert (
            digest == "ba40d3e3f506d703f5a122b2069a4b3a2b5187b5d312b3431c3ccdf1cc95bb4d"
        )

    def test_canonical_provenance_vector_2_null_timestamps(self) -> None:
        """Vector 2: SENT record with NULL timestamps."""
        v2 = {
            "key_version": "eb-prov-k1-202611",
            "migrated_at": "2026-11-10T00:00:00.000000Z",
            "migration_executor": "eb_migration_runner",
            "migration_txid": "10002",
            "migration_version": "0003_v26_0_0",
            "notification_id": "00000000-0000-0000-0000-000000000002",
            "original_attempt_count": 1,
            "original_last_attempt_at": None,
            "original_retry_count": 0,
            "original_sent_at": None,
            "original_status": "SENT",
            "provenance_reason": "MIGRATION_0003_LEGACY_SENT_NULL_TIMESTAMPS",
            "serialization_version": "eb-prov-v1",
        }
        b2 = mig.rfc8785_canonical_serialize(v2)
        digest = hmac.new(TEST_VERIFICATION_KEY, b2, hashlib.sha256).hexdigest()
        assert (
            digest == "1bb61a13907c88acb50ec7fd62ce41603788f3933a66e6818d076b0e60423349"
        )

    def test_canonical_provenance_vectors_8_9_10_txid_boundaries(self) -> None:
        """Vectors 8, 9, 10: 64-bit boundary decimal representations."""
        v_base: dict[str, Any] = {
            "key_version": "eb-prov-k1-202611",
            "migrated_at": "2026-11-10T00:00:00.000000Z",
            "migration_executor": "eb_migration_runner",
            "migration_version": "0003_v26_0_0",
            "notification_id": "00000000-0000-0000-0000-000000000006",
            "original_attempt_count": 0,
            "original_last_attempt_at": None,
            "original_retry_count": 0,
            "original_sent_at": "2026-11-09T12:00:00.000000Z",
            "original_status": "SENT",
            "serialization_version": "eb-prov-v1",
        }

        # Vector 8: 2^53 - 1
        v8 = dict(
            v_base,
            migration_txid="9007199254740991",
            provenance_reason="MIGRATION_TXID_BOUNDARY_TEST_9007199254740991",
        )
        d8 = hmac.new(
            TEST_VERIFICATION_KEY,
            mig.rfc8785_canonical_serialize(v8),
            hashlib.sha256,
        ).hexdigest()
        assert d8 == "17a4b5f19feb483cd0c39201e0b28f2aa57dd385db4f05d4dc4bda12ddc1f3bb"

        # Vector 9: 2^53
        v9 = dict(
            v_base,
            migration_txid="9007199254740992",
            provenance_reason="MIGRATION_TXID_BOUNDARY_TEST_9007199254740992",
        )
        d9 = hmac.new(
            TEST_VERIFICATION_KEY,
            mig.rfc8785_canonical_serialize(v9),
            hashlib.sha256,
        ).hexdigest()
        assert d9 == "be53873930f1fb2e093010f01d0fcdc375dc4720630502d0b95241c5c4d704d4"

        # Vector 10: 2^63 - 1
        v10 = dict(
            v_base,
            migration_txid="9223372036854775807",
            provenance_reason="MIGRATION_TXID_BOUNDARY_TEST_9223372036854775807",
        )
        d10 = hmac.new(
            TEST_VERIFICATION_KEY,
            mig.rfc8785_canonical_serialize(v10),
            hashlib.sha256,
        ).hexdigest()
        assert d10 == "19012506c578a0029d8c79d5ea4dde130b5d37cf685b474ddd31cc2bbf58d4f9"

    def test_utf16_code_unit_sorting(self) -> None:
        """RFC 8785 requires property keys sorted by UTF-16 code units."""
        sample = {"\u00e9": 1, "z": 2, "a": 3}
        serialized = mig.rfc8785_canonical_serialize(sample).decode("utf-8")
        assert serialized == '{"a":3,"z":2,"\u00e9":1}'

    def test_lone_surrogates_rejection(self) -> None:
        """Lone surrogates (0xD800..0xDFFF) must be rejected fail-closed."""
        bad_str = "invalid\ud800character"
        with pytest.raises(ValueError) as exc_info:
            mig.rfc8785_canonical_serialize({"key": bad_str})
        assert "Lone surrogate" in str(exc_info.value)

    def test_duplicate_keys_and_nfc_collision_rejection(self) -> None:
        """Keys colliding under Unicode NFC normalization must raise ValueError."""
        # e + combining acute (U+0301) normalizes to \u00e9
        sample = {"\u00e9": 1, "e\u0301": 2}
        with pytest.raises(ValueError) as exc_info:
            mig.rfc8785_canonical_serialize(sample)
        assert "Duplicate object key after NFC normalization" in str(exc_info.value)

    def test_string_escaping_rfc8785(self) -> None:
        """Verify strict RFC 8785 §3.2.2.2 control character escapes."""
        sample = {"control": '\b\f\n\r\t"\\'}
        serialized = mig.rfc8785_canonical_serialize(sample).decode("utf-8")
        assert serialized == '{"control":"\\b\\f\\n\\r\\t\\"\\\\"}'

    def test_datetime_serialization_iso8601_microsecond_utc(self) -> None:
        """Datetime objects formatted with microsecond resolution and trailing 'Z'."""
        dt = datetime(2026, 11, 10, 14, 30, 45, 123456, tzinfo=UTC)
        serialized = mig.rfc8785_canonical_serialize({"timestamp": dt}).decode("utf-8")
        assert serialized == '{"timestamp":"2026-11-10T14:30:45.123456Z"}'


# =============================================================================
# DEFECT 3: OFFLINE PROVENANCE MANIFEST VERIFICATION & SAFE EMISSION
# =============================================================================


class TestDefect3OfflineManifestVerification:
    """Validate cryptographic verification and safe SQL emission for offline manifest."""

    @pytest.fixture
    def valid_manifest_entry(self) -> dict[str, Any]:
        """Produce a canonically signed manifest entry."""
        payload = {
            "key_version": "eb-prov-k1-202611",
            "migrated_at": "2026-11-10T00:00:00.000000Z",
            "migration_executor": "eb_migration_runner",
            "migration_txid": "10001",
            "migration_version": "0003_v43_0_0",
            "notification_id": "00000000-0000-0000-0000-000000000001",
            "original_attempt_count": 0,
            "original_last_attempt_at": "2026-11-09T12:00:00.000000Z",
            "original_retry_count": 0,
            "original_sent_at": "2026-11-09T12:00:05.000000Z",
            "original_status": "SENT",
            "provenance_reason": "MIGRATION_0003_LEGACY_SENT_CONTRADICTORY_COUNTERS",
            "serialization_version": "eb-prov-v1",
        }
        canonical_bytes = mig.rfc8785_canonical_serialize(payload)
        digest = hmac.new(
            TEST_VERIFICATION_KEY, canonical_bytes, hashlib.sha256
        ).hexdigest()
        return dict(payload, provenance_sha256=digest)

    def test_offline_sql_emission_with_verified_manifest(
        self, valid_manifest_entry: dict[str, Any]
    ) -> None:
        """Alembic --sql with valid manifest and verification key emits safe SQL."""
        cmd = [
            os.path.abspath("backend/.venv/bin/alembic"),
            "-c",
            DEFERRED_ALEMBIC_INI,
            "upgrade",
            "0002_add_enquiry_idempotency:0003_v43_0_0",
            "--sql",
        ]
        manifest_json = json.dumps([valid_manifest_entry])
        env = dict(
            os.environ,
            PYTHONPATH="backend",
            PRECOMPUTED_PROVENANCE_MANIFEST=manifest_json,
            EB_PROVENANCE_VERIFICATION_KEY=TEST_VERIFICATION_KEY.decode("utf-8"),
        )
        res = subprocess.run(
            cmd,
            check=False,
            cwd="backend",
            capture_output=True,
            text=True,
            env=env,
        )
        assert res.returncode == 0, f"Alembic --sql failed: {res.stderr}"

        sql = res.stdout
        assert "00000000-0000-0000-0000-000000000001" in sql
        assert valid_manifest_entry["provenance_sha256"] in sql
        assert "::uuid" in sql
        assert "::timestamptz" in sql

    def test_offline_manifest_missing_verification_key_fails_closed(
        self, valid_manifest_entry: dict[str, Any]
    ) -> None:
        """Providing manifest without verification key fails closed."""
        cmd = [
            os.path.abspath("backend/.venv/bin/alembic"),
            "-c",
            DEFERRED_ALEMBIC_INI,
            "upgrade",
            "0002_add_enquiry_idempotency:0003_v43_0_0",
            "--sql",
        ]
        manifest_json = json.dumps([valid_manifest_entry])
        env = dict(
            os.environ,
            PYTHONPATH="backend",
            PRECOMPUTED_PROVENANCE_MANIFEST=manifest_json,
        )
        env.pop("EB_PROVENANCE_VERIFICATION_KEY", None)
        env.pop("EB_OFFLINE_VERIFICATION_KEY", None)

        res = subprocess.run(
            cmd,
            check=False,
            cwd="backend",
            capture_output=True,
            text=True,
            env=env,
        )
        assert res.returncode != 0
        assert "OFFLINE PROVENANCE MANIFEST VERIFICATION FAILED" in res.stderr

    def test_offline_manifest_tampered_hmac_fails(
        self, valid_manifest_entry: dict[str, Any]
    ) -> None:
        """Altered HMAC signature raises CRYPTOGRAPHIC INTEGRITY ERROR."""
        tampered_entry = dict(valid_manifest_entry, provenance_sha256="0" * 64)
        cmd = [
            os.path.abspath("backend/.venv/bin/alembic"),
            "-c",
            DEFERRED_ALEMBIC_INI,
            "upgrade",
            "0002_add_enquiry_idempotency:0003_v43_0_0",
            "--sql",
        ]
        env = dict(
            os.environ,
            PYTHONPATH="backend",
            PRECOMPUTED_PROVENANCE_MANIFEST=json.dumps([tampered_entry]),
            EB_PROVENANCE_VERIFICATION_KEY=TEST_VERIFICATION_KEY.decode("utf-8"),
        )
        res = subprocess.run(
            cmd,
            check=False,
            cwd="backend",
            capture_output=True,
            text=True,
            env=env,
        )
        assert res.returncode != 0
        assert "CRYPTOGRAPHIC INTEGRITY ERROR" in res.stderr

    def test_offline_manifest_duplicate_notification_id_fails(
        self, valid_manifest_entry: dict[str, Any]
    ) -> None:
        """Duplicate notification_id in manifest is rejected."""
        cmd = [
            os.path.abspath("backend/.venv/bin/alembic"),
            "-c",
            DEFERRED_ALEMBIC_INI,
            "upgrade",
            "0002_add_enquiry_idempotency:0003_v43_0_0",
            "--sql",
        ]
        env = dict(
            os.environ,
            PYTHONPATH="backend",
            PRECOMPUTED_PROVENANCE_MANIFEST=json.dumps(
                [valid_manifest_entry, valid_manifest_entry]
            ),
            EB_PROVENANCE_VERIFICATION_KEY=TEST_VERIFICATION_KEY.decode("utf-8"),
        )
        res = subprocess.run(
            cmd,
            check=False,
            cwd="backend",
            capture_output=True,
            text=True,
            env=env,
        )
        assert res.returncode != 0
        assert "Duplicate notification_id" in res.stderr

    def test_offline_manifest_invalid_uuid_fails(
        self, valid_manifest_entry: dict[str, Any]
    ) -> None:
        """Malformed notification_id UUID is rejected."""
        bad_entry = dict(valid_manifest_entry, notification_id="not-a-uuid")
        cmd = [
            os.path.abspath("backend/.venv/bin/alembic"),
            "-c",
            DEFERRED_ALEMBIC_INI,
            "upgrade",
            "0002_add_enquiry_idempotency:0003_v43_0_0",
            "--sql",
        ]
        env = dict(
            os.environ,
            PYTHONPATH="backend",
            PRECOMPUTED_PROVENANCE_MANIFEST=json.dumps([bad_entry]),
            EB_PROVENANCE_VERIFICATION_KEY=TEST_VERIFICATION_KEY.decode("utf-8"),
        )
        res = subprocess.run(
            cmd,
            check=False,
            cwd="backend",
            capture_output=True,
            text=True,
            env=env,
        )
        assert res.returncode != 0
        assert "invalid UUID" in res.stderr

    def test_offline_manifest_txid_overflow_fails(
        self, valid_manifest_entry: dict[str, Any]
    ) -> None:
        """txid exceeding 2^63 - 1 is rejected."""
        bad_entry = dict(valid_manifest_entry, migration_txid="9223372036854775808")
        cmd = [
            os.path.abspath("backend/.venv/bin/alembic"),
            "-c",
            DEFERRED_ALEMBIC_INI,
            "upgrade",
            "0002_add_enquiry_idempotency:0003_v43_0_0",
            "--sql",
        ]
        env = dict(
            os.environ,
            PYTHONPATH="backend",
            PRECOMPUTED_PROVENANCE_MANIFEST=json.dumps([bad_entry]),
            EB_PROVENANCE_VERIFICATION_KEY=TEST_VERIFICATION_KEY.decode("utf-8"),
        )
        res = subprocess.run(
            cmd,
            check=False,
            cwd="backend",
            capture_output=True,
            text=True,
            env=env,
        )
        assert res.returncode != 0
        assert "migration_txid out of bounds" in res.stderr


# =============================================================================
# DEFECT 4: ROLE MATRIX & PERMISSIONS CONSISTENCY
# =============================================================================


class TestDefect4RoleMatrixConsistency:
    """Validate 7-role RBAC architecture and least-privilege matrix."""

    def test_all_seven_roles_present_in_migration_source(self) -> None:
        """Verify all seven authoritative database roles are defined in the migration."""
        with open(MIGRATION_PATH, encoding="utf-8") as f:
            src = f.read()

        authoritative_roles = [
            "eb_app_user",
            "eb_worker_user",
            "eb_migration_runner",
            "eb_migration_role",
            "eb_schema_owner",
            "eb_sec_admin",
            "eb_archival_role",
        ]
        for role in authoritative_roles:
            assert f"'{role}'" in src or f'"{role}"' in src or role in src, (
                f"Missing role {role} in migration source"
            )

    def test_no_six_role_inconsistency_in_headings(self) -> None:
        """Docstring and phase headings must uniformly reference Seven-Role model."""
        with open(MIGRATION_PATH, encoding="utf-8") as f:
            src = f.read()

        assert "SIX-ROLE" not in src
        assert "Six-Role" not in src
        assert "Seven-role" in src or "SEVEN-ROLE" in src

    def test_archival_role_read_only_table_grants_in_generated_sql(self) -> None:
        """Verify eb_archival_role receives SELECT-only grants in emitted SQL."""
        cmd = [
            os.path.abspath("backend/.venv/bin/alembic"),
            "-c",
            DEFERRED_ALEMBIC_INI,
            "upgrade",
            "0002_add_enquiry_idempotency:0003_v43_0_0",
            "--sql",
        ]
        res = subprocess.run(
            cmd,
            check=False,
            cwd="backend",
            capture_output=True,
            text=True,
            env=dict(os.environ, PYTHONPATH="backend"),
        )
        assert res.returncode == 0
        sql = res.stdout

        assert "GRANT USAGE ON SCHEMA public TO eb_archival_role;" in sql
        assert "GRANT SELECT ON public.notification_logs TO eb_archival_role;" in sql
        assert (
            "GRANT SELECT ON public.legacy_notification_provenance TO eb_archival_role;"
            in sql
        )
        assert "GRANT SELECT ON public.smtp_evidence_store TO eb_archival_role;" in sql


# =============================================================================
# DEFECT 5 / REMEDIATION: PROVENANCE TIMESTAMP INTEGRITY & REGRESSION TESTS
# =============================================================================


class TestProvenanceTimestampIntegrity:
    """Validate single timezone-aware UTC microsecond timestamp integrity.

    Verifies that:
    1. A single timezone-aware UTC timestamp with non-zero microseconds is generated.
    2. The exact same timestamp is used for the canonical HMAC preimage and database insert.
    3. Truncating microseconds breaks verification.
    4. The verifier reconstructs the identical HMAC whether migrated_at is a datetime or string.
    5. All five legacy provenance registration paths maintain round-trip integrity.
    6. Independent HMAC reconstruction from the persisted timestamp succeeds for all 5 paths.
    """

    @pytest.fixture
    def test_kms(self) -> Any:
        return mig.ExternalKMSClient.create_test_client(
            {"eb-prov-k1-202611": TEST_VERIFICATION_KEY}
        )

    def test_normalize_iso_ts(self) -> None:
        """Verify _normalize_iso_ts handles datetimes and database timestamp strings."""
        dt = datetime(2026, 11, 10, 15, 30, 45, 123456, tzinfo=UTC)
        assert mig._normalize_iso_ts(dt) == "2026-11-10T15:30:45.123456Z"

        # Naive datetime is assumed UTC
        naive_dt = datetime(2026, 11, 10, 15, 30, 45, 123456)
        assert mig._normalize_iso_ts(naive_dt) == "2026-11-10T15:30:45.123456Z"

        # String with Z
        assert (
            mig._normalize_iso_ts("2026-11-10T15:30:45.123456Z")
            == "2026-11-10T15:30:45.123456Z"
        )

        # String with +00:00
        assert (
            mig._normalize_iso_ts("2026-11-10T15:30:45.123456+00:00")
            == "2026-11-10T15:30:45.123456Z"
        )

        # PostgreSQL timestamptz string representation (space-delimited)
        assert (
            mig._normalize_iso_ts("2026-11-10 15:30:45.123456+00")
            == "2026-11-10T15:30:45.123456Z"
        )

        # None or empty string
        assert mig._normalize_iso_ts(None) is None
        assert mig._normalize_iso_ts("") is None

    @pytest.mark.parametrize(
        ("reason", "status", "att", "ret", "last_att", "sent_at", "tf_class"),
        [
            (
                "MIGRATION_0003_LEGACY_SENT_CONTRADICTORY_COUNTERS",
                "SENT",
                0,
                0,
                datetime(2026, 11, 10, 12, 0, 0, 111111, tzinfo=UTC),
                datetime(2026, 11, 10, 12, 0, 5, 222222, tzinfo=UTC),
                None,
            ),
            (
                "MIGRATION_0003_LEGACY_EXHAUSTED_CONTRADICTORY_COUNTERS",
                "EXHAUSTED",
                1,
                2,
                datetime(2026, 11, 10, 13, 0, 0, 333333, tzinfo=UTC),
                None,
                "LEGACY_FAILURE_UNCLASSIFIED",
            ),
            (
                "MIGRATION_0003_LEGACY_PENDING_ATTEMPT_EVIDENCE_QUARANTINED",
                "EXHAUSTED",
                2,
                1,
                datetime(2026, 11, 10, 14, 0, 0, 444444, tzinfo=UTC),
                None,
                "LEGACY_FAILURE_UNCLASSIFIED",
            ),
            (
                "MIGRATION_0003_LEGACY_FAILED_CONTRADICTORY_COUNTERS",
                "EXHAUSTED",
                0,
                1,
                datetime(2026, 11, 10, 15, 0, 0, 555555, tzinfo=UTC),
                None,
                "LEGACY_FAILURE_UNCLASSIFIED",
            ),
            (
                "MIGRATION_0003_LEGACY_CLAIMED_CORRUPT_LEASE_QUARANTINED",
                "EXHAUSTED",
                3,
                1,
                datetime(2026, 11, 10, 16, 0, 0, 666666, tzinfo=UTC),
                None,
                "LEGACY_FAILURE_UNCLASSIFIED",
            ),
        ],
    )
    def test_all_five_paths_with_nonzero_microseconds(
        self,
        test_kms: Any,
        reason: str,
        status: str,
        att: int,
        ret: int,
        last_att: datetime | None,
        sent_at: datetime | None,
        tf_class: str | None,
    ) -> None:
        """Verify all 5 legacy paths maintain microsecond integrity and round-trip verification."""
        nid = "11111111-2222-3333-4444-555555555555"
        non_zero_ts = datetime(2026, 11, 10, 16, 45, 12, 987654, tzinfo=UTC)

        prov_record = mig.build_legacy_provenance_record(
            notification_id=nid,
            original_status=status,
            original_attempt_count=att,
            original_retry_count=ret,
            original_last_attempt_at=last_att,
            original_sent_at=sent_at,
            provenance_reason=reason,
            migration_txid="50001",
            kms_client=test_kms,
            migrated_at=non_zero_ts,
        )

        assert prov_record["migrated_at_iso"] == "2026-11-10T16:45:12.987654Z"
        assert prov_record["migrated_at"] == non_zero_ts

        notif_row = {
            "id": nid,
            "status": status,
            "is_legacy_exception": True,
            "attempt_count": att,
            "retry_count": ret,
            "last_attempt_at": last_att,
            "sent_at": sent_at,
            "claimed_by": None,
            "claim_expires_at": None,
            "retry_eligible_at": None,
            "terminal_failure_class": tf_class,
        }

        # 1. Verification with datetime object (as returned by SQLAlchemy/psycopg)
        v_res = mig.verify_provenance_row(prov_record, notif_row, test_kms)
        assert v_res["status"] == mig.VerificationStatus.VALID, (
            f"Failed for {reason}: {v_res}"
        )

        # 2. Verification with PostgreSQL string format (e.g. from raw SQL or manifest)
        prov_record_str_ts = dict(
            prov_record, migrated_at="2026-11-10 16:45:12.987654+00"
        )
        v_res_str = mig.verify_provenance_row(prov_record_str_ts, notif_row, test_kms)
        assert v_res_str["status"] == mig.VerificationStatus.VALID

    @pytest.mark.parametrize(
        ("reason", "status", "att", "ret", "last_att", "sent_at"),
        [
            (
                "MIGRATION_0003_LEGACY_SENT_CONTRADICTORY_COUNTERS",
                "SENT",
                0,
                0,
                datetime(2026, 11, 10, 10, 15, 30, 123456, tzinfo=UTC),
                datetime(2026, 11, 10, 10, 15, 35, 654321, tzinfo=UTC),
            ),
            (
                "MIGRATION_0003_LEGACY_EXHAUSTED_CONTRADICTORY_COUNTERS",
                "EXHAUSTED",
                2,
                3,
                datetime(2026, 11, 10, 11, 20, 45, 234567, tzinfo=UTC),
                None,
            ),
            (
                "MIGRATION_0003_LEGACY_PENDING_ATTEMPT_EVIDENCE_QUARANTINED",
                "PENDING",
                1,
                0,
                datetime(2026, 11, 10, 12, 25, 50, 345678, tzinfo=UTC),
                None,
            ),
            (
                "MIGRATION_0003_LEGACY_FAILED_CONTRADICTORY_COUNTERS",
                "FAILED",
                2,
                0,
                datetime(2026, 11, 10, 13, 30, 55, 456789, tzinfo=UTC),
                None,
            ),
            (
                "MIGRATION_0003_LEGACY_CLAIMED_CORRUPT_LEASE_QUARANTINED",
                "CLAIMED",
                4,
                2,
                datetime(2026, 11, 10, 14, 35, 10, 567890, tzinfo=UTC),
                None,
            ),
        ],
    )
    def test_reconstruct_hmac_from_persisted_timestamp_all_five_paths(
        self,
        test_kms: Any,
        reason: str,
        status: str,
        att: int,
        ret: int,
        last_att: datetime | None,
        sent_at: datetime | None,
    ) -> None:
        """Explicitly reconstruct and validate HMAC from persisted record for all 5 paths."""
        nid = f"44444444-5555-6666-7777-{hashlib.md5(reason.encode()).hexdigest()[:12]}"
        persisted_ts = datetime(2026, 11, 10, 17, 30, 45, 789123, tzinfo=UTC)
        txid = "80005"

        # 1. Generate provenance record (as written during migration backfill)
        record = mig.build_legacy_provenance_record(
            notification_id=nid,
            original_status=status,
            original_attempt_count=att,
            original_retry_count=ret,
            original_last_attempt_at=last_att,
            original_sent_at=sent_at,
            provenance_reason=reason,
            migration_txid=txid,
            kms_client=test_kms,
            migrated_at=persisted_ts,
        )
        stored_hmac = record["provenance_sha256"]

        # 2. Simulate reading back the row from PostgreSQL (migrated_at as timestamptz datetime)
        reconstructed_ts_iso = mig._normalize_iso_ts(record["migrated_at"])
        assert reconstructed_ts_iso == "2026-11-10T17:30:45.789123Z"
        assert reconstructed_ts_iso.endswith(".789123Z")

        # 3. Assemble canonical pre-image independently from the persisted record
        independent_pre_image = {
            "key_version": "eb-prov-k1-202611",
            "migrated_at": reconstructed_ts_iso,
            "migration_executor": "eb_migration_runner",
            "migration_txid": txid,
            "migration_version": "0003_v43_0_0",
            "notification_id": nid,
            "original_attempt_count": att,
            "original_last_attempt_at": mig._normalize_iso_ts(last_att),
            "original_retry_count": ret,
            "original_sent_at": mig._normalize_iso_ts(sent_at),
            "original_status": status,
            "provenance_reason": reason,
            "serialization_version": "eb-prov-v1",
        }
        canonical_bytes = mig.rfc8785_canonical_serialize(independent_pre_image)
        recalculated_hmac = hmac.new(
            TEST_VERIFICATION_KEY, canonical_bytes, hashlib.sha256
        ).hexdigest()

        # 4. Assert exact match with stored HMAC
        assert recalculated_hmac == stored_hmac, (
            f"HMAC reconstruction mismatch for {reason}"
        )

        # 5. Simulate reading back as PostgreSQL formatted string (e.g. '2026-11-10 17:30:45.789123+00')
        pg_str_ts = "2026-11-10 17:30:45.789123+00"
        normalized_from_str = mig._normalize_iso_ts(pg_str_ts)
        assert normalized_from_str == "2026-11-10T17:30:45.789123Z"

        str_pre_image = dict(independent_pre_image, migrated_at=normalized_from_str)
        str_canonical_bytes = mig.rfc8785_canonical_serialize(str_pre_image)
        str_hmac = hmac.new(
            TEST_VERIFICATION_KEY, str_canonical_bytes, hashlib.sha256
        ).hexdigest()
        assert str_hmac == stored_hmac

        # 6. Verify that truncating microseconds in persisted timestamp breaks HMAC verification
        truncated_pre_image = dict(
            independent_pre_image, migrated_at="2026-11-10T17:30:45.000000Z"
        )
        truncated_bytes = mig.rfc8785_canonical_serialize(truncated_pre_image)
        truncated_hmac = hmac.new(
            TEST_VERIFICATION_KEY, truncated_bytes, hashlib.sha256
        ).hexdigest()
        assert truncated_hmac != stored_hmac, (
            "Microsecond truncation must alter HMAC digest"
        )

    def test_microsecond_truncation_breaks_hmac(self, test_kms: Any) -> None:
        """Verify that truncating microseconds causes HMAC mismatch."""
        nid = "22222222-3333-4444-5555-666666666666"
        exact_ts = datetime(2026, 11, 10, 16, 45, 12, 123456, tzinfo=UTC)

        prov_record = mig.build_legacy_provenance_record(
            notification_id=nid,
            original_status="SENT",
            original_attempt_count=0,
            original_retry_count=0,
            original_last_attempt_at=None,
            original_sent_at=None,
            provenance_reason="MIGRATION_0003_LEGACY_SENT_CONTRADICTORY_COUNTERS",
            migration_txid="50002",
            kms_client=test_kms,
            migrated_at=exact_ts,
        )

        notif_row = {
            "id": nid,
            "status": "SENT",
            "is_legacy_exception": True,
            "attempt_count": 0,
            "retry_count": 0,
            "last_attempt_at": None,
            "sent_at": None,
            "claimed_by": None,
            "claim_expires_at": None,
            "retry_eligible_at": None,
            "terminal_failure_class": None,
        }

        # Tamper by truncating microseconds in provenance row
        tampered_record = dict(prov_record, migrated_at="2026-11-10T16:45:12.000000Z")
        v_res = mig.verify_provenance_row(tampered_record, notif_row, test_kms)
        assert v_res["status"] == mig.VerificationStatus.INVALID_HMAC_DIGEST

    def test_independent_hmac_reconstruction_matches(self, test_kms: Any) -> None:
        """Verify independent RFC 8785 canonical reconstruction matches generated digest."""
        nid = "33333333-4444-5555-6666-777777777777"
        dt = datetime(2026, 11, 10, 17, 1, 23, 456789, tzinfo=UTC)

        prov = mig.build_legacy_provenance_record(
            notification_id=nid,
            original_status="SENT",
            original_attempt_count=1,
            original_retry_count=1,
            original_last_attempt_at=None,
            original_sent_at=None,
            provenance_reason="MIGRATION_0003_LEGACY_SENT_CONTRADICTORY_COUNTERS",
            migration_txid="70001",
            kms_client=test_kms,
            migrated_at=dt,
        )

        # Manually assemble pre-image dictionary
        manual_pre_image = {
            "key_version": "eb-prov-k1-202611",
            "migrated_at": "2026-11-10T17:01:23.456789Z",
            "migration_executor": "eb_migration_runner",
            "migration_txid": "70001",
            "migration_version": "0003_v43_0_0",
            "notification_id": nid,
            "original_attempt_count": 1,
            "original_last_attempt_at": None,
            "original_retry_count": 1,
            "original_sent_at": None,
            "original_status": "SENT",
            "provenance_reason": "MIGRATION_0003_LEGACY_SENT_CONTRADICTORY_COUNTERS",
            "serialization_version": "eb-prov-v1",
        }
        canonical_bytes = mig.rfc8785_canonical_serialize(manual_pre_image)
        manual_hmac = hmac.new(
            TEST_VERIFICATION_KEY, canonical_bytes, hashlib.sha256
        ).hexdigest()

        assert prov["provenance_sha256"] == manual_hmac


# =============================================================================
# DEFECT 6 / REMEDIATION: MIGRATION OWNERSHIP AUTHORITY & RBAC VALIDATION
# =============================================================================


class TestMigrationOwnershipAuthority:
    """Validate migration runner ownership transfer authority and RBAC rules."""

    def test_valid_authority_succeeds(self) -> None:
        """Execution passes when runner possesses all required target roles."""
        user_roles = {"eb_migration_role", "eb_schema_owner", "eb_sec_admin"}
        # Should execute cleanly with no exceptions
        mig.validate_migration_authority("eb_migration_runner", user_roles)

    def test_prerequisite_infrastructure_roles_validation_passes(self) -> None:
        """When all 7 authoritative infrastructure roles are present, validation passes."""
        mig.validate_prerequisite_roles_exist(mig.AUTHORITATIVE_INFRASTRUCTURE_ROLES)

    @pytest.mark.parametrize(
        "missing_role", sorted(mig.AUTHORITATIVE_INFRASTRUCTURE_ROLES)
    )
    def test_prerequisite_infrastructure_roles_missing_fails_closed(
        self, missing_role: str
    ) -> None:
        """Missing any of the 7 prerequisite infrastructure roles fails closed before execution."""
        present_roles = mig.AUTHORITATIVE_INFRASTRUCTURE_ROLES - {missing_role}
        with pytest.raises(PermissionError) as exc_info:
            mig.validate_prerequisite_roles_exist(present_roles)
        err = str(exc_info.value)
        assert "PRE-REQUISITE ROLES MISSING" in err
        assert missing_role in err
        assert "out-of-band by an authorized DBA principal" in err
        assert "lacks CREATEROLE" in err

    def test_superuser_without_roles_fails_closed(self) -> None:
        """Superuser role without explicit target roles fails closed (no undocumented bypass)."""
        with pytest.raises(PermissionError) as exc_info:
            mig.validate_migration_authority("postgres", set())
        assert "AUTHORIZATION VIOLATION" in str(exc_info.value)
        assert "eb_schema_owner" in str(exc_info.value)
        assert "eb_sec_admin" in str(exc_info.value)
        assert "eb_migration_role" in str(exc_info.value)

    @pytest.mark.parametrize(
        ("granted_roles", "missing_role"),
        [
            ({"eb_migration_role", "eb_sec_admin"}, "eb_schema_owner"),
            ({"eb_migration_role", "eb_schema_owner"}, "eb_sec_admin"),
            ({"eb_schema_owner", "eb_sec_admin"}, "eb_migration_role"),
        ],
    )
    def test_missing_single_authority_role_fails_closed(
        self, granted_roles: set[str], missing_role: str
    ) -> None:
        """Missing any required target role raises PermissionError before schema changes."""
        with pytest.raises(PermissionError) as exc_info:
            mig.validate_migration_authority("eb_migration_runner", granted_roles)
        assert "AUTHORIZATION VIOLATION" in str(exc_info.value)
        assert missing_role in str(exc_info.value)

    def test_empty_roles_fails_closed_with_all_missing(self) -> None:
        """Complete lack of roles lists all missing requirements."""
        with pytest.raises(PermissionError) as exc_info:
            mig.validate_migration_authority("unprivileged_user", set())
        err = str(exc_info.value)
        assert "eb_migration_role" in err
        assert "eb_schema_owner" in err
        assert "eb_sec_admin" in err

    def test_migration_runner_non_superuser_no_createrole_or_admin_option(self) -> None:
        """Verify migration runner adheres strictly to PostgreSQL 16 least-privilege RBAC.

        The migration runner must not assume superuser, CREATEROLE, or ADMIN OPTION authority:
        1. Migration source contains NO 'CREATE ROLE' statements (runner cannot provision roles).
        2. Migration source contains NO self-granting 'GRANT ... TO eb_migration_runner' statements.
        3. Phase 0 in emitted SQL asserts all 7 roles exist (SQLSTATE '42704') and fails closed.
        4. Phase 0 in emitted SQL asserts runner ownership-transfer authority (SQLSTATE '42501').
        5. Generated SQL contains NO 'CREATE ROLE' or self-granting role DDL.
        6. Generated SQL contains NO undocumented 'rolsuper' superuser bypasses.
        """
        with open(MIGRATION_PATH, encoding="utf-8") as f:
            src = f.read()

        # 1. No CREATE ROLE in migration source
        assert "CREATE ROLE" not in src, (
            "Migration runner must not attempt CREATE ROLE (lacks CREATEROLE privilege)"
        )

        # 2. No self-granting role memberships in migration source
        assert "GRANT eb_migration_role TO eb_migration_runner" not in src
        assert "GRANT eb_schema_owner TO eb_migration_runner" not in src
        assert "GRANT eb_sec_admin TO eb_migration_runner" not in src

        # 3. Emitted SQL contains no CREATE ROLE and no self-granting DDL
        cmd = [
            os.path.abspath("backend/.venv/bin/alembic"),
            "-c",
            DEFERRED_ALEMBIC_INI,
            "upgrade",
            "0002_add_enquiry_idempotency:0003_v43_0_0",
            "--sql",
        ]
        res = subprocess.run(
            cmd,
            check=False,
            cwd="backend",
            capture_output=True,
            text=True,
            env=dict(os.environ, PYTHONPATH="backend"),
        )
        assert res.returncode == 0
        sql = res.stdout

        assert "CREATE ROLE" not in sql
        assert "GRANT eb_migration_role TO eb_migration_runner" not in sql
        assert "GRANT eb_schema_owner TO eb_migration_runner" not in sql
        assert "GRANT eb_sec_admin TO eb_migration_runner" not in sql
        assert "rolsuper" not in sql

        # 4. Phase 0 validates prerequisite role existence (42704) and executor authority (42501)
        assert "ERRCODE = '42704'" in sql
        assert "ERRCODE = '42501'" in sql
        for role in mig.AUTHORITATIVE_INFRASTRUCTURE_ROLES:
            assert f"'{role}'" in sql

    def test_phase0_preflight_and_ownership_in_generated_sql(self) -> None:
        """Verify Phase 0 DO $auth_preflight$ and table ownership statements are generated."""
        cmd = [
            os.path.abspath("backend/.venv/bin/alembic"),
            "-c",
            DEFERRED_ALEMBIC_INI,
            "upgrade",
            "0002_add_enquiry_idempotency:0003_v43_0_0",
            "--sql",
        ]
        res = subprocess.run(
            cmd,
            check=False,
            cwd="backend",
            capture_output=True,
            text=True,
            env=dict(os.environ, PYTHONPATH="backend"),
        )
        assert res.returncode == 0
        sql = res.stdout

        # Phase 0 authority validation block is present
        assert "DO $auth_preflight$" in sql
        assert "ERRCODE = '42704'" in sql
        assert "ERRCODE = '42501'" in sql
        assert "pg_has_role(SESSION_USER, 'eb_schema_owner', 'MEMBER')" in sql
        assert "pg_has_role(SESSION_USER, 'eb_sec_admin', 'MEMBER')" in sql
        assert "pg_has_role(SESSION_USER, 'eb_migration_role', 'MEMBER')" in sql

        # No CREATE ROLE or self-granting in emitted SQL
        assert "CREATE ROLE" not in sql
        assert "GRANT eb_migration_role TO eb_migration_runner" not in sql

        # No undocumented superuser execution bypasses in Phase 0 preflight
        assert "rolsuper" not in sql

        # Preflight occurs before CREATE TABLE
        auth_idx = sql.find("DO $auth_preflight$")
        table_idx = sql.find("CREATE TABLE legacy_notification_provenance")
        assert auth_idx != -1
        assert table_idx != -1
        assert auth_idx < table_idx, (
            "Phase 0 auth preflight must precede table creation"
        )

        # Table and schema ownership statements
        assert "ALTER TABLE public.notification_logs OWNER TO eb_schema_owner;" in sql
        assert (
            "ALTER TABLE public.platform_circuit_breakers OWNER TO eb_schema_owner;"
            in sql
        )
        assert (
            "ALTER TABLE public.legacy_notification_provenance OWNER TO eb_schema_owner;"
            in sql
        )
        assert "ALTER TABLE public.smtp_evidence_store OWNER TO eb_schema_owner;" in sql
        assert "ALTER SCHEMA eb_security OWNER TO eb_sec_admin;" in sql


class TestSingleAdministratorRequirementAlignment:
    """Validate that Migration 0003 strictly complies with the EDEN BOUNTY Single Administrator Requirement.

    Requirements:
    1. Maintain one initial SUPER_ADMIN account.
    2. Do not create multiple application administrator accounts.
    3. Do not implement administrator invitations, registration, or multi-admin management.
    4. Do not add separate operational staff accounts.
    5. All dashboard operations will be handled by the single administrator.
    6. Preserve existing PostgreSQL infrastructure roles only where required for database security
       and least-privilege access. These are not application administrator accounts.
    7. Do not modify the frozen C13.5 V43 architecture unnecessarily.
    """

    def test_migration_does_not_modify_admin_users_or_roles(self) -> None:
        """Verify Migration 0003 contains no DDL or DML modifying application admin accounts.

        Migration 0003 is scoped strictly to notification infrastructure and must not touch
        admin_users, admin_roles, or admin_user_roles.
        """
        with open(MIGRATION_PATH, encoding="utf-8") as f:
            src = f.read()

        assert "admin_users" not in src
        assert "admin_user_roles" not in src
        assert "create_table('admin_roles'" not in src
        assert "CREATE TABLE admin_users" not in src

    def test_migration_emitted_sql_does_not_alter_admin_tables(self) -> None:
        """Verify emitted SQL contains no operations targeting application administrator tables."""
        cmd = [
            os.path.abspath("backend/.venv/bin/alembic"),
            "-c",
            DEFERRED_ALEMBIC_INI,
            "upgrade",
            "0002_add_enquiry_idempotency:0003_v43_0_0",
            "--sql",
        ]
        res = subprocess.run(
            cmd,
            check=False,
            cwd="backend",
            capture_output=True,
            text=True,
            env=dict(os.environ, PYTHONPATH="backend"),
        )
        assert res.returncode == 0
        sql = res.stdout

        assert "admin_users" not in sql
        assert "admin_user_roles" not in sql

    def test_infrastructure_roles_isolated_from_application_accounts(self) -> None:
        """Verify all 7 infrastructure roles are PostgreSQL database engine roles, NOT application accounts.

        PostgreSQL roles (eb_app_user, eb_worker_user, eb_migration_runner, eb_migration_role,
        eb_schema_owner, eb_sec_admin, eb_archival_role) are connection/privilege isolation principals.
        They do not create, grant, or manage application administrator accounts.
        """
        for role in mig.AUTHORITATIVE_INFRASTRUCTURE_ROLES:
            assert role.startswith("eb_")
            assert role not in ("SUPER_ADMIN", "OPERATIONS_ADMIN")

    def test_quarantine_audit_records_external_signatory_without_app_user_fk(
        self,
    ) -> None:
        """Verify notification_quarantine_audit does not introduce FK constraints to admin_users.

        Audit columns (primary_operator_id, secondary_approver_id, override_ticket_id) are
        unconstrained VARCHAR(64) fields that record the single SUPER_ADMIN's operational ID
        and external ticketing signatories (ITSM-[A-Z0-9_-]+) without requiring multi-admin accounts.
        """
        with open(MIGRATION_PATH, encoding="utf-8") as f:
            src = f.read()

        assert "REFERENCES admin_users" not in src
        assert "REFERENCES public.admin_users" not in src
