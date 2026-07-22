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


# --------------------------------------------------------------------------
# Platform analytics — feeds the charts in super-admin DashboardPage.
# All rollups scoped to the last N days (default 30), settable via ?days=N.
# --------------------------------------------------------------------------


class AnalyticsKpis(BaseModel):
    total_messages: int
    active_orgs: int
    total_conversations: int
    total_escalations: int
    escalation_rate_pct: float
    avg_messages_per_day: float
    estimated_cost_usd: float


class MessagesPerDayPoint(BaseModel):
    date: str  # ISO date (YYYY-MM-DD) — no timezone; day-buckets are UTC
    webchat: int
    whatsapp: int
    voice: int


class ChannelBreakdownEntry(BaseModel):
    channel: str
    count: int


class OrgAnalyticsRow(BaseModel):
    org_id: str
    org_name: str
    is_active: bool
    messages: int
    conversations: int
    escalations: int
    escalation_rate_pct: float
    estimated_cost_usd: float


class AnalyticsResponse(BaseModel):
    window_days: int
    generated_at: datetime
    kpis: AnalyticsKpis
    messages_per_day: list[MessagesPerDayPoint]
    channel_breakdown: list[ChannelBreakdownEntry]
    per_org: list[OrgAnalyticsRow]
