import uuid

import structlog

from app.api.auth.jwt import decode_token
from app.models.escalation import Escalation
from app.realtime.socket_manager import chat_sio, inbox_sio as sio

logger = structlog.get_logger()


def _org_room(org_id: uuid.UUID | str) -> str:
    return f"org:{org_id}"


def _conversation_room(conversation_id: uuid.UUID | str) -> str:
    return f"conversation:{conversation_id}"


@sio.on("connect", namespace="/inbox")
async def inbox_connect(sid: str, environ: dict, auth: dict | None) -> None:
    """Staff must present a valid org_staff access token to connect at all —
    which org room they may join is then derived from the token, never from
    client-supplied input (see join_org_room below)."""
    token = (auth or {}).get("token")
    if not token:
        raise ConnectionRefusedError("authentication required")

    try:
        payload = decode_token(token)
    except Exception:  # decode_token raises HTTPException on invalid/expired tokens
        raise ConnectionRefusedError("invalid or expired token")

    if payload.get("type") != "access" or payload.get("role") != "org_staff" or not payload.get("org_id"):
        raise ConnectionRefusedError("org staff access required")

    await sio.save_session(sid, {"org_id": payload["org_id"], "user_id": payload["sub"]}, namespace="/inbox")
    logger.info("inbox_connected", org_id=payload["org_id"], user_id=payload["sub"], sid=sid)


@sio.on("join_org_room", namespace="/inbox")
async def join_org_room(sid: str, data: dict | None = None) -> None:
    session = await sio.get_session(sid, namespace="/inbox")
    org_id = session.get("org_id")
    if not org_id:
        return
    await sio.enter_room(sid, _org_room(org_id), namespace="/inbox")
    logger.info("staff_joined_org_room", org_id=org_id, sid=sid)


@sio.on("disconnect", namespace="/inbox")
async def inbox_disconnect(sid: str) -> None:
    logger.info("inbox_disconnected", sid=sid)


async def notify_new_message(org_id: uuid.UUID, conversation_id: uuid.UUID, role: str, content: str) -> None:
    """Called whenever a customer message is saved — lets the staff inbox
    update in real time without polling."""
    await sio.emit(
        "new_message",
        {
            "conversation_id": str(conversation_id),
            "role": role,
            "content": content,
        },
        room=_org_room(org_id),
        namespace="/inbox",
    )


async def notify_escalation_created(org_id: uuid.UUID, escalation: Escalation) -> None:
    await sio.emit(
        "escalation_created",
        {
            "escalation_id": str(escalation.id),
            "conversation_id": str(escalation.conversation_id),
            "reason": escalation.reason,
            "priority": escalation.priority.value,
        },
        room=_org_room(org_id),
        namespace="/inbox",
    )


async def notify_staff_reply_to_customer(conversation_id: uuid.UUID, content: str) -> None:
    """Delivers a staff reply to the customer's own webchat widget in real
    time — targeted at just this conversation's room in /chat, not the whole
    org, since multiple customers of the same org share that namespace.
    Webchat-only: WhatsApp/voice customers aren't connected to chat_sio at
    all, so this would just be a no-op room emit for those channels — callers
    should only invoke this for channel == webchat (see conversation_service.
    send_staff_reply, which routes WhatsApp/voice replies differently)."""
    await chat_sio.emit(
        "staff_message",
        {"conversation_id": str(conversation_id), "content": content},
        room=_conversation_room(conversation_id),
        namespace="/chat",
    )


async def notify_staff_reply_to_inbox(org_id: uuid.UUID, conversation_id: uuid.UUID, content: str) -> None:
    """Lets every staff client viewing this org's inbox see a just-sent reply
    in real time — channel-agnostic, called for every reply regardless of
    which channel it was actually delivered over."""
    await sio.emit(
        "new_message",
        {"conversation_id": str(conversation_id), "role": "staff", "content": content},
        room=_org_room(org_id),
        namespace="/inbox",
    )


async def notify_takeover(conversation_id: uuid.UUID) -> None:
    """Tells the customer's webchat widget a human has taken over, so it can
    show "you're now chatting with a team member" instead of implying the AI
    is still responding. Webchat-only, same reasoning as
    notify_staff_reply_to_customer above."""
    await chat_sio.emit(
        "takeover_event",
        {"conversation_id": str(conversation_id)},
        room=_conversation_room(conversation_id),
        namespace="/chat",
    )


async def notify_escalation_picked_up(org_id: uuid.UUID, escalation_id: uuid.UUID, conversation_id: uuid.UUID) -> None:
    await sio.emit(
        "escalation_picked_up",
        {"escalation_id": str(escalation_id), "conversation_id": str(conversation_id)},
        room=_org_room(org_id),
        namespace="/inbox",
    )
