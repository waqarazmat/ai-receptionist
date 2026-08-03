import re
import uuid
from datetime import date, datetime, timedelta, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm_router import LLMProviderError, NoLLMProviderConfiguredError, call_llm, get_org_llm_client, parse_json_response
from app.ai.prompts.booking_prompts import get_booking_extraction_prompt, get_contact_info_extraction_prompt
from app.booking import slot_manager
from app.booking.fsm import BookingFSM, BookingState
from app.booking.google_calendar import GoogleCalendarClient, GoogleCalendarError
from app.booking.slot_manager import resolve_org_timezone
from app.models.contact import Contact
from app.models.organization import Organization
from app.services import appointment_service

logger = structlog.get_logger()

DEFAULT_SERVICE_DURATION_MINUTES = 30
SLOTS_LOOKAHEAD_DAYS = 7

FALLBACK_MESSAGE = (
    "We're having trouble with booking right now — please call us directly and our team will "
    "be happy to get you scheduled."
)
DETAILS_LOST_MESSAGE = (
    "Sorry, something went wrong collecting your booking details — could you tell me the "
    "service and preferred time again?"
)

_CANCEL_RE = re.compile(r"\b(cancel|nevermind|never mind|forget it|stop|start over)\b", re.IGNORECASE)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_valid_email(email: str | None) -> bool:
    return bool(email) and bool(_EMAIL_RE.match(email))


def _format_time(dt: datetime) -> str:
    return dt.strftime("%I:%M %p").lstrip("0")


def _format_slot_options(slots: list[datetime]) -> str:
    return ", ".join(f"{slot.strftime('%a')} {_format_time(slot)}" for slot in slots)


def _parse_slot_datetime(date_str: str, time_str: str, org_timezone) -> datetime | None:
    """`org_timezone` is a ZoneInfo — the date/time strings are the literal
    wall-clock values the customer meant, local to the org's timezone, not
    UTC (see get_booking_extraction_prompt)."""
    try:
        naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return None
    return naive.replace(tzinfo=org_timezone)


async def _extract_booking_fields(
    db: AsyncSession, org_id: uuid.UUID, message_text: str, service_names: list[str], org_timezone_name: str, org_tz
) -> dict:
    try:
        client = await get_org_llm_client(db, org_id, model_tier="fast")
        raw = await call_llm(
            client,
            messages=[{"role": "user", "content": message_text}],
            system_prompt=get_booking_extraction_prompt(
                service_names=service_names,
                today=datetime.now(org_tz).date().isoformat(),
                org_timezone=org_timezone_name,
            ),
        )
        return parse_json_response(raw)
    except (LLMProviderError, NoLLMProviderConfiguredError, ValueError, TypeError) as exc:
        logger.warning("booking_extraction_failed", org_id=str(org_id), error=str(exc))
        return {}


async def _extract_contact_info(db: AsyncSession, org_id: uuid.UUID, message_text: str) -> dict:
    try:
        client = await get_org_llm_client(db, org_id, model_tier="fast")
        raw = await call_llm(
            client,
            messages=[{"role": "user", "content": message_text}],
            system_prompt=get_contact_info_extraction_prompt(),
        )
        return parse_json_response(raw)
    except (LLMProviderError, NoLLMProviderConfiguredError, ValueError, TypeError) as exc:
        logger.warning("contact_info_extraction_failed", org_id=str(org_id), error=str(exc))
        return {}


async def _next_available_slots(
    db: AsyncSession, org_id: uuid.UUID, duration_minutes: int, org_tz, *, start_day: date | None = None
) -> list[datetime]:
    """Looks ahead up to SLOTS_LOOKAHEAD_DAYS for the first day with openings —
    a fresh org's calendar might have nothing open today (closed, fully
    booked), and offering nothing is a worse experience than checking the
    next few days automatically."""
    day = start_day or datetime.now(org_tz).date()
    for offset in range(SLOTS_LOOKAHEAD_DAYS):
        slots = await slot_manager.get_available_slots(db, org_id, day + timedelta(days=offset), duration_minutes)
        if slots:
            return slots
    return []


async def booking_session_active(conversation_id: uuid.UUID) -> bool:
    """True when this conversation has a booking mid-flow (past IDLE, not yet
    terminal).

    The channel routers use this to stay in "booking mode" once a booking has
    started, routing every subsequent customer reply into the FSM instead of
    re-classifying intent each turn. Without it, replies like a name+email
    ("John, john@x.com") or a bare "yes" at the confirm step get classified as
    off_topic/faq and fall through to RAG, abandoning the half-finished booking.
    """
    fsm = await BookingFSM.load(str(conversation_id))
    return fsm.current_state not in (BookingState.IDLE, BookingState.BOOKED, BookingState.CANCELLED)


async def clear_booking_session(conversation_id: uuid.UUID) -> None:
    """Drop any in-progress booking state — used when the customer breaks out
    of a booking (e.g. escalates to a human) so it doesn't linger in Redis and
    re-capture their next, unrelated message."""
    fsm = await BookingFSM.load(str(conversation_id))
    await fsm.clear()


async def process_booking_intent(
    db: AsyncSession,
    org_id: uuid.UUID,
    conversation_id: uuid.UUID,
    contact_id: uuid.UUID,
    user_input: str,
    intent: str = "booking_request",
) -> str:
    """Loads/creates the conversation's booking FSM, advances it with
    `user_input`, and returns the text to send back. On reaching BOOKED,
    actually performs the booking: hold slot -> create Calendar event ->
    save appointment -> release hold -> confirmation text.
    """
    org = await db.get(Organization, org_id)
    services = (org.booking_config or {}).get("services", []) if org else []
    service_by_name = {s["name"]: s for s in services}
    org_tz = resolve_org_timezone(org)
    org_timezone_name = org.timezone if org else "UTC"

    fsm = await BookingFSM.load(str(conversation_id))

    if fsm.current_state != BookingState.IDLE and _CANCEL_RE.search(user_input or ""):
        await fsm.clear()
        return "No problem, I've cancelled that booking request. Let me know if you'd like to start over."

    previous_state = fsm.current_state

    # Extract on the opening message (IDLE) too — details the customer already
    # gave ("book a cleaning tomorrow at 2pm") must not be thrown away and re-asked.
    if previous_state in (BookingState.IDLE, BookingState.COLLECTING_SERVICE, BookingState.COLLECTING_TIME):
        extracted = await _extract_booking_fields(
            db, org_id, user_input, list(service_by_name.keys()), org_timezone_name, org_tz
        )
        if extracted.get("service") in service_by_name:
            fsm.collected_data["service"] = extracted["service"]
        if extracted.get("date"):
            fsm.collected_data["date"] = extracted["date"]
        if extracted.get("time"):
            fsm.collected_data["time"] = extracted["time"]

        # Whenever we now hold a concrete date+time, validate it against real
        # availability; if it isn't bookable, drop it and offer alternatives.
        if fsm.collected_data.get("date") and fsm.collected_data.get("time"):
            service = service_by_name.get(fsm.collected_data.get("service", ""), {})
            duration = service.get("duration_minutes", DEFAULT_SERVICE_DURATION_MINUTES)
            requested_dt = _parse_slot_datetime(fsm.collected_data["date"], fsm.collected_data["time"], org_tz)

            slot_valid = requested_dt is not None and await slot_manager.is_slot_available(
                db, org_id, requested_dt, duration
            )
            if not slot_valid:
                fsm.collected_data.pop("date", None)
                fsm.collected_data.pop("time", None)
                await fsm.save()
                alternatives = await _next_available_slots(db, org_id, duration, org_tz)
                if alternatives:
                    return (
                        f"Sorry, that time isn't available. Some other options: "
                        f"{_format_slot_options(alternatives)}. What works for you?"
                    )
                return "Sorry, that time isn't available and I couldn't find another opening soon — could you try a different day?"

        # Fast-forward past steps already satisfied on the opening message, so
        # we don't greet-and-ask "what service?" when they already told us. The
        # FSM's IDLE/service handlers only prompt; they don't skip ahead.
        if previous_state == BookingState.IDLE:
            cd = fsm.collected_data
            if cd.get("service") and cd.get("date") and cd.get("time"):
                fsm.current_state = BookingState.COLLECTING_TIME
            elif cd.get("service"):
                fsm.current_state = BookingState.COLLECTING_SERVICE

    elif previous_state == BookingState.COLLECTING_CONTACT_INFO:
        extracted = await _extract_contact_info(db, org_id, user_input)
        name = (extracted.get("name") or "").strip() or None
        email = (extracted.get("email") or "").strip() or None
        valid_email = email if _is_valid_email(email) else None

        if name:
            fsm.collected_data["customer_name"] = name
        if valid_email:
            fsm.collected_data["customer_email"] = valid_email

        if name or valid_email:
            contact = await db.get(Contact, contact_id)
            if contact is not None:
                if name:
                    contact.name = name
                if valid_email:
                    contact.email = valid_email
                await db.commit()

    result = fsm.transition(intent, user_input)
    new_state = BookingState(result["new_state"])

    if new_state == BookingState.BOOKED:
        response_text = await _finalize_booking(
            db, org_id, conversation_id, contact_id, fsm, service_by_name, org_tz, org_timezone_name
        )
        await fsm.clear()
        return response_text

    response_text = result["response_text"]

    if new_state == BookingState.COLLECTING_SERVICE and service_by_name:
        response_text += " We offer: " + ", ".join(service_by_name.keys()) + "."
    elif new_state == BookingState.COLLECTING_TIME:
        service = service_by_name.get(fsm.collected_data.get("service", ""), {})
        duration = service.get("duration_minutes", DEFAULT_SERVICE_DURATION_MINUTES)
        slots = await _next_available_slots(db, org_id, duration, org_tz)
        if slots:
            response_text += f" Some open times: {_format_slot_options(slots)}."

    await fsm.save()
    return response_text


async def _finalize_booking(
    db: AsyncSession,
    org_id: uuid.UUID,
    conversation_id: uuid.UUID,
    contact_id: uuid.UUID,
    fsm: BookingFSM,
    service_by_name: dict,
    org_tz,
    org_timezone_name: str,
) -> str:
    service_name = fsm.collected_data.get("service")
    date_str = fsm.collected_data.get("date")
    time_str = fsm.collected_data.get("time")
    start = _parse_slot_datetime(date_str, time_str, org_tz) if date_str and time_str else None
    if not (service_name and start):
        return DETAILS_LOST_MESSAGE

    service = service_by_name.get(service_name, {})
    duration = service.get("duration_minutes", DEFAULT_SERVICE_DURATION_MINUTES)
    end = start + timedelta(minutes=duration)

    held = await slot_manager.hold_slot(org_id, start, contact_id)
    if not held:
        return "Sorry, that slot was just taken by someone else. Could you pick another time?"

    # Final guard against an overlapping appointment created between slot
    # validation and now (the Redis hold only covers this exact start time).
    if await slot_manager.has_conflicting_appointment(db, org_id, start, end):
        await slot_manager.release_slot(org_id, start, contact_id)
        return "Sorry, that slot was just taken by someone else. Could you pick another time?"

    try:
        contact = await db.get(Contact, contact_id)
        google_event_id = None
        try:
            client = await GoogleCalendarClient.for_org(db, org_id)
            google_event_id = await client.create_event(
                summary=f"{service_name} — {contact.name if contact else 'Customer'}",
                start=start,
                end=end,
                attendee_email=contact.email if contact else None,
                time_zone=org_timezone_name,
            )
        except GoogleCalendarError as exc:
            # Booking still proceeds without a calendar event — staff see it
            # in the appointments list and can add it to the calendar
            # manually; that's better than losing the booking outright.
            logger.warning("calendar_event_create_failed", org_id=str(org_id), error=str(exc))

        # Postgres stores timestamptz internally as UTC regardless of the
        # tzinfo passed in, but converting explicitly here keeps what's
        # actually sent over the wire unambiguous — the org's local
        # timezone is already recorded on Organization.timezone, so nothing
        # about the local time is lost by storing the UTC instant.
        await appointment_service.create_appointment(
            db,
            org_id,
            contact_id,
            conversation_id,
            service_name,
            start.astimezone(timezone.utc),
            end.astimezone(timezone.utc),
            google_event_id,
        )
    finally:
        await slot_manager.release_slot(org_id, start, contact_id)

    return (
        f"You're all set! I've booked your {service_name} for {start.strftime('%A, %B %d')} at "
        f"{_format_time(start)}. We look forward to seeing you!"
    )
