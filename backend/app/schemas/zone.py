from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# Polygon is a list of [x, y] integer pairs
Polygon = List[List[int]]


class ZoneCreate(BaseModel):
    camera_id: int
    name: str = Field(..., min_length=1, max_length=128)
    polygon: Polygon = Field(..., min_length=3, description="At least 3 points required")
    threshold: int = Field(default=5, ge=1, description="Max occupancy before alert fires")
    is_active: bool = True


class ZoneUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    polygon: Optional[Polygon] = None
    threshold: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class ZoneResponse(BaseModel):
    id: int
    camera_id: int
    name: str
    polygon: Polygon
    threshold: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
