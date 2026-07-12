"""
websocket/handlers.py
─────────────────────
WebSocket route handler functions for the Smart Vision System.

Extracted from main.py so the app factory stays clean.

Each handler is a plain async function that accepts a WebSocket and
the ConnectionManager (via dependency injection). main.py registers
them as @app.websocket() routes and passes manager via Depends().

Handlers:
  handle_camera_stream(websocket, camera_id, manager)  → /ws/cameras/{id}
  handle_alerts_stream(websocket, manager)              → /ws/alerts

STRICT: No Redis access here. No AI logic. Pure connection lifecycle.
"""

from __future__ import annotations

import logging

from fastapi import WebSocket, WebSocketDisconnect

from backend.app.websocket.manager import ConnectionManager

logger = logging.getLogger(__name__)


async def handle_camera_stream(
    websocket: WebSocket,
    camera_id: int,
    manager: ConnectionManager,
) -> None:
    """
    Handle a single /ws/cameras/{camera_id} connection lifecycle.

    Flow:
      1. Register the WebSocket with ConnectionManager (triggers Redis listener)
      2. Block on receive_text() — this keeps the connection open and detects
         client disconnection (browser close / network drop)
      3. On disconnect: unregister from ConnectionManager

    The actual data push happens inside ConnectionManager._redis_listener()
    which reads from Redis and calls broadcast_to_camera() — this handler
    only manages the connection lifecycle.

    Message schema received by the browser (api-reference.md §8.1):
    {
        "camera_id": int,
        "timestamp": "ISO-8601",
        "frame":     "base64-jpeg",
        "occupancy": int,
        "tracks":    [{"track_id": int, "bbox": [x, y, w, h]}]
    }
    """
    await manager.connect(websocket, camera_id)
    logger.info("[WS] /ws/cameras/%s — connection opened", camera_id)

    try:
        while True:
            # receive_text() blocks until the client sends a message or closes.
            # We don't process incoming messages in this version; the call exists
            # solely to detect disconnection (WebSocketDisconnect).
            await websocket.receive_text()

    except WebSocketDisconnect:
        logger.info("[WS] /ws/cameras/%s — client disconnected", camera_id)

    except Exception as exc:
        logger.warning("[WS] /ws/cameras/%s — unexpected error: %s", camera_id, exc)

    finally:
        await manager.disconnect(websocket, camera_id)


async def handle_alerts_stream(
    websocket: WebSocket,
    manager: ConnectionManager,
) -> None:
    """
    Handle a single /ws/alerts connection lifecycle.

    This endpoint receives alerts from ALL cameras. The manager broadcasts
    to the virtual "alerts" key which was subscribed to all camera alert
    channels during ConnectionManager.broadcast_alert().

    Message schema received by the browser (api-reference.md §8.2):
    {
        "camera_id": int,
        "type":      "zone_overcrowding" | "loitering" | "crossing_event",
        "severity":  "high" | "medium" | "low",
        "message":   str,
        "timestamp": "ISO-8601",
        "metadata":  { … }
    }
    """
    await manager.connect(websocket, "alerts")
    logger.info("[WS] /ws/alerts — connection opened")

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        logger.info("[WS] /ws/alerts — client disconnected")

    except Exception as exc:
        logger.warning("[WS] /ws/alerts — unexpected error: %s", exc)

    finally:
        await manager.disconnect(websocket, "alerts")
