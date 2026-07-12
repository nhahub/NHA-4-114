"""
dependencies.py
───────────────
Single source of truth for all FastAPI dependency injection.

Every router, WebSocket handler, and background task that needs a shared
resource (DB session, Redis client, settings) imports it from HERE — never
directly from db/session.py, core/redis.py, or config.py.

Why this matters
────────────────
- One import path to update if the underlying implementation changes
- Makes unit testing trivial: override a single dependency in the test client
- Matches the project_structure.md spec §1.1 (dependencies.py responsibility)

Available dependencies
──────────────────────
  get_db        → AsyncSession     (one per HTTP request, auto-commit / rollback)
  get_redis     → aioredis.Redis   (shared pool, do NOT close it in routes)
  get_settings  → Settings         (singleton, read-only config)
  get_ws_manager→ ConnectionManager (singleton WebSocket manager)
"""

from __future__ import annotations

from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

# ── Internal imports ──────────────────────────────────────────────────────────
from backend.app.config import Settings, settings as _settings
from backend.app.db.session import AsyncSessionLocal

# Redis pool is now owned by core/redis.py — import helpers from there.
from backend.app.core.redis import (
    get_redis_client,
    close_redis,          # re-exported so main.py keeps one import path
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Database session
# ─────────────────────────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a SQLAlchemy async session for the duration of one HTTP request.

    - Auto-commits on clean exit
    - Auto-rolls back on any exception
    - Always closes the session (returns connection to pool)

    Usage in a router:
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        # session.__aexit__ closes automatically — no explicit close() needed


# ─────────────────────────────────────────────────────────────────────────────
# 2. Redis client  (pool owned by core/redis.py)
# ─────────────────────────────────────────────────────────────────────────────

async def get_redis() -> aioredis.Redis:
    """
    Return the shared async Redis client (connection pool).

    Do NOT call .aclose() on the returned client inside a route — it is a
    shared pool managed by core/redis.py.  Shutdown is handled in main.py
    via close_redis().

    Usage in a router:
        @router.get("/live-count")
        async def live_count(redis: aioredis.Redis = Depends(get_redis)):
            value = await redis.get("camera:1:occupancy")
            ...
    """
    return await get_redis_client()

# close_redis is re-exported from core/redis.py above — main.py imports it
# from here so it never needs to know about core/redis.py directly.


# ─────────────────────────────────────────────────────────────────────────────
# 3. Settings (read-only config)
# ─────────────────────────────────────────────────────────────────────────────

def get_settings() -> Settings:
    """
    Return the application settings singleton.

    Useful for routes that need to read config values (e.g. MAX_FPS, DEBUG)
    without importing config.py directly, keeping routers decoupled.

    Usage in a router:
        @router.get("/config")
        async def get_config(cfg: Settings = Depends(get_settings)):
            return {"max_fps": cfg.MAX_FPS}
    """
    return _settings


# ─────────────────────────────────────────────────────────────────────────────
# 4. WebSocket ConnectionManager
# ─────────────────────────────────────────────────────────────────────────────

def get_ws_manager():
    """
    Return the singleton ConnectionManager instance.

    Avoids circular imports between main.py and websocket handlers by
    providing the manager through the dependency system.

    Usage in a WebSocket handler:
        from backend.app.websocket.manager import ConnectionManager
        async def camera_ws(
            websocket: WebSocket,
            camera_id: int,
            manager: ConnectionManager = Depends(get_ws_manager),
        ):
            await manager.connect(websocket, camera_id)
    """
    from backend.app.websocket.manager import manager
    return manager
