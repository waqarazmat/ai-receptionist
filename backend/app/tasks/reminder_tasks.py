from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.booking.reminders import format_reminder_message, get_upcoming_appointments
from app.channels.whatsapp.message_sender import send_template_message, send_text_message
from app.db.engine import async_session_maker
from app.db.redis import redis_client
from app.models.appointment import Appointment
from app.models.contact import Contact
from app.models.enums import Channel
from app.models.organization import Organization
from app.services.conversation_service import get_last_customer_message_at

logger = structlog.get_logger()

# Comfortably covers the 24h reminder lookahead so a dedupe marker never
# expires before the appointment it's guarding has passed.
REMINDED_KEY_TTL_SECONDS = 60 * 60 * 48

# Meta's 24-hour customer service window: free-form text is only deliverable
# within 24h of the customer's last inbound message; outside it, only an
# approved template message is allowed. Must match a template name already
# approved in Meta Business Manager for the org (see template_manager.py) —
# overridable per-org the same way the free-form text template already is.
DEFAULT_WHATSAPP_TEMPLATE_NAME = "appointment_reminder"
WHATSAPP_WINDOW_HOURS = 24


def _reminded_key(appointment_id) -> str:
    return f"reminded:{appointment_id}"


async def send_appointment_reminders(ctx: dict) -> int:
    """Arq cron job — runs every 15 minutes. Finds confirmed appointments in
    the next 24h that haven't been reminded yet and sends a reminder for
    each, formatted per the org's template. WhatsApp contacts get a real
    message via the Cloud API (free-form if the customer messaged in the
    last 24h, otherwise an approved template); everything else still logs a
    placeholder ahead of its own channel integration.
    """
    sent = 0
    async with async_session_maker() as db:
        appointments = await get_upcoming_appointments(db, hours_ahead=24)

        for appointment in appointments:
            key = _reminded_key(appointment.id)
            # SET NX doubles as the "already reminded" check and the dedupe
            # marker in one atomic op, so two overlapping cron ticks can't
            # both send the same reminder.
            claimed = await redis_client.set(key, "1", nx=True, ex=REMINDED_KEY_TTL_SECONDS)
            if not claimed:
                continue

            org = await db.get(Organization, appointment.org_id)
            contact = await db.get(Contact, appointment.contact_id)
            if org is None or contact is None:
                continue

            message = format_reminder_message(org, contact, appointment)

            if contact.channel == Channel.whatsapp and contact.phone:
                await _send_whatsapp_reminder(db, org, contact, appointment, message)
            else:
                # Placeholder for channels without a reminder integration yet.
                logger.info(
                    "appointment_reminder_sent",
                    appointment_id=str(appointment.id),
                    org_id=str(appointment.org_id),
                    contact_id=str(appointment.contact_id),
                    message=message,
                )

            sent += 1

    logger.info("reminder_sweep_complete", reminders_sent=sent)
    return sent


async def _send_whatsapp_reminder(
    db: AsyncSession, org: Organization, contact: Contact, appointment: Appointment, message: str
) -> None:
    last_customer_message_at = await get_last_customer_message_at(db, contact.id)
    within_window = last_customer_message_at is not None and (
        datetime.now(timezone.utc) - last_customer_message_at
    ) <= timedelta(hours=WHATSAPP_WINDOW_HOURS)

    if within_window:
        wamid = await send_text_message(org.id, contact.phone, message)
    else:
        template_name = (org.system_prompts or {}).get("reminder_template_name") or DEFAULT_WHATSAPP_TEMPLATE_NAME
        parameters = [
            contact.name,
            appointment.service_name,
            org.name,
            appointment.start_time.strftime("%A, %B %d"),
            appointment.start_time.strftime("%I:%M %p").lstrip("0"),
        ]
        wamid = await send_template_message(org.id, contact.phone, template_name, parameters)

    if wamid is None:
        logger.warning(
            "whatsapp_reminder_send_failed",
            appointment_id=str(appointment.id),
            org_id=str(org.id),
            within_window=within_window,
        )
