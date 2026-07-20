import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ApiKeyProvider


class OrgApiKey(Base):
    __tablename__ = "org_api_keys"
    __table_args__ = (UniqueConstraint("org_id", "provider", name="uq_org_api_keys_org_provider"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    provider: Mapped[ApiKeyProvider] = mapped_column(
        Enum(ApiKeyProvider, name="api_key_provider"), nullable=False
    )
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
