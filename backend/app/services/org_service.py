import re
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm_router import PROVIDER_PRIORITY
from app.channels.voice import retell_provisioner
from app.config import settings
from app.models.appointment import Appointment
from app.models.channel_config import ChannelConfig
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.enums import ApiKeyProvider, Channel
from app.models.escalation import Escalation
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.message import Message
from app.models.org_api_keys import OrgApiKey
from app.models.organization import Organization
from app.models.user import User
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


_REGULATED_VERTICALS = {"medical", "dental", "veterinary", "legal"}


async def create_organization(db: AsyncSession, data: OrganizationCreate) -> Organization:
    # Regulated verticals get a shorter default retention window so new orgs
    # don't accidentally store sensitive data longer than necessary. Still
    # overridable per-org via data_retention_days.
    retention: int | None = None
    if data.business_vertical.value in _REGULATED_VERTICALS:
        retention = settings.REGULATED_VERTICAL_RETENTION_DAYS

    org = Organization(
        name=data.name,
        slug=await _unique_slug(db, data.name),
        industry=data.industry,
        timezone=data.timezone,
        business_vertical=data.business_vertical,
        data_retention_days=retention,
        country=data.country,
        supported_languages=data.supported_languages,
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
            supported_languages=org.supported_languages or ["en"],
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


async def erase_organization(db: AsyncSession, org_id: uuid.UUID) -> None:
    """Irreversibly delete ALL data for an org — GDPR Article 17 hard-erase.

    Cascade order respects FK constraints (children before parents).
    KnowledgeChunk rows include the pgvector embedding column — deleting the
    row removes the vector; there is no separate vector-store to clean up.

    The audit log entry must be committed by the caller BEFORE invoking this
    function so the record of the erasure survives even if the delete rolls back.
    """
    # 1. Escalations reference conversations and orgs
    await db.execute(delete(Escalation).where(Escalation.org_id == org_id))
    # 2. Appointments reference conversations, contacts, and orgs
    await db.execute(delete(Appointment).where(Appointment.org_id == org_id))
    # 3. Messages reference conversations and orgs
    await db.execute(delete(Message).where(Message.org_id == org_id))
    # 4. Conversations reference contacts and orgs
    await db.execute(delete(Conversation).where(Conversation.org_id == org_id))
    # 5. Contacts reference orgs
    await db.execute(delete(Contact).where(Contact.org_id == org_id))
    # 6. KnowledgeChunks (vectors) reference knowledge_bases and orgs
    await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.org_id == org_id))
    # 7. KnowledgeBases reference orgs
    await db.execute(delete(KnowledgeBase).where(KnowledgeBase.org_id == org_id))
    # 8. ChannelConfigs reference orgs
    await db.execute(delete(ChannelConfig).where(ChannelConfig.org_id == org_id))
    # 9. OrgApiKeys reference orgs
    await db.execute(delete(OrgApiKey).where(OrgApiKey.org_id == org_id))
    # 10. Org staff users — deactivate rather than delete so their user record
    # isn't a dangling FK target in audit_log rows (audit_log is never erased).
    await db.execute(
        User.__table__.update()
        .where(User.org_id == org_id)
        .values(is_active=False, org_id=None)
    )
    # 11. Organization itself
    await db.execute(delete(Organization).where(Organization.id == org_id))
    await db.commit()


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
