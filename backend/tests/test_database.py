"""Tests for Database Connection, Session Management, and Safe Failures."""

import pytest
from app.db.session import check_database_connection
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool


@pytest.mark.asyncio
async def test_database_connectivity_check():
    """Verify check_database_connection() returns True against live PostgreSQL."""
    is_connected = await check_database_connection()
    assert is_connected is True


@pytest.mark.asyncio
async def test_sqlalchemy_session_execution(db_session: AsyncSession):
    """Verify async SQLAlchemy session can execute queries."""
    result = await db_session.execute(text("SELECT 1 AS num"))
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_invalid_database_url_fails_safely():
    """Verify that an invalid database configuration fails safely without crashing."""
    bad_engine = create_async_engine(
        "postgresql+asyncpg://invalid_user:invalid_pass@127.0.0.1:59999/nonexistent_db",
        poolclass=NullPool,
    )
    try:
        async with bad_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        assert False, "Should have raised an exception"
    except Exception as exc:  # noqa: BLE001
        # Fails safely with connection refused / error
        assert "59999" in str(exc) or "Connect call failed" in str(exc) or "refused" in str(exc).lower()
    finally:
        await bad_engine.dispose()
