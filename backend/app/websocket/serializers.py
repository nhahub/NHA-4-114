"""
websocket/serializers.py
────────────────────────
All payload serialisation for the Smart Vision System WebSocket layer.

Two distinct payload contracts (api-reference.md §8 vs §9):
──────────────────────────────────────────────────────────
  §9.1 Internal Redis frame payload  (AI worker → Redis → alert_worker)
       Fields: camera_id, frame (base64), events, timestamp

  §8.1 WebSocket outbound frame payload  (Redis → manager.py → browser)
       Fields: camera_id, timestamp, frame, occupancy, tracks, events

  §9.2 Internal Redis alert payload  (camera_worker → Redis → alert_worker)
  §8.2 WebSocket outbound alert payload  (Redis → manager.py → browser)

Public functions
────────────────
  encode_frame_base64(frame)              → str
  event_to_dict(event)                    → dict
  serialize_internal_frame(camera_id, result) → dict   (§9.1)
  serialize_ws_frame(camera_id, result)   → dict       (§8.1)
  serialize_alert_payload(camera_id, event_dict) → dict (§8.2 / §9.2)

STRICT: No AI imports. No Redis imports. Pure data transformation.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

import cv2

from backend.app.config import settings

logger = logging.getLogger(__name__)

JPEG_QUALITY: int = settings.JPEG_QUALITY


# ─────────────────────────────────────────────────────────────────────────────
# Primitives
# ─────────────────────────────────────────────────────────────────────────────

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def encode_frame_base64(frame) -> str:
    """
    Encode an OpenCV BGR frame (numpy ndarray) to a base64 JPEG string.

    Parameters
    ----------
    frame : numpy.ndarray  (H × W × 3, uint8, BGR)

    Returns
    -------
    str : base64-encoded JPEG bytes as a UTF-8 string
    """
    ok, buf = cv2.imencode(
        ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
    )
    if not ok:
        raise RuntimeError("JPEG encoding failed — check frame shape and dtype")
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def event_to_dict(event: Any) -> dict:
    """
    Convert any event object (dataclass, dict, or str) to a plain dict.

    Handles:
      - dataclasses (from AI pipeline AlertEvent / CrossingEvent)
      - plain dicts (already serialised)
      - anything else: wrapped in {"raw": str(event)}

    This is the single conversion point — no other file calls asdict().
    """
    if hasattr(event, "__dataclass_fields__"):
        return asdict(event)
    if isinstance(event, dict):
        return event
    # Fallback: unknown type — log and wrap
    logger.debug("event_to_dict: unknown type %s", type(event).__name__)
    return {"raw": str(event)}


# ─────────────────────────────────────────────────────────────────────────────
# §9.1  Internal Redis frame payload  (AI worker → Redis)
# ─────────────────────────────────────────────────────────────────────────────

def serialize_internal_frame(camera_id: int | str, result) -> dict:
    """
    Build the internal Redis frame payload (api-reference.md §9.1).

    This is what camera_worker.py publishes to Redis.
    alert_worker.py reads it to extract events.
    websocket/manager.py reads it and calls serialize_ws_frame() before
    forwarding to the browser.

    Schema:
    {
        "camera_id": int,
        "frame":     str (base64 JPEG of the annotated frame),
        "events":    list[dict],
        "timestamp": str (ISO-8601 UTC)
    }

    Note: this payload does NOT include tracks or occupancy — those are
    added in the WebSocket outbound payload (§8.1) below.

    `events` carries the analyzer output (result.business_events): these are
    the dicts that actually carry `type`/`severity` (crossing/zone/loitering).
    The track-lifecycle objects in result.events have no such fields and are
    not what downstream consumers (dashboard, alert_worker) expect. (C4)
    """
    return {
        "camera_id": camera_id,
        "frame": encode_frame_base64(result.annotated_frame),
        "events": [event_to_dict(e) for e in (result.business_events or [])],
        "timestamp": _utcnow(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# §8.1  WebSocket outbound frame payload  (Redis → browser)
# ─────────────────────────────────────────────────────────────────────────────

def serialize_ws_frame(camera_id: int | str, result) -> dict:
    """
    Build the WebSocket outbound frame payload (api-reference.md §8.1).

    This is what the browser dashboard receives on /ws/cameras/{id}.

    Schema:
    {
        "camera_id": int,
        "timestamp": str (ISO-8601 UTC),
        "frame":     str (base64 JPEG),
        "occupancy": int,
        "tracks":    [{"track_id": int, "bbox": [x, y, w, h]}, ...],
        "events":    list[dict]
    }

    Note: tracks and occupancy come from result.tracks — the AI pipeline
    populates these via ByteTrack. If tracks is None (e.g. no detections),
    an empty list is used.
    """
    tracks = [
        {"track_id": t.id, "bbox": list(t.bbox)}
        for t in (result.tracks or [])
    ]
    return {
        "camera_id": camera_id,
        "timestamp": _utcnow(),
        "frame": encode_frame_base64(result.annotated_frame),
        "occupancy": len(tracks),
        "tracks": tracks,
        "events": [event_to_dict(e) for e in (result.events or [])],
    }


# ─────────────────────────────────────────────────────────────────────────────
# §8.2 / §9.2  Alert payload  (camera_worker → Redis → browser / alert_worker)
# ─────────────────────────────────────────────────────────────────────────────

def serialize_alert_payload(camera_id: int | str, event_dict: dict) -> dict:
    """
    Build the alert payload published to the Redis alert channel.

    Used by:
      - camera_worker.py  → publishes to Redis (§9.2 internal)
      - manager.py        → forwards to /ws/alerts clients (§8.2 outbound)
      - alert_worker.py   → persists to PostgreSQL

    Schema (api-reference.md §8.2 + §9.2):
    {
        "camera_id": int,
        "type":      str,
        "severity":  str,
        "message":   str,
        "timestamp": str (ISO-8601),
        "metadata":  dict   ← fully preserved from the AI AlertEvent
    }

    All fields from event_dict are forwarded. metadata is extracted from
    the event dict if present, otherwise built from any remaining fields.
    """
    # Extract known top-level fields; everything else goes into metadata.
    known_keys = {"type", "severity", "message", "metadata", "timestamp"}

    alert_type   = event_dict.get("type", "unknown")
    severity     = event_dict.get("severity", "low")
    message      = event_dict.get("message", "")
    timestamp    = event_dict.get("timestamp") or _utcnow()

    # Preserve existing metadata block OR build one from remaining fields
    if "metadata" in event_dict and isinstance(event_dict["metadata"], dict):
        metadata = event_dict["metadata"]
    else:
        metadata = {k: v for k, v in event_dict.items() if k not in known_keys}

    return {
        "camera_id": camera_id,
        "type":      alert_type,
        "severity":  severity,
        "message":   message,
        "timestamp": timestamp,
        "metadata":  metadata,
    }
