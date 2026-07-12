"""
db/session.py
─────────────
Async SQLAlchemy engine, session factory, and lifecycle helpers.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.POSTGRES_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """Create all tables (dev convenience; use Alembic for production migrations)."""
    async with engine.begin() as conn:
        from backend.app.models import camera, event, alert, zone  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
    logger.info("[DB] Tables initialised.")


async def close_db() -> None:
    await engine.dispose()
    logger.info("[DB] Engine disposed.")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a DB session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
