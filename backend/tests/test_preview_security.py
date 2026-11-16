"""Security regression and verification test suite for temporary preview environments.

Covers:
1. Origin validation: authorized preview origins allowed, unauthorized origins rejected, wildcards rejected.
2. Verification secrets: public registration and resend endpoints never disclose tokens/links.
3. Session cookies: HTTPS preview origins enforce Secure=True, HttpOnly=True, SameSite=lax.
4. Proxy IP handling: resistance to X-Forwarded-For and CF-Connecting-IP spoofing.
5. Role authorization: public signup restricted to CUSTOMER/INVESTOR; ADMIN/SUPER_ADMIN rejected.
"""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.deps import validate_request_origin
from app.core.config import Settings, settings
from app.core.rate_limit import get_client_ip
from app.models.admin import AdminRole, AdminUser
from app.models.portal import PORTAL_ROLE_CUSTOMER, PORTAL_ROLE_INVESTOR
from app.schemas.auth import RegisterRequest, RegisterResponseData
from app.schemas.portal import PortalUserPublic
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.datastructures import Headers
from starlette.requests import Request

# ==============================================================================
# 1. Origin Validation & Cloudflare Preview Origin
# ==============================================================================


def test_preview_origin_exact_allowed():
    """Exact preview origin is added to all_allowed_origins and validated."""
    cfg = Settings(
        APP_ENV="development",
        PREVIEW_ORIGIN="https://preview-client-abc.trycloudflare.com",
    )
    assert "https://preview-client-abc.trycloudflare.com" in cfg.all_allowed_origins
    assert cfg.PREVIEW_ORIGIN == "https://preview-client-abc.trycloudflare.com"


def test_preview_origin_wildcard_rejected():
    """Wildcards are forbidden in PREVIEW_ORIGIN to prevent trusting arbitrary tunnel subdomains."""
    with pytest.raises(ValidationError, match="must not contain wildcards"):
        Settings(
            APP_ENV="development",
            PREVIEW_ORIGIN="https://*.trycloudflare.com",
        )


def test_preview_origin_non_http_rejected():
    """Non-HTTP(S) schemes are rejected in PREVIEW_ORIGIN."""
    with pytest.raises(ValidationError, match="must start with https:// or http://"):
        Settings(
            APP_ENV="development",
            PREVIEW_ORIGIN="ftp://preview.trycloudflare.com",
        )


def test_validate_request_origin_accepts_authorized_preview(monkeypatch):
    """validate_request_origin accepts requests originating from PREVIEW_ORIGIN."""
    preview = "https://preview-approved.trycloudflare.com"
    monkeypatch.setattr(settings, "PREVIEW_ORIGIN", preview)

    req = Request(
        scope={
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": [(b"origin", preview.encode("utf-8"))],
        }
    )
    # Must not raise
    validate_request_origin(req)


def test_validate_request_origin_rejects_arbitrary_unauthorized(monkeypatch):
    """validate_request_origin rejects requests originating from unauthorized domains."""
    preview = "https://preview-approved.trycloudflare.com"
    monkeypatch.setattr(settings, "PREVIEW_ORIGIN", preview)

    req = Request(
        scope={
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": [(b"origin", b"https://arbitrary-attacker.trycloudflare.com")],
        }
    )
    with pytest.raises(HTTPException) as exc_info:
        validate_request_origin(req)
    assert exc_info.value.status_code == 403
    assert "Request origin not permitted by security policy" in exc_info.value.detail


# ==============================================================================
# 2. Token & Verification Secrets Non-Disclosure
# ==============================================================================


def test_register_response_schema_never_exposes_token():
    """RegisterResponseData defaults verification_link to None and omits secret tokens."""
    dummy_user = PortalUserPublic(
        id=uuid4(),
        email="client@example.com",
        role="CUSTOMER",
        full_name="Client Test",
    )
    data = RegisterResponseData(
        user=dummy_user,
        delivery="MANUAL",
        message="Account created successfully.",
    )
    dumped = data.model_dump()
    assert dumped.get("verification_link") is None
    assert "token" not in dumped


# ==============================================================================
# 3. Session Security & Cookie Attributes
# ==============================================================================


def test_session_cookie_secure_under_https_preview():
    """When PREVIEW_ORIGIN is an HTTPS URL, session_cookie_secure is True even in dev mode."""
    cfg = Settings(
        APP_ENV="development",
        PREVIEW_ORIGIN="https://preview.trycloudflare.com",
    )
    assert cfg.session_cookie_secure is True
    assert cfg.SESSION_COOKIE_HTTPONLY is True
    assert cfg.SESSION_COOKIE_SAMESITE == "lax"


def test_session_cookie_secure_override_respected():
    """SESSION_COOKIE_SECURE_OVERRIDE explicitly overrides auto-detection."""
    cfg = Settings(
        APP_ENV="development",
        PREVIEW_ORIGIN="https://preview.trycloudflare.com",
        SESSION_COOKIE_SECURE_OVERRIDE=False,
    )
    assert cfg.session_cookie_secure is False


# ==============================================================================
# 4. Trusted Proxy & Rate Limiting (IP Spoofing Resistance)
# ==============================================================================


def test_proxy_ip_spoofing_resistance_untrusted_peer():
    """An untrusted direct client sending X-Forwarded-For cannot spoof its client IP."""
    req = MagicMock(spec=Request)
    req.client = MagicMock()
    req.client.host = "198.51.100.22"  # Public untrusted client
    req.headers = Headers({"x-forwarded-for": "10.0.0.1, 1.1.1.1"})

    ip = get_client_ip(req)
    # The client IP must be the immediate connection IP, not the forwarded header
    assert ip == "198.51.100.22"


def test_proxy_ip_forwarding_from_trusted_proxy():
    """A trusted local proxy (127.0.0.1) forwarding X-Forwarded-For is unwrapped correctly."""
    req = MagicMock(spec=Request)
    req.client = MagicMock()
    req.client.host = "127.0.0.1"  # In TRUSTED_PROXIES
    req.headers = Headers({"x-forwarded-for": "203.0.113.195, 127.0.0.1"})

    ip = get_client_ip(req)
    assert ip == "203.0.113.195"


def test_cf_connecting_ip_untrusted_without_cloudflare_peer(monkeypatch):
    """CF-Connecting-IP is ignored if the immediate peer is not a recognized Cloudflare proxy."""
    monkeypatch.setattr(settings, "TRUSTED_CLOUDFLARE_PROXIES", ["173.245.48.0/20"])

    req = MagicMock(spec=Request)
    req.client = MagicMock()
    req.client.host = "198.51.100.99"  # Untrusted peer
    req.headers = Headers({"cf-connecting-ip": "8.8.8.8"})

    ip = get_client_ip(req)
    assert ip == "198.51.100.99"


# ==============================================================================
# 5. Role Authorization & Signup Boundaries
# ==============================================================================


def test_signup_accepts_customer_and_investor():
    """Public registration schema accepts valid CUSTOMER and INVESTOR roles."""
    c = RegisterRequest(
        role="CUSTOMER",
        full_name="Valid Customer",
        email="customer@example.com",
        password="StrongPassword123!@#",
    )
    assert c.role == "CUSTOMER"

    inv = RegisterRequest(
        role="INVESTOR",
        full_name="Valid Investor",
        email="investor@example.com",
        password="StrongPassword123!@#",
    )
    assert inv.role == "INVESTOR"


def test_signup_rejects_admin_role():
    """Public registration strictly rejects ADMIN, SUPER_ADMIN or arbitrary roles."""
    with pytest.raises(ValidationError):
        RegisterRequest(
            role="ADMIN",  # type: ignore[arg-type]
            full_name="Attacker",
            email="admin@example.com",
            password="StrongPassword123!@#",
        )

    with pytest.raises(ValidationError):
        RegisterRequest(
            role="SUPER_ADMIN",  # type: ignore[arg-type]
            full_name="Attacker",
            email="superadmin@example.com",
            password="StrongPassword123!@#",
        )


def test_admin_portal_role_access_boundary():
    """OPERATIONS_ADMIN can access CUSTOMER records but is strictly forbidden from INVESTOR records."""
    from app.api.v1.endpoints.admin_portal import _require_role_access

    ops_admin = AdminUser(
        email="ops@edenbounty.org",
        first_name="Ops",
        last_name="Admin",
        roles=[AdminRole(id="OPERATIONS_ADMIN", name="Operations Administrator")],
    )

    # Allowed for customer
    _require_role_access(ops_admin, PORTAL_ROLE_CUSTOMER)

    # Forbidden for investor
    with pytest.raises(HTTPException) as exc:
        _require_role_access(ops_admin, PORTAL_ROLE_INVESTOR)
    assert exc.value.status_code == 403
    assert "SUPER_ADMIN" in exc.value.detail


# ==============================================================================
# 6. Administrative CLI & Verification Tools
# ==============================================================================


@pytest.mark.asyncio
async def test_verify_account_cli_rejects_invalid_email():
    """verify_account_cli validates email format before database execution."""
    from app.cli.verify_account import verify_account_cli

    mock_session = MagicMock()
    code = await verify_account_cli(mock_session, "not-an-email")
    assert code == 1


@pytest.mark.asyncio
async def test_verify_account_cli_user_not_found():
    """verify_account_cli returns error code 1 when user does not exist."""
    from unittest.mock import AsyncMock

    from app.cli.verify_account import verify_account_cli

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    code = await verify_account_cli(mock_session, "nonexistent@example.com")
    assert code == 1

