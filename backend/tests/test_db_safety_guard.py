"""Tests for the test-database safety guard (tests/db_safety.py and tests/conftest.py).

The suite's fixtures delete rows, so these tests prove it cannot be pointed at a development
or production database. The subprocess tests use an unreachable port: a refusal must happen
before any connection is attempted.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.db_safety import (
    UnsafeTestDatabaseError,
    assert_connected_to_test_database,
    assert_safe_test_database,
    database_name,
    is_test_database_name,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEV_URL = "postgresql+asyncpg://eb_db_user:secret-value@localhost:5433/eden_bounty_db"
TEST_URL = "postgresql+asyncpg://eb_db_user:secret-value@localhost:5433/eden_bounty_test"


@pytest.mark.parametrize(
    "name",
    ["eden_bounty_test", "eden_bounty_test_baseline", "test_eb", "eb-test-2", "test", "eb_tests"],
)
def test_names_recognised_as_test_databases(name: str):
    assert is_test_database_name(name)


@pytest.mark.parametrize(
    "name",
    ["eden_bounty_db", "eiden_bounty", "postgres", "production", "latest", "contest_db", "attestation", ""],
)
def test_names_refused_as_test_databases(name: str):
    assert not is_test_database_name(name)


@pytest.mark.parametrize("missing", [None, "", "   "])
def test_missing_test_database_url_is_refused(missing):
    with pytest.raises(UnsafeTestDatabaseError, match="TEST_DATABASE_URL is not set"):
        assert_safe_test_database(missing, application_url=DEV_URL, app_env="development")


def test_development_database_is_refused():
    with pytest.raises(UnsafeTestDatabaseError, match="not recognised as a test database"):
        assert_safe_test_database(DEV_URL, application_url=DEV_URL, app_env="development")


def test_production_style_database_is_refused():
    prod = "postgresql+asyncpg://eb_app:secret-value@db.example.internal:5432/postgres"
    with pytest.raises(UnsafeTestDatabaseError, match="not recognised as a test database"):
        assert_safe_test_database(prod, app_env="development")


def test_production_environment_is_refused_even_with_test_name():
    with pytest.raises(UnsafeTestDatabaseError, match="production"):
        assert_safe_test_database(TEST_URL, application_url=DEV_URL, app_env="production")


def test_same_database_as_application_is_refused():
    # Different driver prefix and credentials, same host/port/database
    app_url = "postgresql://other_user:other@LOCALHOST:5433/eden_bounty_test"
    with pytest.raises(UnsafeTestDatabaseError, match="same database the application uses"):
        assert_safe_test_database(TEST_URL, application_url=app_url, app_env="development")


def test_dedicated_test_database_is_accepted():
    assert assert_safe_test_database(f"  {TEST_URL} ", application_url=DEV_URL, app_env="development") == TEST_URL
    assert database_name(TEST_URL) == "eden_bounty_test"


def test_refusal_messages_never_contain_credentials():
    for url in (DEV_URL, TEST_URL):
        with pytest.raises(UnsafeTestDatabaseError) as excinfo:
            assert_safe_test_database(url, application_url=url, app_env="production" if url == TEST_URL else None)
        assert "secret-value" not in str(excinfo.value)


def test_connection_check_rejects_unexpected_database():
    with pytest.raises(UnsafeTestDatabaseError, match="Aborting before any destructive fixture"):
        assert_connected_to_test_database("eden_bounty_db", TEST_URL)
    assert_connected_to_test_database("eden_bounty_test", TEST_URL)


@pytest.mark.asyncio
async def test_this_session_is_connected_to_a_test_database(db_session: AsyncSession):
    """The running suite itself is on a database that passes the guard."""
    actual = (await db_session.execute(text("select current_database()"))).scalar_one()
    assert is_test_database_name(actual)
    assert actual == database_name(os.environ["DATABASE_URL"])


def _run_pytest_with(env_overrides: dict[str, str | None]) -> subprocess.CompletedProcess:
    """Runs a real pytest session for one harmless test under a modified environment."""
    env = {k: v for k, v in os.environ.items() if k not in {"TEST_DATABASE_URL", "DATABASE_URL", "APP_ENV"}}
    env["EB_TEST_ENV_FILE"] = str(BACKEND_DIR / "does-not-exist.env.test")  # ignore any local .env.test
    for key, value in env_overrides.items():
        if value is not None:
            env[key] = value
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-c", str(BACKEND_DIR / "pytest.ini"), str(BACKEND_DIR / "tests" / "test_health.py"), "-q", "-p", "no:cacheprovider"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        check=False,
        text=True,
        timeout=120,
    )


@pytest.mark.parametrize(
    ("overrides", "expected_text"),
    [
        ({}, "TEST_DATABASE_URL is not set"),
        # Port 1 is unreachable: the refusal must come from the guard, not from a connection error.
        ({"TEST_DATABASE_URL": "postgresql+asyncpg://u:p@127.0.0.1:1/eden_bounty_db"}, "not recognised as a test database"),
        ({"TEST_DATABASE_URL": "postgresql+asyncpg://u:p@127.0.0.1:1/eb_test", "APP_ENV": "production"}, "production"),
    ],
    ids=["no-test-database-configured", "development-database-name", "production-environment"],
)
def test_pytest_session_refuses_to_start_on_unsafe_database(overrides, expected_text):
    result = _run_pytest_with(overrides)
    output = result.stdout + result.stderr
    assert result.returncode == 4, output
    assert "REFUSING TO RUN TESTS" in output
    assert expected_text in output
    assert " passed" not in output and " failed" not in output
