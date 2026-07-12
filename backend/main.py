"""
main.py
───────
FastAPI application factory for the Smart Vision System backend.

Responsibilities
────────────────
  - Create the FastAPI app
  - Register middleware (CORS)
  - Mount REST router  → /api/v1  (via api/router.py)
  - Register WebSocket endpoints  (delegate logic to websocket/handlers.py)
  - Manage application lifespan (startup / shutdown order)

Import contract
───────────────
  All REST routes     ← backend.app.api.router       (api_router)
  Shared resources    ← backend.app.dependencies      (get_ws_manager, close_redis)
  WS lifecycle logic  ← backend.app.websocket.handlers

STRICT: No AI logic. No Redis logic. No serialization. Pure wiring.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.router import api_router
from backend.app.config import settings
from backend.app.core.redis import close_redis
from backend.app.dependencies import get_ws_manager
from backend.app.websocket.handlers import handle_camera_stream, handle_alerts_stream
from backend.app.websocket.manager import ConnectionManager

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup → yield → shutdown.

    Order matters:
      1. DB     — tables must exist before any worker writes events
      2. WS manager startup  — logs readiness (Redis pool is lazy)
    Shutdown (reverse):
      1. WS manager shutdown  — cancel listeners, close WebSockets
      2. Redis pool close     — flush remaining commands
      3. DB engine dispose    — return pooled connections
    """
    logger.info("SVS Backend starting up…")

    from backend.app.db.session import init_db
    await init_db()

    ws_manager = get_ws_manager()
    await ws_manager.startup()

    logger.info(
        "SVS Backend ready — docs at http://%s:%d/docs",
        settings.HOST, settings.PORT,
    )
    yield

    logger.info("SVS Backend shutting down…")
    await ws_manager.shutdown()
    await close_redis()

    from backend.app.db.session import close_db
    await close_db()

    logger.info("SVS Backend stopped cleanly.")


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="Smart Vision System API",
        description=(
            "Real-time AI surveillance and analytics backend.\n\n"
            "- **REST** `/api/v1/` — cameras, alerts, analytics, logs, health\n"
            "- **WebSocket** `/ws/` — live annotated frames and alert stream"
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

    # ── REST API ──────────────────────────────────────────────────────────────
    app.include_router(api_router, prefix="/api/v1")

    # ── WebSocket: live camera frame stream ───────────────────────────────────
    @app.websocket("/ws/cameras/{camera_id}")
    async def camera_stream_ws(
        websocket: WebSocket,
        camera_id: int,
        manager: ConnectionManager = Depends(get_ws_manager),
    ):
        await handle_camera_stream(websocket, camera_id, manager)

    # ── WebSocket: global alert stream ────────────────────────────────────────
    @app.websocket("/ws/alerts")
    async def alerts_ws(
        websocket: WebSocket,
        manager: ConnectionManager = Depends(get_ws_manager),
    ):
        await handle_alerts_stream(websocket, manager)

    # ── Root ──────────────────────────────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    async def root():
        return {"status": "ok", "docs": "/docs", "version": "1.0.0"}

    return app


# ── ASGI entry-point ──────────────────────────────────────────────────────────
app = create_app()

# uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
