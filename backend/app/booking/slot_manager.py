import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.booking.google_calendar import GoogleCalendarClient, GoogleCalendarError
from app.db.redis import redis_client
from app.models.organization import Organization

logger = structlog.get_logger()

HOLD_TTL_SECONDS = 300
SLOT_INTERVAL_MINUTES = 30
DEFAULT_OPEN_TIME = time(9, 0)
DEFAULT_CLOSE_TIME = time(17, 0)
DEFAULT_MAX_SLOTS_RETURNED = 6


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

    weekday_name = day.strftime("%A").lower()
    hours = (org.working_hours or {}).get("hours", {}).get(weekday_name)
    if not hours:
        return DEFAULT_OPEN_TIME, DEFAULT_CLOSE_TIME
    if hours.get("open") is None or hours.get("close") is None:
        return None  # explicitly closed that day

    try:
        open_time = datetime.strptime(hours["open"], "%H:%M").time()
        close_time = datetime.strptime(hours["close"], "%H:%M").time()
    except (ValueError, TypeError):
        return DEFAULT_OPEN_TIME, DEFAULT_CLOSE_TIME
    return open_time, close_time


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

    busy_ranges: list[tuple[datetime, datetime]] = []
    try:
        client = await GoogleCalendarClient.for_org(db, org_id)
        busy_periods = await client.get_free_busy(day_start, day_end)
        busy_ranges = [
            (datetime.fromisoformat(period["start"]), datetime.fromisoformat(period["end"]))
            for period in busy_periods
        ]
    except GoogleCalendarError as exc:
        logger.warning("calendar_unavailable_for_slots", org_id=str(org_id), error=str(exc))

    slots: list[datetime] = []
    cursor = day_start
    step = timedelta(minutes=SLOT_INTERVAL_MINUTES)
    duration = timedelta(minutes=service_duration_minutes)

    while cursor + duration <= day_end and len(slots) < max_results:
        slot_end = cursor + duration
        overlaps_busy = any(cursor < busy_end and slot_end > busy_start for busy_start, busy_end in busy_ranges)
        if not overlaps_busy and not await is_slot_held(org_id, cursor):
            slots.append(cursor)
        cursor += step

    return slots
