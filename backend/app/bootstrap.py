"""One-off super admin bootstrap. Run via `python -m app.bootstrap` after first deploy."""

import asyncio

import structlog
from sqlalchemy import select

from app.config import settings
from app.db.engine import async_session_maker
from app.models.enums import UserRole
from app.models.user import User

logger = structlog.get_logger()


async def create_super_admin() -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == settings.SUPER_ADMIN_EMAIL))
        if result.scalar_one_or_none() is not None:
            logger.info("super_admin_already_exists", email=settings.SUPER_ADMIN_EMAIL)
            return

        session.add(User(email=settings.SUPER_ADMIN_EMAIL, role=UserRole.super_admin, org_id=None))
        await session.commit()
        logger.info("super_admin_created", email=settings.SUPER_ADMIN_EMAIL)


if __name__ == "__main__":
    asyncio.run(create_super_admin())
