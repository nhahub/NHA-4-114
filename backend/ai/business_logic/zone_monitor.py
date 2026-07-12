"""
zone_monitor.py
---------------
Monitors configurable polygon zones and fires alerts when occupancy
exceeds a defined threshold.

Design constraints:
  - No YOLO / ByteTrack imports
  - Pure geometry + track state — no display logic
  - Multiple zones supported per camera instance
  - Registers with Pipeline via pipeline.register_analyzer()
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from ..tracker.track_manager import Track, TrackEvent, TrackEventType

logger = logging.getLogger(__name__)


@dataclass
class ZoneConfig:
    """
    Configuration for a single monitored zone.

    Attributes
    ----------
    zone_id : int
        Unique identifier within a camera.
    name : str
        Human-readable label shown in the dashboard.
    polygon : List[Tuple[int, int]]
        Ordered list of (x, y) vertices defining the zone boundary.
    threshold : int
        Number of persons that triggers a ``zone_overcrowding`` alert.
    alert_cooldown_s : float
        Minimum seconds between consecutive alerts for this zone.
    """

    zone_id: int
    name: str
    polygon: List[Tuple[int, int]]
    threshold: int = 5
    alert_cooldown_s: float = 10.0


@dataclass
class ZoneState:
    """Runtime state tracked per zone per frame."""

    occupancy: int = 0
    occupant_ids: List[int] = field(default_factory=list)
    last_alert_ts: float = 0.0
    alert_active: bool = False


class ZoneMonitor:
    """
    Monitors one or more polygon zones for occupancy threshold breaches.

    Usage
    -----
    >>> zones = [
    ...     ZoneConfig(
    ...         zone_id=1, name="Entrance", threshold=5,
    ...         polygon=[(100, 100), (400, 100), (400, 500), (100, 500)],
    ...     )
    ... ]
    >>> monitor = ZoneMonitor(zones)
    >>> pipeline.register_analyzer(monitor)
    """

    def __init__(self, zones: List[ZoneConfig]) -> None:
        self._zones: Dict[int, ZoneConfig] = {z.zone_id: z for z in zones}
        self._states: Dict[int, ZoneState] = {
            z.zone_id: ZoneState() for z in zones
        }
        # Pre-build NumPy contour arrays for cv2.pointPolygonTest
        self._contours: Dict[int, np.ndarray] = {
            z.zone_id: np.array(z.polygon, dtype=np.int32).reshape(-1, 1, 2)
            for z in zones
        }
        logger.info(
            "ZoneMonitor initialised | zones=%d | ids=%s",
            len(zones),
            [z.zone_id for z in zones],
        )

    # ------------------------------------------------------------------
    # Analyzer interface
    # ------------------------------------------------------------------

    def analyze(
        self,
        tracks: List[Track],
        events: List[TrackEvent],
    ) -> List[dict]:
        """
        Called once per frame by Pipeline.
        Updates zone occupancy and emits alerts when thresholds are breached.
        """
        output: List[dict] = []

        # Reset occupancy counts for this frame
        for state in self._states.values():
            state.occupancy = 0
            state.occupant_ids = []

        # Assign each active track to zones it occupies
        for track in tracks:
            cx, cy = track.centroid
            for zone_id, contour in self._contours.items():
                if self._point_in_zone(cx, cy, contour):
                    self._states[zone_id].occupancy += 1
                    self._states[zone_id].occupant_ids.append(track.track_id)

        # Check thresholds and emit events
        now = time.time()
        for zone_id, zone_cfg in self._zones.items():
            state = self._states[zone_id]
            occupancy = state.occupancy
            threshold = zone_cfg.threshold

            # Always emit occupancy snapshot for dashboard
            output.append(
                {
                    "type": "zone_occupancy",
                    "zone_id": zone_id,
                    "zone_name": zone_cfg.name,
                    "occupancy": occupancy,
                    "threshold": threshold,
                    "timestamp": now,
                }
            )

            # Threshold breach alert (with cooldown)
            if occupancy >= threshold:
                cooldown_elapsed = (now - state.last_alert_ts) >= zone_cfg.alert_cooldown_s
                if cooldown_elapsed:
                    state.last_alert_ts = now
                    state.alert_active = True
                    logger.warning(
                        "Zone alert: zone_id=%d '%s'  occupancy=%d  threshold=%d",
                        zone_id,
                        zone_cfg.name,
                        occupancy,
                        threshold,
                    )
                    output.append(
                        {
                            "type": "zone_overcrowding",
                            "severity": "high",
                            "zone_id": zone_id,
                            "zone_name": zone_cfg.name,
                            "occupancy": occupancy,
                            "threshold": threshold,
                            "occupant_ids": list(state.occupant_ids),
                            "timestamp": now,
                        }
                    )
            else:
                state.alert_active = False

        return output

    def update_zones(self, zones: List[ZoneConfig]) -> None:
        """
        Replace the monitored zone set in place (hot-reload).

        Preserves runtime state (occupant history, alert cooldown) for zone_ids
        that remain across the reload; brand-new zone_ids start fresh.
        """
        new_zones: Dict[int, ZoneConfig] = {z.zone_id: z for z in zones}
        new_states: Dict[int, ZoneState] = {
            zone_id: self._states.get(zone_id, ZoneState())
            for zone_id in new_zones
        }
        new_contours: Dict[int, np.ndarray] = {
            z.zone_id: np.array(z.polygon, dtype=np.int32).reshape(-1, 1, 2)
            for z in zones
        }
        self._zones = new_zones
        self._states = new_states
        self._contours = new_contours
        logger.info(
            "ZoneMonitor zones reloaded | zones=%d | ids=%s",
            len(zones),
            [z.zone_id for z in zones],
        )

    def get_zone_state(self, zone_id: int) -> Optional[ZoneState]:
        """Return current state for *zone_id*, or None if not found."""
        return self._states.get(zone_id)

    def get_all_states(self) -> Dict[int, ZoneState]:
        """Return a snapshot of all zone states."""
        return dict(self._states)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _point_in_zone(cx: float, cy: float, contour: np.ndarray) -> bool:
        """
        Use OpenCV's pointPolygonTest.
        Returns True if (cx, cy) is inside or on the boundary.
        """
        result = cv2.pointPolygonTest(contour, (float(cx), float(cy)), measureDist=False)
        return result >= 0
