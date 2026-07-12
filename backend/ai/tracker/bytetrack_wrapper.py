"""
bytetrack_wrapper.py
--------------------
Wraps the ByteTrack multi-object tracker via the `supervision` library.

Design constraints (from handoff):
  - Input  : List[Detection]  (from person_detector)
  - Output : List[TrackedObject]  (track_id + bbox per active track)
  - No business logic — identity assignment only
  - No FastAPI imports

Install dependency:
    pip install supervision
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

import numpy as np

from ..detector.person_detector import Detection

logger = logging.getLogger(__name__)


@dataclass
class TrackedObject:
    """
    A single tracked person returned by ByteTrack for one frame.

    Attributes
    ----------
    track_id:
        Unique integer ID assigned by ByteTrack; stable across frames.
    bbox:
        Bounding box ``(x1, y1, x2, y2)`` in pixel coordinates.
    confidence:
        Detection confidence at the time of last association.
    is_confirmed:
        True once the track has been confirmed over multiple frames.
    """

    track_id: int
    bbox: tuple[int, int, int, int]
    confidence: float
    is_confirmed: bool = True


class ByteTrackWrapper:
    """
    Stateful wrapper around supervision's ByteTracker.

    One instance per camera — do not share across cameras because
    ByteTrack's internal Kalman filters hold per-camera state.

    Usage
    -----
    >>> tracker = ByteTrackWrapper(frame_rate=25)
    >>> tracked = tracker.update(detections, frame_shape=(720, 1280))
    """

    def __init__(
        self,
        frame_rate: int = 30,
        track_thresh: float = 0.5,
        track_buffer: int = 60,
        match_thresh: float = 0.8,
    ) -> None:
        """
        Parameters
        ----------
        frame_rate:
            Expected frames-per-second of the input stream.
            Used to tune the Kalman filter motion model.
        track_thresh:
            Minimum detection score for high-confidence track association.
        track_buffer:
            Frames to keep a lost track alive before removing it.
            Set to 60 (2 s @ 30 fps) per handoff risk-mitigation note.
        match_thresh:
            IoU threshold for track-detection matching.
        """
        try:
            import supervision as sv  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "supervision is not installed. Run:  pip install supervision"
            ) from exc

        self._sv = sv
        self._track_thresh = track_thresh
        self._track_buffer = track_buffer
        self._match_thresh = match_thresh
        self._frame_rate = frame_rate

        self._tracker = sv.ByteTrack(
            lost_track_buffer=track_buffer,
            minimum_matching_threshold=match_thresh,
            frame_rate=frame_rate,
            minimum_consecutive_frames=1,
        )

        logger.info(
            "ByteTrackWrapper initialised (supervision) | "
            "frame_rate=%d | track_buffer=%d | match_thresh=%.2f",
            frame_rate,
            track_buffer,
            match_thresh,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(
        self,
        detections: List[Detection],
        frame_shape: tuple[int, int],
    ) -> List[TrackedObject]:
        """
        Associate *detections* with existing tracks and return active tracks.

        Parameters
        ----------
        detections:
            Output of ``PersonDetector.detect()`` for the current frame.
        frame_shape:
            ``(height, width)`` of the source frame.

        Returns
        -------
        List[TrackedObject]
            All currently active tracks with stable IDs.
        """
        sv = self._sv

        if not detections:
            # Advance Kalman filters with an empty detection set
            empty = sv.Detections(
                xyxy=np.empty((0, 4), dtype=np.float32),
                confidence=np.empty(0, dtype=np.float32),
                class_id=np.empty(0, dtype=int),
            )
            try:
                self._tracker.update_with_detections(empty)
            except Exception:
                pass
            return []

        sv_dets = self._detections_to_sv(detections)

        try:
            tracked = self._tracker.update_with_detections(sv_dets)
        except Exception as exc:
            logger.error("ByteTrack update failed: %s", exc, exc_info=True)
            return []

        return self._sv_to_tracked_objects(tracked)

    def reset(self) -> None:
        """
        Reset tracker state (call between disconnected video segments).
        supervision's ByteTracker has no reset() method so we re-instantiate.
        """
        sv = self._sv
        self._tracker = sv.ByteTrack(
            lost_track_buffer=self._track_buffer,
            minimum_matching_threshold=self._match_thresh,
            frame_rate=self._frame_rate,
            minimum_consecutive_frames=1,
        )
        logger.debug("ByteTrackWrapper state reset.")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _detections_to_sv(self, detections: List[Detection]):
        """Convert Detection list → supervision Detections object."""
        sv = self._sv
        xyxy = np.array(
            [list(d.bbox) for d in detections], dtype=np.float32
        )  # shape (N, 4)
        confidence = np.array(
            [d.confidence for d in detections], dtype=np.float32
        )
        class_id = np.zeros(len(detections), dtype=int)  # all person (class 0)

        return sv.Detections(xyxy=xyxy, confidence=confidence, class_id=class_id)

    @staticmethod
    def _sv_to_tracked_objects(tracked) -> List[TrackedObject]:
        """Convert supervision Detections (with tracker_id) → TrackedObject list."""
        result: List[TrackedObject] = []

        if tracked.tracker_id is None or len(tracked.tracker_id) == 0:
            return result

        for i in range(len(tracked.xyxy)):
            tid = tracked.tracker_id[i]
            if tid is None:
                continue

            x1, y1, x2, y2 = (int(v) for v in tracked.xyxy[i])
            conf = float(tracked.confidence[i]) if tracked.confidence is not None else 1.0

            result.append(
                TrackedObject(
                    track_id=int(tid),
                    bbox=(x1, y1, x2, y2),
                    confidence=conf,
                    is_confirmed=True,
                )
            )

        return result