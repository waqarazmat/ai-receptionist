import uuid
from collections.abc import AsyncGenerator

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth.jwt import decode_token
from app.db.engine import async_session_maker
from app.db.rls import set_tenant_context
from app.models.enums import UserRole
from app.models.user import User
from app.security.rbac import require_org_access_dependency

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/verify-otp")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        user_id = uuid.UUID(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    async with async_session_maker() as session:
        user = await session.get(User, user_id)

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # Bind org_id (and user_id) to structlog context so every log line emitted
    # during this request automatically carries them — no need for each handler
    # to pass org_id manually. Cleared at request end by RequestIDMiddleware.
    structlog.contextvars.bind_contextvars(
        user_id=str(user.id),
        org_id=str(user.org_id) if user.org_id else "super_admin",
    )

    return user


async def require_super_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin access required")
    return user


async def require_org_staff(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.org_staff:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Org staff access required")
    return user


async def get_db_session(user: User = Depends(get_current_user)) -> AsyncGenerator[AsyncSession, None]:
    """DB session with RLS tenant context set based on the caller's role."""
    async with async_session_maker() as session:
        await set_tenant_context(session, user)
        yield session


async def get_admin_db_session(
    user: User = Depends(require_super_admin),
) -> AsyncGenerator[AsyncSession, None]:
    """DB session for super_admin routes — RLS is bypassed via table ownership."""
    async with async_session_maker() as session:
        yield session


# FastAPI dependency: 403s unless the caller (super_admin, or org_staff whose
# own org matches) may access the route's `org_id` path parameter.
require_org_access = require_org_access_dependency(get_current_user)
