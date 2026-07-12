"""
frame_annotator.py
------------------
Full annotation pass applied to each video frame after the AI pipeline runs.

Draws:
  - Bounding boxes with track IDs and confidence scores
  - Zone polygons with occupancy labels
  - Virtual entry/exit line with IN/OUT counters
  - Loitering indicator (flashing border or warning label)
  - Processing metadata overlay (FPS, frame count)
  - Weapon detections with prominent alerts
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from .tracker.track_manager import Track
from .detector.person_detector import Detection
from .business_logic.zone_monitor import ZoneConfig, ZoneState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Colour palette — deterministic, high-contrast BGR colours per track ID
# ---------------------------------------------------------------------------

_PALETTE = [
    (255, 56, 56),   (255, 157, 151), (255, 112, 31),  (255, 178, 29),
    (207, 210, 49),  (72, 249, 10),   (146, 204, 23),  (61, 219, 134),
    (26, 147, 52),   (0, 212, 187),   (44, 153, 168),  (0, 194, 255),
    (52, 69, 147),   (100, 115, 255), (0, 24, 236),    (132, 56, 255),
    (82, 0, 133),    (203, 56, 255),  (255, 149, 200), (255, 55, 199),
]


def track_color(track_id: int) -> Tuple[int, int, int]:
    return _PALETTE[track_id % len(_PALETTE)]


# ---------------------------------------------------------------------------
# AnnotationConfig
# ---------------------------------------------------------------------------


@dataclass
class AnnotationConfig:
    """
    Controls what the annotator draws and at what visual fidelity.
    """

    draw_boxes: bool = True
    draw_track_ids: bool = True
    draw_weapons: bool = True
    draw_zones: bool = True
    draw_entry_line: bool = True
    draw_counters: bool = True
    draw_loitering_flags: bool = True
    draw_meta_overlay: bool = True
    box_thickness: int = 2
    font_scale: float = 0.55
    font_thickness: int = 2


# ---------------------------------------------------------------------------
# FrameAnnotator
# ---------------------------------------------------------------------------


class FrameAnnotator:
    """
    Stateless annotator — call ``annotate()`` once per frame.
    """

    def __init__(self, config: Optional[AnnotationConfig] = None) -> None:
        self._cfg = config or AnnotationConfig()
        logger.info("FrameAnnotator initialised.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def annotate(
        self,
        frame: np.ndarray,
        tracks: List[Track],
        weapon_detections: Optional[List[Detection]] = None,
        zones: Optional[List[ZoneConfig]] = None,
        zone_states: Optional[Dict[int, ZoneState]] = None,
        line_start: Optional[Tuple[int, int]] = None,
        line_end: Optional[Tuple[int, int]] = None,
        count_in: int = 0,
        count_out: int = 0,
        loitering_ids: Optional[set] = None,
        frame_index: int = 0,
        processing_ms: float = 0.0,
    ) -> np.ndarray:
        """
        Draw all configured annotations onto a copy of *frame*.
        """
        canvas = frame.copy()
        loitering_ids = loitering_ids or set()

        if self._cfg.draw_zones and zones and zone_states:
            self._draw_zones(canvas, zones, zone_states)

        if self._cfg.draw_entry_line and line_start and line_end:
            self._draw_entry_line(canvas, line_start, line_end, count_in, count_out)

        if self._cfg.draw_boxes:
            self._draw_tracks(canvas, tracks, loitering_ids)

        if self._cfg.draw_counters:
            self._draw_counters(canvas, count_in, count_out)

        if self._cfg.draw_meta_overlay:
            self._draw_meta(canvas, frame_index, processing_ms, len(tracks))

        if self._cfg.draw_weapons and weapon_detections:
            self._draw_weapons(canvas, weapon_detections)

        return canvas

    # ------------------------------------------------------------------
    # Drawing primitives
    # ------------------------------------------------------------------

    def _draw_tracks(
        self,
        canvas: np.ndarray,
        tracks: List[Track],
        loitering_ids: set,
    ) -> None:
        cfg = self._cfg
        for track in tracks:
            x1, y1, x2, y2 = track.bbox
            color = track_color(track.track_id)
            is_loitering = track.track_id in loitering_ids

            if is_loitering:
                draw_color = (0, 0, 255)
                thickness = cfg.box_thickness + 2
            else:
                draw_color = color
                thickness = cfg.box_thickness

            cv2.rectangle(canvas, (x1, y1), (x2, y2), draw_color, thickness)

            if cfg.draw_track_ids:
                label = f"ID:{track.track_id}"
                if is_loitering and cfg.draw_loitering_flags:
                    label += " [LOITER]"

                label_y = max(y1 - 8, 14)
                cv2.putText(canvas, label, (x1, label_y), cv2.FONT_HERSHEY_SIMPLEX, cfg.font_scale, draw_color, cfg.font_thickness, cv2.LINE_AA)
                
                conf_label = f"{track.confidence:.2f}"
                cv2.putText(canvas, conf_label, (x1, label_y + 18), cv2.FONT_HERSHEY_SIMPLEX, cfg.font_scale * 0.75, draw_color, 1, cv2.LINE_AA)

    def _draw_weapons(
        self,
        canvas: np.ndarray,
        detections: List[Detection],
    ) -> None:
        """Draw prominent red boxes and alert bar for weapons."""
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            color = (0, 0, 255)
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 3)
            
            label = f"WEAPON {det.confidence:.2f}"
            cv2.putText(canvas, label, (x1, max(y1 - 10, 25)), cv2.FONT_HERSHEY_DUPLEX, 0.8, color, 2, cv2.LINE_AA)

        if detections:
            h, w = canvas.shape[:2]
            overlay = canvas.copy()
            cv2.rectangle(overlay, (0, 0), (w, 50), (0, 0, 255), -1)
            cv2.addWeighted(overlay, 0.6, canvas, 0.4, 0, canvas)
            cv2.putText(canvas, "!!! SECURITY ALERT: WEAPON DETECTED !!!", (w // 2 - 250, 35), cv2.FONT_HERSHEY_DUPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)

    def _draw_zones(
        self,
        canvas: np.ndarray,
        zones: List[ZoneConfig],
        zone_states: Dict[int, ZoneState],
    ) -> None:
        for zone in zones:
            state = zone_states.get(zone.zone_id)
            if state is None: continue
            pts = np.array(zone.polygon, dtype=np.int32)
            if state.alert_active:
                zone_color = (0, 0, 200)
                overlay_alpha = 0.25
            else:
                zone_color = (0, 180, 0)
                overlay_alpha = 0.15
            overlay = canvas.copy()
            cv2.fillPoly(overlay, [pts], zone_color)
            cv2.addWeighted(overlay, overlay_alpha, canvas, 1 - overlay_alpha, 0, canvas)
            cv2.polylines(canvas, [pts], isClosed=True, color=zone_color, thickness=2)
            cx = int(pts[:, 0].mean())
            cy = int(pts[:, 1].mean())
            label = f"{zone.name} {state.occupancy}/{zone.threshold}"
            cv2.putText(canvas, label, (cx - 50, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

    def _draw_entry_line(
        self,
        canvas: np.ndarray,
        line_start: Tuple[int, int],
        line_end: Tuple[int, int],
        count_in: int,
        count_out: int,
    ) -> None:
        cv2.line(canvas, line_start, line_end, (0, 255, 255), 2, cv2.LINE_AA)
        mid_x = (line_start[0] + line_end[0]) // 2
        mid_y = (line_start[1] + line_end[1]) // 2
        cv2.putText(canvas, f"IN:{count_in} OUT:{count_out}", (mid_x - 60, mid_y - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2, cv2.LINE_AA)

    def _draw_counters(self, canvas: np.ndarray, count_in: int, count_out: int) -> None:
        h = canvas.shape[0]
        cv2.rectangle(canvas, (0, h - 50), (220, h), (0, 0, 0), -1)
        cv2.putText(canvas, f"IN: {count_in} OUT: {count_out}", (8, h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 200), 2, cv2.LINE_AA)

    def _draw_meta(self, canvas: np.ndarray, frame_index: int, processing_ms: float, track_count: int) -> None:
        fps_est = 1000.0 / processing_ms if processing_ms > 0 else 0.0
        text = f"Frame:{frame_index} {processing_ms:.1f}ms ~{fps_est:.0f}fps tracks:{track_count}"
        cv2.putText(canvas, text, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)
