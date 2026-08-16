import asyncio
import re
import uuid
from datetime import date, datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm_router import (
    LLMProviderError,
    NoLLMProviderConfiguredError,
    call_llm_with_fallback,
    get_org_llm_clients,
    parse_json_response,
)
from app.ai.prompts.booking_prompts import get_booking_extraction_prompt, get_contact_info_extraction_prompt
from app.config import settings
from app.booking import slot_manager
from app.booking.fsm import _AFFIRMATIVE_RE, _NEGATIVE_RE, BookingFSM, BookingState
from app.booking.google_calendar import GoogleCalendarClient, GoogleCalendarError
from app.booking.slot_manager import resolve_org_timezone
from app.db.engine import async_session_maker
from app.models.appointment import Appointment
from app.models.contact import Contact
from app.models.enums import AppointmentStatus
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
# Only ever offer the nearest few openings — a caller (especially on voice)
# can't hold six times in their head. One per open day gives a spread of three.
MAX_SUGGESTED_SLOTS = 3

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
# At CONFIRMING, a request to hear/verify the details again ("read back the
# email", "confirm my email", "repeat that", "spell my name") — as opposed to a
# yes/no or a correction. Checked BEFORE the yes/no match so "confirm my email"
# re-reads the details instead of booking, while a bare "confirm"/"confirm it"
# still books (the object list here is name/email/details, not "booking").
_REVIEW_REQUEST_RE = re.compile(
    r"\b(?:"
    r"read\s+(?:it|that|the|my|back)"
    r"|repeat|say\s+(?:it|that)\s+again"
    r"|spell\s+(?:it|that|my|the)"
    r"|hear\s+(?:it|that|my|the)"
    r"|(?:confirm|check|verify|review|go\s+over)\s+(?:my\s+|the\s+)?(?:e-?mail|name|details|spelling|address|info(?:rmation)?)"
    r"|what(?:'?s| is)\s+my\s+(?:e-?mail|name)"
    r")\b",
    re.IGNORECASE,
)

# At CONFIRMING, a message that supplies/corrects a name or email ("my name is
# Waqar", "it's spelled W-A-Q-A-R", "the email is …"). Used so an affirmative
# word buried in a correction ("the date is CORRECT, but my name is …") is NOT
# mistaken for a full booking confirmation — that booked prematurely with the
# wrong details and dropped the session.
_CONTACT_CORRECTION_RE = re.compile(
    r"\b(?:(?:my|the|your)\s+(?:name|e-?mail)|(?:name|e-?mail)\s+is|"
    r"spell(?:ed|ing)?|(?:it'?s|that'?s)\s+spelled)\b",
    re.IGNORECASE,
)


def _looks_like_contact_correction(text: str) -> bool:
    return bool(_CONTACT_CORRECTION_RE.search(text or ""))


# During the service/time-collection steps, a bare answer ("cleaning", "sun 1pm")
# classifies as faq/off_topic, NOT a booking intent — so to keep the booking alive
# we route any non-question reply back into the FSM and only let a genuine question
# break out to be answered normally (see should_route_to_booking). These detect the
# "genuine question" vs "scheduling answer" cases.
_QUESTION_RE = re.compile(
    r"\?\s*$|^\s*(what|where|when|how|why|which|who|whose|do|does|did|can|could|"
    r"would|will|is|are|am|may|should)\b",
    re.IGNORECASE,
)
_SCHEDULING_RE = re.compile(
    r"\b(mon|tue|wed|thu|fri|sat|sun)\w*\b|"
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\b|"
    r"\b(today|tomorrow|tonight|morning|afternoon|evening|noon|midday|midnight)\b|"
    r"\b(next|this)\s+(week|month|mon|tue|wed|thu|fri|sat|sun)\w*\b|"
    r"\b\d{1,2}\s*(:\d{2})?\s*(am|pm|a\.m\.|p\.m\.|o'?clock)\b|"
    r"\b\d{1,2}(st|nd|rd|th)\b",
    re.IGNORECASE,
)

# Availability / slot / appointment language — a customer asking to book or
# check open times, even when phrased as a question ("do you have any open
# slots?", "are you open Friday at three PM?"). These often classify as faq and
# then get DEFLECTED ("I can't check availability, let me connect you with the
# team") instead of shown real open times — so we route them into the booking
# flow, which lists actual openings.
_BOOKING_INQUIRY_RE = re.compile(
    r"\b(book|booking|appointment|schedul|reschedul|reserve|"
    r"availabilit(?:y|ies)|(?:open|free|available)\s+slots?|slots?\s+(?:available|open|free)|"
    r"any\s+(?:open(?:ing)?s?|slots?|times?)|make\s+an?\s+appointment|"
    r"come\s+in\s+for|set\s+up\s+(?:an?\s+)?(?:appointment|time|visit))\b",
    re.IGNORECASE,
)
# A spoken/typed clock time, digit ("3pm", "3:00") or word ("three PM").
_TIME_MENTION_RE = re.compile(
    r"\b(\d{1,2}(:\d{2})?\s*(am|pm|a\.m\.|p\.m\.|o'?clock)|"
    r"(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*(am|pm|o'?clock)|"
    r"noon|midday|midnight)\b",
    re.IGNORECASE,
)


def _looks_like_booking_inquiry(text: str) -> bool:
    """True when a not-yet-booking message is really an availability/booking
    request that should open the booking flow rather than be answered as FAQ."""
    if _BOOKING_INQUIRY_RE.search(text or ""):
        return True
    # "are you open Friday at three PM?" — asking whether a SPECIFIC time is open
    # is an availability check (booking), not an opening-hours question. A plain
    # "are you open on Sundays?" (a day, no clock time) is left to FAQ/RAG.
    if re.search(r"\bopen\b", text or "", re.IGNORECASE) and _TIME_MENTION_RE.search(text or ""):
        return True
    return False


# --- Deterministic day resolution -------------------------------------------
# The fast-tier extraction LLM cannot reliably compute weekday->date arithmetic
# (it resolved "sunday" to a Thursday date, so the closed-day check never fired
# and it booked the wrong day). When the customer names a day OUTRIGHT — a
# weekday, "today", or "tomorrow" — we compute the calendar date ourselves and
# trust it over the model's guess.
_WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tues": 1, "tue": 1,
    "wednesday": 2, "weds": 2, "wed": 2,
    "thursday": 3, "thurs": 3, "thur": 3, "thu": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}
_WEEKDAY_RE = re.compile(
    r"\b(next\s+|this\s+(?:coming\s+)?)?"
    r"(monday|mon|tuesday|tues|tue|wednesday|weds|wed|thursday|thurs|thur|thu|friday|fri|saturday|sat|sunday|sun)\b",
    re.IGNORECASE,
)
_TODAY_RE = re.compile(r"\btoday\b", re.IGNORECASE)
_TOMORROW_RE = re.compile(r"\btomorrow\b", re.IGNORECASE)


def _resolve_explicit_day(text: str, today: date) -> date | None:
    """Resolve a day the customer named plainly ("monday", "next fri", "today",
    "tomorrow") to a real date, in the org's timezone. Returns None when the
    message names no such day (e.g. "the 15th" — left to the LLM, which handles
    explicit day-of-month better than weekday arithmetic)."""
    if not text:
        return None
    if _TOMORROW_RE.search(text):
        return today + timedelta(days=1)
    m = _WEEKDAY_RE.search(text)
    if m:
        target = _WEEKDAYS[m.group(2).lower()]
        delta = (target - today.weekday()) % 7  # 0..6; today counts as "this <day>"
        if m.group(1) and m.group(1).lower().startswith("next") and delta == 0:
            delta = 7  # "next monday" said on a Monday -> the following week
        return today + timedelta(days=delta)
    if _TODAY_RE.search(text):
        return today
    return None


# A caller picks from the slots we just read out either by position ("the first
# one", "the second") or by the time we spoke ("the 10:30"). The fast-tier LLM
# often can't turn "the first one" into a date, so we map the reference back to
# the exact slot we offered, deterministically.
_ORDINAL_INDEX = {
    "first": 0, "1st": 0,
    "second": 1, "2nd": 1,
    "third": 2, "3rd": 2,
    "fourth": 3, "4th": 3,
    "fifth": 4, "5th": 4,
}
_ORDINAL_RE = re.compile(r"\b(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th)\b", re.IGNORECASE)
# A spoken clock time: "10:30" (colon form) or "9 am"/"3pm" (hour + am/pm). Bare
# numbers with neither a colon nor am/pm are ignored, so "17 aug" isn't read as a
# time. Matched against the KNOWN offered slots, which keeps it unambiguous.
_CLOCK_COLON_RE = re.compile(r"\b(\d{1,2}):(\d{2})\b")
_CLOCK_AMPM_RE = re.compile(r"\b(\d{1,2})\s*(a\.?m\.?|p\.?m\.?)\b", re.IGNORECASE)


def _slot_matches_spoken_time(slot: datetime, text: str) -> bool:
    for m in _CLOCK_COLON_RE.finditer(text):
        h, mn = int(m.group(1)), int(m.group(2))
        if mn == slot.minute and slot.hour % 12 == h % 12:  # 1:30 matches 13:30
            return True
    for m in _CLOCK_AMPM_RE.finditer(text):
        h = int(m.group(1)) % 12 + (12 if m.group(2).lower().startswith("p") else 0)
        if slot.hour == h:
            return True
    return False


def _resolve_offered_slot(text: str, offered_iso: list[str], extracted_time: str | None) -> datetime | None:
    """Map a reply that refers to one of the slots we just offered back to that
    exact slot, or None if it references none. `offered_iso` are the slot start
    times (org-local, ISO) we last presented; `extracted_time` is the HH:MM the
    LLM parsed from this reply, if any."""
    slots: list[datetime] = []
    for iso in offered_iso or []:
        try:
            slots.append(datetime.fromisoformat(iso))
        except (ValueError, TypeError):
            continue
    if not slots:
        return None
    lowered = (text or "").lower()
    if re.search(r"\blast\b", lowered):
        return slots[-1]
    m = _ORDINAL_RE.search(lowered)
    if m:
        idx = _ORDINAL_INDEX.get(m.group(1).lower())
        if idx is not None and idx < len(slots):
            return slots[idx]
    if extracted_time:
        for s in slots:
            if s.strftime("%H:%M") == extracted_time:
                return s
    for s in slots:
        if _slot_matches_spoken_time(s, text or ""):
            return s
    return None


# --- Cancel / reschedule of an ALREADY-booked appointment -------------------
# Distinct from _CANCEL_RE (which aborts an in-progress booking attempt): these
# act on an appointment the customer previously committed. Both require an
# appointment-ish object so a bare "cancel"/"change" mid-flow can't trigger them.
_CANCEL_APPT_RE = re.compile(
    r"\b(cancel|delete|remove|drop|call\s+off)\b.{0,30}\b(appointment|booking|reservation|slot|visit)\b"
    r"|\bcancel\s+(?:my|the|it)\b",
    re.IGNORECASE,
)
_RESCHEDULE_APPT_RE = re.compile(
    r"\breschedul\w*|\bre-schedul\w*"
    r"|\b(change|move|shift|switch|push\s+back|bring\s+forward)\b.{0,30}\b(appointment|booking|time|slot|visit)\b",
    re.IGNORECASE,
)


def _wants_cancel_appointment(text: str) -> bool:
    return bool(_CANCEL_APPT_RE.search(text or ""))


def _wants_reschedule_appointment(text: str) -> bool:
    return bool(_RESCHEDULE_APPT_RE.search(text or ""))


async def _find_upcoming_appointment(
    db: AsyncSession, org_id: uuid.UUID, contact_id: uuid.UUID
) -> Appointment | None:
    """The customer's next confirmed, still-upcoming appointment (the one a
    'cancel'/'reschedule' request refers to), or None if they have none."""
    stmt = (
        select(Appointment)
        .where(
            Appointment.org_id == org_id,
            Appointment.contact_id == contact_id,
            Appointment.status == AppointmentStatus.confirmed,
            Appointment.start_time >= datetime.now(timezone.utc),
        )
        .order_by(Appointment.start_time)
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


def _looks_like_question(text: str) -> bool:
    return bool(_QUESTION_RE.search(text or ""))


def _looks_like_scheduling_answer(text: str) -> bool:
    return bool(_SCHEDULING_RE.search(text or ""))


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
        clients = await get_org_llm_clients(db, org_id, model_tier="fast")
        raw = await call_llm_with_fallback(
            clients,
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
        clients = await get_org_llm_clients(db, org_id, model_tier="fast")
        raw = await call_llm_with_fallback(
            clients,
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


def should_route_to_booking(
    booking_active: bool, booking_state: BookingState, intent: str, message_text: str = ""
) -> bool:
    """Whether a customer message should be handled by the booking FSM (vs
    answered normally by RAG). Escalation is decided by the caller before this.

    - A booking-shaped intent always routes in (starts or continues a booking).
    - While a booking is mid-flow, the sticky states (collecting name/email, or
      confirming) route in even for off_topic/faq-looking messages, because those
      answers ("John", "john@x.com", "yes") classify that way.
    - In the earlier service/time-collection states, a bare answer ("cleaning",
      "sun 1pm") also classifies as faq/off_topic — so we keep the booking alive
      for any reply that looks like a scheduling answer OR simply isn't a question,
      and let ONLY a genuine question ("do you take insurance?") break out to be
      answered normally, so the customer is neither trapped re-hearing "what time?"
      nor silently dropped out of the booking when they answer it.
    """
    if not booking_active:
        # No booking in progress yet — a booking-shaped intent starts one, and so
        # does an availability/slot/appointment inquiry that the classifier may
        # have tagged as faq (otherwise "do you have open slots?" gets deflected
        # instead of shown real open times).
        return intent in _BOOKING_INTENTS or _looks_like_booking_inquiry(message_text)

    # A booking is mid-flow.
    if booking_state in STICKY_BOOKING_STATES:
        # Collecting name/email or confirming: the answers ("John", "yes") look
        # like faq/off_topic, so stay in the FSM unconditionally.
        return True

    if booking_state in (BookingState.COLLECTING_SERVICE, BookingState.COLLECTING_TIME):
        # A concrete scheduling answer ("sun 1pm", "tomorrow") always stays in.
        if _looks_like_scheduling_answer(message_text):
            return True
        # A genuine question breaks out to be answered — EVEN if the classifier
        # tagged it a booking intent (e.g. "can I book for my whole family on the
        # same day?" often classifies as booking_info). Otherwise the customer is
        # trapped re-hearing "what day and time?" instead of getting an answer.
        # The booking session stays alive (Redis), so they resume by naming a time.
        if _looks_like_question(message_text):
            return False
        # Not a question and not obviously a time — a bare service answer
        # ("cleaning") or a booking continuation: keep the booking going.
        return True

    # Any other active state: continue only on a booking-shaped intent.
    return intent in _BOOKING_INTENTS


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

    # Reuse the customer's known identity across bookings in this conversation:
    # once they've given a name/email (persisted on the Contact), a SECOND
    # booking must NOT ask for them again — "use what I gave earlier" should just
    # work, and the flow skips straight to confirmation.
    contact = await db.get(Contact, contact_id)
    if contact is not None:
        if not fsm.collected_data.get("customer_name") and contact.name:
            fsm.collected_data["customer_name"] = contact.name
        if not fsm.collected_data.get("customer_email") and _is_valid_email(contact.email):
            fsm.collected_data["customer_email"] = contact.email

    # Cancel / reschedule of an appointment the customer ALREADY booked. Only
    # entertained when we're not deep in collecting a new booking's details, so a
    # stray "change"/"move" inside the flow can't hijack it.
    if previous_state in (BookingState.IDLE, BookingState.COLLECTING_SERVICE, BookingState.COLLECTING_TIME):
        if _wants_cancel_appointment(user_input):
            appt = await _find_upcoming_appointment(db, org_id, contact_id)
            if appt is not None:
                when = appt.start_time.astimezone(org_tz)
                try:
                    await appointment_service.cancel_appointment(db, org_id, appt.id)
                except Exception as exc:  # noqa: BLE001 — never surface a crash to the customer
                    logger.warning("appointment_cancel_failed", org_id=str(org_id), error=str(exc))
                    return "Sorry, I ran into a problem cancelling that — please call us and we'll sort it out."
                await fsm.clear()
                return (
                    f"Done — I've cancelled your {appt.service_name} on "
                    f"{when.strftime('%A, %B %d')} at {_format_time(when)}. "
                    "Let me know if you'd like to book a new time."
                )
            return (
                "I couldn't find an upcoming appointment under your details to cancel. "
                "Would you like to book a new one?"
            )

        if _wants_reschedule_appointment(user_input):
            appt = await _find_upcoming_appointment(db, org_id, contact_id)
            if appt is not None:
                when = appt.start_time.astimezone(org_tz)
                # Start a fresh time-collection, remembering which appointment to
                # replace (cancelled in _finalize_booking once the new one commits)
                # and reusing the service + known name/email so we only re-ask time.
                fsm.collected_data = {"service": appt.service_name, "reschedule_of": str(appt.id)}
                if contact is not None and contact.name:
                    fsm.collected_data["customer_name"] = contact.name
                if contact is not None and _is_valid_email(contact.email):
                    fsm.collected_data["customer_email"] = contact.email
                fsm.current_state = BookingState.COLLECTING_TIME
                await fsm.save()
                return (
                    f"Sure — your {appt.service_name} is currently on "
                    f"{when.strftime('%A, %B %d')} at {_format_time(when)}. "
                    "What day and time would you like to move it to?"
                )
            # No existing appointment — fall through and treat it as a new booking.

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

        # Override the LLM's date whenever the customer named a day outright — the
        # fast-tier model gets weekday->date arithmetic wrong (booked "monday" as
        # a Friday, and never caught that "sunday" is a closed day). This resolves
        # it deterministically in the org's timezone.
        explicit_day = _resolve_explicit_day(user_input, datetime.now(org_tz).date())
        if explicit_day is not None:
            fsm.collected_data["date"] = explicit_day.isoformat()

        # The caller may be picking a slot we just read out ("the first one", "the
        # 10:30") — resolve that to the exact offered slot when we don't already
        # hold a full date+time, so their selection isn't lost and re-asked.
        if not (fsm.collected_data.get("date") and fsm.collected_data.get("time")):
            picked = _resolve_offered_slot(
                user_input, fsm.collected_data.get("offered_slots") or [], fsm.collected_data.get("time")
            )
            if picked is not None:
                fsm.collected_data["date"] = picked.date().isoformat()
                fsm.collected_data["time"] = picked.strftime("%H:%M")

        # If the requested day is one the practice is CLOSED (e.g. a weekend),
        # say so immediately and ask for another day — don't accept the day and
        # then reject it after they also give a time. Drop the closed date.
        req_date_str = fsm.collected_data.get("date")
        if req_date_str:
            req_dt = _parse_slot_datetime(req_date_str, fsm.collected_data.get("time") or "12:00", org_tz)
            if req_dt is not None and not slot_manager.is_open_on(org, req_dt.date()):
                fsm.collected_data.pop("date", None)
                fsm.collected_data.pop("time", None)
                await fsm.save()
                day_name = req_dt.strftime("%A")
                open_phrase = slot_manager.open_days_phrase(org)
                if open_phrase:
                    return f"Sorry, we're closed on {day_name}s — we're open {open_phrase}. Which day would suit you?"
                return f"Sorry, we're closed on {day_name}s. Which other day would suit you?"

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
                # Show only a few nearest alternatives, not the whole list again.
                alternatives = (await _next_available_slots(db, org_id, duration, org_tz))[:MAX_SUGGESTED_SLOTS]
                # Remember what we offered so "the first one"/"the 10:30" resolves.
                fsm.collected_data["offered_slots"] = [s.isoformat() for s in alternatives]
                await fsm.save()
                if alternatives:
                    return (
                        f"Sorry, that time isn't available. The nearest openings are "
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

    elif previous_state == BookingState.CONFIRMING:
        # During confirmation, callers frequently CORRECT an ASR mis-hear of
        # their name/email ("no, my name is USAMA") instead of giving a clean
        # yes/no — especially on voice, where the read-back exists precisely so
        # they can catch a mis-hear. A plain yes (with no correction words) is
        # left to the FSM to book; anything else, we try to extract a name/email
        # correction and, if one is found, apply it and RE-READ-BACK rather than
        # looping "Sorry, should I go ahead and book that? (yes/no)".
        text = user_input or ""
        # The caller wants to hear/verify the details again ("read back the
        # email", "confirm my email", "repeat that") — re-read them back instead
        # of booking or looping yes/no. Checked FIRST so "confirm my email" is a
        # review, not a booking confirmation (that bug booked with a wrong email).
        if _REVIEW_REQUEST_RE.search(text):
            await fsm.save()
            if channel == "voice":
                return _build_voice_confirmation(fsm.collected_data, org_tz)
            return fsm._confirmation_result().response_text

        # A confirmation must be a CLEAN yes — not a negative, and not a message
        # that's actually supplying/correcting the name or email (where an
        # affirmative like "correct" refers to the date, not "book it").
        pure_yes = (
            bool(_AFFIRMATIVE_RE.search(text))
            and not bool(_NEGATIVE_RE.search(text))
            and not _looks_like_contact_correction(text)
        )
        if not pure_yes:
            extracted = await _extract_contact_info(db, org_id, user_input)
            name = (extracted.get("name") or "").strip() or None
            email = (extracted.get("email") or "").strip() or None
            valid_email = email if _is_valid_email(email) else None

            changed = False
            if name and name != fsm.collected_data.get("customer_name"):
                fsm.collected_data["customer_name"] = name
                changed = True
            if valid_email and valid_email != fsm.collected_data.get("customer_email"):
                fsm.collected_data["customer_email"] = valid_email
                changed = True

            if changed:
                contact = await db.get(Contact, contact_id)
                if contact is not None:
                    if name:
                        contact.name = name
                    if valid_email:
                        contact.email = valid_email
                    await db.commit()
                await fsm.save()  # stay in CONFIRMING with the corrected details
                logger.info(
                    "booking_confirm_correction",
                    conversation_id=str(conversation_id),
                    updated_name=bool(name),
                    updated_email=bool(valid_email),
                )
                if channel == "voice":
                    return _build_voice_confirmation(fsm.collected_data, org_tz)
                return fsm._confirmation_result().response_text

    result = fsm.transition(intent, user_input)
    new_state = BookingState(result["new_state"])

    if new_state == BookingState.BOOKED:
        success, response_text = await _finalize_booking(
            db, org_id, conversation_id, contact_id, fsm, service_by_name, org_tz, org_timezone_name
        )
        if success:
            await fsm.clear()
        else:
            # The booking couldn't complete (its time went missing or the slot was
            # just taken). Do NOT drop the session — that made voice callers hear
            # "how can I help you?" and lose their name/slot mid-call. Keep the
            # collected identity and step back to time selection so they can pick
            # another slot without being re-asked their name/email.
            fsm.current_state = BookingState.COLLECTING_TIME
            fsm.collected_data.pop("date", None)
            fsm.collected_data.pop("time", None)
            await fsm.save()
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
    elif new_state == BookingState.COLLECTING_TIME and not (
        fsm.collected_data.get("date") or fsm.collected_data.get("time")
    ):
        # Offer the open-times list when the caller is still at square one — no day
        # AND no time captured yet (first entry, or a reply that gave neither).
        # Once they've given a partial (e.g. just a day), the FSM asks a targeted
        # follow-up instead, so we don't re-dump every slot each turn (the
        # "consultation slots repeated over and over" complaint).
        service = service_by_name.get(fsm.collected_data.get("service", ""), {})
        duration = service.get("duration_minutes", DEFAULT_SERVICE_DURATION_MINUTES)
        slots = await _next_available_slots(db, org_id, duration, org_tz)
        if slots:
            # Remember what we offered so a "the first one"/"the 10:30" reply next
            # turn resolves to the exact slot instead of being lost.
            fsm.collected_data["offered_slots"] = [s.isoformat() for s in slots]
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


async def _create_calendar_event(
    db: AsyncSession,
    org_id: uuid.UUID,
    org_timezone_name: str,
    service_name: str,
    contact_name: str | None,
    contact_email: str | None,
    start,
    end,
) -> str | None:
    """Build the org's calendar client and create the event — together, so the
    caller can bound the whole thing (build + create) under a single timeout.
    Raises GoogleCalendarError on config/API failure."""
    client = await GoogleCalendarClient.for_org(db, org_id)
    return await client.create_event(
        summary=f"{service_name} — {contact_name or 'Customer'}",
        start=start,
        end=end,
        attendee_email=contact_email,
        time_zone=org_timezone_name,
    )


# Fire-and-forget booking side-effect tasks are tracked in a module set so the
# event loop keeps a strong reference to them until they finish (otherwise a
# background task can be garbage-collected mid-flight).
_booking_side_effect_tasks: set = set()


def _spawn_booking_side_effects(coro) -> None:
    task = asyncio.create_task(coro)
    _booking_side_effect_tasks.add(task)
    task.add_done_callback(_booking_side_effect_tasks.discard)


async def _run_booking_side_effects(
    org_id: uuid.UUID,
    appointment_id: uuid.UUID,
    service_name: str,
    start,
    end,
    org_timezone_name: str,
    contact_name: str | None,
    contact_email: str | None,
    customer_email: str | None,
) -> None:
    """Create the Google Calendar event and send the confirmation email AFTER the
    booking is already saved and confirmed to the customer — so neither can ever
    delay or hang the confirmation reply (the repeated "stuck on yes" freeze).

    Runs on its OWN DB session (the request's session is gone by now), bounds the
    calendar call with a timeout, and swallows every error: these are best-effort
    niceties; the actual booking is already committed."""
    # 1. Calendar event — bounded + best-effort. On success, backfill the id.
    try:
        async with async_session_maker() as db:
            event_id = await asyncio.wait_for(
                _create_calendar_event(
                    db, org_id, org_timezone_name, service_name, contact_name, contact_email, start, end
                ),
                timeout=settings.CALENDAR_EVENT_TIMEOUT_SECONDS,
            )
            if event_id:
                appt = await db.get(Appointment, appointment_id)
                if appt is not None:
                    appt.google_event_id = event_id
                    await db.commit()
    except (GoogleCalendarError, asyncio.TimeoutError) as exc:
        logger.warning("calendar_event_create_failed", org_id=str(org_id), error=str(exc))
    except Exception as exc:  # noqa: BLE001 — a background side effect must never crash
        logger.warning("booking_calendar_side_effect_failed", org_id=str(org_id), error=str(exc))

    # 2. Confirmation email — best-effort (already internally guarded), bounded too.
    if customer_email:
        try:
            async with async_session_maker() as db:
                await asyncio.wait_for(
                    _enqueue_confirmation_email(
                        db, org_id, customer_email, contact_name, service_name, start
                    ),
                    timeout=settings.CALENDAR_EVENT_TIMEOUT_SECONDS,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("confirmation_email_enqueue_failed", org_id=str(org_id), error=str(exc))


async def _finalize_booking(
    db: AsyncSession,
    org_id: uuid.UUID,
    conversation_id: uuid.UUID,
    contact_id: uuid.UUID,
    fsm: BookingFSM,
    service_by_name: dict,
    org_tz,
    org_timezone_name: str,
) -> tuple[bool, str]:
    """Returns (success, message). On failure the caller keeps the booking
    session alive (rather than dropping it) so the customer can pick another
    time without re-giving their name/email or losing the call's context."""
    service_name = fsm.collected_data.get("service")
    date_str = fsm.collected_data.get("date")
    time_str = fsm.collected_data.get("time")
    start = _parse_slot_datetime(date_str, time_str, org_tz) if date_str and time_str else None
    if not (service_name and start):
        return False, DETAILS_LOST_MESSAGE

    service = service_by_name.get(service_name, {})
    duration = service.get("duration_minutes", DEFAULT_SERVICE_DURATION_MINUTES)
    end = start + timedelta(minutes=duration)

    held = await slot_manager.hold_slot(org_id, start, contact_id)
    if not held:
        return False, "Sorry, that slot was just taken by someone else. Could you pick another time?"

    # Final guard against an overlapping appointment created between slot
    # validation and now (the Redis hold only covers this exact start time).
    if await slot_manager.has_conflicting_appointment(db, org_id, start, end):
        await slot_manager.release_slot(org_id, start, contact_id)
        return False, "Sorry, that slot was just taken by someone else. Could you pick another time?"

    try:
        contact = await db.get(Contact, contact_id)
        # Save the appointment NOW — this IS the booking. The Google Calendar
        # event id is backfilled later by the background task. Postgres stores
        # timestamptz as UTC regardless; converting explicitly just keeps what's
        # sent over the wire unambiguous.
        appointment = await appointment_service.create_appointment(
            db,
            org_id,
            contact_id,
            conversation_id,
            service_name,
            start.astimezone(timezone.utc),
            end.astimezone(timezone.utc),
            None,
        )
    finally:
        await slot_manager.release_slot(org_id, start, contact_id)

    # If this booking is a RESCHEDULE, cancel the ORIGINAL appointment now that
    # the replacement is safely committed (this also cancels its Calendar event).
    reschedule_of = fsm.collected_data.get("reschedule_of")
    if reschedule_of:
        try:
            await appointment_service.cancel_appointment(db, org_id, uuid.UUID(reschedule_of))
        except Exception as exc:  # noqa: BLE001 — the new booking already stands
            logger.warning("reschedule_cancel_old_failed", org_id=str(org_id), error=str(exc))

    # The slow external side effects — Google Calendar event + confirmation email
    # — run in the BACKGROUND so the confirmation is returned to the customer
    # IMMEDIATELY and can never hang waiting on Google or the email queue (the
    # cause of the repeated "stuck after yes" freeze). The booking itself is
    # already durably committed above.
    customer_email = fsm.collected_data.get("customer_email") or (contact.email if contact else None)
    _spawn_booking_side_effects(
        _run_booking_side_effects(
            org_id,
            appointment.id,
            service_name,
            start,
            end,
            org_timezone_name,
            contact.name if contact else None,
            contact.email if contact else None,
            customer_email,
        )
    )

    verb = "rescheduled" if reschedule_of else "booked"
    return True, (
        f"You're all set! I've {verb} your {service_name} for {start.strftime('%A, %B %d')} at "
        f"{_format_time(start)}. We look forward to seeing you!"
    )
