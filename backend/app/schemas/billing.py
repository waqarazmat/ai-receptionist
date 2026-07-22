import uuid
from datetime import datetime

from pydantic import BaseModel


# ─── Super-admin billing analytics response ──────────────────────────


class BillingKpis(BaseModel):
    total_ai_messages: int
    total_usd: float
    llm_input_usd: float
    llm_output_usd: float
    external_api_usd: float
    cost_per_message_usd: float


class BillingDailyPoint(BaseModel):
    date: str  # ISO YYYY-MM-DD
    total_usd: float


class BillingProviderEntry(BaseModel):
    provider: str
    total_usd: float


class BillingChannelEntry(BaseModel):
    channel: str
    total_usd: float


class OrgBillingRow(BaseModel):
    org_id: str
    org_name: str
    plan: str
    provider: str
    ai_messages: int
    llm_input_usd: float
    llm_output_usd: float
    external_api_usd: float
    total_usd: float
    channels: dict[str, float]


class BillingAnalyticsResponse(BaseModel):
    window_days: int
    generated_at: datetime
    org_id: str | None
    kpis: BillingKpis
    cost_by_day: list[BillingDailyPoint]
    cost_by_provider: list[BillingProviderEntry]
    cost_by_channel: list[BillingChannelEntry]
    per_org: list[OrgBillingRow]


# ─── Org-staff current-month billing snapshot ────────────────────────


class PlanInfo(BaseModel):
    key: str
    display_name: str
    monthly_message_quota: int
    price_usd_monthly: int
    features: list[str]


class UsageInfo(BaseModel):
    messages_used: int
    messages_quota: int
    percent_used: float
    ai_messages_this_month: int


class ProviderInfo(BaseModel):
    key: str
    model: str
    llm_input_price_per_1k: float
    llm_output_price_per_1k: float
    input_tokens_per_message: int
    output_tokens_per_message: int


class ChannelCostEntry(BaseModel):
    channel: str
    ai_messages: int
    total_usd: float


class CostThisMonth(BaseModel):
    llm_input_usd: float
    llm_output_usd: float
    external_api_usd: float
    total_usd: float
    by_channel: list[ChannelCostEntry]


class OrgBillingSnapshotResponse(BaseModel):
    org_id: uuid.UUID
    generated_at: datetime
    month_start: datetime
    plan: PlanInfo
    usage: UsageInfo
    provider: ProviderInfo
    channel_extras_per_msg: dict[str, float]
    cost_this_month: CostThisMonth
