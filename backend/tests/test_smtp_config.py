"""Focused configuration tests for SMTP_ENABLED safety boundaries.

Phase C13.5 — Step 5.1.2: SMTP Local Environment Safety Correction.
Guarantees:
1. Default SMTP_ENABLED evaluates to False.
2. In local development or automated test environments, SMTP dispatch cannot be enabled,
   even if SMTP_ENABLED=True is supplied via environment variables or settings parameters.
3. If the environment cannot be reliably identified, it fails safely rather than assuming production.
4. Production configuration parsing remains fully supported without enabling SMTP automatically.
5. In verified production, enabling SMTP strictly requires non-empty credentials.
6. Zero live network connections or database operations occur.
"""

import pytest
from app.core.config import Settings
from pydantic import ValidationError


def test_smtp_default_is_disabled():
    """Verifies that SMTP_ENABLED strictly defaults to False."""
    settings = Settings(APP_ENV="development")
    assert settings.SMTP_ENABLED is False
    assert settings.SMTP_HOST == "smtp.hostinger.com"
    assert settings.SMTP_PORT == 465
    assert settings.SMTP_USE_SSL is True
    assert settings.OPERATIONS_NOTIFY_EMAIL == "info@edenbounty.org"
    assert settings.is_production is False


def test_local_environment_with_smtp_enabled_true():
    """Verifies that local development unconditionally clamps SMTP_ENABLED to False."""
    # Test standard 'development'
    settings_dev = Settings(APP_ENV="development", SMTP_ENABLED=True)
    assert settings_dev.SMTP_ENABLED is False
    assert settings_dev.is_production is False

    # Test alias 'local'
    settings_local = Settings(APP_ENV="local", SMTP_ENABLED=True)
    assert settings_local.SMTP_ENABLED is False
    assert settings_local.is_production is False

    # Test alias 'dev'
    settings_short = Settings(APP_ENV="dev", SMTP_ENABLED=True)
    assert settings_short.SMTP_ENABLED is False
    assert settings_short.is_production is False


def test_test_environment_with_smtp_enabled_true():
    """Verifies that automated test environments unconditionally clamp SMTP_ENABLED to False."""
    # Test standard 'test'
    settings_test = Settings(APP_ENV="test", SMTP_ENABLED=True)
    assert settings_test.SMTP_ENABLED is False
    assert settings_test.is_production is False

    # Test alias 'testing'
    settings_testing = Settings(APP_ENV="testing", SMTP_ENABLED=True)
    assert settings_testing.SMTP_ENABLED is False
    assert settings_testing.is_production is False


def test_unidentifiable_environment_fails_safely():
    """Verifies that unrecognized environments fail safely and never assume production."""
    # Empty string environment
    settings_empty = Settings(APP_ENV="", SMTP_ENABLED=True)
    assert settings_empty.SMTP_ENABLED is False
    assert settings_empty.is_production is False

    # Unknown environment name
    settings_unknown = Settings(APP_ENV="custom_staging_zone", SMTP_ENABLED=True)
    assert settings_unknown.SMTP_ENABLED is False
    assert settings_unknown.is_production is False


# A production configuration that passes the production startup guard, so these tests
# exercise SMTP parsing rather than the unrelated DEBUG/CORS/database checks.
PRODUCTION_BASE = {
    "DEBUG": False,
    "CORS_ORIGINS": ["https://edenbounty.org"],
    "DATABASE_URL": "postgresql+asyncpg://eb_app:strong-unique-secret@db.example.internal:5432/eb",
    "PUBLIC_SITE_URL": "https://edenbounty.org",
}


def test_production_parsing_without_enabling_smtp_automatically():
    """Verifies that production environment does not enable SMTP automatically."""
    # Production without explicit SMTP_ENABLED
    settings_prod_default = Settings(APP_ENV="production", **PRODUCTION_BASE)
    assert settings_prod_default.is_production is True
    assert settings_prod_default.SMTP_ENABLED is False

    # Production with explicit SMTP_ENABLED=False
    settings_prod_disabled = Settings(APP_ENV="production", SMTP_ENABLED=False, **PRODUCTION_BASE)
    assert settings_prod_disabled.is_production is True
    assert settings_prod_disabled.SMTP_ENABLED is False


def test_production_missing_smtp_credentials():
    """Verifies that enabling SMTP in production strictly requires credentials."""
    # Both credentials empty
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            APP_ENV="production",
            SMTP_ENABLED=True,
            SMTP_USER="",
            SMTP_PASSWORD="",
        )
    assert "SMTP credentials" in str(exc_info.value)

    # Missing password only
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            APP_ENV="production",
            SMTP_ENABLED=True,
            SMTP_USER="valid_user@edenbounty.org",
            SMTP_PASSWORD="",
        )
    assert "SMTP credentials" in str(exc_info.value)

    # Missing user only
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            APP_ENV="production",
            SMTP_ENABLED=True,
            SMTP_USER="",
            SMTP_PASSWORD="valid_password",
        )
    assert "SMTP credentials" in str(exc_info.value)


def test_production_valid_configuration_parsing():
    """Verifies that valid production configuration parses cleanly without network calls."""
    settings_prod_valid = Settings(
        APP_ENV="production",
        **PRODUCTION_BASE,
        SMTP_ENABLED=True,
        SMTP_USER="smtp-delivery@edenbounty.org",
        SMTP_PASSWORD="production_transport_secret_only",
    )
    assert settings_prod_valid.is_production is True
    assert settings_prod_valid.SMTP_ENABLED is True
    assert settings_prod_valid.SMTP_HOST == "smtp.hostinger.com"
    assert settings_prod_valid.SMTP_PORT == 465
    assert settings_prod_valid.SMTP_USE_SSL is True
