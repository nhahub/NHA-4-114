"""
pipeline.py
-----------
Single orchestration point for the AI layer.

Public surface:  pipeline.process_frame(frame) -> PipelineResult

This is the ONLY file camera_worker.py should import from the ai/ package.
All other ai/ modules are internal implementation details.

Design constraints (from handoff):
  - pipeline.py is the integration point; if something breaks, start here
  - ai/ module is pure Python — no FastAPI imports anywhere in this file
  - All exceptions caught here; workers must never crash due to a single bad frame
  - Business logic events are collected from pluggable analyzers registered at init
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np

from .detector.person_detector import Detection, PersonDetector
from .detector.weapon_detector import WeaponDetector
from .tracker.bytetrack_wrapper import ByteTrackWrapper, TrackedObject
from .tracker.track_manager import Track, TrackEvent, TrackManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PipelineResult — the single output contract
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    """
    Everything produced by one call to ``Pipeline.process_frame()``.

    Attributes
    ----------
    annotated_frame:
        BGR NumPy array with bounding boxes, track IDs, etc. drawn on it.
        ``None`` if annotation was skipped (e.g., ``annotate=False``).
    detections:
        Raw detections from the person detector (before tracking).
    weapon_detections:
        Raw detections from the weapon detector.
    tracks:
        Active tracks with stable IDs after ByteTrack association.
    events:
        Track lifecycle events emitted by TrackManager this frame.
    business_events:
        Higher-level events from business logic analyzers
        (entry/exit, zone alerts, loitering flags, etc.).
    frame_index:
        Zero-based frame counter incremented each call.
    timestamp:
        Unix timestamp at the start of processing this frame.
    processing_time_ms:
        Wall-clock milliseconds spent inside ``process_frame()``.
    """

    annotated_frame: Optional[np.ndarray]
    detections: List[Detection]
    tracks: List[Track]
    events: List[TrackEvent]
    weapon_detections: List[Detection] = field(default_factory=list)
    business_events: List[dict] = field(default_factory=list)
    frame_index: int = 0
    timestamp: float = field(default_factory=time.time)
    processing_time_ms: float = 0.0


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class Pipeline:
    """
    Orchestrates detection → tracking → (business logic) → annotation.

    One instance per camera.  Not thread-safe — call from a single asyncio
    task or Celery worker per camera.
    """

    def __init__(
        self,
        model_path: str | Path = "models/yolov8n.pt",
        weapon_model_path: str | Path = "models/yolov8n.pt",
        confidence_threshold: float = 0.4,
        frame_rate: int = 30,
        max_frames_lost: int = 45,
        imgsz: int = 640,
        weapon_imgsz: int = 416,
    ) -> None:
        """
        Parameters
        ----------
        model_path:
            Path to YOLOv8n weights file for persons.
        weapon_model_path:
            Path to fine-tuned weights for weapons.
        confidence_threshold:
            Minimum YOLO confidence to accept a detection.
        frame_rate:
            Expected FPS of the source video — used to tune ByteTrack.
        max_frames_lost:
            Frames a track can be lost before being permanently removed.
        imgsz:
            YOLO inference image size for persons.
        weapon_imgsz:
            YOLO inference image size for weapons.
        """
        self._detector = PersonDetector(
            model_path=model_path,
            confidence_threshold=confidence_threshold,
            imgsz=imgsz,
        )
        try:
            self._weapon_detector: Optional[WeaponDetector] = WeaponDetector(
                model_path=weapon_model_path,
                confidence_threshold=confidence_threshold,
                imgsz=weapon_imgsz,
            )
        except FileNotFoundError:
            logger.warning(
                "Weapon model not found at '%s' — weapon detection disabled.",
                weapon_model_path,
            )
            self._weapon_detector = None
        self._tracker = ByteTrackWrapper(
            frame_rate=frame_rate,
            track_buffer=max_frames_lost,
        )
        self._track_manager = TrackManager(max_frames_lost=max_frames_lost)

        self._analyzers: list = []
        self._annotator = None

        self._frame_index: int = 0
        logger.info(
            "Pipeline initialised | person_model=%s | weapon_model=%s",
            Path(model_path).name,
            Path(weapon_model_path).name,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_frame(
        self,
        frame: np.ndarray,
        annotate: bool = True,
    ) -> PipelineResult:
        """
        Run the full AI pipeline on a single frame.
        """
        t_start = time.perf_counter()
        self._frame_index += 1

        detections: List[Detection] = []
        weapon_detections: List[Detection] = []
        tracked_objects: List[TrackedObject] = []
        track_events: List[TrackEvent] = []
        business_events: List[dict] = []
        annotated_frame: Optional[np.ndarray] = None

        # ---- Stage 1: Detection ----------------------------------------
        try:
            detections = self._detector.detect(frame)
            if self._weapon_detector is not None:
                weapon_detections = self._weapon_detector.detect(frame)
                for wd in weapon_detections:
                    business_events.append({
                        "type": "weapon_alert",
                        "severity": "critical",
                        "confidence": wd.confidence,
                        "bbox": wd.bbox,
                        "timestamp": time.time(),
                        "message": "!!! WEAPON DETECTED !!!",
                    })
            all_detections = detections + weapon_detections
        except Exception as exc:
            logger.error("[Frame %d] Detection failed: %s", self._frame_index, exc, exc_info=True)

        # ---- Stage 2: Tracking -----------------------------------------
        try:
            h, w = frame.shape[:2]
            tracked_objects = self._tracker.update(all_detections, frame_shape=(h, w))
        except Exception as exc:
            logger.error("[Frame %d] Tracking failed: %s", self._frame_index, exc, exc_info=True)

        # ---- Stage 3: Track manager ------------------------------------
        try:
            track_events = self._track_manager.update(tracked_objects)
        except Exception as exc:
            logger.error("[Frame %d] TrackManager failed: %s", self._frame_index, exc, exc_info=True)

        active_tracks = self._track_manager.get_active_tracks()

        # ---- Stage 4: Business logic analyzers ------------------------
        for analyzer in self._analyzers:
            try:
                events = analyzer.analyze(active_tracks, track_events)
                business_events.extend(events)
            except Exception as exc:
                logger.error("[Frame %d] Analyzer %s failed: %s", self._frame_index, type(analyzer).__name__, exc, exc_info=True)

        processing_ms = (time.perf_counter() - t_start) * 1000.0

        # ---- Stage 5: Annotation ----------------------------------------
        if annotate:
            try:
                if self._annotator:
                    # Logic for full-featured annotator if needed
                    # (Currently smoke test calls annotator manually)
                    pass
                annotated_frame = self._annotate(frame, active_tracks, weapon_detections)
            except Exception as exc:
                logger.error("[Frame %d] Annotation failed: %s", self._frame_index, exc, exc_info=True)
                annotated_frame = frame.copy()

        return PipelineResult(
            annotated_frame=annotated_frame,
            detections=detections,
            weapon_detections=weapon_detections,
            tracks=active_tracks,
            events=track_events,
            business_events=business_events,
            frame_index=self._frame_index,
            timestamp=time.time(),
            processing_time_ms=processing_ms,
        )

    def register_analyzer(self, analyzer) -> None:
        self._analyzers.append(analyzer)
        logger.info("Registered analyzer: %s", type(analyzer).__name__)

    def reset(self) -> None:
        self._tracker.reset()
        self._track_manager.reset()
        self._frame_index = 0
        logger.info("Pipeline state reset.")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _annotate(self, frame: np.ndarray, tracks: List[Track], weapon_detections: List[Detection] = None) -> np.ndarray:
        import cv2

        canvas = frame.copy()
        # Draw tracks
        for track in tracks:
            x1, y1, x2, y2 = track.bbox
            color = self._id_to_color(track.track_id)
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
            label = f"ID:{track.track_id} {track.confidence:.2f}"
            cv2.putText(canvas, label, (x1, max(y1 - 8, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)

        # Draw weapons
        if weapon_detections:
            for wd in weapon_detections:
                x1, y1, x2, y2 = wd.bbox
                cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 0, 255), 3)
                cv2.putText(canvas, "WEAPON!", (x1, max(y1 - 12, 20)), cv2.FONT_HERSHEY_DUPLEX, 0.8, (0, 0, 255), 2, cv2.LINE_AA)

            # Visual Alert bar
            cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 40), (0, 0, 255), -1)
            cv2.putText(canvas, "!!! WEAPON DETECTED !!!", (canvas.shape[1] // 2 - 150, 30), cv2.FONT_HERSHEY_DUPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)

        return canvas

    @staticmethod
    def _id_to_color(track_id: int) -> tuple[int, int, int]:
        palette = [
            (255, 56, 56), (255, 157, 151), (255, 112, 31), (255, 178, 29),
            (207, 210, 49), (72, 249, 10), (146, 204, 23), (61, 219, 134),
            (26, 147, 52), (0, 212, 187), (44, 153, 168), (0, 194, 255),
            (52, 69, 147), (100, 115, 255), (0, 24, 236), (132, 56, 255),
            (82, 0, 133), (203, 56, 255), (255, 149, 200), (255, 55, 199),
        ]
        return palette[track_id % len(palette)]


if __name__ == "__main__":
    import sys
    import cv2

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")

    video_source = sys.argv[1] if len(sys.argv) > 1 else 0
    model_path = sys.argv[2] if len(sys.argv) > 2 else "models/yolov8n.pt"

    pipeline = Pipeline(model_path=model_path, weapon_model_path=model_path)

    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        sys.exit(1)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        result = pipeline.process_frame(frame, annotate=True)
        cv2.imshow("SVS", result.annotated_frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()


# ---------------------------------------------------------------------------
# Backwards-compatible alias
# ---------------------------------------------------------------------------
# Workers that pre-date the Pipeline rename import AIPipeline by name.
# Keep this alias so those imports resolve without touching every caller.
AIPipeline = Pipeline
