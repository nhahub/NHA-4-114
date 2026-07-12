"""
camera_worker.py
────────────────
Async camera capture loop for the Smart Vision System.

Responsibilities:
  - Open video source (file / RTSP / webcam)
  - Read frames in an asyncio-friendly loop
  - Call AI pipeline (process_frame) — no business logic here
  - Throttle output to MAX_FPS
  - Publish PipelineResult payload to Redis pub/sub channel per camera
  - Handle source exhaustion (EOF on video files) and reconnection on RTSP loss

STRICT: This file does NOT import or modify any ai/ module internals.
        It only calls backend.ai.pipeline.Pipeline.process_frame().
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from dataclasses import asdict
from typing import Optional

import cv2
import redis.asyncio as aioredis

from backend.ai.pipeline import Pipeline, PipelineResult

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
MAX_FPS: int = 15
FRAME_INTERVAL: float = 1.0 / MAX_FPS
RECONNECT_DELAY: float = 3.0
MAX_RECONNECT_ATTEMPTS: int = 10
JPEG_QUALITY: int = 75
ZONE_RELOAD_INTERVAL: float = 15.0
HEATMAP_EXPORT_INTERVAL: float = 10.0


# ── Redis channel naming convention ─────────────────────────────────────────
def camera_channel(camera_id: int | str) -> str:
    return f"camera:{camera_id}:frames"


def alert_channel(camera_id: int | str) -> str:
    return f"camera:{camera_id}:alerts"


def event_channel(camera_id: int | str) -> str:
    return f"camera:{camera_id}:events"


def zone_occupancy_key(zone_id: int | str) -> str:
    """Redis key caching a zone's latest live occupancy count."""
    return f"zone:{zone_id}:occupancy"


# ── Payload builders ─────────────────────────────────────────────────────────

def _encode_frame(frame) -> str:
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def _build_frame_payload(camera_id: int | str, result: PipelineResult) -> str:
    tracks = [
        {"track_id": t.track_id, "bbox": list(t.bbox)}
        for t in (result.tracks or [])
    ]
    payload = {
        "camera_id": camera_id,
        "timestamp": _utcnow(),
        "frame": _encode_frame(result.annotated_frame),
        "occupancy": len(tracks),
        "tracks": tracks,
        "events": _serialize_events(result.events),
        "business_events": result.business_events,
    }
    return json.dumps(payload, default=_json_default)


def _build_alert_payload(camera_id: int | str, event: dict) -> str:
    return json.dumps({
        "camera_id": camera_id,
        "type": event.get("type", "unknown"),
        "severity": event.get("severity", "low"),
        "message": event.get("message", ""),
        "timestamp": _utcnow(),
    })


def _build_event_payload(camera_id: int | str, event: dict) -> str:
    return json.dumps({
        "camera_id": camera_id,
        "type": event.get("type", "unknown"),
        "message": event.get("message", f"Event: {event.get('type')}"),
        "timestamp": _utcnow(),
    })


def _json_default(obj):
    from enum import Enum
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _serialize_events(events) -> list:
    if not events:
        return []
    result = []
    for e in events:
        try:
            d = asdict(e) if hasattr(e, "__dataclass_fields__") else dict(e)
            # Normalize enum values to their primitive representation
            import json
            result.append(json.loads(json.dumps(d, default=_json_default)))
        except Exception:
            result.append(str(e))
    return result


def _utcnow() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _draw_zones(frame, zone_configs: list) -> None:
    """Overlay zone polygons and labels onto the frame in-place."""
    import numpy as np
    color = (99, 102, 241)  # indigo — matches the frontend zone editor colour
    for zone in zone_configs:
        pts = [list(p) for p in zone.polygon]
        if len(pts) < 3:
            continue
        pts_arr = np.array(pts, dtype=np.int32)
        overlay = frame.copy()
        cv2.fillPoly(overlay, [pts_arr], color)
        cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
        cv2.polylines(frame, [pts_arr], isClosed=True, color=color, thickness=2)
        x, y, _, _ = cv2.boundingRect(pts_arr)
        cv2.putText(frame, zone.name, (x + 4, y + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)


# ── Source helpers ────────────────────────────────────────────────────────────

def _open_capture(source: str | int) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video source: {source!r}")
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def _is_file(source: str | int) -> bool:
    return isinstance(source, str) and not source.lower().startswith("rtsp://")


# ── Per-camera analyzer configuration (loaded from the DB) ───────────────────

async def _load_zone_configs(camera_id: int | str) -> list:
    """Load active polygon zones for this camera from PostgreSQL."""
    from sqlalchemy import select
    from backend.app.db.session import AsyncSessionLocal
    from backend.app.models.zone import Zone
    from backend.ai.business_logic.zone_monitor import ZoneConfig

    configs: list = []
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(Zone).where(Zone.camera_id == int(camera_id))
            )
        ).scalars().all()

    for z in rows:
        if not getattr(z, "is_active", True):
            continue
        polygon = [tuple(pt) for pt in (z.polygon or [])]
        if len(polygon) < 3:
            logger.warning("[CameraWorker %s] Zone %s skipped — fewer than 3 points.", camera_id, z.id)
            continue
        configs.append(
            ZoneConfig(zone_id=z.id, name=z.name, polygon=polygon, threshold=z.threshold)
        )
    return configs


async def _reload_zones(camera_id: int | str, pipeline: Pipeline, zone_state: dict) -> None:
    """
    Re-read zones for *camera_id* from Postgres and apply them to the running
    pipeline in place (updates zone_state["configs"] / ["monitor"]).

    Handles three cases:
      - Monitor already running        → hot-swap its zone set (update_zones)
      - No monitor yet, zones now exist → register a new ZoneMonitor
      - No monitor, still no zones      → no-op
    """
    from backend.ai.business_logic.zone_monitor import ZoneMonitor

    zone_configs = await _load_zone_configs(camera_id)
    zone_state["configs"] = zone_configs

    monitor: Optional[ZoneMonitor] = zone_state.get("monitor")
    if monitor is not None:
        monitor.update_zones(zone_configs)
    elif zone_configs:
        monitor = ZoneMonitor(zone_configs)
        pipeline.register_analyzer(monitor)
        zone_state["monitor"] = monitor
        logger.info("[CameraWorker %s] ZoneMonitor registered (hot) — %d zone(s).", camera_id, len(zone_configs))

    logger.info("[CameraWorker %s] Zone configs reloaded — %d zone(s).", camera_id, len(zone_configs))


async def _configure_analyzers(
    pipeline: Pipeline,
    camera_id: int | str,
    frame_width: int = 1920,
    frame_height: int = 1080,
) -> tuple[list, Optional["ZoneMonitor"], Optional["HeatmapGenerator"]]:
    """
    Register per-camera business-logic analyzers on the pipeline.
    Returns (zone_configs, zone_monitor, heatmap_generator) so the capture
    loop can draw zones and periodically hot-reload / export them.

    EntryExitCounter  — always registered; uses a default horizontal midline
                        scaled to the actual frame dimensions.
    ZoneMonitor       — registered only when the camera has zones in the DB.
    HeatmapGenerator  — always registered; accumulates density for export_png().
    BehaviorAnalyzer  — always registered (loitering detection).
    """
    from backend.ai.business_logic.entry_exit_counter import EntryExitCounter
    from backend.ai.business_logic.zone_monitor import ZoneMonitor
    from backend.ai.business_logic.heatmap_generator import HeatmapGenerator
    from backend.ai.business_logic.behavior_analyzer import BehaviorAnalyzer

    # ── Entry/exit counter — horizontal midline ──────────────────────────────
    counter = EntryExitCounter(
        line_start=(0, frame_height // 2),
        line_end=(frame_width, frame_height // 2),
        in_direction="down",
    )
    pipeline.register_analyzer(counter)
    logger.info(
        "[CameraWorker %s] EntryExitCounter registered — line y=%d (frame %dx%d).",
        camera_id, frame_height // 2, frame_width, frame_height,
    )

    # ── Zone monitor (DB-backed) ─────────────────────────────────────────────
    zone_configs: list = []
    zone_monitor: Optional[ZoneMonitor] = None
    try:
        zone_configs = await _load_zone_configs(camera_id)
        if zone_configs:
            zone_monitor = ZoneMonitor(zone_configs)
            pipeline.register_analyzer(zone_monitor)
            logger.info("[CameraWorker %s] ZoneMonitor registered — %d zone(s).", camera_id, len(zone_configs))
        else:
            logger.info("[CameraWorker %s] No zones configured — ZoneMonitor skipped.", camera_id)
    except Exception as exc:
        logger.warning("[CameraWorker %s] Could not load zones: %s", camera_id, exc)

    # ── Heatmap generator — always on so density data accumulates from frame 1 ──
    heatmap_gen = HeatmapGenerator(frame_width=frame_width, frame_height=frame_height)
    pipeline.register_analyzer(heatmap_gen)
    logger.info("[CameraWorker %s] HeatmapGenerator registered.", camera_id)

    # ── Behaviour analyzer ───────────────────────────────────────────────────
    pipeline.register_analyzer(BehaviorAnalyzer())
    logger.info("[CameraWorker %s] BehaviorAnalyzer registered.", camera_id)

    return zone_configs, zone_monitor, heatmap_gen


# ── Main worker coroutine ─────────────────────────────────────────────────────

async def run_camera_worker(
    camera_id: int | str,
    source: str | int,
    redis_url: str,
    pipeline: Optional[Pipeline] = None,
    stop_event: Optional[asyncio.Event] = None,
) -> None:
    """Entry-point coroutine for a single camera."""
    if stop_event is None:
        stop_event = asyncio.Event()

    from backend.app.config import settings

    # Probe frame dimensions once — the source geometry doesn't change between reconnects.
    frame_width, frame_height = 1920, 1080
    try:
        cap_probe = _open_capture(source)
        frame_width = int(cap_probe.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap_probe.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap_probe.release()
        logger.info("[CameraWorker %s] Frame size probed: %dx%d", camera_id, frame_width, frame_height)
    except Exception as exc:
        logger.warning("[CameraWorker %s] Could not probe frame size (%s) — using %dx%d default.", camera_id, exc, frame_width, frame_height)

    redis_client: aioredis.Redis = await aioredis.from_url(
        redis_url, encoding="utf-8", decode_responses=True
    )

    frame_ch = camera_channel(camera_id)
    alert_ch = alert_channel(camera_id)
    event_ch = event_channel(camera_id)

    logger.info("[CameraWorker %s] Starting — source=%r", camera_id, source)

    reconnect_attempts = 0

    # When the caller supplies a pre-built pipeline we must not re-register
    # analyzers on every reconnect (that would stack duplicates).  Instead we
    # only rebuild the pipeline for the first connect and just reload zone
    # configs from the DB on subsequent reconnects.
    active_pipeline: Optional[Pipeline] = pipeline  # None → build fresh each iteration
    first_connect = True

    # Mutable holder so _capture_loop's periodic in-loop reload (needed because
    # file sources never "reconnect" — see _is_file below) can update the zone
    # set without needing a return value threaded back through the loop.
    zone_state: dict = {"configs": [], "monitor": None}
    heatmap_gen = None

    while not stop_event.is_set():
        cap = None
        try:
            if first_connect or active_pipeline is None:
                # Build a fresh pipeline (loads YOLO model once).
                active_pipeline = pipeline if pipeline is not None else Pipeline(
                    model_path=settings.MODEL_PATH,
                    weapon_model_path=settings.WEAPON_MODEL_PATH,
                    weapon_imgsz=settings.WEAPON_IMGSZ,
                )
                zone_configs, zone_monitor, heatmap_gen = await _configure_analyzers(
                    active_pipeline, camera_id, frame_width, frame_height
                )
                zone_state["configs"] = zone_configs
                zone_state["monitor"] = zone_monitor
                first_connect = False
            else:
                # Subsequent reconnects: reload zone configs from DB so newly
                # created zones are drawn on the stream without needing a restart.
                await _reload_zones(camera_id, active_pipeline, zone_state)

            cap = await asyncio.get_event_loop().run_in_executor(
                None, _open_capture, source
            )
            reconnect_attempts = 0
            logger.info("[CameraWorker %s] Source opened.", camera_id)

            await _capture_loop(
                camera_id=camera_id,
                cap=cap,
                pipeline=active_pipeline,
                redis_client=redis_client,
                frame_ch=frame_ch,
                alert_ch=alert_ch,
                event_ch=event_ch,
                stop_event=stop_event,
                zone_state=zone_state,
                heatmap_gen=heatmap_gen,
            )

        except asyncio.CancelledError:
            logger.info("[CameraWorker %s] Cancelled.", camera_id)
            break

        except Exception as exc:
            logger.exception("[CameraWorker %s] Error: %s", camera_id, exc)

        finally:
            if cap is not None:
                cap.release()

        if _is_file(source):
            logger.info("[CameraWorker %s] Video file exhausted — worker done.", camera_id)
            break

        reconnect_attempts += 1
        if reconnect_attempts > MAX_RECONNECT_ATTEMPTS:
            logger.error(
                "[CameraWorker %s] Exceeded max reconnect attempts (%d). Giving up.",
                camera_id, MAX_RECONNECT_ATTEMPTS,
            )
            break

        wait = RECONNECT_DELAY * reconnect_attempts
        logger.warning(
            "[CameraWorker %s] Reconnecting in %.1f s (attempt %d/%d)…",
            camera_id, wait, reconnect_attempts, MAX_RECONNECT_ATTEMPTS,
        )
        await asyncio.sleep(wait)

    await redis_client.aclose()
    logger.info("[CameraWorker %s] Worker stopped.", camera_id)


async def _capture_loop(
    camera_id,
    cap: cv2.VideoCapture,
    pipeline: Pipeline,
    redis_client: aioredis.Redis,
    frame_ch: str,
    alert_ch: str,
    event_ch: str,
    stop_event: asyncio.Event,
    zone_state: dict | None = None,
    heatmap_gen=None,
) -> None:
    """Inner frame-reading loop."""
    loop = asyncio.get_event_loop()
    last_publish_time = 0.0
    last_zone_reload = time.monotonic()
    last_heatmap_export = time.monotonic()
    zone_state = zone_state if zone_state is not None else {"configs": [], "monitor": None}

    while not stop_event.is_set():
        ret, frame = await loop.run_in_executor(None, cap.read)

        if not ret:
            logger.debug("[CameraWorker %s] cap.read() returned False — EOF or drop.", camera_id)
            break

        now = time.monotonic()
        elapsed = now - last_publish_time
        if elapsed < FRAME_INTERVAL:
            await asyncio.sleep(FRAME_INTERVAL - elapsed)
            continue

        # ── Periodic zone hot-reload ──────────────────────────────────────────
        # File sources never hit the reconnect path in run_camera_worker (they
        # just exhaust and stop), so a zone created after this worker started
        # would otherwise never be picked up. Reload on a timer instead.
        if now - last_zone_reload >= ZONE_RELOAD_INTERVAL:
            last_zone_reload = now
            try:
                await _reload_zones(camera_id, pipeline, zone_state)
            except Exception as exc:
                logger.warning("[CameraWorker %s] Zone reload failed: %s", camera_id, exc)

        try:
            result: PipelineResult = await loop.run_in_executor(
                None, pipeline.process_frame, frame
            )
        except Exception as exc:
            logger.warning("[CameraWorker %s] Pipeline error: %s", camera_id, exc)
            continue

        last_publish_time = time.monotonic()

        # ── Draw zone overlays onto the annotated frame ──────────────────────
        zone_configs = zone_state.get("configs") or []
        if zone_configs and result.annotated_frame is not None:
            _draw_zones(result.annotated_frame, zone_configs)

        # ── Periodic heatmap export ───────────────────────────────────────────
        if heatmap_gen is not None and now - last_heatmap_export >= HEATMAP_EXPORT_INTERVAL:
            last_heatmap_export = now
            try:
                from backend.app.core.storage import HEATMAP_DIR
                out_path = HEATMAP_DIR / f"camera_{camera_id}_latest.png"
                await loop.run_in_executor(None, heatmap_gen.export_png, out_path)
            except RuntimeError:
                pass  # no centroid data accumulated yet
            except Exception as exc:
                logger.warning("[CameraWorker %s] Heatmap export failed: %s", camera_id, exc)

        # ── Publish annotated frame ──────────────────────────────────────────
        try:
            frame_payload = await loop.run_in_executor(
                None, _build_frame_payload, camera_id, result
            )
            await redis_client.publish(frame_ch, frame_payload)
        except Exception as exc:
            logger.warning("[CameraWorker %s] Redis publish (frame) failed: %s", camera_id, exc)

        # ── Route business events to alert or event channels ─────────────────
        # weapon_alert and overcrowding types → alert channel (high visibility)
        # all other business events → event channel
        all_alerts = []
        all_events = []

        for evt in (result.business_events or []):
            evt_type = evt.get("type", "").lower()

            # zone_occupancy carries live per-zone counts — cache in Redis so
            # REST polling (Analytics page) reflects current occupancy instead
            # of the Zone.current_occupancy DB column, which is never updated.
            if evt_type == "zone_occupancy" and "zone_id" in evt:
                try:
                    await redis_client.set(
                        zone_occupancy_key(evt["zone_id"]), evt.get("occupancy", 0)
                    )
                except Exception as exc:
                    logger.warning(
                        "[CameraWorker %s] Redis zone-occupancy cache failed: %s", camera_id, exc
                    )

            if "alert" in evt_type or "overcrowding" in evt_type:
                all_alerts.append(evt)
            else:
                all_events.append(evt)

        for alert in all_alerts:
            try:
                await redis_client.publish(alert_ch, _build_alert_payload(camera_id, alert))
            except Exception as exc:
                logger.warning("[CameraWorker %s] Redis publish (alert) failed: %s", camera_id, exc)

        for evt in all_events:
            try:
                await redis_client.publish(event_ch, _build_event_payload(camera_id, evt))
            except Exception as exc:
                logger.warning("[CameraWorker %s] Redis publish (event) failed: %s", camera_id, exc)

        await asyncio.sleep(0)
