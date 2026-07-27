import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from app.channels.whatsapp.formatting import to_whatsapp_text
from app.channels.whatsapp.message_sender import send_text_message
from app.db.engine import async_session_maker
from app.db.redis import redis_client
from app.models.enums import Channel, MessageRole
from app.models.message import Message
from app.services import contact_service, conversation_service

logger = structlog.get_logger()

# Guards against duplicate processing (arq retrying a job that raised
# partway through, or Meta redelivering the same webhook) — same SET NX
# dedupe pattern as reminder_tasks.py's _reminded_key, keyed by Meta's own
# per-message id so a retry can't create a second customer message / fire a
# second LLM call / send a second reply.
PROCESSED_MESSAGE_KEY_TTL_SECONDS = 60 * 60 * 24

# AI Act Article 50 — sent as the very first message in every new WhatsApp
# conversation. Not translatable via org config; it's a legal requirement.
_AI_DISCLOSURE_WA = (
    "🤖 This conversation is handled by an AI assistant. "
    "A staff member can take over at any time if needed."
)


def _processed_message_key(wamid: str) -> str:
    return f"whatsapp_processed:{wamid}"


async def process_whatsapp_message(
    ctx: dict, org_id: str, contact_phone: str, contact_name: str | None, message_text: str, message_wamid: str
) -> None:
    """Arq task enqueued by the webhook handler for each inbound text message.
    Mirrors the webchat pipeline exactly (find/create contact + conversation,
    run the same AI pipeline via process_customer_message), then sends the
    reply back over WhatsApp instead of a socket."""
    claimed = await redis_client.set(
        _processed_message_key(message_wamid), "1", nx=True, ex=PROCESSED_MESSAGE_KEY_TTL_SECONDS
    )
    if not claimed:
        logger.info("whatsapp_message_already_processed", wamid=message_wamid)
        return

    org_uuid = uuid.UUID(org_id)

    # ── Phase 1: get or create contact + conversation, mark disclosure ───────
    async with async_session_maker() as db:
        contact = await contact_service.get_or_create_contact_by_phone(
            db, org_uuid, contact_phone, Channel.whatsapp, contact_name
        )
        conversation = await conversation_service.get_or_create_channel_conversation(
            db, org_uuid, contact.id, Channel.whatsapp
        )
        conversation_id = conversation.id
        is_new_conversation = conversation.ai_disclosure_sent_at is None
        if is_new_conversation:
            # Mark first so a concurrent retry can't send a second disclosure.
            conversation.ai_disclosure_sent_at = datetime.now(timezone.utc)
            await db.commit()

    # ── Phase 2: send AI disclosure as the first WhatsApp message ───────────
    # Sent BEFORE the AI reply so it arrives first in the customer's thread.
    if is_new_conversation:
        await send_text_message(org_uuid, contact_phone, _AI_DISCLOSURE_WA)
        logger.info(
            "ai_disclosure_sent",
            org_id=org_id,
            channel="whatsapp",
            conversation_id=str(conversation_id),
        )

    # ── Phase 3: run AI pipeline ─────────────────────────────────────────────
    async with async_session_maker() as db:
        response_text = await conversation_service.process_customer_message(
            db, org_uuid, conversation_id, message_text
        )

    if response_text is None:
        # Staff has taken this conversation over — process_customer_message
        # already saved the customer message and notified the inbox; there's
        # no AI reply to send back over WhatsApp.
        return

    # The AI reply is Markdown (shared pipeline); WhatsApp can't render it, so
    # convert to WhatsApp formatting before sending. The DB keeps the original.
    wamid = await send_text_message(org_uuid, contact_phone, to_whatsapp_text(response_text))
    if not wamid:
        logger.warning("whatsapp_reply_send_failed", org_id=org_id, contact_phone=contact_phone)
        return

    async with async_session_maker() as db:
        # process_customer_message already saved the AI reply as a Message —
        # tag that same row with Meta's message id so a later delivery/read
        # status webhook can be matched back to it.
        last_ai_message = (
            await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id, Message.role == MessageRole.ai)
                .order_by(Message.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if last_ai_message is not None:
            last_ai_message.whatsapp_message_id = wamid
            last_ai_message.delivery_status = "sent"
            await db.commit()


async def send_unsupported_message_reply(ctx: dict, org_id: str, contact_phone: str, text: str) -> None:
    """For non-text inbound messages (image/audio/etc — "others later" per
    the task scope). Sends a plain static reply directly, without touching
    the conversation/AI pipeline — there's no customer text here for intent
    classification or RAG to operate on."""
    await send_text_message(uuid.UUID(org_id), contact_phone, text)


async def process_whatsapp_voice_message(
    ctx: dict,
    org_id: str,
    contact_phone: str,
    contact_name: str | None,
    media_id: str,
    message_wamid: str,
) -> None:
    """Arq task for inbound WhatsApp voice notes (type=audio / type=voice).

    Deduplicates on the Meta message id (same key scheme as text messages),
    then delegates to voice_handler.handle_voice_note which owns the full
    STT → RAG → TTS → send pipeline.
    """
    claimed = await redis_client.set(
        _processed_message_key(message_wamid), "1", nx=True, ex=PROCESSED_MESSAGE_KEY_TTL_SECONDS
    )
    if not claimed:
        logger.info("whatsapp_voice_already_processed", wamid=message_wamid)
        return

    from app.channels.whatsapp.voice_handler import handle_voice_note
    await handle_voice_note(
        org_id=uuid.UUID(org_id),
        contact_phone=contact_phone,
        contact_name=contact_name,
        media_id=media_id,
        wamid=message_wamid,
    )


async def process_whatsapp_status_update(ctx: dict, wamid: str, status_value: str) -> None:
    """Arq task enqueued by the webhook handler for each delivery/read/failed
    status callback."""
    async with async_session_maker() as db:
        message = (
            await db.execute(select(Message).where(Message.whatsapp_message_id == wamid))
        ).scalar_one_or_none()
        if message is None:
            logger.info("whatsapp_status_update_no_match", wamid=wamid, status=status_value)
            return
        message.delivery_status = status_value
        await db.commit()
