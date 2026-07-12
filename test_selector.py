"""
test_selector.py - test line selector directly with a known good frame
Run: python test_selector.py video_test.mp4
"""
import sys
import cv2
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Read a frame directly - same way debug_frame.py did it successfully
source = sys.argv[1] if len(sys.argv) > 1 else "video_test.mp4"

cap = cv2.VideoCapture(source)
best = None
best_mean = 0

for _ in range(30):
    ret, frame = cap.read()
    if not ret:
        break
    m = frame.mean()
    if m > best_mean:
        best_mean = m
        best = frame.copy()
    if m > 10:
        break

cap.release()
print(f"Best frame mean: {best_mean:.1f}")

if best is None or best_mean < 2:
    print("Could not get frame!")
    sys.exit(1)

# Now test select_line with this frame directly
from backend.ai.business_logic.line_selector import select_line

print("Opening selector with real frame...")
line_start, line_end = select_line(best, window_title="TEST — Draw Line")
print(f"Result: {line_start} -> {line_end}")
