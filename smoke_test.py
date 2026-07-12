#!/usr/bin/env python3
"""
smoke_test.py
-------------
Phase 1 smoke test — MANUAL counting line (any angle).

Usage:
    python smoke_test.py video.mp4
    python smoke_test.py video.mp4 models/yolov8n.pt
    python smoke_test.py 0           (webcam)

Line selector controls:
    Left-click + drag  — draw line (horizontal / diagonal / vertical)
    r                  — redraw
    Enter / Space      — confirm

Playback controls:
    q  — quit
    h  — toggle heatmap overlay
    s  — save heatmap PNG
    l  — redraw counting line without restarting  (FIX: was 'r', conflicted with line selector)
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.ai.pipeline import Pipeline
from backend.ai.business_logic.line_selector import select_line, grab_preview_frame
from backend.ai.business_logic.zone_monitor import ZoneConfig, ZoneMonitor
from backend.ai.business_logic.behavior_analyzer import BehaviorAnalyzer
from backend.ai.business_logic.heatmap_generator import HeatmapGenerator
from backend.ai.frame_annotator import AnnotationConfig, FrameAnnotator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("smoke_test")


def build_demo_zones(width: int, height: int) -> list[ZoneConfig]:
    return [
        ZoneConfig(
            zone_id=1, name="Zone-A", threshold=3,
            polygon=[
                (int(width * 0.05), int(height * 0.1)),
                (int(width * 0.45), int(height * 0.1)),
                (int(width * 0.45), int(height * 0.9)),
                (int(width * 0.05), int(height * 0.9)),
            ],
        ),
        ZoneConfig(
            zone_id=2, name="Zone-B", threshold=2,
            polygon=[
                (int(width * 0.55), int(height * 0.1)),
                (int(width * 0.95), int(height * 0.1)),
                (int(width * 0.95), int(height * 0.9)),
                (int(width * 0.55), int(height * 0.9)),
            ],
        ),
    ]


def open_cap(source) -> cv2.VideoCapture:
    """Open and validate a VideoCapture. Exits on failure."""
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        logger.error("Cannot open video source: %s", source)
        sys.exit(1)
    return cap


def main() -> None:
    # Support int (webcam index) or string (file path / RTSP URL)
    raw_source   = sys.argv[1] if len(sys.argv) > 1 else "0"
    video_source = int(raw_source) if raw_source.isdigit() else raw_source
    model_path   = sys.argv[2] if len(sys.argv) > 2 else "models/yolov8n.pt"

    # ---- Open video to read dimensions ------------------------------------
    cap = open_cap(video_source)
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps    = cap.get(cv2.CAP_PROP_FPS) or 25.0
    logger.info("Video: %dx%d @ %.0f fps", width, height, fps)

    # ---- Step 1: grab preview frame for line selector ---------------------
    # FIX: Use grab_preview_frame() from line_selector (no duplicated logic).
    # FIX: After grabbing, REOPEN cap so main loop starts from frame 0.
    #      Do NOT rely on cap.set(CAP_PROP_POS_FRAMES, 0) — unreliable on Windows.
    logger.info("Reading preview frame for line selector...")
    preview_frame = grab_preview_frame(cap)   # reads up to 120 frames, picks brightest
    cap.release()                              # FIX: release THEN reopen — guaranteed frame 0
    cap = open_cap(video_source)
    logger.info("Cap reopened from frame 0 — opening line selector...")

    line_start, line_end = select_line(preview_frame, window_title="SVS - Draw Counting Line")
    logger.info("Line: %s -> %s", line_start, line_end)

    # ---- Step 2: build pipeline -------------------------------------------
    pipeline = Pipeline(
        model_path=model_path,
        weapon_model_path="models/weapon_final.pt",
        confidence_threshold=0.4,
        frame_rate=int(fps),
    )

    # set_counting_line auto-detects IN direction from angle
    counter = pipeline.set_counting_line(
        line_start=line_start,
        line_end=line_end,
        in_direction="auto",
    )

    zones        = build_demo_zones(width, height)
    zone_monitor = ZoneMonitor(zones)
    pipeline.register_analyzer(zone_monitor)

    behavior = BehaviorAnalyzer(loitering_threshold_s=10.0, movement_threshold_px=15.0)
    pipeline.register_analyzer(behavior)

    heatmap_gen = HeatmapGenerator(frame_width=width, frame_height=height)
    pipeline.register_analyzer(heatmap_gen)

    annotator = FrameAnnotator(config=AnnotationConfig())

    # ---- Runtime ----------------------------------------------------------
    show_heatmap  = False
    loitering_ids: set[int] = set()
    frame_times:   list[float] = []
    result        = None

    # FIX: Changed redraw key from 'r' to 'l' to avoid conflict with
    #      the line-selector's own 'r' = reset key inside select_line().
    logger.info("Running. [q] quit | [h] heatmap | [s] save heatmap | [l] redraw line")

    while True:
        ret, frame = cap.read()
        if not ret:
            logger.info("End of stream.")
            break

        t0 = time.perf_counter()
        result = pipeline.process_frame(frame, annotate=False)
        t_pipeline = (time.perf_counter() - t0) * 1000.0

        # Loitering tracking
        for evt in result.business_events:
            if evt.get("type") == "loitering":
                loitering_ids.add(evt["track_id"])
        loitering_ids &= {t.track_id for t in result.tracks}

        # Annotation
        zone_states = zone_monitor.get_all_states()
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

        # Heatmap overlay
        if show_heatmap and heatmap_gen._total_hits > 0:
            overlay     = heatmap_gen.get_overlay(alpha=0.45)
            bgr_overlay = cv2.cvtColor(overlay, cv2.COLOR_BGRA2BGR)
            canvas      = cv2.addWeighted(canvas, 0.7, bgr_overlay, 0.5, 0)

        # FPS stats
        frame_times.append(t_pipeline)
        if len(frame_times) > 30:
            frame_times.pop(0)
        avg_ms     = sum(frame_times) / len(frame_times)
        fps_actual = 1000.0 / avg_ms if avg_ms > 0 else 0

        cv2.putText(
            canvas,
            f"FPS:{fps_actual:.0f}  det:{len(result.detections)}"
            f"  trk:{len(result.tracks)}"
            f"  IN:{counter.count_in}  OUT:{counter.count_out}",
            (8, height - 8),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 255, 200), 1, cv2.LINE_AA,
        )

        cv2.imshow("SVS - Smart Vision System", canvas)

        key = cv2.waitKey(30) & 0xFF

        if key == ord("q"):
            logger.info("Quit.")
            break

        elif key == ord("h"):
            show_heatmap = not show_heatmap
            logger.info("Heatmap: %s", "ON" if show_heatmap else "OFF")

        elif key == ord("s"):
            try:
                out = heatmap_gen.export_png("static/heatmaps/heatmap.png")
                logger.info("Heatmap saved: %s", out)
            except RuntimeError as e:
                logger.warning("Cannot save: %s", e)

        elif key == ord("l"):
            # FIX: Redraw line without restarting pipeline.
            # FIX: Use current frame as preview instead of reading a new one
            #      (avoids a second cap.read() that would skip a frame).
            cv2.destroyWindow("SVS - Smart Vision System")
            redraw_preview = canvas.copy()  # use the last annotated frame as background
            line_start, line_end = select_line(
                redraw_preview, window_title="SVS - Redraw Counting Line"
            )
            counter = pipeline.set_counting_line(
                line_start=line_start,
                line_end=line_end,
                in_direction="auto",
            )
            logger.info("Line updated: %s → %s", line_start, line_end)

    cap.release()
    cv2.destroyAllWindows()
    logger.info(
        "Done | frames=%d | IN=%d | OUT=%d",
        result.frame_index if result else 0,
        counter.count_in,
        counter.count_out,
    )


if __name__ == "__main__":
    main()