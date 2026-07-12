"""models/zone.py"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Tuple
from sqlalchemy import Boolean, DateTime, Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.session import Base

class Zone(Base):
    __tablename__ = "zones"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    polygon: Mapped[List[Tuple[int, int]]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    current_occupancy: Mapped[int] = mapped_column(Integer, default=0)
    threshold: Mapped[int] = mapped_column(Integer, default=5)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
