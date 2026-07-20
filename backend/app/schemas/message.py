import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    channel: str
    created_at: datetime


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]


class StaffMessageCreate(BaseModel):
    content: str
