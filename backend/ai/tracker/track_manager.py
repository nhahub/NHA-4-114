"""
track_manager.py
----------------
Maintains the canonical state of all tracks in the system.

Responsibilities:
  - Reconcile ByteTrack output with previous frame's track set
  - Drive the ACTIVE / LOST / REMOVED state machine per track
  - Compute derived attributes: centroid, age, velocity
  - Emit TrackEvent notifications on state transitions

Design constraints:
  - No FastAPI imports
  - No business logic (no loitering, no zone checks — those live in business_logic/)
  - Thread-safe if a single asyncio task calls update() sequentially
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

from .bytetrack_wrapper import TrackedObject

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class TrackState(Enum):
    """Lifecycle state of a tracked person."""

    ACTIVE = auto()    # Currently visible and confirmed
    LOST = auto()      # Not seen in the last N frames; Kalman predicts position
    REMOVED = auto()   # Permanently dropped; track_id will not be reused


class TrackEventType(Enum):
    """Events emitted when a track changes state."""

    TRACK_CREATED = auto()
    TRACK_UPDATED = auto()
    TRACK_LOST = auto()
    TRACK_RECOVERED = auto()
    TRACK_REMOVED = auto()


# ---------------------------------------------------------------------------
# Data-transfer objects
# ---------------------------------------------------------------------------


@dataclass
class Track:
    """
    Full state of a single tracked person.

    Attributes
    ----------
    track_id : int
        Unique identifier; stable for the lifetime of the track.
    bbox : tuple[int, int, int, int]
        Latest bounding box ``(x1, y1, x2, y2)``.
    centroid : tuple[float, float]
        Centre point ``(cx, cy)`` derived from *bbox*.
    age : int
        Total number of frames this track has existed.
    frames_since_seen : int
        Frames elapsed since the tracker last associated a detection.
        Reset to 0 on each association; incremented every frame when lost.
    state : TrackState
        Current lifecycle state.
    confidence : float
        Confidence of the most recent detection.
    first_seen_ts : float
        Unix timestamp when this track was first created.
    last_seen_ts : float
        Unix timestamp of the last detection association.
    velocity : tuple[float, float]
        Pixel-per-frame velocity ``(vx, vy)`` estimated from last two positions.
        ``(0.0, 0.0)`` until at least two frames have been seen.
    """

    track_id: int
    bbox: tuple[int, int, int, int]
    centroid: tuple[float, float]
    age: int = 0
    frames_since_seen: int = 0
    state: TrackState = TrackState.ACTIVE
    confidence: float = 1.0
    first_seen_ts: float = field(default_factory=time.time)
    last_seen_ts: float = field(default_factory=time.time)
    velocity: tuple[float, float] = (0.0, 0.0)
    _prev_centroid: Optional[tuple[float, float]] = field(default=None, repr=False)

    @staticmethod
    def centroid_from_bbox(bbox: tuple[int, int, int, int]) -> tuple[float, float]:
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


@dataclass(frozen=True)
class TrackEvent:
    """
    Notification emitted by TrackManager on a state transition.

    Consumed by business_logic modules to react to lifecycle changes
    without coupling to TrackManager internals.
    """

    event_type: TrackEventType
    track_id: int
    track: Track
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# TrackManager
# ---------------------------------------------------------------------------


class TrackManager:
    """
    Reconciles ByteTrack output with the persistent track registry.

    Usage
    -----
    >>> manager = TrackManager(max_frames_lost=45)
    >>> events = manager.update(tracked_objects)
    >>> active_tracks = manager.get_active_tracks()
    """

    def __init__(self, max_frames_lost: int = 45) -> None:
        """
        Parameters
        ----------
        max_frames_lost:
            After this many consecutive frames without an association,
            a LOST track transitions to REMOVED.
            45 frames ≈ 1.5 s at 30 fps — keeps lost tracks through brief
            occlusions without polluting memory indefinitely.
        """
        self._tracks: Dict[int, Track] = {}
        self._max_frames_lost = max_frames_lost
        logger.info("TrackManager initialised | max_frames_lost=%d", max_frames_lost)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, tracked_objects: List[TrackedObject]) -> List[TrackEvent]:
        """
        Reconcile *tracked_objects* (ByteTrack output) with the registry.

        Call once per frame **after** ByteTrack has run.

        Parameters
        ----------
        tracked_objects:
            Output of ``ByteTrackWrapper.update()`` for the current frame.

        Returns
        -------
        List[TrackEvent]
            Zero or more state-transition events that occurred this frame.
            Business-logic modules should iterate these to react.
        """
        events: List[TrackEvent] = []
        seen_ids = {obj.track_id for obj in tracked_objects}

        # ---- 1. Process detections returned by ByteTrack this frame ----
        for obj in tracked_objects:
            tid = obj.track_id

            if tid not in self._tracks:
                # Brand new track
                track = self._create_track(obj)
                self._tracks[tid] = track
                events.append(
                    TrackEvent(
                        event_type=TrackEventType.TRACK_CREATED,
                        track_id=tid,
                        track=track,
                    )
                )
            else:
                existing = self._tracks[tid]
                was_lost = existing.state == TrackState.LOST

                updated = self._update_track(existing, obj)
                self._tracks[tid] = updated

                if was_lost:
                    events.append(
                        TrackEvent(
                            event_type=TrackEventType.TRACK_RECOVERED,
                            track_id=tid,
                            track=updated,
                        )
                    )
                else:
                    events.append(
                        TrackEvent(
                            event_type=TrackEventType.TRACK_UPDATED,
                            track_id=tid,
                            track=updated,
                        )
                    )

        # ---- 2. Age tracks that ByteTrack did NOT return this frame ----
        to_remove: List[int] = []
        for tid, track in self._tracks.items():
            if tid in seen_ids or track.state == TrackState.REMOVED:
                continue

            aged = self._age_track(track)
            self._tracks[tid] = aged

            if aged.state == TrackState.LOST and track.state == TrackState.ACTIVE:
                events.append(
                    TrackEvent(
                        event_type=TrackEventType.TRACK_LOST,
                        track_id=tid,
                        track=aged,
                    )
                )
            elif aged.state == TrackState.REMOVED:
                to_remove.append(tid)
                events.append(
                    TrackEvent(
                        event_type=TrackEventType.TRACK_REMOVED,
                        track_id=tid,
                        track=aged,
                    )
                )

        # ---- 3. Remove permanently dropped tracks from registry ----
        for tid in to_remove:
            del self._tracks[tid]

        logger.debug(
            "TrackManager | active=%d | events=%d",
            len(self.get_active_tracks()),
            len(events),
        )
        return events

    def get_active_tracks(self) -> List[Track]:
        """Return all tracks with state == ACTIVE."""
        return [t for t in self._tracks.values() if t.state == TrackState.ACTIVE]

    def get_all_tracks(self) -> List[Track]:
        """Return all tracks regardless of state (includes LOST)."""
        return list(self._tracks.values())

    def get_track(self, track_id: int) -> Optional[Track]:
        """Look up a single track by ID; returns None if not found."""
        return self._tracks.get(track_id)

    def reset(self) -> None:
        """Clear all track state (call between disconnected video segments)."""
        self._tracks.clear()
        logger.debug("TrackManager state reset.")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _create_track(obj: TrackedObject) -> Track:
        centroid = Track.centroid_from_bbox(obj.bbox)
        return Track(
            track_id=obj.track_id,
            bbox=obj.bbox,
            centroid=centroid,
            age=1,
            frames_since_seen=0,
            state=TrackState.ACTIVE,
            confidence=obj.confidence,
            first_seen_ts=time.time(),
            last_seen_ts=time.time(),
            velocity=(0.0, 0.0),
            _prev_centroid=None,
        )

    @staticmethod
    def _update_track(existing: Track, obj: TrackedObject) -> Track:
        now = time.time()
        new_centroid = Track.centroid_from_bbox(obj.bbox)

        # Estimate velocity from previous centroid
        if existing._prev_centroid is not None:
            vx = new_centroid[0] - existing._prev_centroid[0]
            vy = new_centroid[1] - existing._prev_centroid[1]
            velocity: Tuple[float, float] = (vx, vy)
        else:
            velocity = (0.0, 0.0)

        return Track(
            track_id=obj.track_id,
            bbox=obj.bbox,
            centroid=new_centroid,
            age=existing.age + 1,
            frames_since_seen=0,
            state=TrackState.ACTIVE,
            confidence=obj.confidence,
            first_seen_ts=existing.first_seen_ts,
            last_seen_ts=now,
            velocity=velocity,
            _prev_centroid=existing.centroid,
        )

    def _age_track(self, track: Track) -> Track:
        """Increment *frames_since_seen* and advance state if threshold exceeded."""
        frames_since_seen = track.frames_since_seen + 1
        age = track.age + 1

        if frames_since_seen >= self._max_frames_lost:
            new_state = TrackState.REMOVED
        else:
            new_state = TrackState.LOST

        return Track(
            track_id=track.track_id,
            bbox=track.bbox,
            centroid=track.centroid,
            age=age,
            frames_since_seen=frames_since_seen,
            state=new_state,
            confidence=track.confidence,
            first_seen_ts=track.first_seen_ts,
            last_seen_ts=track.last_seen_ts,
            velocity=track.velocity,
            _prev_centroid=track._prev_centroid,
        )
