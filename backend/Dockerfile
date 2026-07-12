# ── Smart Vision System — Backend Dockerfile ──────────────────────────────────
# Builds the FastAPI backend + AI pipeline (YOLOv8 + ByteTrack)
#
# Build context: ./backend   (run from project root: docker compose build)
# WORKDIR is / so that Python resolves:  backend.app.main  →  /backend/app/main.py

FROM python:3.11-slim

# ── System dependencies ────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory = filesystem root ───────────────────────────────────────
# The build context is ./backend, so COPY . . lands everything at /backend/.
# Python then resolves  `from backend.app.xxx`  →  /backend/app/xxx.py  ✓
WORKDIR /

# ── Python dependencies ────────────────────────────────────────────────────────
COPY requirements.txt /backend/requirements.txt
RUN pip install --no-cache-dir -r /backend/requirements.txt

# ── Application code ───────────────────────────────────────────────────────────
COPY . /backend/

# Alembic config at filesystem root so `alembic upgrade head` works from the
# default WORKDIR (/) with no -c flag. (C8)
COPY alembic.ini /alembic.ini

# ── Pre-download YOLOv8n weights ──────────────────────────────────────────────
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')" || true

# ── Import path ──────────────────────────────────────────────────────────────
# Two roots are required:
#   /backend  → makes the top-level `ai.*` namespace package importable
#               (used by the workers: `from ai.pipeline import ...`)
#   /         → makes the `backend.*` package importable
#               (everything imports `from backend.app...`; the `backend`
#                package dir is /backend, whose parent is /)
# Both are needed for Celery (-A backend.app.workers.celery_app) and Alembic
# (env.py imports backend.app.*), which do not add CWD to sys.path. (C3)
ENV PYTHONPATH=/backend:/

# ── Port ───────────────────────────────────────────────────────────────────────
EXPOSE 3000

# ── Default command ────────────────────────────────────────────────────────────
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "3000"]