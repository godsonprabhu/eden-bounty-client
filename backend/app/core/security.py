"""Cryptographic primitives, password hashing, and token utilities.

Phase C13.2 — Administrator Authentication & Session Management.
Strictly adheres to C13-security-design.md v2.1.0:
- Argon2id (RFC 9106): 64MB memory, 3 iterations, 4 parallelism.
- Timing-attack mitigations with constant-time comparisons and dummy verification.
- Cryptographically secure session and CSRF token generation.
- Strict password policy enforcement.
"""

import base64
import hashlib
import hmac
import re
import secrets
import time
from typing import Final

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings

# Argon2id Hasher configured strictly to C13-security-design.md v2.1.0 specifications:
# Memory: 64MB (65536 KiB), Time: 3 iterations, Parallelism: 4 threads, Salt: 16 bytes, Hash: 32 bytes
_ph: Final[PasswordHasher] = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# Pre-computed dummy Argon2id hash for constant-time mitigation when an email does not exist.
# Matches the identical parameter set ($argon2id$v=19$m=65536,t=3,p=4).
_DUMMY_ARGON2_HASH: Final[str] = (
    "$argon2id$v=19$m=65536,t=3,p=4$dGVzdF9kdW1teV9zYWx0"
    "$W5bC+mPqfH4W4bQ0XoE6D6p2K2x+O8R4L1V6e4T7r0M"
)


def hash_password(password: str) -> str:
    """Hashes a plaintext password using Argon2id.

    Never logs or persists the plaintext password.
    """
    return _ph.hash(password)


# Marker for accounts that have no password yet (invitation pending). Such a value can never
# match any input; verification still costs one Argon2id cycle so timing reveals nothing.
UNUSABLE_PASSWORD_PREFIX: Final[str] = "!"


def make_unusable_password() -> str:
    """Returns a password_hash value that no password can ever satisfy."""
    return UNUSABLE_PASSWORD_PREFIX + secrets.token_hex(32)


def has_usable_password(hashed_password: str | None) -> bool:
    return bool(hashed_password) and not hashed_password.startswith(UNUSABLE_PASSWORD_PREFIX)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against an Argon2id hash.

    Returns False safely on any mismatch, invalid format, or error. An unusable (invitation
    pending) hash is rejected after a dummy verification so it takes the same time as a mismatch.
    """
    if not has_usable_password(hashed_password):
        verify_dummy_password()
        return False
    try:
        return _ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def verify_dummy_password() -> None:
    """Executes a dummy Argon2id verification cycle.

    Mitigates timing attacks by consuming equivalent computation time
    when a requested administrator email does not exist.
    """
    try:
        _ph.verify(_DUMMY_ARGON2_HASH, "timing_attack_mitigation_constant_time")
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        pass  # Expected dummy verification failure for constant-time profile


def validate_password_policy(password: str) -> tuple[bool, str | None]:
    """Validates password strength against the EDEN BOUNTY security policy.

    Requirements:
    - Minimum length: defined in settings (12 characters).
    - At least one uppercase letter (A-Z).
    - At least one lowercase letter (a-z).
    - At least one decimal digit (0-9).
    - At least one special symbol.

    Returns (True, None) if compliant, or (False, failure_reason) if invalid.
    """
    min_length = settings.PASSWORD_MIN_LENGTH
    if len(password) < min_length:
        return False, f"Password must be at least {min_length} characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one digit."
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?`~]', password):
        return False, "Password must contain at least one special symbol."
    return True, None


def generate_session_token() -> str:
    """Generates a cryptographically secure random session token.

    Uses OS CSPRNG (48 bytes -> 64 URL-safe characters).
    Raw token is transmitted ONLY to the client via Set-Cookie.
    """
    return secrets.token_urlsafe(48)


def hash_session_token(raw_token: str) -> str:
    """Computes a SHA-256 digest of the raw session token.

    ONLY this digest is stored in the PostgreSQL `admin_sessions.id` column.
    Raw session tokens are NEVER stored in the database.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_link_token() -> str:
    """Generates a single-use invitation or password-reset token (256 bits from the OS CSPRNG).

    Only ``hash_session_token(token)`` (SHA-256) is stored; the raw value goes into the link only.
    """
    return secrets.token_urlsafe(32)


def generate_csrf_token() -> str:
    """Generates a cryptographically secure random per-session CSRF token.

    Uses OS CSPRNG (32 bytes -> 43 URL-safe characters).
    """
    return secrets.token_urlsafe(32)


def constant_time_compare(val_a: str, val_b: str) -> bool:
    """Constant-time string comparison to prevent timing leaks during CSRF verification."""
    return hmac.compare_digest(val_a.strip(), val_b.strip())


def generate_oauth_state(role: str, secret_key: str) -> str:
    """Generates an HMAC-signed state token containing nonce, role, and timestamp."""
    nonce = secrets.token_urlsafe(16)
    timestamp = str(int(time.time()))
    payload = f"{role}:{timestamp}:{nonce}"
    sig = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    token_bytes = f"{payload}.{sig}".encode("utf-8")
    return base64.urlsafe_b64encode(token_bytes).decode("ascii")


def verify_oauth_state(state: str, secret_key: str, max_age_seconds: int = 900) -> tuple[bool, str | None]:
    """Verifies HMAC signature, age, and returns (is_valid, role)."""
    try:
        raw = base64.urlsafe_b64decode(state.encode("ascii")).decode("utf-8")
        payload, sig = raw.rsplit(".", 1)
        expected_sig = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return False, None
        role, ts_str, _ = payload.split(":", 2)
        if time.time() - int(ts_str) > max_age_seconds:
            return False, None
        return True, role
    except Exception:
        return False, None
