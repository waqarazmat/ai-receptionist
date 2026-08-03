from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.booking.reminders import (
    format_appointment_date_time,
    format_reminder_message,
    get_upcoming_appointments,
)
from app.channels.whatsapp.message_sender import send_template_message, send_text_message
from app.config import settings
from app.db.engine import async_session_maker
from app.db.redis import redis_client
from app.models.appointment import Appointment
from app.models.contact import Contact
from app.models.enums import Channel
from app.models.organization import Organization
from app.services.conversation_service import get_last_customer_message_at
from app.utils.email import EmailDeliveryError, email_service

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

# Two reminder offsets, each fires at most once per appointment (per-offset
# dedupe key). "24h" is the day-before/within-24h heads-up; "soon" is the
# short-fuse "are you ready or want to reschedule?" nudge fired
# settings.REMINDER_LEAD_MINUTES before the start.
OFFSET_24H = "24h"
OFFSET_SOON = "soon"


def _reminded_key(appointment_id, offset_key: str) -> str:
    return f"reminded:{appointment_id}:{offset_key}"


async def send_appointment_reminders(ctx: dict) -> int:
    """Arq cron job — runs every 15 minutes. For each confirmed appointment in
    the next 24h, fires whichever reminder offsets are now due (24h-before and
    ~1h-before), once each. Reminders go out by email (the primary channel for
    the client) and, for WhatsApp contacts, also over WhatsApp for the 24h
    heads-up. All times are rendered in the org's local timezone.
    """
    lead_minutes = settings.REMINDER_LEAD_MINUTES
    now = datetime.now(timezone.utc)
    sent = 0

    async with async_session_maker() as db:
        appointments = await get_upcoming_appointments(db, hours_ahead=24)

        for appointment in appointments:
            minutes_until = (appointment.start_time - now).total_seconds() / 60.0
            if minutes_until <= 0:
                continue

            # Which offset is due right now? "soon" wins once we're inside the
            # lead window; otherwise the 24h heads-up. A booking made less than
            # `lead_minutes` out therefore only ever gets the "soon" reminder.
            if minutes_until <= lead_minutes:
                offset_key = OFFSET_SOON
            else:
                offset_key = OFFSET_24H

            # SET NX doubles as the "already reminded for this offset" check and
            # the dedupe marker in one atomic op, so overlapping cron ticks can't
            # both send the same reminder.
            claimed = await redis_client.set(
                _reminded_key(appointment.id, offset_key), "1", nx=True, ex=REMINDED_KEY_TTL_SECONDS
            )
            if not claimed:
                continue

            org = await db.get(Organization, appointment.org_id)
            contact = await db.get(Contact, appointment.contact_id)
            if org is None or contact is None:
                continue

            if await _dispatch_reminder(db, org, contact, appointment, offset_key):
                sent += 1

    logger.info("reminder_sweep_complete", reminders_sent=sent)
    return sent


async def _dispatch_reminder(
    db: AsyncSession, org: Organization, contact: Contact, appointment: Appointment, offset_key: str
) -> bool:
    """Send the reminder for one appointment/offset across the channels the
    contact can be reached on. Returns True if at least one channel was used."""
    sent_any = False

    # Email — the primary reminder channel (the "Gmail reminder" the client sees).
    if contact.email:
        try:
            await _send_email_reminder(org, contact, appointment, offset_key)
            sent_any = True
        except EmailDeliveryError as exc:
            logger.warning(
                "appointment_reminder_email_failed",
                appointment_id=str(appointment.id),
                offset=offset_key,
                error=str(exc),
            )

    # WhatsApp — only for the 24h heads-up (avoid paid template messages twice).
    if offset_key == OFFSET_24H and contact.channel == Channel.whatsapp and contact.phone:
        message = format_reminder_message(org, contact, appointment)
        await _send_whatsapp_reminder(db, org, contact, appointment, message)
        sent_any = True

    if not sent_any:
        # No reachable channel (e.g. a web-chat/voice contact who never gave an
        # email). Log so it's visible rather than silently dropped.
        logger.info(
            "appointment_reminder_no_channel",
            appointment_id=str(appointment.id),
            org_id=str(appointment.org_id),
            offset=offset_key,
        )

    return sent_any


async def _send_email_reminder(
    org: Organization, contact: Contact, appointment: Appointment, offset_key: str
) -> None:
    date_str, time_str = format_appointment_date_time(org, appointment)
    ctx = {
        "contact_name": contact.name or "there",
        "service_name": appointment.service_name,
        "org_name": org.name,
        "date": date_str,
        "time": time_str,
    }

    if offset_key == OFFSET_SOON:
        subject = f"Your {appointment.service_name} is coming up at {time_str}"
        html_body = email_service.render("appointment_reminder_soon.html", **ctx)
        text_body = (
            f"Hi {ctx['contact_name']}, your {appointment.service_name} appointment with "
            f"{org.name} is today at {time_str}. Are you all set? If you need to reschedule, "
            f"just reply to this email or give us a call."
        )
    else:
        subject = f"Reminder: your {appointment.service_name} on {date_str}"
        html_body = email_service.render("appointment_reminder_24h.html", **ctx)
        text_body = (
            f"Hi {ctx['contact_name']}, this is a reminder of your {appointment.service_name} "
            f"appointment with {org.name} on {date_str} at {time_str}. Need to reschedule? "
            f"Just reply to this email or give us a call."
        )

    await email_service.send_email(
        to=contact.email, subject=subject, html_body=html_body, text_body=text_body
    )


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
        date_str, time_str = format_appointment_date_time(org, appointment)
        parameters = [
            contact.name,
            appointment.service_name,
            org.name,
            date_str,
            time_str,
        ]
        wamid = await send_template_message(org.id, contact.phone, template_name, parameters)

    if wamid is None:
        logger.warning(
            "whatsapp_reminder_send_failed",
            appointment_id=str(appointment.id),
            org_id=str(org.id),
            within_window=within_window,
        )
