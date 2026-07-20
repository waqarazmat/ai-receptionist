import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import Channel


class ChannelConfig(Base):
    __tablename__ = "channel_configs"
    __table_args__ = (UniqueConstraint("org_id", "channel_type", name="uq_channel_configs_org_channel"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    channel_type: Mapped[Channel] = mapped_column(Enum(Channel, name="channel"), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
