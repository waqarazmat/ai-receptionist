import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import embed_text
from app.ai.llm_router import LLMProviderError, stream_llm
from app.ai.message_analyzer import analyze_message
from app.ai.rag_pipeline import hybrid_search
from app.ai.response_generator import DEFAULT_OFF_TOPIC_MESSAGE, ESCALATION_MESSAGE, FALLBACK_MESSAGE, build_generation_plan
from app.db.engine import async_session_maker
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.enums import Channel, MessageRole
from app.models.organization import Organization
from app.realtime.socket_manager import chat_sio as sio
from app.security.rate_limiter import check_message_rate_limit, increment_message_count
from app.services.booking_service import process_booking_intent
from app.services.conversation_service import (
    DECLINE_MESSAGE,
    STATIC_RATE_LIMIT_MESSAGE,
    add_message,
    create_conversation,
    create_escalation,
    get_conversation_messages,
)

logger = structlog.get_logger()

UNAVAILABLE_MESSAGE = "This chat isn't available right now — please try again shortly."


def _org_room(org_id: uuid.UUID | str) -> str:
    return f"org:{org_id}"


def _conversation_room(conversation_id: uuid.UUID | str) -> str:
    return f"conversation:{conversation_id}"


async def _send_complete_reply(sid: str, text: str) -> None:
    """For non-streamed responses (shortcuts, canned text) — emit as a single
    token so the client's handling code doesn't need two different code paths."""
    await sio.emit("response_token", {"token": text}, to=sid, namespace="/chat")
    await sio.emit("response_complete", {}, to=sid, namespace="/chat")


@sio.on("connect", namespace="/chat")
async def chat_connect(sid: str, environ: dict, auth: dict | None) -> None:
    """Deliberately does NO database I/O. Socket.IO's polling->websocket
    upgrade has a narrow timing window right after this handler runs — a
    connect handler slow enough to do a couple of sequential DB round trips
    (confirmed with a plain `asyncio.sleep(2)` reproduction) makes the client
    abort the handshake before it ever sees the accept. So `connect` only
    does cheap, local validation; org/conversation resolution happens lazily
    on the first `send_message`, which isn't under that same time pressure.
    """
    org_id_raw = (auth or {}).get("org_id")
    if not org_id_raw:
        raise ConnectionRefusedError("org_id is required")

    try:
        uuid.UUID(org_id_raw)
    except (TypeError, ValueError):
        raise ConnectionRefusedError("invalid org_id")

    conversation_id_raw = (auth or {}).get("conversation_id")
    await sio.save_session(
        sid, {"org_id": org_id_raw, "conversation_id": conversation_id_raw}, namespace="/chat"
    )
    logger.info("webchat_connected", org_id=org_id_raw, sid=sid)


async def _resolve_conversation(db: AsyncSession, sid: str, session: dict) -> Conversation | None:
    """Validates the org and finds-or-creates the conversation. Returns None
    if the org doesn't exist or isn't active — caller should bail out with
    UNAVAILABLE_MESSAGE rather than proceed."""
    org_id = uuid.UUID(session["org_id"])
    org = await db.get(Organization, org_id)
    if org is None or not org.is_active:
        return None

    conversation = None
    conversation_id_raw = session.get("conversation_id")
    if conversation_id_raw:
        try:
            candidate = await db.get(Conversation, uuid.UUID(conversation_id_raw))
        except (TypeError, ValueError):
            candidate = None
        # Don't let a spoofed/foreign conversation_id leak another org's conversation.
        if candidate is not None and candidate.org_id == org_id:
            conversation = candidate

    if conversation is None:
        contact = Contact(org_id=org_id, name="Web Visitor", channel=Channel.webchat)
        db.add(contact)
        await db.flush()
        conversation = await create_conversation(db, org_id, contact.id, Channel.webchat)
        await sio.save_session(
            sid, {"org_id": str(org_id), "conversation_id": str(conversation.id)}, namespace="/chat"
        )
        await sio.emit("connected", {"conversation_id": str(conversation.id)}, to=sid, namespace="/chat")

    # Unconditional (new or resumed) — a reconnecting customer must rejoin
    # their conversation room each time, since Socket.IO room membership
    # doesn't survive a disconnect/reconnect cycle.
    await sio.enter_room(sid, _org_room(org_id), namespace="/chat")
    await sio.enter_room(sid, _conversation_room(conversation.id), namespace="/chat")

    return conversation


@sio.on("join", namespace="/chat")
async def chat_join(sid: str, data: dict | None = None) -> None:
    """Follow-up event emitted by the client right after `connect` — mirrors
    the /inbox namespace's connect -> join_org_room pattern. Resolving and
    joining the conversation room happens here (with DB I/O) rather than in
    `connect` itself, so a reconnecting widget that hasn't sent a message yet
    still ends up in its conversation room in time to receive staff replies.
    """
    # Deliberately doesn't re-emit "connected" here — _resolve_conversation
    # already does that exactly once, for the new-conversation case. Doing
    # it again here double-fires "connected" for a brand-new conversation
    # (this handler runs, calls _resolve_conversation which emits, then used
    # to emit again), which a client that reacts to "connected" by sending
    # its first message would turn into two concurrent LLM generations.
    session = await sio.get_session(sid, namespace="/chat")
    async with async_session_maker() as db:
        await _resolve_conversation(db, sid, session)


@sio.on("send_message", namespace="/chat")
async def chat_send_message(sid: str, data: dict | None) -> None:
    session = await sio.get_session(sid, namespace="/chat")
    message_text = ((data or {}).get("message") or "").strip()
    if not message_text:
        return

    async with async_session_maker() as db:
        conversation = await _resolve_conversation(db, sid, session)
        if conversation is None:
            await _send_complete_reply(sid, UNAVAILABLE_MESSAGE)
            return
        org_id = conversation.org_id
        conversation_id = conversation.id

        if conversation.assigned_to is not None:
            # Staff has taken this conversation over — save the message
            # (add_message already notifies the staff inbox) and stop; no AI
            # response, and no response_token/response_complete either,
            # since a human is expected to reply from the inbox instead.
            await add_message(db, conversation_id, MessageRole.customer, message_text, Channel.webchat)
            return

        # j. Per-org rate limit, checked before any LLM spend.
        if not await check_message_rate_limit(str(org_id)):
            logger.warning("org_message_rate_limit_exceeded", org_id=str(org_id))
            await _send_complete_reply(sid, STATIC_RATE_LIMIT_MESSAGE)
            return
        await increment_message_count(str(org_id))

        history = [
            {"role": m.role.value, "content": m.content}
            for m in await get_conversation_messages(db, conversation_id)
        ]

        # a+c. Combined safety check + intent classification (single LLM call).
        analysis = await analyze_message(db, message_text, history, org_id)

        # b. Save customer message (also notifies the staff inbox)
        await add_message(db, conversation_id, MessageRole.customer, message_text, Channel.webchat)
        history.append({"role": "customer", "content": message_text})

        if not analysis["is_safe"]:
            logger.info("input_declined", org_id=str(org_id), reason=analysis.get("safety_reason"))
            await add_message(db, conversation_id, MessageRole.ai, DECLINE_MESSAGE, Channel.webchat)
            await _send_complete_reply(sid, DECLINE_MESSAGE)
            return

        intent = analysis["intent"]

        contact = await db.get(Contact, conversation.contact_id)
        contact_name = contact.name if contact else None

        if intent == "escalation_request":
            # f. Escalation
            await create_escalation(db, org_id, conversation_id, reason=message_text)
            await add_message(db, conversation_id, MessageRole.ai, ESCALATION_MESSAGE, Channel.webchat)
            await _send_complete_reply(sid, ESCALATION_MESSAGE)
            return

        if intent in ("booking_request", "booking_info"):
            # e. Booking — hands off to the FSM-driven booking flow instead of RAG.
            response_text = await process_booking_intent(
                db, org_id, conversation_id, conversation.contact_id, message_text, intent
            )
            await add_message(db, conversation_id, MessageRole.ai, response_text, Channel.webchat)
            await _send_complete_reply(sid, response_text)
            return

        if intent == "off_topic":
            # g. Off-topic response from org config
            org = await db.get(Organization, org_id)
            prompts = (org.system_prompts if org else None) or {}
            text = prompts.get("off_topic_response") or DEFAULT_OFF_TOPIC_MESSAGE
            await add_message(db, conversation_id, MessageRole.ai, text, Channel.webchat)
            await _send_complete_reply(sid, text)
            return

        # d. FAQ (and greeting/farewell) — RAG + streamed generation
        chunks = []
        if intent == "faq":
            query_embedding = embed_text(message_text)
            chunks = await hybrid_search(db, org_id, message_text, query_embedding)
            if not chunks:
                await create_escalation(
                    db, org_id, conversation_id, reason=f"No confident answer found for: {message_text}"
                )
                await add_message(db, conversation_id, MessageRole.ai, ESCALATION_MESSAGE, Channel.webchat)
                await _send_complete_reply(sid, ESCALATION_MESSAGE)
                return

        plan = await build_generation_plan(db, org_id, intent, chunks, history, contact_name)

        if plan.shortcut_text is not None:
            await add_message(db, conversation_id, MessageRole.ai, plan.shortcut_text, Channel.webchat)
            await _send_complete_reply(sid, plan.shortcut_text)
            return

        collected: list[str] = []
        try:
            async for token in stream_llm(plan.client, plan.messages, plan.system_prompt):
                collected.append(token)
                await sio.emit("response_token", {"token": token}, to=sid, namespace="/chat")
        except LLMProviderError as exc:
            logger.warning("webchat_stream_failed", org_id=str(org_id), error=str(exc))
            if not collected:
                collected.append(FALLBACK_MESSAGE)
                await sio.emit("response_token", {"token": FALLBACK_MESSAGE}, to=sid, namespace="/chat")

        full_text = "".join(collected)
        await add_message(db, conversation_id, MessageRole.ai, full_text, Channel.webchat)
        await sio.emit("response_complete", {}, to=sid, namespace="/chat")


@sio.on("disconnect", namespace="/chat")
async def chat_disconnect(sid: str) -> None:
    session = await sio.get_session(sid, namespace="/chat")
    logger.info("webchat_disconnected", conversation_id=session.get("conversation_id"), sid=sid)
