"""
alert_engine.py
---------------
Central alert generation engine for the Smart Vision System.

Responsibilities:
  - Consume business events from all analyzers (zone, loitering, crossing)
  - Apply severity rules and deduplication
  - Emit structured AlertEvent objects ready for:
      * Redis pub/sub → WebSocket → Frontend dashboard
      * PostgreSQL storage via REST API

Design constraints:
  - No FastAPI imports — pure Python
  - No direct DB access — emits events only
  - Registers with Pipeline via pipeline.register_analyzer()
  - Cooldown per alert type per camera to prevent flooding

Alert Types (matching api-reference.md):
  - zone_overcrowding  → severity: high
  - loitering          → severity: medium
  - crossing_event     → severity: low (info)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from ..tracker.track_manager import Track, TrackEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class AlertSeverity(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


class AlertType(str, Enum):
    ZONE_OVERCROWDING = "zone_overcrowding"
    LOITERING         = "loitering"
    CROSSING_EVENT    = "crossing_event"
    ZONE_OCCUPANCY    = "zone_occupancy"     # informational snapshot


# ---------------------------------------------------------------------------
# AlertEvent — the output contract
# ---------------------------------------------------------------------------

@dataclass
class AlertEvent:
    """
    A single alert emitted by the AlertEngine.

    This is the canonical alert format used across:
      - Redis pub/sub payload
      - WebSocket message (api-reference.md §8.2)
      - PostgreSQL alert record (api-reference.md §4)

    Attributes
    ----------
    camera_id:
        ID of the camera that generated the alert.
    alert_type:
        One of AlertType enum values.
    severity:
        AlertSeverity level.
    message:
        Human-readable description shown in the dashboard.
    timestamp:
        Unix timestamp when the alert was generated.
    metadata:
        Extra context (zone_id, track_id, occupancy, etc.).
    """
    camera_id:  int
    alert_type: AlertType
    severity:   AlertSeverity
    message:    str
    timestamp:  float = field(default_factory=time.time)
    metadata:   dict  = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialise to dict for Redis / WebSocket / REST."""
        return {
            "camera_id":  self.camera_id,
            "type":       self.alert_type.value,
            "severity":   self.severity.value,
            "message":    self.message,
            "timestamp":  self.timestamp,
            "metadata":   self.metadata,
        }


# ---------------------------------------------------------------------------
# AlertEngine
# ---------------------------------------------------------------------------

class AlertEngine:
    """
    Consumes raw business events from other analyzers and emits
    structured AlertEvents with deduplication and cooldown.

    Usage
    -----
    >>> engine = AlertEngine(camera_id=1)
    >>> pipeline.register_analyzer(engine)
    >>> # access emitted alerts:
    >>> alerts = engine.flush_alerts()   # call from camera_worker or REST handler
    """

    # Default cooldown seconds per alert type
    DEFAULT_COOLDOWNS: Dict[AlertType, float] = {
        AlertType.ZONE_OVERCROWDING: 15.0,
        AlertType.LOITERING:         20.0,
        AlertType.CROSSING_EVENT:     0.0,   # no cooldown — every crossing logged
        AlertType.ZONE_OCCUPANCY:     0.0,   # informational, no cooldown
    }

    def __init__(
        self,
        camera_id: int,
        cooldowns: Optional[Dict[AlertType, float]] = None,
    ) -> None:
        """
        Parameters
        ----------
        camera_id:
            Camera this engine is attached to.
        cooldowns:
            Optional override for per-type cooldown seconds.
            Merged with DEFAULT_COOLDOWNS.
        """
        self._camera_id = camera_id
        self._cooldowns  = {**self.DEFAULT_COOLDOWNS, **(cooldowns or {})}

        # (alert_type, key) → last emit timestamp
        # key is e.g. zone_id or track_id for per-entity dedup
        self._last_emit: Dict[Tuple[str, str], float] = {}

        # Buffer of alerts waiting to be flushed
        self._pending: List[AlertEvent] = []

        logger.info(
            "AlertEngine initialised | camera_id=%d | cooldowns=%s",
            camera_id,
            {k.value: v for k, v in self._cooldowns.items()},
        )

    # ------------------------------------------------------------------
    # Analyzer interface (called by Pipeline each frame)
    # ------------------------------------------------------------------

    def analyze(
        self,
        tracks: List[Track],
        events: List[TrackEvent],
    ) -> List[dict]:
        """
        Process business events from other analyzers this frame.

        NOTE: AlertEngine reads from `tracks` and `events` but its
        primary input is the business_events list produced by other
        analyzers. Pipeline calls analyze() with track/event lists;
        alert engine looks at them indirectly through the business
        events it receives via process_business_events().

        Returns
        -------
        List[dict]
            Serialised AlertEvents for this frame (may be empty).
        """
        # Flush any pending alerts accumulated via process_business_events()
        alerts = self.flush_alerts()
        return [a.to_dict() for a in alerts]

    def process_business_events(self, business_events: List[dict]) -> None:
        """
        Convert raw business events from other analyzers into AlertEvents.

        Call this from camera_worker AFTER pipeline.process_frame(),
        passing result.business_events to the engine.

        Parameters
        ----------
        business_events:
            List of dicts produced by entry_exit_counter, zone_monitor,
            behavior_analyzer etc.
        """
        now = time.time()

        for evt in business_events:
            evt_type = evt.get("type", "")

            if evt_type == "zone_overcrowding":
                self._handle_zone_overcrowding(evt, now)

            elif evt_type == "loitering":
                self._handle_loitering(evt, now)

            elif evt_type == "crossing_event":
                self._handle_crossing(evt, now)

            elif evt_type == "zone_occupancy":
                # Informational — always pass through, no cooldown
                self._pending.append(AlertEvent(
                    camera_id  = self._camera_id,
                    alert_type = AlertType.ZONE_OCCUPANCY,
                    severity   = AlertSeverity.LOW,
                    message    = (
                        f"Zone '{evt.get('zone_name', evt.get('zone_id'))}': "
                        f"{evt.get('occupancy', 0)}/{evt.get('threshold', '?')} occupancy"
                    ),
                    timestamp  = evt.get("timestamp", now),
                    metadata   = evt,
                ))

    def flush_alerts(self) -> List[AlertEvent]:
        """
        Return and clear all pending alerts.

        Call from camera_worker after process_business_events() to
        get the batch of alerts for Redis / DB storage.
        """
        alerts = list(self._pending)
        self._pending.clear()
        if alerts:
            logger.debug(
                "AlertEngine flush: %d alert(s) | camera_id=%d",
                len(alerts), self._camera_id,
            )
        return alerts

    def get_pending_count(self) -> int:
        """Return number of alerts waiting to be flushed."""
        return len(self._pending)

    # ------------------------------------------------------------------
    # Private handlers
    # ------------------------------------------------------------------

    def _handle_zone_overcrowding(self, evt: dict, now: float) -> None:
        zone_id = str(evt.get("zone_id", "unknown"))
        key     = (AlertType.ZONE_OVERCROWDING.value, f"zone_{zone_id}")

        if not self._cooldown_ok(key, AlertType.ZONE_OVERCROWDING, now):
            return

        self._last_emit[key] = now
        occupancy  = evt.get("occupancy", 0)
        threshold  = evt.get("threshold", 0)
        zone_name  = evt.get("zone_name", zone_id)

        self._pending.append(AlertEvent(
            camera_id  = self._camera_id,
            alert_type = AlertType.ZONE_OVERCROWDING,
            severity   = AlertSeverity.HIGH,
            message    = (
                f"Zone '{zone_name}' overcrowded: "
                f"{occupancy} persons (threshold: {threshold})"
            ),
            timestamp  = evt.get("timestamp", now),
            metadata   = {
                "zone_id":   evt.get("zone_id"),
                "zone_name": zone_name,
                "occupancy": occupancy,
                "threshold": threshold,
                "occupant_ids": evt.get("occupant_ids", []),
            },
        ))
        logger.warning(
            "ALERT zone_overcrowding | camera=%d zone=%s occ=%d",
            self._camera_id, zone_name, occupancy,
        )

    def _handle_loitering(self, evt: dict, now: float) -> None:
        track_id = str(evt.get("track_id", "unknown"))
        key      = (AlertType.LOITERING.value, f"track_{track_id}")

        if not self._cooldown_ok(key, AlertType.LOITERING, now):
            return

        self._last_emit[key] = now
        duration = evt.get("duration_s", 0)

        self._pending.append(AlertEvent(
            camera_id  = self._camera_id,
            alert_type = AlertType.LOITERING,
            severity   = AlertSeverity.MEDIUM,
            message    = (
                f"Person (ID:{track_id}) stationary for "
                f"{duration:.0f}s"
            ),
            timestamp  = evt.get("timestamp", now),
            metadata   = {
                "track_id":   evt.get("track_id"),
                "duration_s": duration,
                "position":   evt.get("position"),
            },
        ))
        logger.warning(
            "ALERT loitering | camera=%d track=%s duration=%.0fs",
            self._camera_id, track_id, duration,
        )

    def _handle_crossing(self, evt: dict, now: float) -> None:
        # No cooldown on crossings — every crossing is logged
        direction = evt.get("direction", "?")
        count_in  = evt.get("count_in", 0)
        count_out = evt.get("count_out", 0)

        self._pending.append(AlertEvent(
            camera_id  = self._camera_id,
            alert_type = AlertType.CROSSING_EVENT,
            severity   = AlertSeverity.LOW,
            message    = (
                f"Person crossed line ({direction}) — "
                f"IN:{count_in} OUT:{count_out}"
            ),
            timestamp  = evt.get("timestamp", now),
            metadata   = {
                "track_id":  evt.get("track_id"),
                "direction": direction,
                "count_in":  count_in,
                "count_out": count_out,
                "occupancy": evt.get("occupancy", count_in - count_out),
            },
        ))
        logger.info(
            "ALERT crossing | camera=%d direction=%s IN=%d OUT=%d",
            self._camera_id, direction, count_in, count_out,
        )

    def _cooldown_ok(
        self,
        key: Tuple[str, str],
        alert_type: AlertType,
        now: float,
    ) -> bool:
        """Return True if enough time has elapsed since last emit."""
        cooldown    = self._cooldowns.get(alert_type, 0.0)
        last_ts     = self._last_emit.get(key, 0.0)
        return (now - last_ts) >= cooldown
