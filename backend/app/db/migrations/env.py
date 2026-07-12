"""
db/migrations/env.py
────────────────────
Alembic environment for the Smart Vision System.

Uses asyncio mode (run_async_migrations) so it is compatible with the
async SQLAlchemy engine defined in db/session.py.

Auto-import: all ORM models are imported here so Alembic's autogenerate
can detect schema changes without the developer needing to import them
manually in each migration script.

Usage
─────
  Generate a migration:
      alembic revision --autogenerate -m "add zone polygon column"

  Apply migrations:
      alembic upgrade head

  Rollback one step:
      alembic downgrade -1
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── Load app config and Base ──────────────────────────────────────────────────
from backend.app.config import settings
from backend.app.db.session import Base

# ── Import ALL models so Base.metadata is fully populated ────────────────────
# Add every new model file here when it is created.
from backend.app.models.camera import Camera          # noqa: F401
from backend.app.models.event import Event            # noqa: F401
from backend.app.models.alert import Alert            # noqa: F401
from backend.app.models.zone import Zone              # noqa: F401

# ── Alembic config object ─────────────────────────────────────────────────────
config = context.config

# Override the sqlalchemy.url placeholder from alembic.ini with the real URL.
# This reads from the .env file via pydantic-settings — no credentials in VCS.
config.set_main_option(
    "sqlalchemy.url",
    # asyncpg driver is needed for the async engine; alembic uses it via
    # async_engine_from_config below.
    settings.POSTGRES_URL,
)

# Set up Python logging from the alembic.ini [loggers] section if present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support.
target_metadata = Base.metadata


# ─────────────────────────────────────────────────────────────────────────────
# Offline mode  (alembic upgrade head --sql → generates raw SQL)
# ─────────────────────────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """
    Run migrations without a live database connection.
    Produces raw SQL output suitable for review or DBA approval.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ─────────────────────────────────────────────────────────────────────────────
# Online / async mode  (normal migration execution)
# ─────────────────────────────────────────────────────────────────────────────

def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations inside a sync wrapper."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # NullPool: no persistent pool during migrations
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry-point called by Alembic in online mode."""
    asyncio.run(run_async_migrations())


# ── Dispatch ──────────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
