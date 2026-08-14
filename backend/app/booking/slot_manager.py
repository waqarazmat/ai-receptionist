import asyncio
import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.booking.google_calendar import GoogleCalendarClient, GoogleCalendarError
from app.config import settings
from app.db.redis import redis_client
from app.models.appointment import Appointment
from app.models.enums import AppointmentStatus
from app.models.organization import Organization

logger = structlog.get_logger()

HOLD_TTL_SECONDS = 300
SLOT_INTERVAL_MINUTES = 30
DEFAULT_OPEN_TIME = time(9, 0)
DEFAULT_CLOSE_TIME = time(17, 0)
DEFAULT_MAX_SLOTS_RETURNED = 6
# Never offer or accept a slot starting sooner than this from now — avoids
# suggesting times that have already passed earlier today, and blocks
# "book 5 minutes from now" requests.
MIN_BOOKING_LEAD_MINUTES = 30


def resolve_org_timezone(org: Organization | None) -> ZoneInfo:
    """Falls back to UTC for a missing org or an invalid/unrecognized IANA
    name, rather than raising — booking should degrade, not 500, on bad
    timezone data (root CLAUDE.md rule #8)."""
    if org is None or not org.timezone:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(org.timezone)
    except ZoneInfoNotFoundError:
        logger.warning("invalid_org_timezone", org_id=str(org.id), timezone=org.timezone)
        return ZoneInfo("UTC")


def _hold_key(org_id: uuid.UUID, slot_datetime: datetime) -> str:
    return f"slot_hold:{org_id}:{slot_datetime.isoformat()}"


async def hold_slot(org_id: uuid.UUID, slot_datetime: datetime, contact_id: uuid.UUID, ttl: int = HOLD_TTL_SECONDS) -> bool:
    """SET NX — succeeds only if nobody else holds this slot yet. This is
    the actual concurrency guard against two customers booking the same slot
    at once; everything else in the booking flow is best-effort around it."""
    key = _hold_key(org_id, slot_datetime)
    return bool(await redis_client.set(key, str(contact_id), nx=True, ex=ttl))


async def release_slot(org_id: uuid.UUID, slot_datetime: datetime, contact_id: uuid.UUID) -> bool:
    """Only releases if held by this contact — a stranger can't release
    someone else's hold, and a hold that already expired on its own is a
    harmless no-op (returns False either way)."""
    key = _hold_key(org_id, slot_datetime)
    holder = await redis_client.get(key)
    if holder != str(contact_id):
        return False
    await redis_client.delete(key)
    return True


async def is_slot_held(org_id: uuid.UUID, slot_datetime: datetime) -> bool:
    return bool(await redis_client.exists(_hold_key(org_id, slot_datetime)))


def _working_hours_for(org: Organization | None, day: date) -> tuple[time, time] | None:
    if org is None:
        return DEFAULT_OPEN_TIME, DEFAULT_CLOSE_TIME

    hours_map = (org.working_hours or {}).get("hours", {})
    if not hours_map:
        # Org hasn't configured ANY hours → sensible default so bookings still work.
        return DEFAULT_OPEN_TIME, DEFAULT_CLOSE_TIME

    weekday_name = day.strftime("%A").lower()
    hours = hours_map.get(weekday_name)
    if not hours:
        # Hours ARE configured, just not for this weekday → the business is CLOSED
        # that day (a schedule listing Mon–Fri means Sat/Sun are shut). Previously
        # a missing day fell through to the default open hours, which handed out
        # slots on days the org is actually closed (e.g. Sundays).
        return None
    if hours.get("open") is None or hours.get("close") is None:
        return None  # explicitly closed that day

    try:
        open_time = datetime.strptime(hours["open"], "%H:%M").time()
        close_time = datetime.strptime(hours["close"], "%H:%M").time()
    except (ValueError, TypeError):
        return DEFAULT_OPEN_TIME, DEFAULT_CLOSE_TIME
    return open_time, close_time


_WEEKDAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def is_open_on(org: "Organization | None", day: date) -> bool:
    """Whether the org has working hours on `day` (False = closed that day)."""
    return _working_hours_for(org, day) is not None


def open_days_phrase(org: "Organization | None") -> str:
    """A short natural phrase of the weekdays the org is open — "Monday to Friday"
    for a contiguous run, else "Monday, Wednesday and Friday". "" if unknown."""
    hours_map = (org.working_hours or {}).get("hours", {}) if org else {}
    names = [
        d.capitalize()
        for d in _WEEKDAY_ORDER
        if hours_map.get(d) and hours_map[d].get("open") and hours_map[d].get("close")
    ]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    idx = [_WEEKDAY_ORDER.index(n.lower()) for n in names]
    if idx == list(range(idx[0], idx[0] + len(idx))):  # contiguous weekdays
        return f"{names[0]} to {names[-1]}"
    return ", ".join(names[:-1]) + " and " + names[-1]


async def _busy_ranges(
    db: AsyncSession, org_id: uuid.UUID, window_start: datetime, window_end: datetime
) -> list[tuple[datetime, datetime]]:
    """All busy intervals overlapping [window_start, window_end): Google
    Calendar free/busy PLUS confirmed appointments already in our own DB.

    The DB half is the durable double-booking guard: the 5-minute Redis hold is
    released the moment an appointment is saved, and many orgs have no Google
    Calendar configured (or its event creation failed), so without checking our
    own appointments the same slot could be handed out twice.
    """
    ranges: list[tuple[datetime, datetime]] = []

    try:
        client = await GoogleCalendarClient.for_org(db, org_id)
        # Bounded so a slow Calendar API can't stall booking replies under load;
        # on timeout we degrade exactly like a Calendar error below (the DB
        # appointment guard still prevents double-booking).
        periods = await asyncio.wait_for(
            client.get_free_busy(window_start, window_end),
            timeout=settings.CALENDAR_FREEBUSY_TIMEOUT_SECONDS,
        )
        for period in periods:
            ranges.append((datetime.fromisoformat(period["start"]), datetime.fromisoformat(period["end"])))
    except (GoogleCalendarError, asyncio.TimeoutError) as exc:
        logger.warning("calendar_unavailable_for_slots", org_id=str(org_id), error=str(exc))

    appt_rows = (
        await db.execute(
            select(Appointment.start_time, Appointment.end_time).where(
                Appointment.org_id == org_id,
                Appointment.status == AppointmentStatus.confirmed,
                Appointment.end_time > window_start,
                Appointment.start_time < window_end,
            )
        )
    ).all()
    ranges.extend((start, end) for start, end in appt_rows)
    return ranges


async def has_conflicting_appointment(
    db: AsyncSession, org_id: uuid.UUID, start: datetime, end: datetime
) -> bool:
    """Final pre-write double-booking check: is there already a confirmed
    appointment overlapping [start, end)? Cheap (DB only, no Calendar) so it's
    safe to call right before creating the appointment, closing the race
    between slot validation and the actual write."""
    row = (
        await db.execute(
            select(Appointment.id)
            .where(
                Appointment.org_id == org_id,
                Appointment.status == AppointmentStatus.confirmed,
                Appointment.end_time > start,
                Appointment.start_time < end,
            )
            .limit(1)
        )
    ).first()
    return row is not None


async def is_slot_available(
    db: AsyncSession, org_id: uuid.UUID, requested_dt: datetime, service_duration_minutes: int
) -> bool:
    """Whether a specific requested start time can actually be booked — within
    working hours, not overlapping Calendar/DB busy ranges, not currently held.

    Replaces the old "is requested_dt in the (truncated) suggestion list?"
    check, which wrongly rejected any valid time past the first few slots of
    the day."""
    org = await db.get(Organization, org_id)
    hours = _working_hours_for(org, requested_dt.date())
    if hours is None:
        return False
    open_time, close_time = hours
    org_tz = resolve_org_timezone(org)

    # Reject times in the past / too soon (e.g. a 9 AM slot requested at 5 PM).
    if requested_dt < datetime.now(org_tz) + timedelta(minutes=MIN_BOOKING_LEAD_MINUTES):
        return False

    day_start = datetime.combine(requested_dt.date(), open_time, tzinfo=org_tz)
    day_end = datetime.combine(requested_dt.date(), close_time, tzinfo=org_tz)
    slot_end = requested_dt + timedelta(minutes=service_duration_minutes)
    if requested_dt < day_start or slot_end > day_end:
        return False

    busy_ranges = await _busy_ranges(db, org_id, day_start, day_end)
    if any(requested_dt < busy_end and slot_end > busy_start for busy_start, busy_end in busy_ranges):
        return False

    return not await is_slot_held(org_id, requested_dt)


async def get_available_slots(
    db: AsyncSession,
    org_id: uuid.UUID,
    day: date,
    service_duration_minutes: int,
    max_results: int = DEFAULT_MAX_SLOTS_RETURNED,
) -> list[datetime]:
    """Cross-references Google Calendar free/busy for `day` with active Redis
    holds, returning open slot start times of length `service_duration_minutes`.
    Degrades gracefully if Calendar isn't reachable — offers slots based on
    working hours + holds only, rather than failing the whole booking flow."""
    org = await db.get(Organization, org_id)
    hours = _working_hours_for(org, day)
    if hours is None:
        return []
    open_time, close_time = hours
    org_tz = resolve_org_timezone(org)

    day_start = datetime.combine(day, open_time, tzinfo=org_tz)
    day_end = datetime.combine(day, close_time, tzinfo=org_tz)
    if day_start >= day_end:
        return []

    busy_ranges = await _busy_ranges(db, org_id, day_start, day_end)

    # Don't offer slots in the past / too soon (e.g. today's 9 AM when it's 5 PM).
    earliest = datetime.now(org_tz) + timedelta(minutes=MIN_BOOKING_LEAD_MINUTES)

    slots: list[datetime] = []
    cursor = day_start
    step = timedelta(minutes=SLOT_INTERVAL_MINUTES)
    duration = timedelta(minutes=service_duration_minutes)

    while cursor + duration <= day_end and len(slots) < max_results:
        if cursor < earliest:
            cursor += step
            continue
        slot_end = cursor + duration
        overlaps_busy = any(cursor < busy_end and slot_end > busy_start for busy_start, busy_end in busy_ranges)
        if not overlaps_busy and not await is_slot_held(org_id, cursor):
            slots.append(cursor)
        cursor += step

    return slots
