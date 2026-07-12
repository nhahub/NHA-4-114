"""
inference_worker.py
───────────────────
AI inference worker — separates inference execution from frame capture.

Architecture position
─────────────────────
  Phase 2 (current): camera_worker.py runs both capture + inference in one loop.
                     This file provides the scalability-level-2 split.

  Phase 2 dev mode  → camera_worker runs capture + inline inference (default)
  Phase 2 GPU mode  → camera_worker publishes raw frames to Redis
                      inference_worker consumes them, runs pipeline, publishes results

Data flow (GPU mode)
────────────────────
  camera_worker → camera:{id}:raw_frames → inference_worker
                                         ↓
                            AI pipeline (GPU node)
                                         ↓
                   camera:{id}:frames  +  camera:{id}:alerts → WebSocket + alert_worker

Redis channels used
───────────────────
  camera:{id}:raw_frames   INPUT  — raw JPEG frames from camera_worker
  camera:{id}:frames       OUTPUT — annotated frames (same as direct mode)
  camera:{id}:alerts       OUTPUT — alert events

How to activate
───────────────
  1. Set INFERENCE_MODE=distributed in .env
  2. Start camera_worker with --raw-only flag (future CLI arg)
  3. Start inference_worker on the GPU node:
       celery -A backend.app.workers.celery_app worker -Q inference -c 1

Current status: PHASE 2 STUB — full implementation in Phase 3 (GPU node sprint).
                The class and channel names are finalised so camera_worker.py
                can be updated to the distributed mode without API changes.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Optional

import cv2
import numpy as np

from backend.app.config import settings
from backend.app.core.redis import new_pubsub_conn, publish_json
from backend.app.websocket.serializers import (
    serialize_internal_frame,
    serialize_alert_payload,
    event_to_dict,
)

logger = logging.getLogger(__name__)

# ── Channel naming (must match camera_worker.py) ──────────────────────────────
def raw_frame_channel(camera_id: int | str) -> str:
    """Channel where camera_worker publishes raw (unannotated) JPEG frames."""
    return f"camera:{camera_id}:raw_frames"


def camera_channel(camera_id: int | str) -> str:
    return f"camera:{camera_id}:frames"


def alert_channel(camera_id: int | str) -> str:
    return f"camera:{camera_id}:alerts"


ALERT_SEVERITIES: frozenset[str] = frozenset({"critical", "high", "medium", "low"})


# ─────────────────────────────────────────────────────────────────────────────
# InferenceWorker class
# ─────────────────────────────────────────────────────────────────────────────

class InferenceWorker:
    """
    Subscribes to raw_frame channels, runs the AI pipeline, publishes results.

    Designed to run on a GPU node separate from the camera capture host.
    One InferenceWorker instance can serve multiple cameras (multi-camera
    GPU sharing via a single pipeline instance with per-camera state).

    Usage
    -----
    worker = InferenceWorker(camera_ids=[1, 2, 3])
    await worker.run(stop_event)
    """

    def __init__(
        self,
        camera_ids: list[int | str],
        redis_url: Optional[str] = None,
        pipeline=None,
    ) -> None:
        self.camera_ids = camera_ids
        self.redis_url = redis_url or settings.REDIS_URL
        self._pipeline = pipeline  # AIPipeline instance; lazy-loaded if None
        self._stop_event: asyncio.Event = asyncio.Event()

    def _get_pipeline(self):
        if self._pipeline is None:
            from backend.ai.pipeline import AIPipeline
            self._pipeline = AIPipeline()
            logger.info("[InferenceWorker] AIPipeline loaded.")
        return self._pipeline

    async def run(self, stop_event: Optional[asyncio.Event] = None) -> None:
        """Main entry-point: subscribe to all raw channels and process frames."""
        if stop_event:
            self._stop_event = stop_event

        channels = [raw_frame_channel(cid) for cid in self.camera_ids]
        pubsub = await new_pubsub_conn()

        try:
            await pubsub.subscribe(*channels)
            logger.info(
                "[InferenceWorker] Subscribed — cameras=%s", self.camera_ids
            )

            loop = asyncio.get_event_loop()

            async for message in pubsub.listen():
                if self._stop_event.is_set():
                    break
                if message["type"] != "message":
                    continue

                channel: str = message["channel"]
                raw: str     = message["data"]

                # Determine camera_id from channel name: "camera:{id}:raw_frames"
                try:
                    camera_id = int(channel.split(":")[1])
                except (IndexError, ValueError):
                    continue

                await self._process_raw_message(camera_id, raw, loop)

        except asyncio.CancelledError:
            logger.info("[InferenceWorker] Cancelled.")
        except Exception as exc:
            logger.exception("[InferenceWorker] Error: %s", exc)
        finally:
            try:
                await pubsub.unsubscribe(*channels)
                await pubsub.aclose()
            except Exception:
                pass
            logger.info("[InferenceWorker] Stopped.")

    async def _process_raw_message(
        self,
        camera_id: int | str,
        raw_json: str,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Decode a raw frame message, run inference, publish results."""
        try:
            msg = json.loads(raw_json)
            b64_frame: str = msg["frame"]
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("[InferenceWorker] Bad raw frame message: %s", exc)
            return

        # Decode base64 JPEG → numpy BGR frame
        try:
            jpg_bytes = base64.b64decode(b64_frame)
            arr = np.frombuffer(jpg_bytes, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError("cv2.imdecode returned None")
        except Exception as exc:
            logger.warning("[InferenceWorker] Frame decode failed: %s", exc)
            return

        # Run AI pipeline in executor (CPU/GPU bound)
        try:
            pipeline = self._get_pipeline()
            result = await loop.run_in_executor(None, pipeline.process_frame, frame)
        except Exception as exc:
            logger.warning(
                "[InferenceWorker] Pipeline error (camera=%s): %s", camera_id, exc
            )
            return

        # Publish internal frame payload
        try:
            internal = await loop.run_in_executor(
                None, serialize_internal_frame, camera_id, result
            )
            await publish_json(camera_channel(camera_id), internal)
        except Exception as exc:
            logger.warning("[InferenceWorker] Frame publish failed: %s", exc)

        # Publish alert events
        for event in (result.business_events or []):
            try:
                event_dict = event_to_dict(event)
                if event_dict.get("severity", "") in ALERT_SEVERITIES:
                    alert_payload = serialize_alert_payload(camera_id, event_dict)
                    await publish_json(alert_channel(camera_id), alert_payload)
            except Exception as exc:
                logger.warning("[InferenceWorker] Alert publish failed: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Coroutine entry-point (used by Celery task in celery_app.py)
# ─────────────────────────────────────────────────────────────────────────────

async def run_inference_worker(
    camera_ids: list[int | str],
    redis_url: Optional[str] = None,
    stop_event: Optional[asyncio.Event] = None,
) -> None:
    """
    Convenience coroutine that creates an InferenceWorker and runs it.

    Parameters
    ----------
    camera_ids : list of camera IDs this worker should serve
    redis_url  : Redis URL (falls back to settings.REDIS_URL)
    stop_event : set() to stop gracefully
    """
    worker = InferenceWorker(camera_ids=camera_ids, redis_url=redis_url)
    await worker.run(stop_event=stop_event)
