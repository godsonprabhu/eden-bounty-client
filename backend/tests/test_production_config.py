"""Production configuration guard tests (deployment readiness)."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

SAFE = {
    "APP_ENV": "production",
    "DEBUG": False,
    "CORS_ORIGINS": ["https://edenbounty.org", "https://www.edenbounty.org"],
    "DATABASE_URL": "postgresql+asyncpg://eb_app:strong-unique-secret@db.example.internal:5432/postgres",
    "PUBLIC_SITE_URL": "https://edenbounty.org",
}


def build(**overrides):
    return Settings(_env_file=None, **{**SAFE, **overrides})


def test_safe_production_settings_load():
    s = build()
    assert s.is_production
    assert s.session_cookie_secure is True


@pytest.mark.parametrize(
    "overrides, fragment",
    [
        ({"DEBUG": True}, "DEBUG must be false"),
        ({"CORS_ORIGINS": ["*"]}, "wildcards"),
        ({"CORS_ORIGINS": ["http://edenbounty.org"]}, "https://"),
        ({"CORS_ORIGINS": ["https://localhost:3000"]}, "local addresses"),
        ({"CORS_ORIGINS": []}, "must list"),
        ({"SESSION_COOKIE_SECURE_OVERRIDE": False}, "Secure cookie"),
        ({"SESSION_COOKIE_SAMESITE": "none"}, "SAMESITE"),
        ({"DATABASE_URL": None}, "development defaults"),
        ({"DATABASE_URL": "postgresql://u:CHANGE_ME_LOCAL_DEVELOPMENT_PASSWORD@h/db"}, "placeholder"),
        ({"WORKERS": 2}, "WORKERS must be 1"),
        ({"PUBLIC_SITE_URL": "http://localhost:3000"}, "PUBLIC_SITE_URL"),
        ({"PUBLIC_SITE_URL": "http://edenbounty.org"}, "PUBLIC_SITE_URL"),
        ({"DOCUMENT_SCAN_MODE": "maybe"}, "DOCUMENT_SCAN_MODE"),
    ],
)
def test_unsafe_production_settings_rejected(overrides, fragment):
    with pytest.raises(ValidationError) as exc:
        build(**overrides)
    assert fragment in str(exc.value)


def test_development_is_not_restricted():
    s = Settings(_env_file=None, APP_ENV="development", DEBUG=True, CORS_ORIGINS=["http://localhost:3001"])
    assert not s.is_production
    assert s.session_cookie_secure is False


def test_prod_alias_enables_secure_cookie():
    assert build(APP_ENV="prod").session_cookie_secure is True
