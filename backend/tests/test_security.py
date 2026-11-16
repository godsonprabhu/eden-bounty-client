"""Tests for Cryptographic Primitives, Argon2id, and Password Security.

Phase C13.2 — Aligned with C13-security-design.md v2.1.0:
- Argon2id RFC 9106 configuration (64MB memory, 3 iterations, 4 parallelism).
- Password policy validation.
- Timing attack mitigation.
- Session and CSRF token generation and hashing.
"""

import hashlib
import time

from app.core.security import (
    constant_time_compare,
    generate_csrf_token,
    generate_session_token,
    hash_password,
    hash_session_token,
    validate_password_policy,
    verify_dummy_password,
    verify_password,
)


def test_argon2id_hash_format_and_rfc9106_parameters():
    """Verifies that Argon2id output contains the specified 64MB memory, 3 iterations, and 4 threads."""
    test_password = "EdenCorporate2026!#"
    hashed = hash_password(test_password)

    # Must follow standard modular crypt format for Argon2id
    assert hashed.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    assert test_password not in hashed


def test_argon2id_verification_accuracy():
    """Verifies that correct passwords verify successfully and incorrect ones are rejected."""
    pw = "SuperSecurePassword987$"
    hashed = hash_password(pw)

    assert verify_password(pw, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password(pw, "invalid_malformed_hash") is False


def test_password_policy_validation():
    """Verifies password complexity enforcement."""
    # Compliant password
    ok, err = validate_password_policy("Corporate2026!#")
    assert ok is True
    assert err is None

    # Too short (< 12)
    ok, err = validate_password_policy("Short1!Aa")
    assert ok is False
    assert "at least 12 characters" in err

    # Missing uppercase
    ok, err = validate_password_policy("lowercaseonly123!#")
    assert ok is False
    assert "uppercase" in err

    # Missing lowercase
    ok, err = validate_password_policy("UPPERCASEONLY123!#")
    assert ok is False
    assert "lowercase" in err

    # Missing digit
    ok, err = validate_password_policy("NoDigitsAtAllHere!#")
    assert ok is False
    assert "digit" in err

    # Missing symbol
    ok, err = validate_password_policy("NoSymbolsInThis12345")
    assert ok is False
    assert "symbol" in err


def test_dummy_argon2_verification_executes_safely():
    """Verifies that dummy verification executes without raising unhandled errors."""
    start = time.perf_counter()
    verify_dummy_password()
    elapsed = time.perf_counter() - start
    # Should take measurable CPU time (Argon2id 64MB, 3 iterations)
    assert elapsed > 0.005


def test_session_token_and_storage_hash_separation():
    """Verifies that raw session tokens are never stored directly and match SHA-256 digest."""
    raw_token = generate_session_token()
    assert len(raw_token) >= 48
    assert raw_token.isascii()

    hashed_token = hash_session_token(raw_token)
    expected_digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    assert hashed_token == expected_digest
    assert raw_token != hashed_token
    assert len(hashed_token) == 64  # SHA-256 hex digest length


def test_csrf_token_generation_and_constant_time_comparison():
    """Verifies CSRF token generation and constant-time equality comparisons."""
    csrf_a = generate_csrf_token()
    csrf_b = generate_csrf_token()

    assert len(csrf_a) >= 32
    assert csrf_a != csrf_b

    assert constant_time_compare(csrf_a, csrf_a) is True
    assert constant_time_compare(csrf_a, csrf_b) is False
    assert constant_time_compare(csrf_a, "short_mismatch") is False
