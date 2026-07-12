"""
weapon_detector.py
------------------
Wraps a fine-tuned YOLOv8 model for weapon detection.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np
from ultralytics import YOLO

from .model_loader import load_model
from .person_detector import Detection

logger = logging.getLogger(__name__)

# Based on inspection of the trained weights (models/weapon_final.pt):
# 0: '-' (tight bounding box around the weapon)
# 1: 'undefined' (person holding the weapon)
# 2: 'weapon detection - v7 personNweaponGreyGenX2V2' (full person body)
WEAPON_CLASS_ID: int = 0

# Detections below this threshold are discarded
CONFIDENCE_THRESHOLD: float = 0.5


class WeaponDetector:
    """
    Runs a fine-tuned YOLOv8 model to detect weapons in BGR frames.
    """

    def __init__(
        self,
        model_path: str | Path = "models/weapon_final.pt",
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
        imgsz: int = 640,
    ) -> None:
        """
        Parameters
        ----------
        model_path:
            Path to the fine-tuned weights file.
        confidence_threshold:
            Minimum confidence to keep a detection.
        imgsz:
            Inference image size (kept at 416 for 2GB VRAM efficiency).
        """
        self._model: YOLO = load_model(model_path)
        self._confidence_threshold = confidence_threshold
        self._imgsz = imgsz
        
        logger.info(
            "WeaponDetector ready | conf_thresh=%.2f | imgsz=%d",
            self._confidence_threshold,
            self._imgsz,
        )

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        Run inference on a single BGR frame.
        """
        if frame is None or frame.size == 0:
            return []

        try:
            # Optimized for 2GB VRAM:
            is_cuda = next(self._model.parameters()).is_cuda
            results = self._model.predict(
                source=frame,
                imgsz=self._imgsz,
                conf=self._confidence_threshold,
                classes=[WEAPON_CLASS_ID], # Only look for weapons
                verbose=False,
                half=is_cuda,  # FP16 on GPU
            )
        except Exception as exc:
            logger.error("Weapon YOLO inference failed: %s", exc, exc_info=True)
            return []
        finally:
            if is_cuda:
                import torch
                torch.cuda.empty_cache()

        return self._parse_results(results)

    def _parse_results(self, results) -> List[Detection]:
        """Convert raw Ultralytics Results into Detection dataclasses."""
        detections: List[Detection] = []

        for result in results:
            if result.boxes is None:
                continue

            for box in result.boxes:
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                
                # Double check class ID
                if cls_id != WEAPON_CLASS_ID:
                    continue

                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())

                detections.append(
                    Detection(
                        bbox=(x1, y1, x2, y2),
                        confidence=conf,
                        class_id=cls_id,
                    )
                )

        if detections:
            logger.warning("ALERT: Detected %d weapon(s) in frame!", len(detections))
            
        return detections
