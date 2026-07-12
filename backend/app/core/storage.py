"""
core/storage.py
───────────────
Local and cloud storage abstraction for the Smart Vision System.
Currently handles heatmap image persistence to the local filesystem.

Phase 3 note: replace StorageService with an async MinIO client wrapper
(miniopy-async or aiobotocore) that uploads to svs-media bucket and returns
pre-signed URLs. The public API (save_heatmap / upload_snapshot) should
remain stable so callers need no changes.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
STATIC_DIR = BASE_DIR / "static"
HEATMAP_DIR = STATIC_DIR / "heatmaps"

HEATMAP_DIR.mkdir(parents=True, exist_ok=True)


class StorageService:
    """Handles file I/O for AI-generated artifacts."""

    @staticmethod
    def save_heatmap(camera_id: int | str, heatmap: np.ndarray) -> str:
        """
        Save a heatmap BGR frame to the static directory.
        Returns the relative URL path for the API.
        """
        filename = f"camera_{camera_id}_latest.png"
        filepath = HEATMAP_DIR / filename
        try:
            cv2.imwrite(str(filepath), heatmap)
            logger.debug("[Storage] Saved heatmap: %s", filepath)
            return f"/static/heatmaps/{filename}"
        except Exception as exc:
            logger.error("[Storage] Failed to save heatmap for camera %s: %s", camera_id, exc)
            raise


storage_service = StorageService()
