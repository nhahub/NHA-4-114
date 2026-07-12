"""
main.py
───────
FastAPI application factory for the Smart Vision System backend.

Mounts:
  - REST API routers  → /api/v1/cameras, /alerts, /analytics, /health, /logs
  - WebSocket routes  → /ws/cameras/{camera_id}  and  /ws/alerts
  - Lifespan hooks    → startup (ConnectionManager, DB) / shutdown (cleanup)

STRICT: No AI logic here. Backend orchestrates; AI layer is untouched.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.websocket.manager import manager as ws_manager

# ── REST routers ──────────────────────────────────────────────────────────────
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.cameras import router as cameras_router
from backend.app.api.v1.alerts import router as alerts_router
from backend.app.api.v1.analytics import router as analytics_router
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.logs import router as logs_router
from backend.app.api.v1.zones import router as zones_router

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup → yield → shutdown."""
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info("SVS Backend starting up…")

    # 1. Connect WebSocket manager to Redis
    await ws_manager.startup()

    # 2. Initialise DB engine (import here to avoid circular imports)
    from backend.app.db.session import init_db
    await init_db()

    logger.info("SVS Backend ready.")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("SVS Backend shutting down…")
    await ws_manager.shutdown()

    from backend.app.db.session import close_db
    await close_db()
    logger.info("SVS Backend stopped.")


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="Smart Vision System API",
        description=(
            "Real-time AI surveillance analytics backend. "
            "Streams annotated camera frames and security alerts."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── REST routers ──────────────────────────────────────────────────────────
    api_prefix = "/api/v1"
    app.include_router(auth_router,       prefix=api_prefix,                       tags=["auth"])
    app.include_router(cameras_router,   prefix=f"{api_prefix}/cameras",          tags=["cameras"])
    app.include_router(alerts_router,    prefix=f"{api_prefix}/alerts",            tags=["alerts"])
    app.include_router(analytics_router, prefix=f"{api_prefix}/analytics",         tags=["analytics"])
    app.include_router(health_router,    prefix=f"{api_prefix}/health",            tags=["health"])
    app.include_router(logs_router,      prefix=f"{api_prefix}/logs",              tags=["logs"])
    app.include_router(zones_router,     prefix=f"{api_prefix}/zones",             tags=["zones"])

    # ── Static Files (Heatmaps, etc.) ─────────────────────────────────────────
    from backend.app.core.storage import STATIC_DIR
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # ── WebSocket: per-camera frame stream ────────────────────────────────────
    @app.websocket("/ws/cameras/{camera_id}")
    async def camera_stream_ws(websocket: WebSocket, camera_id: int):
        """
        WebSocket endpoint — streams annotated JPEG frames + events.
        """
        await ws_manager.connect(websocket, camera_id)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.debug("[WS /cameras/%s] Unexpected error: %s", camera_id, exc)
        finally:
            await ws_manager.disconnect(websocket, camera_id)

    # ── WebSocket: global alert stream ────────────────────────────────────────
    @app.websocket("/ws/alerts")
    async def alerts_ws(websocket: WebSocket):
        """
        WebSocket endpoint — streams live alert notifications from all cameras.
        """
        await ws_manager.connect(websocket, "alerts")
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.debug("[WS /alerts] Unexpected error: %s", exc)
        finally:
            await ws_manager.disconnect(websocket, "alerts")

    # ── Root health redirect ───────────────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    async def root():
        return {"status": "ok", "docs": "/docs"}

    return app


# ── ASGI entry-point ──────────────────────────────────────────────────────────
app = create_app()
