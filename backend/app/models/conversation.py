import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import Channel, ConversationStatus


class Conversation(Base):
    __tablename__ = "conversations"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False, index=True
    )
    channel: Mapped[Channel] = mapped_column(Enum(Channel, name="channel"), nullable=False)
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus, name="conversation_status"), nullable=False
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Voice-specific — set for channel=voice conversations only. retell_call_id
    # is how the call lifecycle webhook (call_ended) and the Custom LLM
    # WebSocket both find their way back to the same conversation row.
    retell_call_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True, unique=True)
    call_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Set to the timestamp when the AI-identity disclosure was first delivered
    # on this conversation (AI Act Art. 50). NULL = not yet sent. Checked
    # before every outbound message so the disclosure fires exactly once.
    ai_disclosure_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
