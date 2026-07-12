#!/usr/bin/env python3
"""
smoke_test.py
-------------
Phase 1 — Step 6 validation smoke test.

Verifies the complete AI pipeline end-to-end:
  1. YOLOv8 person detection
  2. ByteTrack tracking (stable IDs)
  3. Entry/exit counter (virtual line)
  4. Zone occupancy monitor
  5. Behavior analyzer (loitering)
  6. Heatmap accumulation
  7. Full frame annotation via FrameAnnotator

Usage:
    python smoke_test.py                          # opens webcam (device 0)
    python smoke_test.py path/to/video.mp4        # uses video file
    python smoke_test.py path/to/video.mp4 models/yolov8n.pt

Press 'q' to quit, 'h' to toggle heatmap overlay, 's' to save heatmap PNG.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Bootstrap path so we can import from backend/ai without installing
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # → smart-vision-system/

from backend.ai.pipeline import Pipeline
from backend.ai.business_logic.entry_exit_counter import EntryExitCounter
from backend.ai.business_logic.zone_monitor import ZoneConfig, ZoneMonitor
from backend.ai.business_logic.behavior_analyzer import BehaviorAnalyzer
from backend.ai.business_logic.heatmap_generator import HeatmapGenerator
from backend.ai.frame_annotator import AnnotationConfig, FrameAnnotator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("smoke_test")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_demo_zones(width: int, height: int) -> list[ZoneConfig]:
    """Create two representative zones scaled to the video resolution."""
    return [
        ZoneConfig(
            zone_id=1,
            name="Zone-A",
            threshold=3,
            polygon=[
                (int(width * 0.05), int(height * 0.1)),
                (int(width * 0.45), int(height * 0.1)),
                (int(width * 0.45), int(height * 0.9)),
                (int(width * 0.05), int(height * 0.9)),
            ],
        ),
        ZoneConfig(
            zone_id=2,
            name="Zone-B",
            threshold=2,
            polygon=[
                (int(width * 0.55), int(height * 0.1)),
                (int(width * 0.95), int(height * 0.1)),
                (int(width * 0.95), int(height * 0.9)),
                (int(width * 0.55), int(height * 0.9)),
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    video_source = sys.argv[1] if len(sys.argv) > 1 else 0
    model_path = sys.argv[2] if len(sys.argv) > 2 else "models/yolov8n.pt"

    # ---- Open video --------------------------------------------------------
    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        logger.error("Cannot open video source: %s", video_source)
        sys.exit(1)

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    logger.info("Video: %dx%d @ %.0f fps", width, height, fps)

    # ---- Build pipeline + analyzers ----------------------------------------
    pipeline = Pipeline(
        model_path=model_path,
        confidence_threshold=0.4,
        frame_rate=int(fps),
    )

    # Entry/exit line — horizontal midline
    line_start = (0, height // 2)
    line_end = (width, height // 2)

    counter = EntryExitCounter(
        line_start=line_start,
        line_end=line_end,
        in_direction="down",
    )
    pipeline.register_analyzer(counter)

    zones = build_demo_zones(width, height)
    zone_monitor = ZoneMonitor(zones)
    pipeline.register_analyzer(zone_monitor)

    behavior = BehaviorAnalyzer(loitering_threshold_s=10.0, movement_threshold_px=15.0)
    pipeline.register_analyzer(behavior)

    heatmap_gen = HeatmapGenerator(frame_width=width, frame_height=height)
    pipeline.register_analyzer(heatmap_gen)

    annotator = FrameAnnotator(config=AnnotationConfig())

    # ---- Runtime state -----------------------------------------------------
    show_heatmap = False
    loitering_ids: set[int] = set()
    frame_times: list[float] = []

    logger.info(
        "Smoke test started. Controls: [q] quit | [h] heatmap overlay | [s] save heatmap"
    )

    while True:
        ret, frame = cap.read()
        if not ret:
            logger.info("End of stream.")
            break

        t0 = time.perf_counter()
        result = pipeline.process_frame(frame, annotate=False)
        t_pipeline = (time.perf_counter() - t0) * 1000.0

        # Collect events from business events
        weapon_detected = False
        for evt in result.business_events:
            if evt.get("type") == "loitering":
                loitering_ids.add(evt["track_id"])
            elif evt.get("type") == "weapon_alert":
                weapon_detected = True

        # Remove loitering flag if track disappeared
        active_ids = {t.track_id for t in result.tracks}
        loitering_ids &= active_ids

        # Gather zone states for annotator
        zone_states = zone_monitor.get_all_states()

        # Full annotation pass
        canvas = annotator.annotate(
            frame=frame,
            tracks=result.tracks,
            zones=zones,
            zone_states=zone_states,
            line_start=line_start,
            line_end=line_end,
            count_in=counter.count_in,
            count_out=counter.count_out,
            loitering_ids=loitering_ids,
            frame_index=result.frame_index,
            processing_ms=t_pipeline,
        )

        if weapon_detected:
            # Draw a prominent red alert bar
            cv2.rectangle(canvas, (0, 0), (width, 40), (0, 0, 255), -1)
            cv2.putText(
                canvas, "!!! WEAPON DETECTED !!!", (width // 2 - 150, 30),
                cv2.FONT_HERSHEY_DUPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA
            )
            logger.warning("Weapon detected in frame %d", result.frame_index)

        # Optional heatmap overlay
        if show_heatmap and heatmap_gen._total_hits > 0:
            overlay = heatmap_gen.get_overlay(alpha=0.45)
            bgr_overlay = cv2.cvtColor(overlay, cv2.COLOR_BGRA2BGR)
            canvas = cv2.addWeighted(canvas, 0.7, bgr_overlay, 0.5, 0)

        # Rolling FPS
        frame_times.append(t_pipeline)
        if len(frame_times) > 30:
            frame_times.pop(0)
        avg_ms = sum(frame_times) / len(frame_times)
        fps_actual = 1000.0 / avg_ms if avg_ms > 0 else 0

        # Stats header bar
        stats = (
            f"FPS:{fps_actual:.0f}  det:{len(result.detections)}"
            f"  trk:{len(result.tracks)}"
            f"  IN:{counter.count_in}  OUT:{counter.count_out}"
        )
        cv2.putText(
            canvas, stats, (8, height - 8),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 255, 200), 1, cv2.LINE_AA,
        )

        cv2.imshow("SVS — Phase 1 Smoke Test", canvas)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            logger.info("Quit by user.")
            break
        elif key == ord("h"):
            show_heatmap = not show_heatmap
            logger.info("Heatmap overlay: %s", "ON" if show_heatmap else "OFF")
        elif key == ord("s"):
            try:
                out_path = heatmap_gen.export_png("static/heatmaps/smoke_test_heatmap.png")
                logger.info("Heatmap saved: %s", out_path)
            except RuntimeError as e:
                logger.warning("Cannot save heatmap: %s", e)

    cap.release()
    cv2.destroyAllWindows()
    logger.info(
        "Smoke test complete | frames=%d | IN=%d | OUT=%d",
        result.frame_index if "result" in dir() else 0,
        counter.count_in,
        counter.count_out,
    )


if __name__ == "__main__":
    main()
