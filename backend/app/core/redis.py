"""
core/redis.py
─────────────
Centralised async Redis connection management for the Smart Vision System.

Rules
─────
- ONE connection pool shared by the entire FastAPI process (publish, get, set).
- ONE separate pub/sub connection per camera listener (subscribe channels are
  stateful; mixing them with the publish pool causes message-routing bugs).
- No other file creates aioredis clients directly — import helpers from here.

Public API
──────────
  get_redis_client()   → shared aioredis.Redis   (publish / get / set)
  close_redis()        → call once at app shutdown
  publish_json()       → convenience: json.dumps + publish in one call
  new_pubsub_conn()    → create a fresh dedicated pub/sub connection
                         (used by websocket/manager.py per-listener)
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from backend.app.config import settings

logger = logging.getLogger(__name__)

# ── Shared publish/command pool ───────────────────────────────────────────────
# Created lazily on first call so the module is safe to import before the
# event loop is running (e.g. during Celery worker boot).

_pool: aioredis.Redis | None = None


async def get_redis_client() -> aioredis.Redis:
    """
    Return (or lazily create) the shared async Redis client.

    Thread-safety note: FastAPI/uvicorn run in a single asyncio event loop,
    so the global assignment is race-free for normal API usage.

    DO NOT call .aclose() on the returned client — it is shared.
    Call close_redis() exactly once during application shutdown.
    """
    global _pool
    if _pool is None:
        _pool = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
        logger.info("[Redis] Connection pool created — %s", settings.REDIS_URL)
    return _pool


async def close_redis() -> None:
    """
    Close the shared Redis pool gracefully.

    Called once in FastAPI lifespan shutdown (main.py).
    Safe to call even if get_redis_client() was never invoked.
    """
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
        logger.info("[Redis] Connection pool closed.")


async def publish_json(channel: str, payload: dict[str, Any]) -> None:
    """
    Serialize *payload* to JSON and publish it to *channel*.

    Convenience wrapper so callers never do json.dumps manually before publish.

    Parameters
    ----------
    channel : Redis pub/sub channel name
    payload : dict to serialize — must be JSON-serialisable
    """
    client = await get_redis_client()
    message = json.dumps(payload, default=str)   # default=str handles datetime etc.
    await client.publish(channel, message)


async def new_pubsub_conn() -> aioredis.client.PubSub:
    """
    Create a *fresh* dedicated pub/sub connection.

    Each long-running listener (websocket/manager.py) must own its own
    PubSub object — sharing one pub/sub connection across multiple asyncio
    tasks causes messages to be consumed by whichever coroutine calls
    .listen() first and never reach the others.

    The CALLER is responsible for calling:
        await pubsub.unsubscribe(...)
        await pubsub.close()
        await conn.aclose()          ← the returned conn, not _pool

    Returns
    -------
    pubsub : aioredis PubSub handle (already connected, not yet subscribed)
    """
    conn: aioredis.Redis = await aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    return conn.pubsub()
