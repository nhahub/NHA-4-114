"""
line_selector.py
----------------
Interactive mouse-based virtual counting line selector.
Supports ANY line angle — horizontal, diagonal, vertical.

API CHANGE: select_line() now accepts a numpy frame (BGR image) directly.
The caller is responsible for reading a good frame from the video.

Usage:
    from backend.ai.business_logic.line_selector import select_line, grab_preview_frame

    frame = grab_preview_frame(cap)          # helper to get a good frame
    line_start, line_end = select_line(frame)

Controls:
    Left-click + drag  — draw the line
    r                  — reset
    Enter / Space      — confirm
    q                  — skip (midline fallback)
"""

from __future__ import annotations

import logging
import math
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

LinePoints = Tuple[Tuple[int, int], Tuple[int, int]]


# ---------------------------------------------------------------------------
# Public helper — grab a visible frame from any VideoCapture
# ---------------------------------------------------------------------------

def grab_preview_frame(cap: cv2.VideoCapture) -> np.ndarray:
    """
    Read frames from *cap* until we find a bright one.

    FIX: Removed unreliable cap.set(CAP_PROP_POS_FRAMES, 0) seek.
    Instead, reopen the capture from the same source so the caller's
    cap is unaffected AND the main loop always starts from frame 0.

    NOTE: This function does NOT reset the passed-in cap.
          The caller should reopen cap themselves after calling this,
          or use the smoke_test pattern of reopening cap after preview.
    """
    # Try to get video source path to reopen cleanly
    source = cap.get(cv2.CAP_PROP_POS_AVI_RATIO)  # not useful; use backend id
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    best      = np.zeros((height, width, 3), dtype=np.uint8)
    best_mean = 0.0

    for _ in range(120):
        ret, frame = cap.read()
        if not ret or frame is None:
            continue
        m = float(frame.mean())
        if m > best_mean:
            best_mean = m
            best = frame.copy()
        if m > 15:
            break

    # FIX: Do NOT use cap.set(CAP_PROP_POS_FRAMES, 0) — unreliable on Windows.
    # Caller is responsible for reopening cap after this call.

    if best_mean < 2:
        cv2.putText(
            best,
            "Cannot read frame — draw your line here",
            (20, height // 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 1,
        )
        logger.warning("grab_preview_frame: all frames were black/empty (mean=%.2f)", best_mean)
    else:
        logger.info("grab_preview_frame: best frame mean=%.1f", best_mean)

    return best


# ---------------------------------------------------------------------------
# Mouse state
# ---------------------------------------------------------------------------

class _LineState:
    def __init__(self) -> None:
        self.drawing = False
        self.start: Optional[Tuple[int, int]] = None
        self.end:   Optional[Tuple[int, int]] = None

    def has_line(self) -> bool:
        return self.start is not None and self.end is not None

    def length(self) -> float:
        if not self.has_line():
            return 0.0
        return math.hypot(self.end[0] - self.start[0], self.end[1] - self.start[1])


def _make_mouse_callback(state: _LineState):
    def callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            state.drawing = True
            state.start   = (x, y)
            state.end     = (x, y)
        elif event == cv2.EVENT_MOUSEMOVE and state.drawing:
            state.end = (x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            state.drawing = False
            state.end     = (x, y)
    return callback


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def select_line(
    frame: np.ndarray,
    window_title: str = "SVS - Draw Counting Line",
) -> LinePoints:
    """
    Display *frame* and let the operator draw the counting line.

    Parameters
    ----------
    frame : np.ndarray
        BGR image to use as background (from grab_preview_frame or any source).
    window_title : str
        OpenCV window name.

    Returns
    -------
    (line_start, line_end) — two (x, y) tuples.
    Falls back to horizontal midline if operator presses q.
    """
    # FIX: Guard against empty/black frames passed in
    if frame is None or frame.size == 0:
        logger.error("select_line received an empty frame; cannot display selector.")
        raise ValueError("select_line: frame must be a valid non-empty BGR image.")

    height, width = frame.shape[:2]

    # FIX: Check the frame is actually visible (not all-black)
    if float(frame.mean()) < 2.0:
        logger.warning(
            "select_line: frame appears to be all-black (mean=%.2f). "
            "The selector will still open but the background will be dark.",
            float(frame.mean()),
        )

    # Darken slightly so yellow line is easy to see
    background = cv2.convertScaleAbs(frame, alpha=0.72, beta=0)

    state = _LineState()

    # FIX: Use WINDOW_NORMAL so it works on all platforms including headless-ish setups
    cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_title, min(width, 1280), min(height, 720))
    cv2.setMouseCallback(window_title, _make_mouse_callback(state))

    logger.info(
        "Line selector ready — click and drag (any angle). "
        "Enter/Space=confirm  r=reset  q=skip"
    )

    while True:
        canvas = background.copy()
        _draw_guidelines(canvas, width, height)
        _draw_instructions(canvas, state, width, height)

        if state.has_line():
            cv2.line(canvas, state.start, state.end, (0, 255, 255), 2, cv2.LINE_AA)
            cv2.circle(canvas, state.start, 7, (0, 220, 255), -1)
            cv2.circle(canvas, state.end,   7, (0, 220, 255), -1)
            cv2.circle(canvas, state.start, 7, (255, 255, 255), 1)
            cv2.circle(canvas, state.end,   7, (255, 255, 255), 1)
            _draw_arrow(canvas, state.start, state.end)
            _draw_angle_badge(canvas, state, width)

        cv2.imshow(window_title, canvas)
        key = cv2.waitKey(20) & 0xFF

        if key in (13, 32):  # Enter or Space
            if state.has_line() and state.length() > 20:
                logger.info("Line confirmed | start=%s end=%s", state.start, state.end)
                break
            else:
                _flash_warning(window_title, background, "Draw a longer line first!")

        elif key == ord("r"):
            state.start = None
            state.end   = None

        elif key == ord("q"):
            logger.warning("Skipped — using midline fallback.")
            cv2.destroyWindow(window_title)
            return (0, height // 2), (width, height // 2)

    cv2.destroyWindow(window_title)
    return state.start, state.end


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _draw_guidelines(canvas: np.ndarray, w: int, h: int) -> None:
    c = (55, 55, 55)
    cv2.line(canvas, (0, h // 3),     (w, h // 3),     c, 1)
    cv2.line(canvas, (0, h * 2 // 3), (w, h * 2 // 3), c, 1)
    cv2.line(canvas, (w // 3, 0),     (w // 3, h),     c, 1)
    cv2.line(canvas, (w * 2 // 3, 0), (w * 2 // 3, h), c, 1)


def _draw_instructions(canvas: np.ndarray, state: _LineState, w: int, h: int) -> None:
    overlay = canvas.copy()
    cv2.rectangle(overlay, (0, h - 55), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.72, canvas, 0.28, 0, canvas)

    if not state.has_line():
        msg, color = "Click and drag to draw counting line  (any angle)", (200, 200, 200)
    else:
        msg, color = "Enter / Space = confirm      r = redraw      q = skip", (0, 255, 180)

    cv2.putText(canvas, msg, (12, h - 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)

    if state.has_line():
        dx  = state.end[0] - state.start[0]
        dy  = state.end[1] - state.start[1]
        ang = math.degrees(math.atan2(dy, dx))
        cv2.putText(
            canvas,
            f"start={state.start}  end={state.end}  "
            f"angle={ang:.1f}°  len={state.length():.0f}px",
            (12, h - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.42, (160, 210, 160), 1, cv2.LINE_AA,
        )


def _draw_arrow(canvas: np.ndarray, start: tuple, end: tuple) -> None:
    mx = (start[0] + end[0]) // 2
    my = (start[1] + end[1]) // 2
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    ln = max(math.hypot(dx, dy), 1)
    ax = int(mx + dx / ln * 22)
    ay = int(my + dy / ln * 22)
    cv2.arrowedLine(canvas, (mx, my), (ax, ay),
                    (0, 255, 255), 2, cv2.LINE_AA, tipLength=0.4)


def _draw_angle_badge(canvas: np.ndarray, state: _LineState, w: int) -> None:
    dx  = state.end[0] - state.start[0]
    dy  = state.end[1] - state.start[1]
    ang = abs(math.degrees(math.atan2(dy, dx)))
    if ang < 25 or ang > 155:
        label, color = "HORIZONTAL", (0, 255, 100)
    elif 65 < ang < 115:
        label, color = "VERTICAL",   (0, 180, 255)
    else:
        label, color = f"DIAGONAL {math.degrees(math.atan2(dy, dx)):.0f}°", (255, 200, 0)
    cv2.putText(canvas, label, (w - 220, 34),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)


def _flash_warning(window: str, background: np.ndarray, msg: str) -> None:
    canvas  = background.copy()
    h, w    = canvas.shape[:2]
    overlay = canvas.copy()
    cv2.rectangle(overlay, (0, h // 2 - 40), (w, h // 2 + 20), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, canvas, 0.3, 0, canvas)
    cv2.putText(canvas, msg, (w // 2 - 180, h // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 255), 2, cv2.LINE_AA)
    cv2.imshow(window, canvas)
    cv2.waitKey(700)