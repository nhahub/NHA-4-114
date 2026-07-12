"""
db/seed.py
Creates the first superuser if the users table is empty.
Called from main.py startup event.

Reads credentials from environment:
    FIRST_SUPERUSER       (default: admin)
    FIRST_SUPERUSER_PASSWORD (default: changeme)
"""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.core.security import hash_password
from backend.app.models.user import User

logger = logging.getLogger(__name__)


async def seed_superuser(db: AsyncSession) -> None:
    result = await db.execute(select(User).limit(1))
    existing = result.scalar_one_or_none()

    if existing:
        return  # users already exist — skip seeding

    superuser = User(
        username=settings.FIRST_SUPERUSER,
        hashed_password=hash_password(settings.FIRST_SUPERUSER_PASSWORD),
        is_active=True,
        is_superuser=True,
    )
    db.add(superuser)
    await db.commit()
    logger.info("✅ Superuser '%s' created", settings.FIRST_SUPERUSER)