"""
behavior_analyzer.py
--------------------
Detects suspicious behavioral patterns:
  1. Loitering — a person stationary beyond a configurable duration
  2. Intrusion — a person entering a restricted zone (extension point)

Design constraints:
  - No display logic, no YOLO/ByteTrack imports
  - Stationary = centroid displacement < movement_threshold pixels over
    the loitering_window_s time window
  - Registers with Pipeline via pipeline.register_analyzer()
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..tracker.track_manager import Track, TrackEvent, TrackEventType

logger = logging.getLogger(__name__)


@dataclass
class LoiterRecord:
    """Internal per-track loitering bookkeeping."""

    anchor_centroid: Tuple[float, float]  # Centroid when "stationary" started
    stationary_since_ts: float           # Unix timestamp when stationarity began
    alert_emitted: bool = False          # Prevent alert flood for same incident
    last_alert_ts: float = 0.0


class BehaviorAnalyzer:
    """
    Per-frame behavioral analysis of active tracks.

    Usage
    -----
    >>> analyzer = BehaviorAnalyzer(loitering_threshold_s=30.0, movement_threshold_px=15.0)
    >>> pipeline.register_analyzer(analyzer)
    """

    def __init__(
        self,
        loitering_threshold_s: float = 30.0,
        movement_threshold_px: float = 15.0,
        alert_cooldown_s: float = 20.0,
    ) -> None:
        """
        Parameters
        ----------
        loitering_threshold_s:
            Seconds a person must be stationary before a loitering alert fires.
        movement_threshold_px:
            Maximum centroid displacement (pixels) to consider a person stationary.
        alert_cooldown_s:
            Minimum seconds between repeated loitering alerts for the same track.
        """
        self._loitering_threshold_s = loitering_threshold_s
        self._movement_threshold_px = movement_threshold_px
        self._alert_cooldown_s = alert_cooldown_s

        self._records: Dict[int, LoiterRecord] = {}

        logger.info(
            "BehaviorAnalyzer ready | loiter=%.0fs | movement_px=%.0f",
            loitering_threshold_s,
            movement_threshold_px,
        )

    # ------------------------------------------------------------------
    # Analyzer interface
    # ------------------------------------------------------------------

    def analyze(
        self,
        tracks: List[Track],
        events: List[TrackEvent],
    ) -> List[dict]:
        """Called once per frame by Pipeline."""
        output: List[dict] = []
        now = time.time()

        # Clean up records for permanently removed tracks
        removed_ids = {
            e.track_id
            for e in events
            if e.event_type == TrackEventType.TRACK_REMOVED
        }
        for tid in removed_ids:
            self._records.pop(tid, None)

        for track in tracks:
            tid = track.track_id
            cx, cy = track.centroid

            if tid not in self._records:
                # First frame — start tracking stationary period
                self._records[tid] = LoiterRecord(
                    anchor_centroid=(cx, cy),
                    stationary_since_ts=now,
                )
                continue

            record = self._records[tid]
            displacement = self._euclidean(
                (cx, cy), record.anchor_centroid
            )

            if displacement > self._movement_threshold_px:
                # Person moved — reset anchor
                self._records[tid] = LoiterRecord(
                    anchor_centroid=(cx, cy),
                    stationary_since_ts=now,
                )
                continue

            # Person is still stationary — check duration
            stationary_duration = now - record.stationary_since_ts

            if stationary_duration >= self._loitering_threshold_s:
                cooldown_elapsed = (now - record.last_alert_ts) >= self._alert_cooldown_s
                if cooldown_elapsed:
                    record.last_alert_ts = now
                    record.alert_emitted = True

                    logger.warning(
                        "Loitering: track_id=%d  duration=%.0fs  pos=(%.0f, %.0f)",
                        tid,
                        stationary_duration,
                        cx,
                        cy,
                    )
                    output.append(
                        {
                            "type": "loitering",
                            "severity": "medium",
                            "track_id": tid,
                            "duration_s": round(stationary_duration, 1),
                            "position": (cx, cy),
                            "timestamp": now,
                        }
                    )

        return output

    def get_stationary_duration(self, track_id: int) -> float:
        """Return how long (seconds) track_id has been stationary; 0.0 if unknown."""
        record = self._records.get(track_id)
        if record is None:
            return 0.0
        return time.time() - record.stationary_since_ts

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _euclidean(
        a: Tuple[float, float], b: Tuple[float, float]
    ) -> float:
        return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)
