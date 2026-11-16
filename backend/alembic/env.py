import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.db.base import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set model MetaData object for 'autogenerate' support
target_metadata = Base.metadata

# Override URL with application configuration.
# ConfigParser treats "%" as interpolation syntax, so escape it: URL-encoded passwords
# (e.g. "p%40ss") would otherwise crash Alembic before connecting.
config.set_main_option("sqlalchemy.url", settings.async_database_url.replace("%", "%%"))

# Revisions moved out of the active graph to backend/alembic/deferred/ (see README there).
# They were never applied to any environment. If a database nevertheless carries one of them,
# stop instead of silently migrating it along a different path.
DEFERRED_REVISIONS = frozenset(
    {"0003_v43_0_0", "0004_optional_enquiry_contact_number", "0006_merge_contact_branches"}
)


def assert_no_deferred_revisions(connection: Connection) -> None:
    from sqlalchemy import inspect, text

    try:
        if not inspect(connection).has_table("alembic_version"):
            return
        applied = {row[0] for row in connection.execute(text("SELECT version_num FROM alembic_version"))}
    finally:
        # End the read-only transaction this check auto-began. Otherwise Alembic treats the
        # connection as externally managed and never commits the migration (silent no-op).
        connection.rollback()
    found = applied & DEFERRED_REVISIONS
    if found:
        raise RuntimeError(
            "Database is stamped with deferred migration revision(s) "
            f"{sorted(found)}. These are not part of the authoritative migration path "
            "(0001 -> 0002 -> 0005 -> 0007 -> 0008 -> 0009). "
            "See backend/alembic/deferred/README.md before proceeding."
        )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    assert_no_deferred_revisions(connection)
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with asyncpg."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
