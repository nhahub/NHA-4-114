"""
websocket/manager.py
────────────────────
ConnectionManager for the Smart Vision System.

Responsibilities (Phase 1 refactor)
─────────────────────────────────────
  - Accept FastAPI WebSocket connections keyed by camera_id
  - Subscribe to Redis pub/sub channels via core/redis.new_pubsub_conn()
  - Broadcast arriving Redis messages to all connected dashboard clients
  - Handle disconnection cleanly without crashing the broadcast loop
  - One dedicated pub/sub connection per active camera (created lazily)

Changes from original
─────────────────────
  - Removed inline `aioredis.from_url()` inside _redis_listener()
  - Now delegates to core.redis.new_pubsub_conn() for all pub/sub connections
  - startup() no longer creates its own Redis client (shared pool in core/redis.py)

Data flow:
    Redis channel → _redis_listener() → broadcast() → WebSocket clients
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Dict, Set

from fastapi import WebSocket, WebSocketDisconnect

from backend.app.core.redis import new_pubsub_conn

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages all active WebSocket connections and their Redis subscriptions.
    """

    def __init__(self) -> None:
        # camera_id → set of connected WebSocket clients
        self._connections: Dict[str | int, Set[WebSocket]] = defaultdict(set)

        # camera_id → asyncio.Task running the Redis listener
        self._listener_tasks: Dict[str | int, asyncio.Task] = {}

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def startup(self) -> None:
        """
        Called once during FastAPI lifespan startup.
        Redis pool is managed by core/redis.py — nothing to open here.
        """
        logger.info("[WSManager] Ready (Redis pool managed by core/redis.py).")

    async def shutdown(self) -> None:
        """Called once during FastAPI lifespan shutdown."""
        for camera_id, task in list(self._listener_tasks.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._listener_tasks.clear()

        for camera_id, sockets in list(self._connections.items()):
            for ws in list(sockets):
                try:
                    await ws.close()
                except Exception:
                    pass
        self._connections.clear()

        logger.info("[WSManager] Shutdown complete.")

    # ── Public API ────────────────────────────────────────────────────────────

    async def connect(self, websocket: WebSocket, camera_id: int | str) -> None:
        """Accept a new WebSocket connection and start a Redis listener if needed."""
        await websocket.accept()
        self._connections[camera_id].add(websocket)
        logger.info(
            "[WSManager] Client connected — camera_id=%s total=%d",
            camera_id, len(self._connections[camera_id]),
        )
        await self._ensure_listener(camera_id)

    async def disconnect(self, websocket: WebSocket, camera_id: int | str) -> None:
        """Remove a WebSocket connection; stop Redis listener if no clients remain."""
        self._connections[camera_id].discard(websocket)
        logger.info(
            "[WSManager] Client disconnected — camera_id=%s remaining=%d",
            camera_id, len(self._connections[camera_id]),
        )
        if not self._connections[camera_id]:
            await self._stop_listener(camera_id)
            del self._connections[camera_id]

    async def broadcast_to_camera(self, camera_id: int | str, message: str) -> None:
        """Send a raw JSON string to every client subscribed to camera_id."""
        dead: list[WebSocket] = []
        for ws in list(self._connections.get(camera_id, [])):
            try:
                await ws.send_text(message)
            except (WebSocketDisconnect, Exception) as exc:
                logger.debug("[WSManager] Send error (%s): %s", camera_id, exc)
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws, camera_id)

    async def broadcast_alert(self, alert_payload: str) -> None:
        """Broadcast an alert to ALL connected clients (all cameras + /ws/alerts)."""
        for camera_id, sockets in list(self._connections.items()):
            for ws in list(sockets):
                try:
                    await ws.send_text(alert_payload)
                except Exception:
                    pass

    # ── Redis listener management ─────────────────────────────────────────────

    async def _ensure_listener(self, camera_id: int | str) -> None:
        """Start a Redis listener for camera_id if one is not already running."""
        existing = self._listener_tasks.get(camera_id)
        if existing and not existing.done():
            return

        task = asyncio.create_task(
            self._redis_listener(camera_id),
            name=f"redis-listener-{camera_id}",
        )
        self._listener_tasks[camera_id] = task
        logger.debug("[WSManager] Listener started — camera_id=%s", camera_id)

    async def _stop_listener(self, camera_id: int | str) -> None:
        task = self._listener_tasks.pop(camera_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        logger.debug("[WSManager] Listener stopped — camera_id=%s", camera_id)

    async def _redis_listener(self, camera_id: int | str) -> None:
        """
        Long-running coroutine. Subscribes to frame + alert channels for
        camera_id and forwards messages to connected WebSocket clients.

        Uses core/redis.new_pubsub_conn() for an isolated connection so
        this listener does not interfere with the shared publish pool.
        """
        from backend.app.workers.camera_worker import camera_channel, alert_channel

        frame_ch = camera_channel(camera_id)
        alert_ch = alert_channel(camera_id)

        pubsub = await new_pubsub_conn()

        try:
            await pubsub.subscribe(frame_ch, alert_ch)
            logger.info(
                "[WSManager] Subscribed — channels: %s, %s", frame_ch, alert_ch
            )

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                data: str = message["data"]
                channel: str = message["channel"]

                if channel == frame_ch:
                    await self.broadcast_to_camera(camera_id, data)
                elif channel == alert_ch:
                    await self.broadcast_alert(data)

        except asyncio.CancelledError:
            logger.info("[WSManager] Listener cancelled — camera_id=%s", camera_id)
        except Exception as exc:
            logger.exception(
                "[WSManager] Listener error — camera_id=%s: %s", camera_id, exc
            )
        finally:
            try:
                await pubsub.unsubscribe(frame_ch, alert_ch)
                await pubsub.aclose()
            except Exception:
                pass
            logger.debug("[WSManager] Listener cleaned up — camera_id=%s", camera_id)

    # ── Debug helpers ─────────────────────────────────────────────────────────

    @property
    def active_cameras(self) -> list:
        return list(self._connections.keys())

    def client_count(self, camera_id: int | str) -> int:
        return len(self._connections.get(camera_id, set()))


# ── Module-level singleton ─────────────────────────────────────────────────────
manager = ConnectionManager()
