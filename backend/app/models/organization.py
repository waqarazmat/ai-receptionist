from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Organization(Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    industry: Mapped[str] = mapped_column(String, nullable=False)
    timezone: Mapped[str] = mapped_column(String, nullable=False)
    working_hours: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_trial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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
