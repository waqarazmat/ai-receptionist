import enum


class UserRole(str, enum.Enum):
    super_admin = "super_admin"
    org_staff = "org_staff"


class Channel(str, enum.Enum):
    webchat = "webchat"
    whatsapp = "whatsapp"
    voice = "voice"


class ConversationStatus(str, enum.Enum):
    active = "active"
    escalated = "escalated"
    resolved = "resolved"


class MessageRole(str, enum.Enum):
    customer = "customer"
    ai = "ai"
    staff = "staff"


class AppointmentStatus(str, enum.Enum):
    held = "held"
    confirmed = "confirmed"
    cancelled = "cancelled"


class EscalationPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class EscalationStatus(str, enum.Enum):
    pending = "pending"
    picked_up = "picked_up"
    resolved = "resolved"


class ApiKeyProvider(str, enum.Enum):
    openai = "openai"
    anthropic = "anthropic"
    cohere = "cohere"
    whatsapp = "whatsapp"
    google_calendar = "google_calendar"
    retell = "retell"


class BillingPlan(str, enum.Enum):
    """Subscription tiers. `free` is the default at org creation.
    Quotas live in app.billing.plans — kept out of the enum so a plan
    tuning change doesn't need a migration."""
    free = "free"
    starter = "starter"
    pro = "pro"
    enterprise = "enterprise"
