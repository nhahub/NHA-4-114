"""
event_worker.py
───────────────
Async consumer for the Smart Vision System that persists business events to the database.

Responsibilities:
  - Subscribe to Redis event channels (camera:*:events)
  - Parse JSON event payloads
  - Create and save Event objects to PostgreSQL
  - Run as a long-lived background service
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.db.session import AsyncSessionLocal
from backend.app.models.event import Event

logger = logging.getLogger(__name__)


async def run_event_worker(stop_event: asyncio.Event | None = None) -> None:
    """
    Main entry point for the event persistence worker.
    """
    if stop_event is None:
        stop_event = asyncio.Event()

    redis_client: aioredis.Redis = await aioredis.from_url(
        settings.REDIS_URL, encoding="utf-8", decode_responses=True
    )
    
    # Subscribe to ALL camera events
    pubsub = redis_client.pubsub()
    event_pattern = "camera:*:events"

    try:
        await pubsub.psubscribe(event_pattern)
        logger.info("[EventWorker] Subscribed to %s", event_pattern)

        while not stop_event.is_set():
            try:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is None:
                    continue

                data = message.get("data")
                if not data:
                    continue

                await _process_event_payload(data)

            except Exception as exc:
                logger.error("[EventWorker] Processing error: %s", exc, exc_info=True)
                await asyncio.sleep(1.0)

    except asyncio.CancelledError:
        logger.info("[EventWorker] Cancelled.")
    finally:
        await pubsub.punsubscribe(event_pattern)
        await pubsub.close()
        await redis_client.aclose()
        logger.info("[EventWorker] Stopped.")


async def _process_event_payload(payload_str: str) -> None:
    """Parse JSON and save to database."""
    try:
        data = json.loads(payload_str)
        
        camera_id = data.get("camera_id")
        event_type = data.get("type", "unknown")
        message = data.get("message", f"Event: {event_type}")
        ts_str = data.get("timestamp")
        
        if ts_str:
            # Handle float timestamp (unix) or ISO string
            if isinstance(ts_str, (int, float)):
                timestamp = datetime.fromtimestamp(ts_str, tz=timezone.utc)
            else:
                timestamp = datetime.fromisoformat(ts_str)
        else:
            timestamp = datetime.now(timezone.utc)

        async with AsyncSessionLocal() as db:
            new_event = Event(
                camera_id=camera_id,
                event_type=event_type,
                message=message,
                timestamp=timestamp
            )
            db.add(new_event)
            await db.commit()
            logger.info("[EventWorker] Persisted event: %s (camera=%s)", event_type, camera_id)

    except json.JSONDecodeError:
        logger.error("[EventWorker] Failed to decode JSON payload: %r", payload_str)
    except Exception as exc:
        logger.error("[EventWorker] Database persistence failed: %s", exc)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    )
    try:
        asyncio.run(run_event_worker())
    except KeyboardInterrupt:
        pass
