import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    contact_id: uuid.UUID
    contact_name: str
    channel: str
    status: str
    assigned_to: uuid.UUID | None
    last_message_at: datetime
    unread_count: int
    last_message_preview: str | None


class ConversationListResponse(BaseModel):
    conversations: list[ConversationResponse]
