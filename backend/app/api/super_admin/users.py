"""Super-admin Users management endpoints. Every route is audit-logged per
root CLAUDE.md security rule #10."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_db_session, require_super_admin
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import (
    UserInviteInput,
    UserListResponse,
    UserResponse,
    UserUpdateInput,
)
from app.services import user_service
from app.services.audit_service import log_action

router = APIRouter()


@router.get("/users", response_model=UserListResponse)
async def list_users(
    q: str | None = Query(default=None, description="Case-insensitive email substring"),
    org_id: uuid.UUID | None = Query(default=None),
    role: UserRole | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    db: AsyncSession = Depends(get_admin_db_session),
) -> UserListResponse:
    users = await user_service.list_users(db, q=q, org_id=org_id, role=role, is_active=is_active)
    return UserListResponse(users=[UserResponse.model_validate(u) for u in users])


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_admin_db_session),
) -> UserResponse:
    try:
        user = await user_service.get_user(db, user_id)
    except user_service.UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse.model_validate(user)


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def invite_user(
    body: UserInviteInput,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> UserResponse:
    try:
        user = await user_service.invite_user(db, body)
    except user_service.EmailAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )
    except user_service.OrganizationNotFoundForUserError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    await log_action(
        db,
        user_id=current_user.id,
        action="user.invite",
        target_type="user",
        target_id=user["id"],
        details={"email": user["email"], "org_id": str(user["org_id"])},
        ip_address=request.client.host if request.client else None,
    )
    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdateInput,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_admin_db_session),
) -> UserResponse:
    try:
        user = await user_service.update_user(db, user_id, body, current_user_id=current_user.id)
    except user_service.UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    except user_service.OrganizationNotFoundForUserError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    except user_service.SelfMutationForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await log_action(
        db,
        user_id=current_user.id,
        # Split the action so audit-log filters can tell activation from
        # reassignment apart at a glance.
        action=(
            "user.deactivate" if body.is_active is False
            else "user.activate" if body.is_active is True
            else "user.reassign" if body.org_id is not None
            else "user.update"
        ),
        target_type="user",
        target_id=user_id,
        details=body.model_dump(exclude_unset=True),
        ip_address=request.client.host if request.client else None,
    )
    return UserResponse.model_validate(user)
