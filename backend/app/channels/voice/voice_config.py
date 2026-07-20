import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel_config import ChannelConfig
from app.models.enums import Channel


async def get_voice_config(db: AsyncSession, org_id: uuid.UUID) -> dict | None:
    """Org's voice settings — greeting, voice agent display name, and the
    Retell agent id this org's calls come in on. Returns None if voice isn't
    configured/enabled for this org, so callers can reject/close rather than
    proceed with defaults for an org that never set voice up.

    config shape (channel_configs.config JSONB):
        retell_agent_id: str   — Retell's agent id, used to cross-check the
                                  call_details event on the LLM WebSocket
                                  actually belongs to this org's agent
        greeting: str | None
        voice_agent_name: str | None
    """
    channel_config = (
        await db.execute(
            select(ChannelConfig).where(
                ChannelConfig.org_id == org_id, ChannelConfig.channel_type == Channel.voice
            )
        )
    ).scalar_one_or_none()

    if channel_config is None or not channel_config.is_enabled:
        return None

    config = channel_config.config or {}
    if not config.get("retell_agent_id"):
        return None

    return {
        "retell_agent_id": config["retell_agent_id"],
        "greeting": config.get("greeting"),
        "voice_agent_name": config.get("voice_agent_name"),
    }


async def get_org_id_for_retell_agent(db: AsyncSession, retell_agent_id: str) -> uuid.UUID | None:
    """Routes an inbound Retell webhook/call to the right org via its agent
    id — same shared-endpoint-plus-JSONB-lookup pattern as WhatsApp's
    phone_number_id routing (app/channels/whatsapp/webhook_handler.py)."""
    channel_config = (
        await db.execute(
            select(ChannelConfig).where(
                ChannelConfig.channel_type == Channel.voice,
                ChannelConfig.config["retell_agent_id"].astext == retell_agent_id,
            )
        )
    ).scalar_one_or_none()
    return channel_config.org_id if channel_config else None
