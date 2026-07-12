"""
api/v1/auth.py
Public endpoints: POST /token, POST /refresh
Protected endpoint: GET /me
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
    get_current_user,
    _EXPIRE_HOURS,
)
from backend.app.dependencies import get_db
from backend.app.models.user import User
from backend.app.schemas.auth import LoginRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# POST /api/v1/auth/token  — Login
# ---------------------------------------------------------------------------
@router.post("/token", response_model=TokenResponse, summary="Login and obtain JWT")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == payload.username))
    user: User | None = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    # Update last_login timestamp
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(last_login=datetime.now(timezone.utc))
    )
    await db.commit()

    token = create_access_token(
        user_id=user.id,
        username=user.username,
        is_superuser=user.is_superuser,
    )
    return TokenResponse(
        access_token=token,
        expires_in=_EXPIRE_HOURS * 3600,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/auth/refresh  — Refresh token (reissue with new expiry)
# ---------------------------------------------------------------------------
@router.post("/refresh", response_model=TokenResponse, summary="Refresh JWT token")
async def refresh_token(current_user: User = Depends(get_current_user)):
    token = create_access_token(
        user_id=current_user.id,
        username=current_user.username,
        is_superuser=current_user.is_superuser,
    )
    return TokenResponse(
        access_token=token,
        expires_in=_EXPIRE_HOURS * 3600,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/auth/me  — Current user info
# ---------------------------------------------------------------------------
@router.get("/me", response_model=UserResponse, summary="Get current user info")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
