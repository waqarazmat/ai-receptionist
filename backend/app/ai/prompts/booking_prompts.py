def get_booking_extraction_prompt(service_names: list[str], today: str, org_timezone: str) -> str:
    """`today` must already be resolved in the org's local timezone (not UTC
    or the server's local date) — see booking_service._extract_booking_fields."""
    return f"""You extract appointment-booking details from a customer's latest chat message.

Available services: {", ".join(service_names) or "(none configured)"}
Today's date: {today}
The business's timezone is {org_timezone}. All dates and times — including "today" above and \
anything the customer says (e.g. "9am", "tomorrow at 2pm") — are in this timezone, not UTC. \
Extract the time exactly as the customer means it in {org_timezone}; do not convert it to UTC \
or any other timezone.

Respond with ONLY this JSON, no other text:
{{"service": "<one of the available services, exactly as listed, or null>", "date": "<YYYY-MM-DD, or null>", "time": "<HH:MM in 24h format, or null>"}}

Set "date" and "time" INDEPENDENTLY — do not require both to be present:
- Set "date" whenever the customer names a resolvable day, EVEN WITHOUT a time \
("Friday", "next Tuesday", "the 15th", "tomorrow", "this weekend" -> pick the nearest matching \
day). Resolve relative days using today's date above.
- Set "time" whenever the customer gives a clock time, EVEN WITHOUT a day ("2pm", "at ten", \
"half past nine").
- A day alone -> set "date", leave "time" null. A time alone -> set "time", leave "date" null. \
Only leave a field null when that specific piece (the day, or the clock time) is genuinely absent \
from the message.

Only set "service" if it clearly matches one of the available services listed above \
(case-insensitive match is fine, but the value you return must be the exact listed name).
"""


def get_contact_info_extraction_prompt() -> str:
    return """You extract the customer's name and email address from their latest message \
(which may be a CHAT message or a VOICE call transcript), for booking confirmation purposes.

Respond with ONLY this JSON, no other text:
{"name": "<the customer's full name, or null>", "email": "<a valid email address, or null>"}

The message may be a voice transcript where the caller dictated their email out loud. \
Reconstruct a valid email address from spoken form:
- "at" -> "@";  "dot" or "period" -> "."
- Spelled-out letters ("j-o-h-n", "J O H N", "jay oh en") -> join into the intended letters ("john")
- Join tokens that clearly belong to one address and remove the spaces dictation adds \
(e.g. "john dot smith at gmail dot com" -> "john.smith@gmail.com"; \
"m a r y at outlook dot com" -> "mary@outlook.com")
- Lowercase the whole email and strip any surrounding punctuation
- Spoken domains map to the obvious host ("gmail dot com" -> "gmail.com", also hotmail, outlook, \
yahoo, icloud, proton, etc.)

Only set a field if the customer's message actually contains it — don't guess, invent, or infer \
one from context. If you cannot form a plausible, valid-looking email, set "email" to null rather \
than guessing.
"""
