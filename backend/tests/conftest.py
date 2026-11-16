"""Pytest configuration and shared async fixtures for EDEN BOUNTY test suite.

DATABASE SAFETY: fixtures in this suite delete rows (enquiries, administrators, sessions,
audit logs). Before the application is imported, this file requires an explicitly named test
database (TEST_DATABASE_URL) and refuses anything that looks like a development or production
database. See tests/db_safety.py for the rules.
"""

import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from dotenv import dotenv_values

from tests.db_safety import (
    TEST_DATABASE_ENV_VAR,
    UnsafeTestDatabaseError,
    assert_connected_to_test_database,
    assert_safe_test_database,
)

_BACKEND_DIR = Path(__file__).resolve().parents[1]


def _resolve_test_database_url() -> str:
    """Finds and validates the explicit test database, or stops the whole session.

    Sources, in order: the TEST_DATABASE_URL environment variable, then backend/.env.test
    (path overridable with EB_TEST_ENV_FILE). The application's own settings are only read to
    make sure the test database is a different one.
    """
    env_file = Path(os.environ.get("EB_TEST_ENV_FILE", _BACKEND_DIR / ".env.test"))
    test_url = os.environ.get(TEST_DATABASE_ENV_VAR)
    if not test_url and env_file.is_file():
        test_url = dotenv_values(env_file).get(TEST_DATABASE_ENV_VAR)

    app_env_file = dotenv_values(_BACKEND_DIR / ".env") if (_BACKEND_DIR / ".env").is_file() else {}
    application_url = os.environ.get("DATABASE_URL") or app_env_file.get("DATABASE_URL")
    app_env = os.environ.get("APP_ENV") or app_env_file.get("APP_ENV")

    try:
        return assert_safe_test_database(test_url, application_url=application_url, app_env=app_env)
    except UnsafeTestDatabaseError as exc:
        pytest.exit(f"\nREFUSING TO RUN TESTS — unsafe database configuration.\n{exc}\n", returncode=4)


# Must happen before anything imports `app`, because the engine is created from settings at import.
TEST_DATABASE_URL = _resolve_test_database_url()
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.core.config import settings
from app.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Session-scoped async SQLAlchemy engine with NullPool.

    Verifies the live connection is the approved test database before yielding, so no
    destructive fixture can run against anything else.
    """
    engine = create_async_engine(
        settings.async_database_url,
        echo=False,
        poolclass=NullPool,
    )
    try:
        async with engine.connect() as conn:
            actual_name = (await conn.execute(text("select current_database()"))).scalar_one()
        assert_connected_to_test_database(actual_name, TEST_DATABASE_URL)
    except UnsafeTestDatabaseError as exc:
        await engine.dispose()
        pytest.exit(f"\nREFUSING TO RUN TESTS — {exc}\n", returncode=4)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _reset_login_failure_throttle():
    """The in-memory sign-in and reset throttles are process-wide; isolate them between tests."""
    from app.core.login_throttle import login_failure_throttle, password_reset_throttle

    await login_failure_throttle.reset()
    await password_reset_throttle.reset()
    yield
    await login_failure_throttle.reset()
    await password_reset_throttle.reset()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Function-scoped async session for database operations."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.close()


@pytest_asyncio.fixture(scope="session")
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for testing FastAPI endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
