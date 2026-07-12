"""
debug_frame.py - diagnose why frame appears black
Run: python debug_frame.py video_test.mp4
"""
import sys
import cv2
import numpy as np

source = sys.argv[1] if len(sys.argv) > 1 else "video_test.mp4"

print(f"Opening: {source}")
cap = cv2.VideoCapture(source)
print(f"Opened: {cap.isOpened()}")
print(f"Width:  {cap.get(cv2.CAP_PROP_FRAME_WIDTH)}")
print(f"Height: {cap.get(cv2.CAP_PROP_FRAME_HEIGHT)}")
print(f"FPS:    {cap.get(cv2.CAP_PROP_FPS)}")
print(f"Frames: {cap.get(cv2.CAP_PROP_FRAME_COUNT)}")
print()

for i in range(10):
    ret, frame = cap.read()
    if not ret:
        print(f"Frame {i}: FAILED to read")
        continue
    mean = frame.mean() if frame is not None else -1
    print(f"Frame {i}: shape={frame.shape}  mean={mean:.2f}  {'OK' if mean > 5 else 'BLACK'}")

cap.release()

# Now try showing frame 5
cap2 = cv2.VideoCapture(source)
for _ in range(5):
    cap2.read()
ret, frame = cap2.read()
cap2.release()

if ret and frame is not None and frame.mean() > 5:
    print(f"\nShowing frame — mean={frame.mean():.1f}")
    cv2.imshow("Test Frame", frame)
    print("Press any key to close...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()
else:
    print(f"\nFrame is black or unreadable — mean={frame.mean() if frame is not None else 'None'}")
    print("Try: is the video file corrupted? Can you open it in VLC?")
