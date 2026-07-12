"""
api/router.py
─────────────
Central REST API router aggregator for the Smart Vision System.

This is the ONLY file that main.py imports for REST routes.
All versioned sub-routers register themselves here, not in main.py.

Adding a new resource:
  1. Create  backend/app/api/v1/your_resource.py  with its APIRouter
  2. Import and include it below — that's it. main.py never changes.

Mount structure produced (all under /api/v1):
  /auth             → auth.router
  /cameras          → cameras.router
  /alerts           → alerts.router
  /analytics        → analytics.router
  /logs             → logs.router
  /health           → health.router
  /zones            → zones.router
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.v1.cameras   import router as cameras_router
from backend.app.api.v1.alerts    import router as alerts_router
from backend.app.api.v1.analytics import router as analytics_router
from backend.app.api.v1.logs      import router as logs_router
from backend.app.api.v1.health    import router as health_router
from backend.app.api.v1.auth      import router as auth_router
from backend.app.api.v1.zones     import router as zones_router

# ── Versioned root ────────────────────────────────────────────────────────────
# All REST routes are namespaced under /api/v1 in main.py.
# The prefix is set here per-resource so the tags appear correctly in /docs.

api_router = APIRouter()

api_router.include_router(
    auth_router,
    tags=["Auth"],
)

api_router.include_router(
    cameras_router,
    prefix="/cameras",
    tags=["Cameras"],
)

api_router.include_router(
    alerts_router,
    prefix="/alerts",
    tags=["Alerts"],
)

api_router.include_router(
    analytics_router,
    prefix="/analytics",
    tags=["Analytics"],
)

api_router.include_router(
    logs_router,
    prefix="/logs",
    tags=["Logs"],
)

api_router.include_router(
    health_router,
    prefix="/health",
    tags=["Health"],
)

api_router.include_router(
    zones_router,
    tags=["Zones"],
)