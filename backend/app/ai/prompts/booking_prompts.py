def get_booking_extraction_prompt(service_names: list[str], today: str, org_timezone: str) -> str:
    """`today` must already be resolved in the org's local timezone (not UTC
    or the server's local date) — see booking_service._extract_booking_fields."""
    return f"""You extract appointment-booking details from a customer's latest message.

You may be shown the recent conversation for context. Extract the booking details from \
the customer's LATEST message, but use the earlier turns to COMPLETE a detail the latest \
message refers back to — voice callers often split one request across turns or pause \
mid-sentence:
- earlier "Monday at ten thirty" + latest "AM" -> date = that Monday, time = 10:30.
- earlier "ten thirty PM" + latest "no, AM" (a correction) -> time = 10:30 (morning).
- latest "the seventeenth" after you offered slots -> date = the 17th.
Never carry over a detail the customer has clearly moved on from; only use context to \
finish a fragment or apply a correction to something they just said.

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

You may be shown the recent conversation for context. Extract from the customer's LATEST \
message, using earlier turns only to complete a value they are continuing or correcting.

Respond with ONLY this JSON, no other text:
{"name": "<the customer's full name, or null>", "email": "<a valid email address, or null>"}

CRITICAL — the NAME and the EMAIL are separate. NEVER build, extend, or infer the name \
from the email address, even when the email obviously contains a name. The name is ONLY \
the words the customer explicitly gives as their name; the local part of the email is NOT \
part of the name.
- "My name is Asif, my email is asifalian@gmail.com" -> name is "Asif" (NOT "Asif Alian" — \
do not pull "alian" out of the email).
- "I'm John, john.smith@x.com" -> name is "John" (NOT "John Smith").
- Only include a surname in the name if the customer actually SPOKE it as their name.
When the customer corrects their name ("no, my name is only Asif"), take the corrected \
name exactly and do not re-add anything from the email.

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
