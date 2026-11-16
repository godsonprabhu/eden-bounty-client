"""Safety guard for the test suite's destructive database fixtures.

Many fixtures in this suite run ``DELETE FROM`` on enquiries, administrators, sessions and
audit logs to isolate tests. Pointed at a development or production database they would
destroy real data. This module decides whether a database may be used by the tests.

Rules (all must hold):
1. The test database must be named explicitly through ``TEST_DATABASE_URL``. The application's
   own ``DATABASE_URL`` / ``.env`` settings are never used as a fallback.
2. The database name must carry a standalone ``test`` marker, e.g. ``eden_bounty_test`` or
   ``test_eb``. Names such as ``eden_bounty_db``, ``postgres`` or ``latest`` are refused.
3. It must not be the same database the application is configured to use.
4. ``APP_ENV`` must not be ``production``.

The functions here are pure (no I/O, no imports from ``app``) so they can be unit-tested and
called before the application package is imported.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

TEST_DATABASE_ENV_VAR = "TEST_DATABASE_URL"

# "test" as a whole word within the name: eb_test, test_eb, eb-test-1, test. Not "latest" or "contest".
_TEST_MARKER = re.compile(r"(?:^|[_\-.])tests?(?:$|[_\-.])", re.IGNORECASE)

SETUP_HINT = (
    "Create a dedicated test database, migrate it, and point the tests at it:\n"
    "  createdb eden_bounty_test\n"
    "  DATABASE_URL=<url of eden_bounty_test> alembic upgrade head\n"
    "  export TEST_DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:<port>/eden_bounty_test\n"
    "or put TEST_DATABASE_URL in backend/.env.test (see backend/.env.test.example)."
)


class UnsafeTestDatabaseError(RuntimeError):
    """Raised when the configured database must not be used by destructive test fixtures."""


def database_name(url: str) -> str:
    """Returns the database name from a SQLAlchemy/PostgreSQL URL ('' if absent)."""
    return urlsplit(url).path.lstrip("/")


def _identity(url: str) -> tuple[str, int, str]:
    """(host, port, database) — enough to tell whether two URLs address the same database."""
    parts = urlsplit(url)
    return ((parts.hostname or "localhost").lower(), parts.port or 5432, database_name(url))


def is_test_database_name(name: str) -> bool:
    return bool(name) and bool(_TEST_MARKER.search(name))


def assert_safe_test_database(
    test_url: str | None,
    *,
    application_url: str | None = None,
    app_env: str | None = None,
) -> str:
    """Validates the explicitly configured test database and returns its URL.

    Raises UnsafeTestDatabaseError with an actionable message otherwise. Never includes
    credentials in the message.
    """
    if not test_url or not test_url.strip():
        raise UnsafeTestDatabaseError(
            f"{TEST_DATABASE_ENV_VAR} is not set. The test suite deletes rows from its database, "
            "so it refuses to fall back to the application's DATABASE_URL.\n" + SETUP_HINT
        )
    test_url = test_url.strip()

    if (app_env or "").strip().lower() == "production":
        raise UnsafeTestDatabaseError(
            "APP_ENV is 'production'. The test suite must never run in a production environment."
        )

    name = database_name(test_url)
    if not is_test_database_name(name):
        raise UnsafeTestDatabaseError(
            f"Database '{name or '<none>'}' is not recognised as a test database: its name must "
            "contain 'test' as a separate word (for example 'eden_bounty_test').\n" + SETUP_HINT
        )

    if application_url and _identity(application_url) == _identity(test_url):
        raise UnsafeTestDatabaseError(
            f"{TEST_DATABASE_ENV_VAR} points at the same database the application uses ('{name}'). "
            "Use a separate database for tests."
        )

    return test_url


def assert_connected_to_test_database(actual_name: str, expected_url: str) -> None:
    """Last line of defence: checks the database the engine really connected to."""
    expected = database_name(expected_url)
    if actual_name != expected or not is_test_database_name(actual_name):
        raise UnsafeTestDatabaseError(
            f"Connected to database '{actual_name}' but the approved test database is '{expected}'. "
            "Aborting before any destructive fixture runs."
        )
