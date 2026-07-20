import uuid

import structlog
from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import async_session_maker
from app.models.channel_config import ChannelConfig
from app.models.enums import Channel
from app.security.webhook_verify import verify_timestamp, verify_whatsapp_signature
from app.tasks.queue import get_arq_pool

logger = structlog.get_logger()

router = APIRouter()

UNSUPPORTED_MESSAGE_TYPE_REPLY = "Sorry, I can only read text messages right now — could you type that out for me?"


@router.get("/whatsapp")
async def verify_webhook(request: Request) -> Response:
    """Meta calls this once (and whenever the subscription is re-verified)
    when the webhook URL is configured in the Developer Console, to prove we
    control the endpoint."""
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and settings.WHATSAPP_VERIFY_TOKEN
        and params.get("hub.verify_token") == settings.WHATSAPP_VERIFY_TOKEN
        and params.get("hub.challenge")
    ):
        return Response(content=params["hub.challenge"], media_type="text/plain")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification failed")


async def _org_id_for_phone_number(db: AsyncSession, phone_number_id: str) -> uuid.UUID | None:
    """One shared webhook URL serves every org — Meta's payload identifies
    which WhatsApp number a message came in on via phone_number_id, which
    is how we route it back to the right org (stored, unencrypted since it's
    not a secret, in channel_configs.config)."""
    config_row = (
        await db.execute(
            select(ChannelConfig).where(
                ChannelConfig.channel_type == Channel.whatsapp,
                ChannelConfig.config["phone_number_id"].astext == phone_number_id,
            )
        )
    ).scalar_one_or_none()
    return config_row.org_id if config_row else None


@router.post("/whatsapp")
async def receive_webhook(request: Request) -> Response:
    body = await request.body()
    signature = request.headers.get("x-hub-signature-256")

    # a. Verify HMAC signature before anything else touches the payload —
    # reject unsigned/mis-signed requests outright. No "skip in dev mode"
    # (root CLAUDE.md security rule #3).
    if (
        not settings.WHATSAPP_APP_SECRET
        or not signature
        or not verify_whatsapp_signature(body, signature, settings.WHATSAPP_APP_SECRET)
    ):
        logger.warning("whatsapp_webhook_invalid_signature")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    payload = await request.json()
    if payload.get("object") != "whatsapp_business_account":
        # Signed but not something we handle — still 200 so Meta doesn't retry.
        return Response(status_code=status.HTTP_200_OK)

    pool = await get_arq_pool()

    async with async_session_maker() as db:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                phone_number_id = value.get("metadata", {}).get("phone_number_id")
                if not phone_number_id:
                    continue

                org_id = await _org_id_for_phone_number(db, phone_number_id)
                if org_id is None:
                    logger.warning("whatsapp_webhook_unknown_phone_number_id", phone_number_id=phone_number_id)
                    continue

                contacts_by_wa_id = {c["wa_id"]: c for c in value.get("contacts", []) if c.get("wa_id")}

                for message in value.get("messages", []):
                    # b. Replay protection — skip (don't process) anything
                    # older than 5 minutes. Meta doesn't send a separate
                    # request-level timestamp header, so this uses each
                    # message's own embedded timestamp.
                    if not verify_timestamp(message.get("timestamp", "")):
                        logger.warning("whatsapp_message_stale", message_id=message.get("id"))
                        continue

                    from_number = message.get("from")
                    if not from_number:
                        continue
                    contact_name = contacts_by_wa_id.get(from_number, {}).get("profile", {}).get("name")

                    # c. Parse message — text handled now; other types (image,
                    # audio, ...) get a graceful static reply rather than
                    # being silently dropped or fed into the AI pipeline as
                    # if they were customer text.
                    if message.get("type") == "text":
                        message_text = message.get("text", {}).get("body", "").strip()
                        if not message_text:
                            continue
                        await pool.enqueue_job(
                            "process_whatsapp_message",
                            str(org_id),
                            from_number,
                            contact_name,
                            message_text,
                            message.get("id"),
                        )
                    else:
                        await pool.enqueue_job(
                            "send_unsupported_message_reply",
                            str(org_id),
                            from_number,
                            UNSUPPORTED_MESSAGE_TYPE_REPLY,
                        )

                for status_entry in value.get("statuses", []):
                    if not verify_timestamp(status_entry.get("timestamp", "")):
                        logger.warning("whatsapp_status_stale", wamid=status_entry.get("id"))
                        continue
                    wamid = status_entry.get("id")
                    status_value = status_entry.get("status")
                    if wamid and status_value:
                        await pool.enqueue_job("process_whatsapp_status_update", wamid, status_value)

    # d. Return 200 immediately — all actual processing was just enqueued
    # to Arq above, not done inline.
    return Response(status_code=status.HTTP_200_OK)
