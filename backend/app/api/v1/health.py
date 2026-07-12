"""
api/v1/health.py  — api-reference.md §7
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.config import settings
from backend.app.core.redis import get_redis_client

router = APIRouter()


class HealthOut(BaseModel):
    status: str
    database: str
    redis: str


@router.get("/", response_model=HealthOut)
async def health_check():
    import asyncpg

    db_status = "disconnected"
    redis_status = "disconnected"

    # ── Database ping ─────────────────────────────────────────────────────────
    try:
        conn = await asyncpg.connect(
            settings.POSTGRES_URL.replace("postgresql+asyncpg://", "postgresql://")
        )
        await conn.fetchval("SELECT 1")
        await conn.close()
        db_status = "connected"
    except Exception:
        pass

    # ── Redis ping via shared pool (core/redis.py) ────────────────────────────
    try:
        client = await get_redis_client()
        await client.ping()
        redis_status = "connected"
    except Exception:
        pass

    return HealthOut(status="ok", database=db_status, redis=redis_status)
