import uuid

import httpx
import structlog
from sqlalchemy import select

from app.config import settings
from app.db.engine import async_session_maker
from app.models.channel_config import ChannelConfig
from app.models.enums import ApiKeyProvider, Channel
from app.models.org_api_keys import OrgApiKey
from app.security.encryption import decrypt_api_key

logger = structlog.get_logger()

GRAPH_API_BASE = f"https://graph.facebook.com/{settings.WHATSAPP_GRAPH_API_VERSION}"
REQUEST_TIMEOUT_SECONDS = 15.0


class WhatsAppCredentialsError(Exception):
    """Org has no active WhatsApp access token or no phone_number_id
    configured yet. Callers should degrade gracefully (root CLAUDE.md rule
    #8) rather than let this become a 500."""


async def get_credentials(org_id: uuid.UUID) -> tuple[str, str]:
    """Returns (access_token, phone_number_id). The access token is the
    org's own secret (org_api_keys, encrypted); phone_number_id is not
    sensitive — Meta's own public routing id for the org's WhatsApp number —
    so it lives in channel_configs.config alongside other non-secret,
    channel-specific settings."""
    async with async_session_maker() as db:
        key_row = (
            await db.execute(
                select(OrgApiKey).where(
                    OrgApiKey.org_id == org_id,
                    OrgApiKey.provider == ApiKeyProvider.whatsapp,
                    OrgApiKey.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        config_row = (
            await db.execute(
                select(ChannelConfig).where(
                    ChannelConfig.org_id == org_id, ChannelConfig.channel_type == Channel.whatsapp
                )
            )
        ).scalar_one_or_none()

    if key_row is None:
        raise WhatsAppCredentialsError(f"No WhatsApp access token configured for org {org_id}")

    phone_number_id = (config_row.config if config_row else {}).get("phone_number_id")
    if not phone_number_id:
        raise WhatsAppCredentialsError(f"No WhatsApp phone_number_id configured for org {org_id}")

    access_token = decrypt_api_key(str(org_id), key_row.encrypted_key)
    return access_token, phone_number_id


async def _post_message(org_id: uuid.UUID, payload: dict) -> str | None:
    try:
        access_token, phone_number_id = await get_credentials(org_id)
    except WhatsAppCredentialsError as exc:
        logger.warning("whatsapp_send_no_credentials", org_id=str(org_id), error=str(exc))
        return None

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{GRAPH_API_BASE}/{phone_number_id}/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["messages"][0]["id"]
    except httpx.HTTPError as exc:
        logger.warning("whatsapp_send_failed", org_id=str(org_id), error=str(exc))
        return None


async def send_text_message(org_id: uuid.UUID, phone_number: str, text: str) -> str | None:
    """Free-form text — only deliverable within Meta's 24h customer service
    window (see conversation_service.get_last_customer_message_at). Returns
    the Meta message id (wamid) on success, or None on any failure."""
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": text},
    }
    return await _post_message(org_id, payload)


async def send_template_message(
    org_id: uuid.UUID, phone_number: str, template_name: str, parameters: list[str] | None = None
) -> str | None:
    """Approved template message — the only kind Meta allows outside the 24h
    window. The template itself must already be approved in Meta Business
    Manager (see template_manager.py); this just fills in its parameters."""
    components = (
        [{"type": "body", "parameters": [{"type": "text", "text": p} for p in parameters]}] if parameters else []
    )
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "en_US"},
            "components": components,
        },
    }
    return await _post_message(org_id, payload)
