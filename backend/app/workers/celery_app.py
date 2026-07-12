"""
celery_app.py
─────────────
Celery application for the Smart Vision System backend.

Responsibilities:
  - Create and configure the Celery app (Redis broker + backend)
  - Register `start_camera_worker` as a Celery task
  - Each camera gets its own isolated worker via task routing
  - Wrap the asyncio camera_worker coroutine so Celery can invoke it
  - Support graceful task revocation (stop_event per task)

Usage (dev):
    celery -A backend.app.workers.celery_app worker \
           --loglevel=info --concurrency=4 -Q cameras

Usage (per-camera queue):
    celery -A backend.app.workers.celery_app worker \
           --loglevel=info -Q camera.1 -c 1

STRICT: No AI logic lives here. This file only imports camera_worker.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from celery import Celery, signals
from celery.utils.log import get_task_logger

from backend.app.config import settings

logger = get_task_logger(__name__)

# ── Celery application ────────────────────────────────────────────────────────

celery_app = Celery(
    "svs_workers",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    # ── Serialization ──────────────────────────────────────────────────────────
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # ── Timezone ───────────────────────────────────────────────────────────────
    timezone="UTC",
    enable_utc=True,
    # ── Task routing — each camera gets its own queue for isolation ───────────
    task_routes={
        "backend.app.workers.celery_app.start_camera_worker": {
            "queue": "cameras",       # default; overridden per task call
        },
    },
    # ── Worker behaviour ───────────────────────────────────────────────────────
    worker_prefetch_multiplier=1,         # one task per worker process at a time
    task_acks_late=True,                  # ack only after the task completes
    task_reject_on_worker_lost=True,      # re-queue if the worker dies
    # ── Result expiry ──────────────────────────────────────────────────────────
    result_expires=3600,
)

# ── Active asyncio event loops / stop events (per task) ──────────────────────
# Keyed by Celery task request id so revoke() can signal the loop to stop.
_active_stop_events: dict[str, asyncio.Event] = {}
_lock = threading.Lock()


# ── Signal: worker startup ────────────────────────────────────────────────────
@signals.worker_ready.connect
def on_worker_ready(**kwargs: Any) -> None:
    logging.info("[Celery] SVS worker ready — broker=%s", settings.REDIS_URL)


# ── Task ──────────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="backend.app.workers.celery_app.start_camera_worker",
    max_retries=5,
    default_retry_delay=5,
    acks_late=True,
)
def start_camera_worker(
    self,
    camera_id: int | str,
    source: str | int,
    redis_url: str | None = None,
) -> dict:
    """
    Celery task: run a camera worker until the source is exhausted
    or the task is revoked.

    Parameters
    ----------
    camera_id  : camera DB id
    source     : video file path, RTSP URL, or webcam index
    redis_url  : override config REDIS_URL (optional)
    """
    # Late import to avoid circular dependencies at module load
    from backend.app.workers.camera_worker import run_camera_worker
    from backend.ai.pipeline import Pipeline

    effective_redis_url = redis_url or settings.REDIS_URL
    task_id = self.request.id

    logger.info(
        "[CeleryTask %s] Starting camera_worker — camera_id=%s source=%r",
        task_id, camera_id, source,
    )

    # ── Create a stop event so task revocation works ──────────────────────
    stop_event = asyncio.Event()
    with _lock:
        _active_stop_events[task_id] = stop_event

    # ── Build the AI pipeline once per task (model stays in memory) ──────────
    pipeline = Pipeline(
        model_path=settings.MODEL_PATH,
        weapon_model_path=settings.WEAPON_MODEL_PATH,
        weapon_imgsz=settings.WEAPON_IMGSZ
    )


    # ── Run the asyncio coroutine in a new event loop ─────────────────────────
    # Celery workers are synchronous processes; we spin our own loop here.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            run_camera_worker(
                camera_id=camera_id,
                source=source,
                redis_url=effective_redis_url,
                pipeline=pipeline,
                stop_event=stop_event,
            )
        )
    except Exception as exc:
        logger.exception("[CeleryTask %s] Unhandled error: %s", task_id, exc)
        # Retry on transient errors (e.g. Redis unavailable at startup)
        raise self.retry(exc=exc)
    finally:
        loop.close()
        with _lock:
            _active_stop_events.pop(task_id, None)

    logger.info("[CeleryTask %s] Camera worker finished.", task_id)
    return {"camera_id": camera_id, "status": "done"}


# ── Revocation handler ────────────────────────────────────────────────────────

@signals.task_revoked.connect
def on_task_revoked(request, **kwargs: Any) -> None:
    """Signal the asyncio stop_event when a task is revoked via celery.control.revoke()."""
    task_id = request.id if request else None
    if task_id:
        with _lock:
            ev = _active_stop_events.get(task_id)
        if ev:
            ev.set()
            logger.info("[Celery] Revoke signal sent to camera worker — task_id=%s", task_id)


# ── Convenience helper (called by FastAPI to spawn a worker) ──────────────────

def dispatch_camera_worker(
    camera_id: int | str,
    source: str | int,
    redis_url: str | None = None,
) -> str:
    """
    Send a `start_camera_worker` task to Celery and return the task id.

    Called by FastAPI camera-creation endpoints to spin up a worker
    without blocking the API event loop.
    """
    result = start_camera_worker.apply_async(
        kwargs={
            "camera_id": camera_id,
            "source": source,
            "redis_url": redis_url,
        },
        queue="cameras",   # consumed by the worker pool started with -Q cameras (C2)
    )
    return result.id


def stop_camera_worker(task_id: str) -> bool:
    """
    Revoke a running camera worker task.
    Returns True if the revoke command was sent.
    """
    celery_app.control.revoke(task_id, terminate=False, signal="SIGUSR1")
    # Also set the in-process stop event if the task is running in this process
    with _lock:
        ev = _active_stop_events.get(task_id)
    if ev:
        ev.set()
    return True
