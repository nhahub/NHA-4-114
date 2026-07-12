# Smart Vision System - Project Instructions

This document outlines the architecture, coding standards, and hardware optimizations for the Smart Vision System graduation project.

## Project Overview
A real-time AI-powered surveillance and analytics system for small businesses, capable of person detection, tracking, counting, and behavior analysis.

## Hardware Constraints & Optimization
The system is optimized for **low-resource hardware**:
- **VRAM:** 2GB (NVIDIA GPU)
- **RAM:** 8GB
- **OS:** Windows

### AI Optimization Rules
1. **Model Selection:** Always use **YOLOv8n** (Nano) weights for detection and training to minimize memory footprint.
2. **Training (models/train_pipeline.py):**
   - Default `batch=4` to avoid CUDA Out of Memory (OOM).
   - Default `workers=2` to keep RAM usage within 8GB.
   - Use `amp=True` (Automatic Mixed Precision) for faster, lower-memory training.
   - Disable caching (`cache=False`) to save system RAM.
3. **Inference (backend/ai/detector/person_detector.py):**
   - Use `half=True` (FP16) on GPU to reduce VRAM usage by ~50% and double speed.
   - Default `imgsz=640` or `416` depending on required precision vs. performance.
   - Ensure `torch.cuda.empty_cache()` is called if swapping models.

## Repository Structure
- `backend/`: FastAPI backend, AI processing pipeline, and WebSocket management.
- `models/`: Weights, training scripts, and experiment logs.
- `dataset/`: Dataset management and preprocessing scripts.
- `weapon-detection-1/`: The primary weapon detection dataset (ignored by git).
- `docx/`: Academic documentation and project descriptions.

## Coding Standards
- **Modularity:** Keep AI logic separate from API logic. The AI layer should be "pure" Python/NumPy.
- **Type Hinting:** Use Python type hints (`from __future__ import annotations`) for all new code.
- **Error Handling:** All AI processing steps (detection, tracking, analyzers) must be wrapped in try-except blocks within the `Pipeline`. A single frame failure should never crash the worker.
- **Style:** Follow PEP 8 and use professional, modular design patterns.

## Skills & MCPs
The project uses custom skills located in `.gemini/skills/`:
- `ai-vision`: Guidelines for YOLOv8, ByteTrack, and stream processing.
- `fastapi-backend`: Guidelines for FastAPI, WebSockets, and Celery.
- `nextjs-frontend`: Guidelines for the Next.js monitoring dashboard.

## Reference Files
- [Architecture](docx/architecture.md)
- [API Reference](docx/api-reference.md)
- [Project Structure](docx/project_structure.md)
