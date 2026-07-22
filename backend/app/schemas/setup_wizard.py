from datetime import date

from pydantic import BaseModel

from app.models.enums import ApiKeyProvider


class BasicInfoStep(BaseModel):
    name: str
    industry: str
    timezone: str
    address: str | None = None
    phone: str | None = None
    email: str | None = None


class DayHours(BaseModel):
    open: str
    close: str


class WorkingHoursStep(BaseModel):
    hours: dict[str, DayHours]
    holidays: list[date] = []


class ChannelConfigStep(BaseModel):
    webchat: bool
    whatsapp: bool
    voice: bool
    is_trial: bool


class ApiKeysStep(BaseModel):
    provider: ApiKeyProvider
    api_key: str


class WhatsappConfigStep(BaseModel):
    # Both fields are optional and saved independently so the two inline fields
    # in the wizard (display number + Meta's phone_number_id) can each save on
    # their own without clobbering the other. `phone_number` is the human-
    # readable display number; `phone_number_id` is Meta's numeric id for that
    # number — the one used to route inbound webhooks and to build the Graph
    # API send URL (see channels/whatsapp/*). They are NOT interchangeable.
    phone_number: str | None = None
    phone_number_id: str | None = None


class VoiceConfigStep(BaseModel):
    retell_agent_id: str


class KnowledgeChunkInput(BaseModel):
    content: str


class KnowledgeBaseStep(BaseModel):
    name: str
    chunks: list[KnowledgeChunkInput]


class BookingServiceInput(BaseModel):
    name: str
    duration_minutes: int
    buffer_minutes: int


class BookingConfigStep(BaseModel):
    services: list[BookingServiceInput]
    calendar_enabled: bool


class SystemPromptsStep(BaseModel):
    greeting: str
    personality: str
    escalation_rules: str
    off_topic_response: str
    # Free-form custom system prompt appended to the built prompt (see
    # app/ai/prompts/receptionist_system.py). Lets an org add extra guardrails,
    # brand voice quirks, or industry-specific context on top of the structured
    # fields above. Optional — the wizard passes an empty string when unused.
    system_prompt: str | None = None


class StaffAccessStep(BaseModel):
    emails: list[str]


class ReviewActivateStep(BaseModel):
    pass


class SetupStateResponse(BaseModel):
    setup_progress: dict[str, bool]
    setup_completed: bool
    basic_info: BasicInfoStep | None = None
    working_hours: WorkingHoursStep | None = None
    channels: ChannelConfigStep | None = None
    api_keys_configured: list[ApiKeyProvider] = []
    knowledge_base: KnowledgeBaseStep | None = None
    booking: BookingConfigStep | None = None
    system_prompts: SystemPromptsStep | None = None
    staff_emails: list[str] = []
    google_calendar_service_account_email: str | None = None
    whatsapp_phone_number: str | None = None
    whatsapp_phone_number_id: str | None = None
    voice_retell_agent_id: str | None = None
