"""
entry_exit_counter.py
---------------------
Detects when tracked persons cross a configurable virtual line and
counts IN / OUT transitions.

Design constraints:
  - Receives active tracks + track events from the pipeline
  - No direct YOLO / ByteTrack imports
  - Registers with Pipeline via pipeline.register_analyzer()
  - Thread-safe per-camera (single asyncio task per instance)

Configuration
-------------
Define the line as two (x, y) pixel points:
    line_start = (0, 360)
    line_end   = (1280, 360)

Direction semantics:
    For a HORIZONTAL line:
        Moving from y < line_y  →  y > line_y  counts as IN
        Moving from y > line_y  →  y < line_y  counts as OUT
    For a VERTICAL line:
        Moving from x < line_x  →  x > line_x  counts as IN
        Moving from x > line_x  →  x < line_x  counts as OUT
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

from ..tracker.track_manager import Track, TrackEvent, TrackEventType

logger = logging.getLogger(__name__)


class LineOrientation(Enum):
    HORIZONTAL = auto()
    VERTICAL = auto()


@dataclass
class CrossingEvent:
    """Emitted each time a track crosses the virtual line."""

    track_id: int
    direction: str  # "IN" or "OUT"
    position: Tuple[float, float]  # centroid at crossing moment
    timestamp: float = field(default_factory=time.time)


class EntryExitCounter:
    """
    Counts persons crossing a virtual line.

    Usage
    -----
    >>> counter = EntryExitCounter(
    ...     line_start=(0, 360), line_end=(1280, 360)
    ... )
    >>> pipeline.register_analyzer(counter)
    >>> # access totals at any time:
    >>> print(counter.count_in, counter.count_out)
    """

    def __init__(
        self,
        line_start: Tuple[int, int],
        line_end: Tuple[int, int],
        in_direction: str = "down",   # "down" | "up" | "right" | "left"
        debounce_frames: int = 10,
    ) -> None:
        """
        Parameters
        ----------
        line_start, line_end:
            Endpoints of the virtual counting line in pixel coordinates.
        in_direction:
            Which crossing direction counts as an entry:
            "down"  — centroid moves downward  (horizontal line)
            "up"    — centroid moves upward    (horizontal line)
            "right" — centroid moves rightward (vertical line)
            "left"  — centroid moves leftward  (vertical line)
        debounce_frames:
            Minimum frames between two counts for the same track ID.
            Prevents double-counting when a track oscillates near the line.
        """
        self.line_start = line_start
        self.line_end = line_end
        self._in_direction = in_direction
        self._debounce_frames = debounce_frames

        self.count_in: int = 0
        self.count_out: int = 0

        # Per-track state: last signed side (-1 or +1) relative to line
        self._track_side: Dict[int, float] = {}
        # Per-track: frame index of last counted crossing
        self._last_cross_frame: Dict[int, int] = {}
        self._frame_index: int = 0

        self._orientation = self._detect_orientation(line_start, line_end)
        logger.info(
            "EntryExitCounter ready | line=%s→%s | orientation=%s | in=%s",
            line_start,
            line_end,
            self._orientation.name,
            in_direction,
        )

    # ------------------------------------------------------------------
    # Analyzer interface (called by Pipeline)
    # ------------------------------------------------------------------

    def analyze(
        self,
        tracks: List[Track],
        events: List[TrackEvent],
    ) -> List[dict]:
        """
        Called once per frame by Pipeline.

        Returns
        -------
        List[dict]
            One dict per crossing event, serialisable for Redis/WebSocket.
        """
        self._frame_index += 1
        output: List[dict] = []

        # Remove state for tracks that were permanently removed
        removed_ids = {
            e.track_id
            for e in events
            if e.event_type == TrackEventType.TRACK_REMOVED
        }
        for tid in removed_ids:
            self._track_side.pop(tid, None)
            self._last_cross_frame.pop(tid, None)

        for track in tracks:
            crossing = self._check_crossing(track)
            if crossing is None:
                continue

            # Debounce: ignore if crossed too recently
            last = self._last_cross_frame.get(track.track_id, -self._debounce_frames)
            if self._frame_index - last < self._debounce_frames:
                continue

            self._last_cross_frame[track.track_id] = self._frame_index

            if crossing.direction == "IN":
                self.count_in += 1
            else:
                self.count_out += 1

            logger.info(
                "Crossing: track_id=%d  direction=%s  IN=%d  OUT=%d",
                crossing.track_id,
                crossing.direction,
                self.count_in,
                self.count_out,
            )

            output.append(
                {
                    "type": "crossing_event",
                    "track_id": crossing.track_id,
                    "direction": crossing.direction,
                    "count_in": self.count_in,
                    "count_out": self.count_out,
                    "occupancy": self.count_in - self.count_out,
                    "timestamp": crossing.timestamp,
                }
            )

        return output

    def reset_counts(self) -> None:
        """Reset counters to zero (e.g., at the start of each business day)."""
        self.count_in = 0
        self.count_out = 0
        self._track_side.clear()
        self._last_cross_frame.clear()
        logger.info("EntryExitCounter counts reset.")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_crossing(self, track: Track) -> Optional[CrossingEvent]:
        """
        Determine if *track* has crossed the line since last frame.
        Returns a CrossingEvent or None.
        """
        cx, cy = track.centroid
        current_side = self._signed_distance(cx, cy)

        if track.track_id not in self._track_side:
            # First observation — record side, no crossing yet
            self._track_side[track.track_id] = current_side
            return None

        prev_side = self._track_side[track.track_id]
        self._track_side[track.track_id] = current_side

        # Crossing detected when sign flips (prev and current on opposite sides)
        if (prev_side < 0 and current_side >= 0) or (prev_side > 0 and current_side <= 0):
            direction = self._classify_direction(prev_side, current_side)
            return CrossingEvent(
                track_id=track.track_id,
                direction=direction,
                position=(cx, cy),
            )

        return None

    def _signed_distance(self, cx: float, cy: float) -> float:
        """
        Return a signed scalar indicating which side of the line (cx, cy) is on.
        Positive and negative sides are determined by the line normal.
        """
        x1, y1 = self.line_start
        x2, y2 = self.line_end
        # Cross product of (line_vector) × (point_vector) gives signed area
        return (x2 - x1) * (cy - y1) - (y2 - y1) * (cx - x1)

    def _classify_direction(self, prev_side: float, current_side: float) -> str:
        """Map a side transition to IN or OUT based on in_direction config."""
        # For a horizontal line (in_direction = "down"):
        #   prev_side < 0 (above line) → current_side > 0 (below line) = moving DOWN = IN
        if self._in_direction in ("down", "right"):
            return "IN" if prev_side < 0 else "OUT"
        else:  # "up" or "left"
            return "IN" if prev_side > 0 else "OUT"

    @staticmethod
    def _detect_orientation(
        start: Tuple[int, int], end: Tuple[int, int]
    ) -> LineOrientation:
        dx = abs(end[0] - start[0])
        dy = abs(end[1] - start[1])
        return LineOrientation.HORIZONTAL if dx >= dy else LineOrientation.VERTICAL
