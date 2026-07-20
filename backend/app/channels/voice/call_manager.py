import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.enums import Channel, ConversationStatus
from app.services import contact_service
from app.services.conversation_service import create_conversation

logger = structlog.get_logger()


async def on_call_start(
    db: AsyncSession, org_id: uuid.UUID, retell_call_id: str, from_number: str
) -> Conversation:
    """Creates the contact + conversation for a new inbound call. Unlike
    WhatsApp's get_or_create_channel_conversation (which reuses a contact's
    still-open conversation), a phone call always gets its own fresh
    Conversation — a call is inherently a single bounded session with its own
    duration, and reusing an old one would make call_duration_seconds and
    on_call_end's status flip ambiguous about which call they belong to.

    Idempotent against being called twice for the same retell_call_id (the
    call-lifecycle webhook and the LLM WebSocket's own call_details event can
    both try to register the same call if webhook delivery and WS connect
    race) — returns the existing conversation instead of creating a second one.
    """
    existing = (
        await db.execute(select(Conversation).where(Conversation.retell_call_id == retell_call_id))
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    contact = await contact_service.get_or_create_contact_by_phone(db, org_id, from_number, Channel.voice)
    conversation = await create_conversation(db, org_id, contact.id, Channel.voice)
    conversation.retell_call_id = retell_call_id
    await db.commit()
    await db.refresh(conversation)

    logger.info("voice_call_started", org_id=str(org_id), retell_call_id=retell_call_id, from_number=from_number)
    return conversation


async def on_call_end(db: AsyncSession, retell_call_id: str, duration_seconds: int | None) -> None:
    conversation = (
        await db.execute(select(Conversation).where(Conversation.retell_call_id == retell_call_id))
    ).scalar_one_or_none()
    if conversation is None:
        logger.info("voice_call_end_no_match", retell_call_id=retell_call_id)
        return

    conversation.status = ConversationStatus.resolved
    conversation.call_duration_seconds = duration_seconds
    await db.commit()

    logger.info(
        "voice_call_ended",
        org_id=str(conversation.org_id),
        retell_call_id=retell_call_id,
        duration_seconds=duration_seconds,
    )


async def get_active_calls(db: AsyncSession, org_id: uuid.UUID) -> list[Conversation]:
    result = await db.execute(
        select(Conversation).where(
            Conversation.org_id == org_id,
            Conversation.channel == Channel.voice,
            Conversation.status == ConversationStatus.active,
            Conversation.retell_call_id.is_not(None),
        )
    )
    return list(result.scalars().all())
