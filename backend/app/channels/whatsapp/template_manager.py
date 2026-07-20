import uuid

import httpx
import structlog
from sqlalchemy import select

from app.channels.whatsapp.message_sender import GRAPH_API_BASE, REQUEST_TIMEOUT_SECONDS, WhatsAppCredentialsError, get_credentials
from app.db.engine import async_session_maker
from app.models.channel_config import ChannelConfig
from app.models.enums import Channel

logger = structlog.get_logger()

# Template CREATION/approval happens in Meta Business Manager, not here — Meta
# requires human review of template content and can take hours to days to
# approve one. This module only reads what's already approved, so the app can
# reference a template by name when sending reminders/follow-ups outside the
# 24h customer service window.


async def list_templates(org_id: uuid.UUID) -> list[dict]:
    async with async_session_maker() as db:
        config_row = (
            await db.execute(
                select(ChannelConfig).where(
                    ChannelConfig.org_id == org_id, ChannelConfig.channel_type == Channel.whatsapp
                )
            )
        ).scalar_one_or_none()

    waba_id = (config_row.config if config_row else {}).get("waba_id")
    if not waba_id:
        logger.warning("whatsapp_no_waba_id_configured", org_id=str(org_id))
        return []

    try:
        access_token, _phone_number_id = await get_credentials(org_id)
    except WhatsAppCredentialsError as exc:
        logger.warning("whatsapp_list_templates_no_credentials", org_id=str(org_id), error=str(exc))
        return []

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(
                f"{GRAPH_API_BASE}/{waba_id}/message_templates",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"limit": 50},
            )
            response.raise_for_status()
            return response.json().get("data", [])
    except httpx.HTTPError as exc:
        logger.warning("whatsapp_list_templates_failed", org_id=str(org_id), error=str(exc))
        return []
