"""
api/v1/cameras.py
─────────────────
Camera CRUD endpoints.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import get_current_user
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.schemas.camera import CameraCreate, CameraOut, CameraUpdate
from backend.app.models.camera import Camera

router = APIRouter()


@router.post("/", response_model=CameraOut, status_code=status.HTTP_201_CREATED)
async def create_camera(
    payload: CameraCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    cam = Camera(**payload.model_dump())
    db.add(cam)
    await db.flush()
    await db.refresh(cam)

    # Dispatch Celery worker
    from backend.app.workers.celery_app import dispatch_camera_worker
    from backend.app.config import settings
    task_id = dispatch_camera_worker(cam.id, cam.source_url, settings.REDIS_URL)
    cam.worker_task_id = task_id
    await db.flush()

    return cam


@router.get("/", response_model=List[CameraOut])
async def list_cameras(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Camera))
    return result.scalars().all()


@router.get("/{camera_id}", response_model=CameraOut)
async def get_camera(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    cam = await db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    return cam


@router.put("/{camera_id}", response_model=CameraOut)
async def update_camera(
    camera_id: int,
    payload: CameraUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    cam = await db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(cam, field, value)
    await db.flush()
    await db.refresh(cam)
    return cam


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    cam = await db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    if cam.worker_task_id:
        from backend.app.workers.celery_app import stop_camera_worker
        stop_camera_worker(cam.worker_task_id)

    await db.delete(cam)
