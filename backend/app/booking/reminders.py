from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


def format_reminder_message(org: Organization, contact: Contact, appointment: Appointment) -> str:
    prompts = org.system_prompts or {}
    template = prompts.get("reminder_template") or DEFAULT_REMINDER_TEMPLATE
    return template.format(
        contact_name=contact.name,
        service_name=appointment.service_name,
        org_name=org.name,
        date=appointment.start_time.strftime("%A, %B %d"),
        time=appointment.start_time.strftime("%I:%M %p").lstrip("0"),
    )
