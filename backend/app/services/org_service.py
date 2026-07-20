import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm_router import PROVIDER_PRIORITY
from app.channels.voice import retell_provisioner
from app.config import settings
from app.models.channel_config import ChannelConfig
from app.models.enums import ApiKeyProvider, Channel
from app.models.escalation import Escalation
from app.models.message import Message
from app.models.org_api_keys import OrgApiKey
from app.models.organization import Organization
from app.schemas.organization import (
    OrgChannelStatusResponse,
    OrganizationCreate,
    OrganizationUpdate,
    VoiceChannelStatus,
    WebchatChannelStatus,
    WhatsappChannelStatus,
)

REQUIRED_SETUP_STEPS = [
    "basic_info",
    "working_hours",
    "channels",
    "api_keys",
    "knowledge_base",
    "booking",
    "system_prompts",
    "staff",
]


class OrganizationNotFoundError(Exception):
    pass


class OrganizationNotReadyError(Exception):
    pass


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "org"


async def _unique_slug(db: AsyncSession, name: str) -> str:
    base_slug = _slugify(name)
    slug = base_slug
    suffix = 1
    while (await db.execute(select(Organization.id).where(Organization.slug == slug))).scalar_one_or_none():
        suffix += 1
        slug = f"{base_slug}-{suffix}"
    return slug


def _stats_subqueries():
    message_count_sq = (
        select(Message.org_id, func.count(Message.id).label("message_count"))
        .group_by(Message.org_id)
        .subquery()
    )
    escalation_count_sq = (
        select(Escalation.org_id, func.count(Escalation.id).label("escalation_count"))
        .group_by(Escalation.org_id)
        .subquery()
    )
    return message_count_sq, escalation_count_sq


def _stats_select():
    message_count_sq, escalation_count_sq = _stats_subqueries()
    return (
        select(
            Organization,
            func.coalesce(message_count_sq.c.message_count, 0).label("message_count"),
            func.coalesce(escalation_count_sq.c.escalation_count, 0).label("escalation_count"),
        )
        .outerjoin(message_count_sq, message_count_sq.c.org_id == Organization.id)
        .outerjoin(escalation_count_sq, escalation_count_sq.c.org_id == Organization.id)
    )


async def create_organization(db: AsyncSession, data: OrganizationCreate) -> Organization:
    org = Organization(
        name=data.name,
        slug=await _unique_slug(db, data.name),
        industry=data.industry,
        timezone=data.timezone,
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    org.message_count = 0
    org.escalation_count = 0
    return org


async def list_organizations(db: AsyncSession) -> list[Organization]:
    stmt = _stats_select().order_by(Organization.created_at.desc())
    result = await db.execute(stmt)

    organizations = []
    for org, message_count, escalation_count in result.all():
        org.message_count = message_count
        org.escalation_count = escalation_count
        organizations.append(org)
    return organizations


async def get_organization(db: AsyncSession, org_id: uuid.UUID) -> Organization:
    stmt = _stats_select().where(Organization.id == org_id)
    row = (await db.execute(stmt)).first()
    if row is None:
        raise OrganizationNotFoundError(str(org_id))

    org, message_count, escalation_count = row
    org.message_count = message_count
    org.escalation_count = escalation_count
    return org


async def get_channel_status(db: AsyncSession, org_id: uuid.UUID) -> OrgChannelStatusResponse:
    """Per-channel setup status for the Test Center page — `enabled` comes
    from the org's own channel toggles, `configured` from whether the actual
    credentials needed to make that channel work exist."""
    org = await get_organization(db, org_id)
    channels_enabled = org.channels_enabled or {}

    active_providers = {
        row.provider
        for row in (
            await db.execute(
                select(OrgApiKey).where(OrgApiKey.org_id == org_id, OrgApiKey.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    }
    config_by_channel: dict[Channel, dict] = {
        row.channel_type: (row.config or {})
        for row in (await db.execute(select(ChannelConfig).where(ChannelConfig.org_id == org_id))).scalars().all()
    }
    whatsapp_config = config_by_channel.get(Channel.whatsapp, {})
    voice_config = config_by_channel.get(Channel.voice, {})

    # Ask Retell whether the agent's Custom LLM URL already points at this
    # backend. Best-effort and only when there's actually an agent + key to
    # check — verify_agent never raises, but skip the network round-trip
    # entirely otherwise so channel status stays fast/offline-safe.
    voice_agent_id = voice_config.get("retell_agent_id")
    voice_provisioned: bool | None = None
    if voice_agent_id and settings.RETELL_API_KEY:
        info = await retell_provisioner.verify_agent(voice_agent_id)
        voice_provisioned = retell_provisioner.is_provisioned_for_org(
            str(org_id), info.get("current_llm_url")
        )

    return OrgChannelStatusResponse(
        webchat=WebchatChannelStatus(
            enabled=bool(channels_enabled.get("webchat")),
            # Webchat has no channel-specific credential of its own — it just
            # needs *some* LLM provider configured to generate a response at all.
            configured=any(provider in active_providers for provider in PROVIDER_PRIORITY),
        ),
        whatsapp=WhatsappChannelStatus(
            enabled=bool(channels_enabled.get("whatsapp")),
            configured=ApiKeyProvider.whatsapp in active_providers,
            phone_number=whatsapp_config.get("phone_number") or whatsapp_config.get("display_phone_number"),
        ),
        voice=VoiceChannelStatus(
            enabled=bool(channels_enabled.get("voice")),
            configured=ApiKeyProvider.retell in active_providers,
            agent_id=voice_config.get("retell_agent_id"),
            phone_number=voice_config.get("phone_number"),
            retell_agent_id=voice_config.get("retell_agent_id"),
            provisioned=voice_provisioned,
        ),
    )


async def update_organization(db: AsyncSession, org_id: uuid.UUID, data: OrganizationUpdate) -> Organization:
    org = await get_organization(db, org_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(org, field, value)
    await db.commit()
    await db.refresh(org)
    return org


async def delete_organization(db: AsyncSession, org_id: uuid.UUID) -> Organization:
    """Soft delete — deactivates the org without removing any data."""
    org = await get_organization(db, org_id)
    org.is_active = False
    await db.commit()
    await db.refresh(org)
    return org


async def activate_organization(db: AsyncSession, org_id: uuid.UUID) -> Organization:
    org = await get_organization(db, org_id)
    progress = org.setup_progress or {}
    missing = [step for step in REQUIRED_SETUP_STEPS if not progress.get(step)]
    if missing:
        raise OrganizationNotReadyError(f"Setup incomplete: missing {', '.join(missing)}")

    org.is_active = True
    org.setup_completed = True
    await db.commit()
    await db.refresh(org)
    return org
