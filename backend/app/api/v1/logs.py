"""
api/v1/logs.py  — matches api-reference.md §6
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db
from backend.app.schemas.event import EventLogOut, PaginatedEvents
from backend.app.models.event import Event

router = APIRouter()


@router.get("/", response_model=PaginatedEvents)
async def list_event_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    camera_id: Optional[int] = None,
    event_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Event).order_by(Event.timestamp.desc())
    if camera_id:
        query = query.where(Event.camera_id == camera_id)
    if event_type:
        query = query.where(Event.event_type == event_type)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedEvents(items=items, page=page, limit=limit, total=total)


@router.get("/{event_id}", response_model=EventLogOut)
async def get_event(event_id: int, db: AsyncSession = Depends(get_db)):
    event = await db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event
