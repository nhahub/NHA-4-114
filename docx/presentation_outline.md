# Graduation Project Presentation: Smart Vision System

## 1. Project Overview
- **Title:** Smart Vision System for Small Businesses.
- **Problem:** Affordable, intelligent surveillance for retail.
- **Solution:** AI for person tracking and weapon detection.

## 2. System Architecture
- **Layers:** AI Core -> Business Logic -> FastAPI Backend -> Next.js Frontend.
- **Tools:** YOLOv8, ByteTrack, WebSockets, Redis.

## 3. Hardware Optimization
- **VRAM (2GB):** FP16 Half-precision inference, imgsz=416.
- **RAM (8GB):** 0-worker data loading, batch size=2-4, no-cache training.

## 4. Key Features
- **Security:** Real-time Weapon Detection Alerts.
- **Analytics:** Heatmaps, Entry/Exit Counting, Loitering detection.

## 5. Performance
- **Target:** 15 FPS on target hardware.
- **Stability:** Robust async worker loops.
