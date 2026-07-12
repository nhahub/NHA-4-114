#!/usr/bin/env python3
"""
test_weapon_live.py
-------------------
Standalone test script to verify the fine-tuned Weapon Detection YOLOv8 model.
It strictly uses only the WeaponDetector logic and does not rely on the full backend or tracking layers.

Usage:
    python test_weapon_live.py              (uses webcam 0)
    python test_weapon_live.py video.mp4    (uses a video file)
"""

import sys
import time
import tempfile
import cv2
import torch
import numpy as np
import streamlit as st
from PIL import Image
from pathlib import Path

# Add project root to path so we can import the backend detector correctly
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.ai.detector.weapon_detector import WeaponDetector

st.set_page_config(page_title="Weapon Detection Test", layout="wide")

@st.cache_resource
def load_detector():
    model_path = "models/weapon_final.pt"
    if not Path(model_path).exists():
        st.error(f"ERROR: Model file not found at {model_path}.")
        st.stop()
    return WeaponDetector(
        model_path=model_path,
        confidence_threshold=0.15,
        imgsz=416
    )

def process_frame(detector, frame):
    t0 = time.perf_counter()
    detections = detector.detect(frame)
    t_inference = (time.perf_counter() - t0) * 1000

    # Draw detections
    canvas = frame.copy()
    for det in detections:
        x1, y1, x2, y2 = det.bbox
        # Draw bright RED box for WEAPONS
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 0, 255), 3)
        # Label
        label = f"WEAPON! {det.confidence:.2f}"
        cv2.putText(
            canvas, label, (x1, max(y1 - 10, 20)), 
            cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA
        )

    fps = 1000.0 / t_inference if t_inference > 0 else 0
    vram = torch.cuda.memory_allocated() / 1024**2 if torch.cuda.is_available() else 0
    
    info_text = f"FPS: {fps:.1f} | VRAM: {vram:.0f}MB | Detections: {len(detections)}"
    cv2.putText(
        canvas, info_text, (10, 30), 
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA
    )
    return canvas

def main():
    st.title("🔫 Live Weapon Detection Test")
    st.write("Upload an image or a video file (since you probably don't have a weapon handy for the webcam!) to test the 50-epoch model.")

    detector = load_detector()

    uploaded_file = st.file_uploader("Upload Image or Video", type=["jpg", "jpeg", "png", "mp4", "avi", "mov"])

    if uploaded_file is not None:
        file_type = uploaded_file.name.split('.')[-1].lower()

        if file_type in ['jpg', 'jpeg', 'png']:
            # Process Image
            image = Image.open(uploaded_file).convert('RGB')
            frame = np.array(image)
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            st.write("Processing image...")
            result_bgr = process_frame(detector, frame_bgr)
            result_rgb = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)

            st.image(result_rgb, caption="Processed Image", use_container_width=True)

        elif file_type in ['mp4', 'avi', 'mov']:
            # Process Video
            st.write("Processing video... (This might be slow in Streamlit, but it demonstrates the model)")
            
            # Save uploaded video to a temporary file
            tfile = tempfile.NamedTemporaryFile(delete=False) 
            tfile.write(uploaded_file.read())
            
            cap = cv2.VideoCapture(tfile.name)
            
            frame_placeholder = st.empty()
            stop_button = st.button("Stop Video")

            while cap.isOpened() and not stop_button:
                ret, frame = cap.read()
                if not ret:
                    st.write("End of video.")
                    break
                
                result_bgr = process_frame(detector, frame)
                result_rgb = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)
                
                frame_placeholder.image(result_rgb, channels="RGB", use_container_width=True)
                
            cap.release()

if __name__ == "__main__":
    main()
