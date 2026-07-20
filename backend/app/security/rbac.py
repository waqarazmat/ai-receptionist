import uuid
from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, status

from app.models.enums import UserRole as RoleEnum
from app.models.user import User

__all__ = ["RoleEnum", "check_org_access", "require_org_access_dependency"]


def check_org_access(user: User, org_id: uuid.UUID) -> bool:
    """True if `user` may access data belonging to `org_id`.

    super_admin always passes; org_staff only for their own org.
    """
    if user.role == RoleEnum.super_admin:
        return True
    return user.org_id == org_id


def require_org_access_dependency(
    get_current_user: Callable[..., Awaitable[User]],
) -> Callable[..., Awaitable[User]]:
    """Build a FastAPI dependency that 403s unless the caller may access the
    route's `org_id` path parameter.

    Takes the api layer's `get_current_user` as an argument rather than
    importing it directly — security/ must not import upward from api/ per
    backend/CLAUDE.md's dependency-flow rule. Compose it once in app/api/deps.py:
        require_org_access = require_org_access_dependency(get_current_user)
    """

    async def _dependency(org_id: uuid.UUID, user: User = Depends(get_current_user)) -> User:
        if not check_org_access(user, org_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to this organization is not permitted",
            )
        return user

    return _dependency
