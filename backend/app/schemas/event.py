"""
schemas/event.py
────────────────
Pydantic schemas for event log entries.

Imported by:  api/v1/logs.py
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


EventType = Literal[
    "entry_event",
    "exit_event",
    "zone_occupancy",
    "loitering",
    "crossing_event",
]


class EventLogOut(BaseModel):
    """Response schema for a single event log entry."""
    id: int
    camera_id: int
    event_type: str
    message: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class PaginatedEvents(BaseModel):
    """Paginated list response for event logs."""
    items: List[EventLogOut]
    page: int
    limit: int
    total: int


class EventFilterParams(BaseModel):
    """Query parameters for GET /api/v1/logs."""
    camera_id: Optional[int] = None
    type: Optional[str] = None
    page: int = Field(1, ge=1)
    limit: int = Field(50, ge=1, le=200)
