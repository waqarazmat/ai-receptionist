from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import BillingPlan, BusinessVertical


class Organization(Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    industry: Mapped[str] = mapped_column(String, nullable=False)
    timezone: Mapped[str] = mapped_column(String, nullable=False)
    working_hours: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_trial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Subscription tier. All new orgs land on `free`. Per-plan quotas live
    # in app.billing.plans so tuning them doesn't need a migration.
    plan: Mapped[BillingPlan] = mapped_column(
        Enum(BillingPlan, name="billing_plan"),
        nullable=False,
        default=BillingPlan.free,
        server_default=BillingPlan.free.value,
    )
    channels_enabled: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=lambda: {"webchat": False, "whatsapp": False, "voice": False}
    )
    setup_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    address: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)

    # Tracks which setup-wizard steps are complete, e.g. {"basic_info": true, ...}
    setup_progress: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    booking_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=lambda: {"services": [], "calendar_enabled": False}
    )
    system_prompts: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Compliance fields ────────────────────────────────────────────────────────
    # Drives per-vertical AI guardrail injection and default retention windows.
    business_vertical: Mapped[BusinessVertical] = mapped_column(
        Enum(BusinessVertical, name="business_vertical"),
        nullable=False,
        default=BusinessVertical.general,
        server_default=BusinessVertical.general.value,
    )
    # Per-org GDPR retention window in days. NULL → use settings.DEFAULT_CONVERSATION_RETENTION_DAYS.
    data_retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # ISO 3166-1 alpha-2 country code (e.g. "BE", "NL", "FR"). Groundwork for
    # per-country legal-text variants; no per-country logic is built yet.
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)

    # ISO 639-1 codes the Retell voice agent presents as a selection menu,
    # e.g. ["en", "nl", "fr"].  A single entry skips the menu entirely and
    # goes straight to that language.  Defaults to ["en"] for all existing orgs.
    supported_languages: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=lambda: ["en"], server_default='["en"]'
    )
