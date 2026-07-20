"""Super-admin user management. The auth flow itself lives in auth_service —
this module only exposes the CRUD needed by the super-admin Users tab.

Guarantees enforced here (not in the router):
- New users are always `org_staff`. Super-admin creation belongs to the env
  var + bootstrap path only (root CLAUDE.md security rule #5).
- Users cannot deactivate or move themselves through this API (would trivially
  lock the super admin out of the panel — but org_staff too, if we ever expose
  self-service endpoints later).
- Email uniqueness is checked before insert with a friendly error rather than
  letting Postgres raise an integrity error the router has to unwrap.
"""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from app.models.organization import Organization
from app.models.user import User
from app.schemas.user import UserInviteInput, UserUpdateInput


class UserNotFoundError(Exception):
    pass


class EmailAlreadyExistsError(Exception):
    pass


class OrganizationNotFoundForUserError(Exception):
    pass


class SelfMutationForbiddenError(Exception):
    """Raised when the current super admin tries to deactivate or move
    themselves through the users API — that would lock them out of the panel
    with no way back short of a database edit."""


def _row_to_response(row: tuple[User, str | None]) -> dict:
    """Turn the (User, org_name) join tuple into the dict shape UserResponse
    expects. Kept as a dict so callers can push it straight through
    UserResponse.model_validate without hand-rolling every field."""
    user, org_name = row
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "org_id": user.org_id,
        "org_name": org_name,
        "is_active": user.is_active,
        "last_login": user.last_login,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def _base_select():
    """SELECT users LEFT JOIN organizations — the join is left because
    super_admin rows carry org_id=NULL by design."""
    return select(User, Organization.name).outerjoin(Organization, Organization.id == User.org_id)


async def list_users(
    db: AsyncSession,
    *,
    q: str | None = None,
    org_id: uuid.UUID | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> list[dict]:
    stmt = _base_select()
    if q:
        # Case-insensitive substring on email — fine for MVP; if the users
        # table ever gets big we'd want a trigram index and ILIKE with a
        # prefix pattern instead.
        pattern = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(User.email).like(pattern)))
    if org_id is not None:
        stmt = stmt.where(User.org_id == org_id)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    stmt = stmt.order_by(User.created_at.desc())

    rows = (await db.execute(stmt)).all()
    return [_row_to_response(row) for row in rows]


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> dict:
    row = (await db.execute(_base_select().where(User.id == user_id))).first()
    if row is None:
        raise UserNotFoundError(str(user_id))
    return _row_to_response(tuple(row))


async def invite_user(db: AsyncSession, data: UserInviteInput) -> dict:
    """Creates the user row so their first OTP-request succeeds. We do NOT
    send an invite email from here — the moment they hit request-otp with
    this email, auth_service issues the code via Brevo. Frontend explains
    that flow to the admin."""
    existing = (
        await db.execute(select(User.id).where(func.lower(User.email) == data.email.lower()))
    ).scalar_one_or_none()
    if existing is not None:
        raise EmailAlreadyExistsError(data.email)

    org = (
        await db.execute(select(Organization).where(Organization.id == data.org_id))
    ).scalar_one_or_none()
    if org is None:
        raise OrganizationNotFoundForUserError(str(data.org_id))

    user = User(
        email=data.email,
        role=UserRole.org_staff,
        org_id=data.org_id,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _row_to_response((user, org.name))


async def update_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: UserUpdateInput,
    *,
    current_user_id: uuid.UUID,
) -> dict:
    row = (await db.execute(_base_select().where(User.id == user_id))).first()
    if row is None:
        raise UserNotFoundError(str(user_id))
    user, _prev_org_name = row

    if user.id == current_user_id and (data.is_active is False or data.org_id is not None):
        # Explicit block; without this a super admin could lock themselves
        # out via the API by toggling their own is_active.
        raise SelfMutationForbiddenError(
            "You cannot deactivate or reassign your own account."
        )

    if data.org_id is not None:
        # Verify the target org exists before mutating.
        target_org = (
            await db.execute(select(Organization).where(Organization.id == data.org_id))
        ).scalar_one_or_none()
        if target_org is None:
            raise OrganizationNotFoundForUserError(str(data.org_id))
        user.org_id = data.org_id

    if data.is_active is not None:
        user.is_active = data.is_active

    await db.commit()
    await db.refresh(user)

    # Re-read the joined org name in case org_id changed.
    org_name = (
        await db.execute(select(Organization.name).where(Organization.id == user.org_id))
    ).scalar_one_or_none() if user.org_id else None
    return _row_to_response((user, org_name))
