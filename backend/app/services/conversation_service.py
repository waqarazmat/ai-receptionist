import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import embed_text
from app.ai.message_analyzer import analyze_message
from app.ai.rag_pipeline import hybrid_search
from app.ai.response_generator import DEFAULT_OFF_TOPIC_MESSAGE, ESCALATION_MESSAGE, generate_response
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.enums import Channel, ConversationStatus, EscalationPriority, EscalationStatus, MessageRole
from app.models.escalation import Escalation
from app.models.message import Message
from app.models.organization import Organization
from app.security.rate_limiter import check_message_rate_limit, increment_message_count
from app.services.booking_service import process_booking_intent

logger = structlog.get_logger()

STATIC_RATE_LIMIT_MESSAGE = (
    "We're getting a high volume of messages right now — please try again in a few minutes, "
    "or call us directly if this is urgent."
)
DECLINE_MESSAGE = "I'm not able to help with that request. Is there something else about our business I can help with?"


class ConversationNotFoundError(Exception):
    pass


async def create_conversation(db: AsyncSession, org_id: uuid.UUID, contact_id: uuid.UUID, channel: Channel) -> Conversation:
    conversation = Conversation(
        org_id=org_id,
        contact_id=contact_id,
        channel=channel,
        status=ConversationStatus.active,
        last_message_at=datetime.now(timezone.utc),
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def get_or_create_channel_conversation(
    db: AsyncSession, org_id: uuid.UUID, contact_id: uuid.UUID, channel: Channel
) -> Conversation:
    """For stateless channels (WhatsApp) that have no client-held session to
    resume a specific conversation_id from, the equivalent of "resuming" is:
    reuse this contact's most recent non-resolved conversation on this
    channel, or start a fresh one if there isn't one."""
    conversation = (
        await db.execute(
            select(Conversation)
            .where(
                Conversation.org_id == org_id,
                Conversation.contact_id == contact_id,
                Conversation.channel == channel,
                Conversation.status != ConversationStatus.resolved,
            )
            .order_by(Conversation.last_message_at.desc())
        )
    ).scalars().first()
    if conversation is not None:
        return conversation
    return await create_conversation(db, org_id, contact_id, channel)


async def get_last_customer_message_at(db: AsyncSession, contact_id: uuid.UUID) -> datetime | None:
    """Most recent inbound message time across all of this contact's
    conversations — used to enforce WhatsApp's 24-hour customer service
    window (free-form replies only within 24h of the customer's last
    message; a template message is required outside it)."""
    return (
        await db.execute(
            select(func.max(Message.created_at))
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(Conversation.contact_id == contact_id, Message.role == MessageRole.customer)
        )
    ).scalar_one_or_none()


async def add_message(
    db: AsyncSession, conversation_id: uuid.UUID, role: MessageRole, content: str, channel: Channel
) -> Message:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise ConversationNotFoundError(str(conversation_id))

    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        channel=channel,
        org_id=conversation.org_id,
    )
    db.add(message)
    conversation.last_message_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(message)

    if role == MessageRole.customer:
        # Local import: realtime -> keeps conversation_service importable (e.g.
        # in tests) without pulling in the Socket.IO server as a hard dependency.
        from app.realtime.events import notify_new_message

        await notify_new_message(conversation.org_id, conversation_id, role.value, content)

    return message


async def get_conversation_messages(db: AsyncSession, conversation_id: uuid.UUID) -> list[Message]:
    result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    )
    return list(result.scalars().all())


def _last_message_preview_subquery():
    return (
        select(Message.content)
        .where(Message.conversation_id == Conversation.id)
        .order_by(Message.created_at.desc())
        .limit(1)
        .correlate(Conversation)
        .scalar_subquery()
    )


def _unread_count_subquery():
    """Customer messages that arrived after the most recent staff/AI reply —
    i.e. trailing customer messages nobody (human or AI) has answered yet.
    Correlates to the outer Conversation row via .correlate() at the call site.
    """
    last_response_at = (
        select(func.max(Message.created_at))
        .where(Message.conversation_id == Conversation.id, Message.role != MessageRole.customer)
        .correlate(Conversation)
        .scalar_subquery()
    )
    return (
        select(func.count(Message.id))
        .where(
            Message.conversation_id == Conversation.id,
            Message.role == MessageRole.customer,
            or_(last_response_at.is_(None), Message.created_at > last_response_at),
        )
        .correlate(Conversation)
        .scalar_subquery()
    )


async def list_conversations(
    db: AsyncSession, org_id: uuid.UUID, status_filter: ConversationStatus | None = None
) -> list[Conversation]:
    stmt = (
        select(Conversation, Contact.name, _unread_count_subquery(), _last_message_preview_subquery())
        .join(Contact, Contact.id == Conversation.contact_id)
        .where(Conversation.org_id == org_id)
    )
    if status_filter is not None:
        stmt = stmt.where(Conversation.status == status_filter)
    stmt = stmt.order_by(Conversation.last_message_at.desc())

    result = await db.execute(stmt)
    conversations = []
    for conversation, contact_name, unread_count, last_message_preview in result.all():
        conversation.contact_name = contact_name
        conversation.unread_count = unread_count or 0
        conversation.last_message_preview = last_message_preview
        conversations.append(conversation)
    return conversations


async def get_conversation(db: AsyncSession, org_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation:
    stmt = (
        select(Conversation, Contact.name, _unread_count_subquery(), _last_message_preview_subquery())
        .join(Contact, Contact.id == Conversation.contact_id)
        .where(Conversation.org_id == org_id, Conversation.id == conversation_id)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise ConversationNotFoundError(str(conversation_id))

    conversation, contact_name, unread_count, last_message_preview = row
    conversation.contact_name = contact_name
    conversation.unread_count = unread_count or 0
    conversation.last_message_preview = last_message_preview
    return conversation


async def send_staff_reply(db: AsyncSession, conversation_id: uuid.UUID, content: str, user_id: uuid.UUID) -> Message:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise ConversationNotFoundError(str(conversation_id))

    # Replying implicitly takes over — a staff member typing a reply IS them
    # handling the conversation, whether or not they clicked "Take Over" first.
    if conversation.assigned_to is None:
        conversation.assigned_to = user_id
        await db.commit()

    message = await add_message(db, conversation_id, MessageRole.staff, content, conversation.channel)

    from app.realtime.events import notify_staff_reply_to_customer, notify_staff_reply_to_inbox

    # Deliver the reply over whichever channel the customer is actually on —
    # the AI pipeline routes outbound replies the same way per-channel, staff
    # replies need to follow the identical routing or WhatsApp/voice
    # customers would never receive them.
    if conversation.channel == Channel.webchat:
        await notify_staff_reply_to_customer(conversation_id, content)
    elif conversation.channel == Channel.whatsapp:
        contact = await db.get(Contact, conversation.contact_id)
        if contact is not None and contact.phone:
            from app.channels.whatsapp.message_sender import send_text_message

            wamid = await send_text_message(conversation.org_id, contact.phone, content)
            if wamid:
                message.whatsapp_message_id = wamid
                message.delivery_status = "sent"
                await db.commit()
            else:
                logger.warning(
                    "staff_reply_whatsapp_send_failed", conversation_id=str(conversation_id)
                )
        else:
            logger.warning("staff_reply_whatsapp_no_phone", conversation_id=str(conversation_id))
    # channel == voice: the call has already ended by the time staff can see
    # and reply to it in the inbox — nothing to deliver, the message above is
    # saved for the record only.

    # Channel-agnostic: every staff reply updates the shared inbox view for
    # any other staff looking at this conversation, regardless of channel.
    await notify_staff_reply_to_inbox(conversation.org_id, conversation_id, content)

    return message


async def take_over_conversation(
    db: AsyncSession, org_id: uuid.UUID, conversation_id: uuid.UUID, user_id: uuid.UUID
) -> Conversation:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.org_id != org_id:
        raise ConversationNotFoundError(str(conversation_id))

    conversation.assigned_to = user_id
    await db.commit()
    await db.refresh(conversation)

    if conversation.channel == Channel.webchat:
        from app.realtime.events import notify_takeover

        await notify_takeover(conversation_id)

    contact = await db.get(Contact, conversation.contact_id)
    conversation.contact_name = contact.name if contact else ""
    conversation.unread_count = 0
    conversation.last_message_preview = None
    return conversation


async def release_conversation(
    db: AsyncSession, org_id: uuid.UUID, conversation_id: uuid.UUID
) -> Conversation:
    """Reverses take_over_conversation — clears assigned_to so the AI
    pipeline (see process_customer_message's assigned_to check below, and
    channels/webchat/handler.py's matching check) resumes handling this
    conversation's future messages instead of them silently going nowhere."""
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.org_id != org_id:
        raise ConversationNotFoundError(str(conversation_id))

    conversation.assigned_to = None
    await db.commit()
    await db.refresh(conversation)

    contact = await db.get(Contact, conversation.contact_id)
    conversation.contact_name = contact.name if contact else ""
    conversation.unread_count = 0
    conversation.last_message_preview = None
    return conversation


async def resolve_conversation(
    db: AsyncSession, org_id: uuid.UUID, conversation_id: uuid.UUID
) -> Conversation:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.org_id != org_id:
        raise ConversationNotFoundError(str(conversation_id))

    conversation.status = ConversationStatus.resolved
    await db.commit()
    await db.refresh(conversation)

    contact = await db.get(Contact, conversation.contact_id)
    conversation.contact_name = contact.name if contact else ""
    conversation.unread_count = 0
    conversation.last_message_preview = None
    return conversation


async def create_escalation(
    db: AsyncSession,
    org_id: uuid.UUID,
    conversation_id: uuid.UUID,
    reason: str,
    priority: EscalationPriority = EscalationPriority.medium,
) -> Escalation:
    escalation = Escalation(
        org_id=org_id,
        conversation_id=conversation_id,
        reason=reason,
        priority=priority,
        status=EscalationStatus.pending,
    )
    db.add(escalation)

    conversation = await db.get(Conversation, conversation_id)
    if conversation is not None:
        conversation.status = ConversationStatus.escalated

    await db.commit()
    await db.refresh(escalation)

    from app.realtime.events import notify_escalation_created

    await notify_escalation_created(org_id, escalation)

    logger.info("escalation_created", org_id=str(org_id), conversation_id=str(conversation_id))
    return escalation


async def process_customer_message(
    db: AsyncSession, org_id: uuid.UUID, conversation_id: uuid.UUID, message_text: str
) -> str | None:
    """The full non-streaming pipeline: analyze (safety+intent in one call) ->
    save -> route -> save AI response -> return it. Used directly by channels
    that don't need token streaming (WhatsApp, voice); the webchat handler
    reimplements this same routing with streaming instead of calling it directly.

    Returns None if a staff member has taken over this conversation
    (conversation.assigned_to set) — the message is still saved and still
    notifies the staff inbox (via add_message), but no AI response is
    generated; a human is expected to reply instead. Callers must treat a
    None return as "nothing to send back", not an error.
    """
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise ConversationNotFoundError(str(conversation_id))

    if conversation.assigned_to is not None:
        await add_message(db, conversation_id, MessageRole.customer, message_text, conversation.channel)
        return None

    # j. Per-org rate limit — checked before any LLM spend.
    if not await check_message_rate_limit(str(org_id)):
        logger.warning("org_message_rate_limit_exceeded", org_id=str(org_id))
        return STATIC_RATE_LIMIT_MESSAGE
    await increment_message_count(str(org_id))

    history = [
        {"role": m.role.value, "content": m.content} for m in await get_conversation_messages(db, conversation_id)
    ]

    # a+c. Combined safety check + intent classification (single LLM call).
    analysis = await analyze_message(db, message_text, history, org_id)

    # b. Save customer message (saved regardless, for the record)
    await add_message(db, conversation_id, MessageRole.customer, message_text, conversation.channel)
    history.append({"role": "customer", "content": message_text})

    if not analysis["is_safe"]:
        logger.info("input_declined", org_id=str(org_id), reason=analysis.get("safety_reason"))
        await add_message(db, conversation_id, MessageRole.ai, DECLINE_MESSAGE, conversation.channel)
        return DECLINE_MESSAGE

    intent = analysis["intent"]

    contact = await db.get(Contact, conversation.contact_id)
    contact_name = contact.name if contact else None

    if intent == "escalation_request":
        # f. Escalation
        await create_escalation(db, org_id, conversation_id, reason=message_text)
        response_text = ESCALATION_MESSAGE
    elif intent in ("booking_request", "booking_info"):
        # e. Booking — hands off to the FSM-driven booking flow instead of RAG.
        response_text = await process_booking_intent(
            db, org_id, conversation_id, conversation.contact_id, message_text, intent
        )
    elif intent == "off_topic":
        # g. Off-topic response from org config
        org = await db.get(Organization, org_id)
        prompts = (org.system_prompts if org else None) or {}
        response_text = prompts.get("off_topic_response") or DEFAULT_OFF_TOPIC_MESSAGE
    else:
        # d. FAQ (and greeting/farewell) — RAG + generation
        chunks = []
        if intent == "faq":
            query_embedding = embed_text(message_text)
            chunks = await hybrid_search(db, org_id, message_text, query_embedding)
            if not chunks:
                # No confident knowledge match — escalate rather than guess.
                await create_escalation(
                    db, org_id, conversation_id, reason=f"No confident answer found for: {message_text}"
                )
                response_text = ESCALATION_MESSAGE
                await add_message(db, conversation_id, MessageRole.ai, response_text, conversation.channel)
                return response_text

        response_text = await generate_response(db, org_id, intent, chunks, history, contact_name)

    # h. Save AI response
    await add_message(db, conversation_id, MessageRole.ai, response_text, conversation.channel)

    # i. Return AI response text
    return response_text
