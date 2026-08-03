import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import BusinessVertical


class OrganizationCreate(BaseModel):
    name: str
    industry: str
    timezone: str
    business_vertical: BusinessVertical = BusinessVertical.general
    country: str | None = None
    supported_languages: list[str] = ["en"]


class OrganizationUpdate(BaseModel):
    name: str | None = None
    industry: str | None = None
    timezone: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    is_active: bool | None = None
    is_trial: bool | None = None
    business_vertical: BusinessVertical | None = None
    data_retention_days: int | None = None
    country: str | None = None
    supported_languages: list[str] | None = None


class OrgEraseRequest(BaseModel):
    """Caller must supply the org's exact name as a confirmation step.
    Prevents accidental hard-erasure from a mis-clicked button."""
    confirm_name: str


class ChannelsEnabled(BaseModel):
    webchat: bool
    whatsapp: bool
    voice: bool


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    industry: str
    timezone: str
    address: str | None
    phone: str | None
    email: str | None
    is_active: bool
    is_trial: bool
    channels_enabled: ChannelsEnabled
    setup_completed: bool
    message_count: int
    escalation_count: int
    business_vertical: BusinessVertical
    data_retention_days: int | None
    country: str | None
    supported_languages: list[str]
    created_at: datetime


class OrganizationListResponse(BaseModel):
    organizations: list[OrganizationResponse]


class WebchatChannelStatus(BaseModel):
    enabled: bool
    configured: bool


class WhatsappChannelStatus(BaseModel):
    enabled: bool
    configured: bool
    phone_number: str | None


class VoiceChannelStatus(BaseModel):
    enabled: bool
    configured: bool
    agent_id: str | None
    phone_number: str | None
    retell_agent_id: str | None
    # Whether the agent's Custom LLM URL in Retell currently points at this
    # backend for this org. None when it couldn't be checked (no RETELL_API_KEY,
    # no agent id, or Retell's API was unreachable).
    provisioned: bool | None = None


class OrgChannelStatusResponse(BaseModel):
    webchat: WebchatChannelStatus
    whatsapp: WhatsappChannelStatus
    voice: VoiceChannelStatus


class OrgProfileResponse(BaseModel):
    """Read-only org profile for org_staff — a deliberately narrower view
    than OrganizationResponse (no is_trial/setup_completed/message counts,
    which are admin-facing concerns), but adds working_hours since that's
    what staff actually need to see about their own org."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    industry: str
    timezone: str
    address: str | None
    phone: str | None
    email: str | None
    working_hours: dict
    channels_enabled: ChannelsEnabled
