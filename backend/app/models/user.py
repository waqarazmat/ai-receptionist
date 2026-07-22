import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import UserRole


class User(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Bumped on logout and on deactivation so any refresh token that carries an
    # older value is instantly invalidated. Embedded in every access/refresh
    # token; the /refresh endpoint rejects mismatches (see app/api/auth/jwt.py
    # and app/api/auth/router.py). Non-nullable with server default 1 so
    # existing rows and new-user creation both have a sane starting value.
    token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1", default=1
    )
