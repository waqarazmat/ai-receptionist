import uuid

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.booking.google_calendar import get_service_account_email
from app.models.channel_config import ChannelConfig
from app.models.enums import Channel
from app.models.org_api_keys import OrgApiKey
from app.models.organization import Organization
from app.schemas.setup_wizard import (
    ApiKeysStep,
    BasicInfoStep,
    BookingConfigStep,
    ChannelConfigStep,
    KnowledgeBaseStep,
    KnowledgeChunkInput,
    SetupStateResponse,
    StaffAccessStep,
    SystemPromptsStep,
    VoiceConfigStep,
    WhatsappConfigStep,
    WorkingHoursStep,
)
from app.security.encryption import encrypt_api_key
from app.services import auth_service, org_service
from app.services.knowledge_base_service import get_knowledge_base_chunks, replace_knowledge_base


def _mark_complete(org: Organization, step: str) -> None:
    org.setup_progress = {**(org.setup_progress or {}), step: True}


async def save_basic_info(db: AsyncSession, org_id: uuid.UUID, data: BasicInfoStep) -> Organization:
    org = await org_service.get_organization(db, org_id)
    org.name = data.name
    org.industry = data.industry
    org.timezone = data.timezone
    org.address = data.address
    org.phone = data.phone
    org.email = data.email
    _mark_complete(org, "basic_info")
    await db.commit()
    await db.refresh(org)
    return org


async def save_working_hours(db: AsyncSession, org_id: uuid.UUID, data: WorkingHoursStep) -> Organization:
    org = await org_service.get_organization(db, org_id)
    org.working_hours = data.model_dump(mode="json")
    _mark_complete(org, "working_hours")
    await db.commit()
    await db.refresh(org)
    return org


async def save_channels(db: AsyncSession, org_id: uuid.UUID, data: ChannelConfigStep) -> Organization:
    org = await org_service.get_organization(db, org_id)
    org.channels_enabled = {"webchat": data.webchat, "whatsapp": data.whatsapp, "voice": data.voice}
    org.is_trial = data.is_trial

    for channel, is_enabled in (
        (Channel.webchat, data.webchat),
        (Channel.whatsapp, data.whatsapp),
        (Channel.voice, data.voice),
    ):
        config = (
            await db.execute(
                select(ChannelConfig).where(ChannelConfig.org_id == org_id, ChannelConfig.channel_type == channel)
            )
        ).scalar_one_or_none()
        if config is None:
            db.add(ChannelConfig(org_id=org_id, channel_type=channel, is_enabled=is_enabled))
        else:
            config.is_enabled = is_enabled

    _mark_complete(org, "channels")
    await db.commit()
    await db.refresh(org)
    return org


async def _get_or_create_channel_config(db: AsyncSession, org_id: uuid.UUID, channel_type: Channel) -> ChannelConfig:
    """In the normal wizard flow, save_channels() already created a row for
    every channel by the time the API Keys step is reached — this fallback
    only matters if these endpoints are ever called out of order."""
    config = (
        await db.execute(
            select(ChannelConfig).where(ChannelConfig.org_id == org_id, ChannelConfig.channel_type == channel_type)
        )
    ).scalar_one_or_none()
    if config is None:
        config = ChannelConfig(org_id=org_id, channel_type=channel_type, is_enabled=False)
        db.add(config)
    return config


async def save_whatsapp_config(db: AsyncSession, org_id: uuid.UUID, data: WhatsappConfigStep) -> ChannelConfig:
    config = await _get_or_create_channel_config(db, org_id, Channel.whatsapp)
    # Merge only the fields actually provided so saving one inline field
    # (display number OR phone_number_id) doesn't wipe the other.
    updates: dict = {}
    if data.phone_number is not None:
        updates["phone_number"] = data.phone_number
    if data.phone_number_id is not None:
        updates["phone_number_id"] = data.phone_number_id
    config.config = {**(config.config or {}), **updates}
    await db.commit()
    await db.refresh(config)
    return config


async def save_voice_config(db: AsyncSession, org_id: uuid.UUID, data: VoiceConfigStep) -> ChannelConfig:
    config = await _get_or_create_channel_config(db, org_id, Channel.voice)
    config.config = {**(config.config or {}), "retell_agent_id": data.retell_agent_id}
    await db.commit()
    await db.refresh(config)
    return config


async def save_api_key(db: AsyncSession, org_id: uuid.UUID, data: ApiKeysStep) -> OrgApiKey:
    encrypted = encrypt_api_key(str(org_id), data.api_key)

    key_row = (
        await db.execute(
            select(OrgApiKey).where(OrgApiKey.org_id == org_id, OrgApiKey.provider == data.provider)
        )
    ).scalar_one_or_none()
    if key_row is None:
        key_row = OrgApiKey(org_id=org_id, provider=data.provider, encrypted_key=encrypted)
        db.add(key_row)
    else:
        key_row.encrypted_key = encrypted
        key_row.is_active = True

    org = await org_service.get_organization(db, org_id)
    _mark_complete(org, "api_keys")

    await db.commit()
    await db.refresh(key_row)
    return key_row


async def save_knowledge_base(db: AsyncSession, org_id: uuid.UUID, data: KnowledgeBaseStep) -> Organization:
    await replace_knowledge_base(db, org_id, data.name, [chunk.content for chunk in data.chunks])

    org = await org_service.get_organization(db, org_id)
    _mark_complete(org, "knowledge_base")
    await db.commit()
    await db.refresh(org)
    return org


async def save_booking_config(db: AsyncSession, org_id: uuid.UUID, data: BookingConfigStep) -> Organization:
    org = await org_service.get_organization(db, org_id)
    org.booking_config = data.model_dump(mode="json")
    _mark_complete(org, "booking")
    await db.commit()
    await db.refresh(org)
    return org


async def save_system_prompts(db: AsyncSession, org_id: uuid.UUID, data: SystemPromptsStep) -> Organization:
    org = await org_service.get_organization(db, org_id)
    org.system_prompts = data.model_dump(mode="json")
    _mark_complete(org, "system_prompts")
    await db.commit()
    await db.refresh(org)
    return org


async def save_staff(db: AsyncSession, org_id: uuid.UUID, data: StaffAccessStep) -> list:
    target_emails = set(data.emails)
    existing_staff = await auth_service.list_org_staff(db, org_id)

    for staff in existing_staff:
        if staff.email not in target_emails:
            await auth_service.remove_org_staff(db, staff.id, org_id)

    users = [await auth_service.create_org_staff_user(db, email, org_id) for email in target_emails]

    org = await org_service.get_organization(db, org_id)
    _mark_complete(org, "staff")
    await db.commit()
    return users


async def get_setup_state(db: AsyncSession, org_id: uuid.UUID) -> SetupStateResponse:
    org = await org_service.get_organization(db, org_id)

    def _try_build(model, payload):
        try:
            return model(**payload)
        except (ValidationError, TypeError):
            return None

    basic_info = _try_build(
        BasicInfoStep,
        {
            "name": org.name,
            "industry": org.industry,
            "timezone": org.timezone,
            "address": org.address,
            "phone": org.phone,
            "email": org.email,
        },
    )
    working_hours = _try_build(WorkingHoursStep, org.working_hours or {})
    channels = _try_build(
        ChannelConfigStep,
        {**(org.channels_enabled or {}), "is_trial": org.is_trial},
    )
    booking = _try_build(BookingConfigStep, org.booking_config or {})
    system_prompts = _try_build(SystemPromptsStep, org.system_prompts or {})

    api_keys_configured = list(
        (
            await db.execute(
                select(OrgApiKey.provider).where(OrgApiKey.org_id == org_id, OrgApiKey.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )

    kb, chunk_contents = await get_knowledge_base_chunks(db, org_id)
    knowledge_base = (
        KnowledgeBaseStep(name=kb.name, chunks=[KnowledgeChunkInput(content=c) for c in chunk_contents])
        if kb is not None
        else None
    )

    staff = await auth_service.list_org_staff(db, org_id)

    config_by_channel: dict[Channel, dict] = {
        row.channel_type: (row.config or {})
        for row in (await db.execute(select(ChannelConfig).where(ChannelConfig.org_id == org_id))).scalars().all()
    }

    return SetupStateResponse(
        setup_progress=org.setup_progress or {},
        setup_completed=org.setup_completed,
        basic_info=basic_info,
        working_hours=working_hours,
        channels=channels,
        api_keys_configured=api_keys_configured,
        knowledge_base=knowledge_base,
        booking=booking,
        system_prompts=system_prompts,
        staff_emails=[u.email for u in staff],
        google_calendar_service_account_email=get_service_account_email(),
        whatsapp_phone_number=config_by_channel.get(Channel.whatsapp, {}).get("phone_number"),
        whatsapp_phone_number_id=config_by_channel.get(Channel.whatsapp, {}).get("phone_number_id"),
        voice_retell_agent_id=config_by_channel.get(Channel.voice, {}).get("retell_agent_id"),
    )
