"""
api/v1/zones.py
Full CRUD for polygon zones per camera.
All endpoints are JWT-protected.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import get_current_user
from backend.app.dependencies import get_db
from backend.app.models.zone import Zone
from backend.app.models.user import User
from backend.app.schemas.zone import ZoneCreate, ZoneUpdate, ZoneResponse

router = APIRouter(tags=["zones"])


# ---------------------------------------------------------------------------
# GET /api/v1/zones?camera_id=1
# ---------------------------------------------------------------------------
@router.get("/", response_model=List[ZoneResponse])
async def list_zones(
    camera_id: Optional[int] = Query(None, description="Filter by camera"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Zone)
    if camera_id is not None:
        stmt = stmt.where(Zone.camera_id == camera_id)
    result = await db.execute(stmt)
    return result.scalars().all()


# ---------------------------------------------------------------------------
# POST /api/v1/zones
# ---------------------------------------------------------------------------
@router.post("/", response_model=ZoneResponse, status_code=status.HTTP_201_CREATED)
async def create_zone(
    payload: ZoneCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    zone = Zone(
        camera_id=payload.camera_id,
        name=payload.name,
        polygon=payload.polygon,
        threshold=payload.threshold,
        is_active=payload.is_active,
    )
    db.add(zone)
    await db.commit()
    await db.refresh(zone)
    return zone


# ---------------------------------------------------------------------------
# GET /api/v1/zones/{zone_id}
# ---------------------------------------------------------------------------
@router.get("/{zone_id}", response_model=ZoneResponse)
async def get_zone(
    zone_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    zone = await _get_or_404(db, zone_id)
    return zone


# ---------------------------------------------------------------------------
# PUT /api/v1/zones/{zone_id}
# ---------------------------------------------------------------------------
@router.put("/{zone_id}", response_model=ZoneResponse)
async def update_zone(
    zone_id: int,
    payload: ZoneUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    zone = await _get_or_404(db, zone_id)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(zone, field, value)

    await db.commit()
    await db.refresh(zone)
    return zone


# ---------------------------------------------------------------------------
# DELETE /api/v1/zones/{zone_id}
# ---------------------------------------------------------------------------
@router.delete("/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_zone(
    zone_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    zone = await _get_or_404(db, zone_id)
    await db.delete(zone)
    await db.commit()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
async def _get_or_404(db: AsyncSession, zone_id: int) -> Zone:
    result = await db.execute(select(Zone).where(Zone.id == zone_id))
    zone = result.scalar_one_or_none()
    if zone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found")
    return zone
