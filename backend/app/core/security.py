"""
core/security.py
JWT creation, validation, and password hashing.
All secrets read from environment via config.py — never hardcoded.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, WebSocket
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.dependencies import get_db
from backend.app.schemas.auth import TokenData

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

_ALGORITHM = settings.JWT_ALGORITHM
_SECRET = settings.JWT_SECRET_KEY
_EXPIRE_HOURS = settings.JWT_EXPIRE_HOURS


def create_access_token(user_id: int, username: str, is_superuser: bool = False) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=_EXPIRE_HOURS)
    payload = {
        "sub": username,
        "user_id": user_id,
        "is_superuser": is_superuser,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def decode_token(token: str) -> TokenData:
    """Decode and validate a JWT. Raises HTTPException on failure."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
        username: Optional[str] = payload.get("sub")
        user_id: Optional[int] = payload.get("user_id")
        if username is None or user_id is None:
            raise credentials_exc
        return TokenData(
            sub=username,
            user_id=user_id,
            is_superuser=payload.get("is_superuser", False),
        )
    except JWTError:
        raise credentials_exc


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Dependency: validate JWT and return the active User ORM object."""
    from backend.app.models.user import User
    from sqlalchemy import select

    token_data = decode_token(token)

    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_superuser(current_user=Depends(get_current_user)):
    """Dependency: require superuser role."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required",
        )
    return current_user


async def ws_get_current_user(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    """
    WebSocket auth: read token from query param `?token=<jwt>`.
    Close with 4001 if invalid.
    """
    from backend.app.models.user import User
    from sqlalchemy import select

    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001)
        return None

    try:
        token_data = decode_token(token)
    except HTTPException:
        await websocket.close(code=4001)
        return None

    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        await websocket.close(code=4001)
        return None

    return user