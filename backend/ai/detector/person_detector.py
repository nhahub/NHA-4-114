"""
person_detector.py
------------------
Wraps YOLOv8 inference and returns structured Detection objects.

Design constraints (from handoff):
  - Input  : np.ndarray  (BGR frame from OpenCV)
  - Output : List[Detection]
  - Filters detections with confidence < CONFIDENCE_THRESHOLD
  - No FastAPI imports — pure Python / NumPy / Ultralytics only
  - No business logic here — raw bounding boxes + confidence only
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import numpy as np
from ultralytics import YOLO

from .model_loader import load_model

logger = logging.getLogger(__name__)

# YOLO class index for "person" in the COCO dataset
PERSON_CLASS_ID: int = 0

# Detections below this threshold are discarded
CONFIDENCE_THRESHOLD: float = 0.4


@dataclass(frozen=True)
class Detection:
    """
    A single person detection from one video frame.

    Attributes
    ----------
    bbox:
        Bounding box as ``(x1, y1, x2, y2)`` in pixel coordinates.
    confidence:
        Model confidence score in ``[0.0, 1.0]``.
    class_id:
        YOLO class index (always ``0`` for person in Phase 1).
    track_id:
        Assigned by the tracker layer; ``-1`` means not yet tracked.
    """

    bbox: tuple[int, int, int, int]
    confidence: float
    class_id: int = PERSON_CLASS_ID
    track_id: int = -1


class PersonDetector:
    """
    Runs YOLOv8 inference on BGR frames and returns person detections.

    Usage
    -----
    >>> detector = PersonDetector(model_path="models/yolov8n.pt")
    >>> detections = detector.detect(frame)   # frame is np.ndarray BGR
    """

    def __init__(
        self,
        model_path: str | Path = "models/yolov8n.pt",
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
        imgsz: int = 640,
    ) -> None:
        """
        Parameters
        ----------
        model_path:
            Path to YOLOv8 weights (loaded via model_loader cache).
        confidence_threshold:
            Minimum confidence to keep a detection.
        imgsz:
            Inference image size passed to YOLO (must be multiple of 32).
        """
        self._model: YOLO = load_model(model_path)
        self._confidence_threshold = confidence_threshold
        self._imgsz = imgsz
        logger.info(
            "PersonDetector ready | conf_thresh=%.2f | imgsz=%d",
            self._confidence_threshold,
            self._imgsz,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        Run inference on a single BGR frame.

        Parameters
        ----------
        frame:
            OpenCV BGR image as ``np.ndarray`` of shape ``(H, W, 3)``.

        Returns
        -------
        List[Detection]
            Person detections filtered by confidence threshold.
            Empty list when no persons are found or on inference error.
        """
        if frame is None or frame.size == 0:
            logger.warning("detect() received an empty frame — skipping.")
            return []

        try:
            # Optimized for 2GB VRAM:
            # - half=True: Uses FP16 inference, significantly reducing VRAM usage and increasing speed on GPUs.
            is_cuda = next(self._model.parameters()).is_cuda
            results = self._model.predict(
                source=frame,
                imgsz=self._imgsz,
                conf=self._confidence_threshold,
                classes=[PERSON_CLASS_ID],
                verbose=False,
                half=is_cuda,  # Enable FP16 only on GPU
            )
        except Exception as exc:
            logger.error("YOLO inference failed: %s", exc, exc_info=True)
            return []

        return self._parse_results(results)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_results(self, results) -> List[Detection]:
        """Convert raw Ultralytics Results into Detection dataclasses."""
        detections: List[Detection] = []

        for result in results:
            if result.boxes is None:
                continue

            for box in result.boxes:
                conf = float(box.conf[0])
                if conf < self._confidence_threshold:
                    continue

                cls_id = int(box.cls[0])
                if cls_id != PERSON_CLASS_ID:
                    continue

                # xyxy format — convert to int pixel coords
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())

                detections.append(
                    Detection(
                        bbox=(x1, y1, x2, y2),
                        confidence=conf,
                        class_id=cls_id,
                    )
                )

        logger.debug("Detected %d person(s) in frame.", len(detections))
        return detections
