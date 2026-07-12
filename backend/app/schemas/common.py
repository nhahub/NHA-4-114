"""
schemas/common.py
─────────────────
Shared Pydantic schemas used across multiple routers.

Rules
─────
- All paginated responses inherit from PaginatedResponse[T].
- Every paginated endpoint exposes: items, page, limit, total.
- Import these into resource-specific schema files — never redefine them.
"""

from __future__ import annotations

from typing import Generic, List, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic paginated list response.

    All list endpoints that support pagination must return this shape.

    Fields
    ------
    items  : the current page of results
    page   : current page number (1-based)
    limit  : maximum items per page
    total  : total number of matching records (across all pages)
    """
    items: List[T]
    page: int = Field(..., ge=1, description="Current page number (1-based)")
    limit: int = Field(..., ge=1, description="Items per page")
    total: int = Field(..., ge=0, description="Total matching records")


class MessageResponse(BaseModel):
    """Simple acknowledgement response for operations that return no data."""
    message: str
