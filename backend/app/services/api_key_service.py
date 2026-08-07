"""Per-org (tenant-isolated) API key resolution.

Single source of truth for "which key does org X use for provider P?". Prefers
the org's own key (encrypted in org_api_keys), and only falls back to a
platform-level env key when settings.ALLOW_PLATFORM_KEY_FALLBACK is True — so
under strict isolation no org ever runs on a shared key (root CLAUDE.md rule #4).

The LLM router (app/ai/llm_router.py) has its own multi-provider selection but
shares this module's platform-fallback policy. This resolver backs the voice
pipeline's STT/TTS keys (see app/channels/whatsapp/voice_handler.py).
"""

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.enums import ApiKeyProvider
from app.models.org_api_keys import OrgApiKey
from app.security.encryption import decrypt_api_key

logger = structlog.get_logger()


def _platform_fallback_key(provider: ApiKeyProvider) -> str | None:
    """The platform-level env key for a provider, or None if it has no fallback.
    Only the voice-pipeline providers have a platform env key; LLM/whatsapp/etc.
    are per-org only."""
    return {
        ApiKeyProvider.groq: settings.GROQ_API_KEY,
        ApiKeyProvider.openai: settings.OPENAI_API_KEY,
        ApiKeyProvider.deepgram: settings.DEEPGRAM_API_KEY,
    }.get(provider)


async def get_org_api_key(
    db: AsyncSession, org_id: uuid.UUID, provider: ApiKeyProvider
) -> str | None:
    """Return the org's own decrypted key for `provider`, or None if it hasn't
    configured one. Never returns another org's key or a platform key."""
    row = (
        await db.execute(
            select(OrgApiKey).where(
                OrgApiKey.org_id == org_id,
                OrgApiKey.provider == provider,
                OrgApiKey.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return decrypt_api_key(str(org_id), row.encrypted_key)


async def resolve_provider_key(
    db: AsyncSession, org_id: uuid.UUID, provider_name: str
) -> str | None:
    """Resolve the API key an org should use for a provider named by string
    (e.g. "groq", "openai", "deepgram").

    Order: the org's own key first; then, ONLY if ALLOW_PLATFORM_KEY_FALLBACK is
    set, the platform env key. Returns None when neither is available — callers
    MUST degrade gracefully (never crash, never borrow another key).
    """
    name = (provider_name or "").lower().strip()
    try:
        provider = ApiKeyProvider(name)
    except ValueError:
        logger.warning("resolve_provider_key_unknown_provider", provider=name, org_id=str(org_id))
        return None

    org_key = await get_org_api_key(db, org_id, provider)
    if org_key:
        return org_key

    if settings.ALLOW_PLATFORM_KEY_FALLBACK:
        fallback = _platform_fallback_key(provider)
        if fallback:
            logger.info("provider_key_platform_fallback", provider=name, org_id=str(org_id))
            return fallback

    return None
