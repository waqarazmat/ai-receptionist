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
from app.tasks.queue import get_arq_pool
from app.utils.email import email_service

logger = structlog.get_logger()

DEFAULT_SERVICE_DURATION_MINUTES = 30
SLOTS_LOOKAHEAD_DAYS = 7
# Slot suggestions span multiple open days (rather than dumping one day's whole
# schedule) so the customer can see several days/times are available.
MAX_SUGGESTED_DAYS = 3
MAX_SUGGESTED_SLOTS = 6

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


def _format_time_voice(dt: datetime) -> str:
    """Time phrased for text-to-speech: drop the ":00" on the hour so it reads
    "9 PM" not "9:00 PM"/"nine o'clock zero zero". Keeps minutes when present
    ("10:30 AM")."""
    if dt.minute == 0:
        return dt.strftime("%I %p").lstrip("0")
    return dt.strftime("%I:%M %p").lstrip("0")


def _ordinal(n: int) -> str:
    """1 -> '1st', 2 -> '2nd', 3 -> '3rd', 11 -> '11th', 21 -> '21st'. Used so a
    spoken date reads "August 11th", not "August eleven"."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _spell_token(token: str) -> str:
    """Hyphenate a token's characters so TTS reads them as individual letters/
    digits: "john" -> "J-O-H-N". Uppercased because "J-O-H-N" is unambiguous for
    a voice engine while "j-o-h-n" can be read as a word by some TTS voices."""
    return "-".join(ch.upper() for ch in token if not ch.isspace())


def _spell_name_for_voice(name: str) -> str:
    """"John Smith" -> "J-O-H-N S-M-I-T-H" (each word spelled, words space-separated)."""
    return " ".join(_spell_token(part) for part in name.split())


def _spell_email_for_voice(email: str) -> str:
    """Spell an email for a voice read-back: the local part letter-by-letter
    (the most ASR-error-prone piece), with "@" and "." spoken as "at"/"dot".
    "john.smith@gmail.com" -> "J-O-H-N dot S-M-I-T-H at gmail dot com". The domain
    is spoken as words (common hosts don't need spelling) to keep it listenable."""
    local, at, domain = email.partition("@")
    local_spelled = " dot ".join(_spell_token(tok) for tok in local.split("."))
    if not at:  # no "@" — spell the whole thing rather than dropping the domain
        return local_spelled
    domain_spoken = domain.replace(".", " dot ")
    return f"{local_spelled} at {domain_spoken}"


def _build_voice_confirmation(cd: dict, org_tz) -> str:
    """Voice-channel booking confirmation that reads the details back AND spells
    the name + email, so a caller can catch an ASR mis-hear before it's booked.
    Text channels keep the plain FSM confirmation (the customer can read those)."""
    service = cd.get("service", "your appointment")
    name = (cd.get("customer_name") or "").strip()
    email = (cd.get("customer_email") or "").strip()

    start = _parse_slot_datetime(cd.get("date"), cd.get("time"), org_tz) if cd.get("date") and cd.get("time") else None
    when = (
        f"{start.strftime('%A, %B')} {_ordinal(start.day)} at {_format_time_voice(start)}"
        if start else f"{cd.get('date')} at {cd.get('time')}"
    )

    parts = [f"Let me read that back to make sure I have it right — {service} on {when}."]
    if name:
        parts.append(f"Your name is {name}, spelled {_spell_name_for_voice(name)}.")
    if email:
        parts.append(f"And your email is {_spell_email_for_voice(email)}.")
    parts.append("Is that all correct?")
    return " ".join(parts)


def _format_slot_options(slots: list[datetime], channel: str = "text") -> str:
    # Include the date so "Tuesday" is never ambiguous between this week and next.
    # Voice spells day/month in full ("Monday, August 11th at 9 PM") because
    # abbreviations ("Mon Aug 11") read badly through TTS; text keeps the compact
    # form that's easy to scan on screen ("Tue Aug 11 at 10:30 AM").
    if channel == "voice":
        return ", ".join(
            f"{slot.strftime('%A, %B')} {_ordinal(slot.day)} at {_format_time_voice(slot)}"
            for slot in slots
        )
    return ", ".join(f"{slot.strftime('%a %b %d')} at {_format_time(slot)}" for slot in slots)


def _spread_pick(slots: list[datetime], n: int) -> list[datetime]:
    """Pick up to `n` slots spread evenly across a day's openings, so a day's
    suggestions show e.g. a morning and an afternoon option rather than two
    adjacent morning slots."""
    if n <= 0:
        return []
    if len(slots) <= n:
        return slots
    step = len(slots) / n
    return [slots[int(i * step)] for i in range(n)]


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
    """A spread of open slots across the next few OPEN days (up to
    SLOTS_LOOKAHEAD_DAYS ahead), so the customer sees that multiple days and
    times are available rather than one day's whole schedule. Closed/fully
    booked days are skipped. When only one day is open, it still returns a good
    morning-to-afternoon spread from that day."""
    day = start_day or datetime.now(org_tz).date()

    open_days: list[list[datetime]] = []
    for offset in range(SLOTS_LOOKAHEAD_DAYS):
        day_slots = await slot_manager.get_available_slots(
            db, org_id, day + timedelta(days=offset), duration_minutes, max_results=16
        )
        if day_slots:
            open_days.append(day_slots)
        if len(open_days) >= MAX_SUGGESTED_DAYS:
            break

    if not open_days:
        return []

    # Divide the suggestion budget across the open days found (≥1 each), so
    # several open days → a couple of times each; a single open day → a fuller
    # spread from that one day.
    per_day = max(1, MAX_SUGGESTED_SLOTS // len(open_days))
    suggestions: list[datetime] = []
    for day_slots in open_days:
        suggestions.extend(_spread_pick(day_slots, per_day))
    return suggestions[:MAX_SUGGESTED_SLOTS]


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


# States where a reply that DOESN'T look like a booking answer must still stay in
# the FSM: the caller is being asked for their name/email or a yes/no, and those
# answers ("John", "john@x.com", "yes") classify as off_topic/faq — routing them
# to RAG would abandon the booking. In the earlier service/time-collection states
# a genuine question/greeting should instead be answered normally (see the
# channel routers), so the customer isn't trapped re-hearing "what service?".
STICKY_BOOKING_STATES = (BookingState.COLLECTING_CONTACT_INFO, BookingState.CONFIRMING)

_BOOKING_INTENTS = ("booking_request", "booking_info")


def should_route_to_booking(booking_active: bool, booking_state: BookingState, intent: str) -> bool:
    """Whether a customer message should be handled by the booking FSM (vs
    answered normally by RAG). Escalation is decided by the caller before this.

    - A booking-shaped intent always routes in (starts or continues a booking).
    - While a booking is mid-flow, the sticky states (collecting name/email, or
      confirming) route in even for off_topic/faq-looking messages, because those
      answers ("John", "john@x.com", "yes") classify that way.
    - In the earlier service/time-collection states, a non-booking message
      (a question, greeting, farewell) does NOT route in — it's answered normally
      so the customer isn't trapped re-hearing "what service?" / "what time?".
    """
    if intent in _BOOKING_INTENTS:
        return True
    return booking_active and booking_state in STICKY_BOOKING_STATES


async def booking_session_state(conversation_id: uuid.UUID) -> tuple[bool, BookingState]:
    """(is a booking mid-flow?, its current state). Lets channel routers keep the
    name/email + confirm steps sticky while allowing questions to break out of the
    earlier service/time steps — see STICKY_BOOKING_STATES."""
    fsm = await BookingFSM.load(str(conversation_id))
    active = fsm.current_state not in (BookingState.IDLE, BookingState.BOOKED, BookingState.CANCELLED)
    return active, fsm.current_state


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
    channel: str = "text",
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

        # Single-service org: there's nothing to choose, so don't make the
        # customer name the only service (which just produces a "what service?
        # — we offer X" loop). Auto-select it and move straight on to the time.
        if not fsm.collected_data.get("service") and len(service_by_name) == 1:
            fsm.collected_data["service"] = next(iter(service_by_name))

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
                        f"{_format_slot_options(alternatives, channel)}. What works for you?"
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

    # On voice, replace the plain confirmation with a spelled read-back the first
    # time we enter CONFIRMING (not on a re-prompt after an unclear yes/no, where
    # previous_state is already CONFIRMING). Lets the caller catch an ASR mis-hear
    # of their name/email before the booking is committed.
    if (
        channel == "voice"
        and new_state == BookingState.CONFIRMING
        and previous_state != BookingState.CONFIRMING
    ):
        response_text = _build_voice_confirmation(fsm.collected_data, org_tz)

    if new_state == BookingState.COLLECTING_SERVICE and service_by_name:
        response_text += " We offer: " + ", ".join(service_by_name.keys()) + "."
    elif new_state == BookingState.COLLECTING_TIME:
        service = service_by_name.get(fsm.collected_data.get("service", ""), {})
        duration = service.get("duration_minutes", DEFAULT_SERVICE_DURATION_MINUTES)
        slots = await _next_available_slots(db, org_id, duration, org_tz)
        if slots:
            response_text += f" Some open times: {_format_slot_options(slots, channel)}."

    await fsm.save()
    return response_text


async def _enqueue_confirmation_email(
    db: AsyncSession,
    org_id: uuid.UUID,
    to_email: str,
    contact_name: str | None,
    service_name: str,
    start_local: datetime,
) -> None:
    """Queue an immediate 'appointment confirmed' email to the customer.

    Enqueued to the Arq worker so it never blocks the booking reply, and
    best-effort — any failure is logged, never raised, so it can't undo a
    completed booking. `start_local` is already in the org's timezone.
    """
    org = await db.get(Organization, org_id)
    org_name = org.name if org else "us"
    date_str = start_local.strftime("%A, %B %d")
    time_str = _format_time(start_local)
    ctx = {
        "contact_name": contact_name or "there",
        "service_name": service_name,
        "org_name": org_name,
        "date": date_str,
        "time": time_str,
    }
    try:
        pool = await get_arq_pool()
        await pool.enqueue_job(
            "send_email_task",
            to=to_email,
            subject=f"Your {service_name} is confirmed — {date_str}",
            html_body=email_service.render("appointment_confirmation.html", **ctx),
            text_body=(
                f"Hi {ctx['contact_name']}, your {service_name} appointment with {org_name} "
                f"is confirmed for {date_str} at {time_str}. We'll send a reminder beforehand. "
                f"Need to change it? Just reply to this email or give us a call."
            ),
            email_type="appointment_confirmation",
        )
    except Exception:  # noqa: BLE001 — a confirmation email must never break a booking
        logger.warning("confirmation_email_enqueue_failed", org_id=str(org_id))


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

        # Immediate booking-confirmation email to the customer (queued to the
        # worker — never blocks the reply). Followed later by the 24h + 1h
        # reminder emails from the reminder cron.
        customer_email = fsm.collected_data.get("customer_email") or (contact.email if contact else None)
        if customer_email:
            await _enqueue_confirmation_email(
                db, org_id, customer_email, contact.name if contact else None, service_name, start
            )
    finally:
        await slot_manager.release_slot(org_id, start, contact_id)

    return (
        f"You're all set! I've booked your {service_name} for {start.strftime('%A, %B %d')} at "
        f"{_format_time(start)}. We look forward to seeing you!"
    )
