import uuid
from datetime import datetime

from pydantic import BaseModel


class RecentActivityEntry(BaseModel):
    action: str
    target_id: uuid.UUID | None
    user_id: uuid.UUID
    details: dict
    created_at: datetime


class DashboardResponse(BaseModel):
    total_orgs: int
    active_orgs: int
    total_messages_today: int
    total_escalations_pending: int
    recent_activity: list[RecentActivityEntry]


class RecentConversationEntry(BaseModel):
    id: uuid.UUID
    contact_name: str
    channel: str
    status: str
    last_message_at: datetime


class OrgDashboardResponse(BaseModel):
    messages_today: int
    open_escalations: int
    upcoming_appointments_24h: int
    active_conversations: int
    recent_conversations: list[RecentConversationEntry]
