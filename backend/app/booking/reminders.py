from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.booking.slot_manager import resolve_org_timezone
from app.models.appointment import Appointment
from app.models.contact import Contact
from app.models.enums import AppointmentStatus
from app.models.organization import Organization

DEFAULT_REMINDER_TEMPLATE = (
    "Hi {contact_name}, this is a reminder of your {service_name} appointment with "
    "{org_name} on {date} at {time}."
)


async def get_upcoming_appointments(db: AsyncSession, hours_ahead: int = 24) -> list[Appointment]:
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=hours_ahead)
    result = await db.execute(
        select(Appointment).where(
            Appointment.status == AppointmentStatus.confirmed,
            Appointment.start_time >= now,
            Appointment.start_time <= cutoff,
        )
    )
    return list(result.scalars().all())


def appointment_local_datetime(org: Organization, appointment: Appointment) -> datetime:
    """The appointment's start time in the ORG's timezone. `start_time` is
    stored as UTC, so any reminder/UI that formats it directly shows the wrong
    wall-clock time (a 2 PM New York slot reads as 6 PM); convert first."""
    return appointment.start_time.astimezone(resolve_org_timezone(org))


def format_appointment_date_time(org: Organization, appointment: Appointment) -> tuple[str, str]:
    """(date, time) strings in the org's local timezone, e.g. ("Monday, August 04", "2:00 PM")."""
    local = appointment_local_datetime(org, appointment)
    return local.strftime("%A, %B %d"), local.strftime("%I:%M %p").lstrip("0")


def format_reminder_message(org: Organization, contact: Contact, appointment: Appointment) -> str:
    prompts = org.system_prompts or {}
    template = prompts.get("reminder_template") or DEFAULT_REMINDER_TEMPLATE
    date_str, time_str = format_appointment_date_time(org, appointment)
    fields = {
        "contact_name": contact.name,
        "service_name": appointment.service_name,
        "org_name": org.name,
        "date": date_str,
        "time": time_str,
    }
    try:
        return template.format(**fields)
    except (KeyError, IndexError, ValueError):
        # A custom org template with an unknown/mis-typed {placeholder} must not
        # crash the reminder sweep — fall back to the default wording.
        return DEFAULT_REMINDER_TEMPLATE.format(**fields)
