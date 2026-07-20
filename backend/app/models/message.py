import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import Channel, MessageRole


class Message(Base):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole, name="message_role"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[Channel] = mapped_column(Enum(Channel, name="channel"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )

    # WhatsApp-specific delivery tracking — populated when an AI/staff reply is
    # sent over WhatsApp, so a later status webhook (sent/delivered/read/failed)
    # can be matched back to this row via Meta's message id (wamid).
    whatsapp_message_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True, unique=True)
    delivery_status: Mapped[str | None] = mapped_column(String, nullable=True)
