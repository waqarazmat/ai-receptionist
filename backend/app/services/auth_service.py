import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from app.models.user import User


class UserNotFoundError(Exception):
    pass


async def create_org_staff_user(db: AsyncSession, email: str, org_id: uuid.UUID) -> User:
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        existing.org_id = org_id
        existing.role = UserRole.org_staff
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)
        return existing

    user = User(email=email, role=UserRole.org_staff, org_id=org_id)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def list_org_staff(db: AsyncSession, org_id: uuid.UUID) -> list[User]:
    result = await db.execute(
        select(User).where(User.org_id == org_id, User.role == UserRole.org_staff).order_by(User.email)
    )
    return list(result.scalars().all())


async def remove_org_staff(db: AsyncSession, user_id: uuid.UUID, org_id: uuid.UUID) -> None:
    user = (
        await db.execute(
            select(User).where(User.id == user_id, User.org_id == org_id, User.role == UserRole.org_staff)
        )
    ).scalar_one_or_none()
    if user is None:
        raise UserNotFoundError(str(user_id))

    user.is_active = False
    await db.commit()
