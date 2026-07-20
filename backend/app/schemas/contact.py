import uuid
from datetime import datetime

from pydantic import BaseModel


class ContactResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    phone: str | None
    email: str | None
    channel: str
    conversation_count: int
    last_contact_at: datetime | None


class ContactListResponse(BaseModel):
    contacts: list[ContactResponse]


class ContactConversationEntry(BaseModel):
    id: uuid.UUID
    channel: str
    status: str
    last_message_at: datetime


class ContactDetailResponse(ContactResponse):
    conversations: list[ContactConversationEntry]
