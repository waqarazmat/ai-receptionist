"""Team management for org staff — self-service teammate invites.

Uses the same user_service.invite_user primitive as the super-admin Users
tab, but hard-scopes to the current user's org_id and role=org_staff.
Prevents a compromised org_staff account from inviting a user into a
different tenant (a real risk given how tempting a "just move to my org"
flow would be to build). No cross-org invites here — full stop.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_db_session, require_org_staff
from app.models.user import User
from app.schemas.user import UserInviteInput, UserResponse
from app.services import user_service
from app.services.audit_service import log_action

logger = structlog.get_logger()
router = APIRouter()


class TeammateInviteInput(BaseModel):
    """Simpler payload than UserInviteInput — org_id is inferred from the
    current user's session, so the caller cannot pass one."""
    email: EmailStr


@router.post("/team/invite", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def invite_teammate(
    body: TeammateInviteInput,
    request: Request,
    current_user: User = Depends(require_org_staff),
    db: AsyncSession = Depends(get_admin_db_session),
) -> UserResponse:
    """Invite another user to join the current staff member's organization.

    New users always land as `org_staff`. There is no path for org_staff to
    mint a super_admin — that's enforced at the schema layer too
    (UserInviteInput hard-codes role=org_staff).
    """
    if current_user.org_id is None:
        # Defensive: org_staff without an org shouldn't exist by construction,
        # but if it does, refuse rather than injecting a null org_id downstream.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must belong to an organization to invite teammates.",
        )

    try:
        user = await user_service.invite_user(
            db,
            UserInviteInput(email=body.email, org_id=current_user.org_id),
        )
    except user_service.EmailAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )
    except user_service.OrganizationNotFoundForUserError:
        # Shouldn't happen — current_user.org_id came out of the DB — but
        # covers the race where an org gets deleted between login and invite.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    await log_action(
        db,
        user_id=current_user.id,
        # Distinct action string so audit-log filters can separate staff
        # self-service invites from super-admin invites.
        action="team.invite",
        target_type="user",
        target_id=user["id"],
        details={"email": user["email"], "org_id": str(current_user.org_id)},
        ip_address=request.client.host if request.client else None,
    )
    return UserResponse.model_validate(user)
