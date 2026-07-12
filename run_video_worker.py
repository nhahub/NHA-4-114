"""
run_video_worker.py
───────────────────
Standalone runner that registers a video file as a camera in the DB and
starts the full pipeline locally — no Celery required:
  - camera_worker  : runs AI inference and publishes frames to Redis
  - alert_worker   : subscribes to Redis, persists entry/exit events to DB

Frames are published to Redis → FastAPI WebSocket manager → frontend.
Entry/exit counts are persisted to DB → /api/v1/analytics/summary → dashboard.

Usage:
    python run_video_worker.py
    python run_video_worker.py D:/path/to/video.mp4
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger("run_video_worker")

VIDEO_PATH = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "video_test.mp4")


async def main() -> None:
    from backend.app.config import settings
    from backend.app.db.session import AsyncSessionLocal, init_db
    from backend.app.models.camera import Camera
    from backend.app.workers.camera_worker import run_camera_worker
    from backend.app.workers.alert_worker import run_alert_worker
    from sqlalchemy import select

    # ── 1. Init DB ────────────────────────────────────────────────────────────
    logger.info("Initialising database…")
    await init_db()

    # ── 2. Register or reuse camera ───────────────────────────────────────────
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Camera).where(Camera.source_url == VIDEO_PATH)
        )
        cam = result.scalar_one_or_none()

        if cam is None:
            cam = Camera(
                name="Test Video",
                source_type="file",
                source_url=VIDEO_PATH,
                is_active=True,
            )
            db.add(cam)
            await db.flush()
            await db.refresh(cam)
            await db.commit()
            logger.info("Camera registered → id=%d  url=%s", cam.id, VIDEO_PATH)
        else:
            logger.info("Reusing existing camera id=%d", cam.id)

        camera_id = cam.id

    logger.info("=" * 60)
    logger.info("Camera ID : %d", camera_id)
    logger.info("Video     : %s", VIDEO_PATH)
    logger.info("Redis     : %s", settings.REDIS_URL)
    logger.info("")
    logger.info("Open the dashboard now:")
    logger.info("  http://localhost:3000/monitor")
    logger.info("Then click on camera #%d to see the live stream.", camera_id)
    logger.info("Total In / Total Out update every 10 s from the analytics API.")
    logger.info("Press Ctrl+C to stop.")
    logger.info("=" * 60)

    stop = asyncio.Event()

    async def _camera():
        try:
            await run_camera_worker(
                camera_id=camera_id,
                source=VIDEO_PATH,
                redis_url=settings.REDIS_URL,
                stop_event=stop,
            )
        finally:
            stop.set()

    async def _alerts():
        try:
            await run_alert_worker(
                redis_url=settings.REDIS_URL,
                stop_event=stop,
            )
        finally:
            stop.set()

    # ── 3. Run camera worker + alert worker concurrently ─────────────────────
    try:
        await asyncio.gather(_camera(), _alerts())
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Stopped by user.")
    finally:
        stop.set()
        logger.info("All workers finished.")


if __name__ == "__main__":
    asyncio.run(main())
