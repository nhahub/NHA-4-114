"""
heatmap_generator.py
--------------------
Accumulates centroid positions into a NumPy density grid and
exports colourised heatmap PNG snapshots on request.

Design constraints:
  - No YOLO / ByteTrack imports
  - Pure NumPy + OpenCV — no display logic beyond save/export
  - Registers with Pipeline via pipeline.register_analyzer()
  - Export is triggered explicitly (REST endpoint will call export_png)
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from ..tracker.track_manager import Track, TrackEvent

logger = logging.getLogger(__name__)


class HeatmapGenerator:
    """
    Maintains a floating-point density grid over the camera frame dimensions.

    Each active track's centroid is added to the grid every frame.
    A Gaussian blur is applied at export time to smooth the density map
    into a visually interpretable heatmap.

    Usage
    -----
    >>> heatmap = HeatmapGenerator(frame_width=1280, frame_height=720)
    >>> pipeline.register_analyzer(heatmap)
    >>> # export when needed (e.g., REST /analytics/heatmap/{camera_id}):
    >>> path = heatmap.export_png("static/heatmaps/camera_1_latest.png")
    """

    def __init__(
        self,
        frame_width: int,
        frame_height: int,
        blur_kernel_size: int = 51,
        decay_rate: float = 0.0,
        colormap: int = cv2.COLORMAP_JET,
    ) -> None:
        """
        Parameters
        ----------
        frame_width, frame_height:
            Pixel dimensions of the source video frame.
        blur_kernel_size:
            Gaussian kernel size for smoothing at export time.
            Must be an odd positive integer.
        decay_rate:
            Fraction of the accumulated density to subtract each frame
            (``0.0`` = no decay; ``0.001`` = slow decay for recency bias).
        colormap:
            OpenCV colormap applied during PNG export (default: COLORMAP_JET).
        """
        self._width = frame_width
        self._height = frame_height
        self._blur_kernel_size = blur_kernel_size | 1  # ensure odd
        self._decay_rate = decay_rate
        self._colormap = colormap

        # 32-bit float grid — accumulate without overflow
        self._grid: np.ndarray = np.zeros(
            (frame_height, frame_width), dtype=np.float32
        )
        self._total_frames: int = 0
        self._total_hits: int = 0

        logger.info(
            "HeatmapGenerator ready | size=%dx%d | blur=%d | decay=%.4f",
            frame_width,
            frame_height,
            self._blur_kernel_size,
            decay_rate,
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
        Accumulate centroid positions from active tracks.
        Returns an empty list — heatmap data is retrieved via export_png().
        """
        self._total_frames += 1

        if self._decay_rate > 0.0:
            self._grid *= 1.0 - self._decay_rate

        for track in tracks:
            cx, cy = track.centroid
            gx = int(np.clip(cx, 0, self._width - 1))
            gy = int(np.clip(cy, 0, self._height - 1))
            self._grid[gy, gx] += 1.0
            self._total_hits += 1

        return []  # No inline events — data lives in self._grid

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_png(self, output_path: str | Path) -> Path:
        """
        Apply Gaussian blur, normalise, colourise, and save as PNG.

        Parameters
        ----------
        output_path:
            Destination file path (parent directory is created if needed).

        Returns
        -------
        Path
            The resolved path where the PNG was saved.

        Raises
        ------
        RuntimeError
            If the grid is empty (no data accumulated yet).
        """
        if self._total_hits == 0:
            raise RuntimeError(
                "Cannot export heatmap: no centroid data accumulated yet."
            )

        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Smooth
        blurred = cv2.GaussianBlur(
            self._grid,
            (self._blur_kernel_size, self._blur_kernel_size),
            sigmaX=0,
        )

        # Normalise to [0, 255]
        max_val = blurred.max()
        if max_val > 0:
            normalised = (blurred / max_val * 255).astype(np.uint8)
        else:
            normalised = np.zeros_like(blurred, dtype=np.uint8)

        # Apply false-colour map
        colourised = cv2.applyColorMap(normalised, self._colormap)

        cv2.imwrite(str(output_path), colourised)
        logger.info(
            "Heatmap exported: %s  (frames=%d  hits=%d)",
            output_path,
            self._total_frames,
            self._total_hits,
        )
        return output_path

    def get_raw_grid(self) -> np.ndarray:
        """Return a copy of the raw accumulation grid (for custom processing)."""
        return self._grid.copy()

    def get_overlay(self, alpha: float = 0.4) -> np.ndarray:
        """
        Return an RGBA heatmap overlay suitable for blending over a video frame.

        Parameters
        ----------
        alpha:
            Opacity of the heatmap layer (0.0 = transparent, 1.0 = opaque).
        """
        if self._total_hits == 0:
            return np.zeros((self._height, self._width, 4), dtype=np.uint8)

        blurred = cv2.GaussianBlur(
            self._grid,
            (self._blur_kernel_size, self._blur_kernel_size),
            sigmaX=0,
        )
        max_val = blurred.max()
        normalised = (blurred / max_val * 255).astype(np.uint8) if max_val > 0 else blurred.astype(np.uint8)
        colourised = cv2.applyColorMap(normalised, self._colormap)

        # Build RGBA
        rgba = cv2.cvtColor(colourised, cv2.COLOR_BGR2BGRA)
        rgba[:, :, 3] = (normalised * alpha).astype(np.uint8)
        return rgba

    def reset(self) -> None:
        """Clear the accumulated grid."""
        self._grid[:] = 0
        self._total_frames = 0
        self._total_hits = 0
        logger.info("HeatmapGenerator grid reset.")
