import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import UserRole


class UserResponse(BaseModel):
    """Shape returned by every super-admin user endpoint. `org_name` is joined
    server-side so the frontend doesn't have to re-fetch the orgs list to
    render the users table."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    role: UserRole
    org_id: uuid.UUID | None
    org_name: str | None
    is_active: bool
    last_login: datetime | None
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    users: list[UserResponse]


class UserInviteInput(BaseModel):
    """Invite a new org_staff user. `role` is deliberately not accepted — the
    UI can only mint org_staff, never super_admin (that promotion happens via
    the SUPER_ADMIN_EMAIL env var only, per root CLAUDE.md security rule #5)."""

    email: EmailStr
    org_id: uuid.UUID


class UserUpdateInput(BaseModel):
    """PATCH shape. `is_active` toggles activation (deactivating preserves the
    audit trail). `org_id` moves a user between organizations. Neither `role`
    nor `email` is mutable through this endpoint."""

    is_active: bool | None = None
    org_id: uuid.UUID | None = None
