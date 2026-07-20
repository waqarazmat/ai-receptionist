import uuid
from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.booking.google_calendar import GoogleCalendarClient, GoogleCalendarError
from app.models.appointment import Appointment
from app.models.contact import Contact
from app.models.enums import AppointmentStatus

logger = structlog.get_logger()


class AppointmentNotFoundError(Exception):
    pass


async def create_appointment(
    db: AsyncSession,
    org_id: uuid.UUID,
    contact_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    service_name: str,
    start_time: datetime,
    end_time: datetime,
    google_event_id: str | None,
) -> Appointment:
    appointment = Appointment(
        org_id=org_id,
        contact_id=contact_id,
        conversation_id=conversation_id,
        service_name=service_name,
        start_time=start_time,
        end_time=end_time,
        status=AppointmentStatus.confirmed,
        google_event_id=google_event_id,
    )
    db.add(appointment)
    await db.commit()
    await db.refresh(appointment)
    return appointment


async def list_appointments(
    db: AsyncSession,
    org_id: uuid.UUID,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    status_filter: AppointmentStatus | None = None,
) -> list[Appointment]:
    stmt = (
        select(Appointment, Contact.name, Contact.channel)
        .join(Contact, Contact.id == Appointment.contact_id)
        .where(Appointment.org_id == org_id)
    )
    if start_date is not None:
        stmt = stmt.where(Appointment.start_time >= start_date)
    if end_date is not None:
        stmt = stmt.where(Appointment.start_time <= end_date)
    if status_filter is not None:
        stmt = stmt.where(Appointment.status == status_filter)
    stmt = stmt.order_by(Appointment.start_time)

    result = await db.execute(stmt)
    appointments = []
    for appointment, contact_name, contact_channel in result.all():
        appointment.contact_name = contact_name
        appointment.channel = contact_channel.value
        appointments.append(appointment)
    return appointments


async def get_appointment(db: AsyncSession, org_id: uuid.UUID, appointment_id: uuid.UUID) -> Appointment:
    stmt = (
        select(Appointment, Contact.name, Contact.channel)
        .join(Contact, Contact.id == Appointment.contact_id)
        .where(Appointment.org_id == org_id, Appointment.id == appointment_id)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise AppointmentNotFoundError(str(appointment_id))
    appointment, contact_name, contact_channel = row
    appointment.contact_name = contact_name
    appointment.channel = contact_channel.value
    return appointment


async def cancel_appointment(db: AsyncSession, org_id: uuid.UUID, appointment_id: uuid.UUID) -> Appointment:
    appointment = await get_appointment(db, org_id, appointment_id)

    if appointment.google_event_id:
        try:
            client = await GoogleCalendarClient.for_org(db, org_id)
            await client.cancel_event(appointment.google_event_id)
        except GoogleCalendarError as exc:
            # Still cancel locally — the important thing is the org's own
            # record reflects the cancellation and the slot is freed; staff
            # can clean up the calendar side manually if this failed.
            logger.warning("calendar_event_cancel_failed", appointment_id=str(appointment_id), error=str(exc))

    appointment.status = AppointmentStatus.cancelled
    await db.commit()
    await db.refresh(appointment)
    return appointment
