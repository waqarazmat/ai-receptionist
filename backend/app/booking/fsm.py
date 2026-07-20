import json
import re
from dataclasses import dataclass, field
from enum import Enum

from app.db.redis import redis_client

BOOKING_STATE_TTL_SECONDS = 1800  # abandoned mid-flow bookings clear themselves after 30 min idle


class BookingState(str, Enum):
    IDLE = "idle"
    COLLECTING_SERVICE = "collecting_service"
    COLLECTING_TIME = "collecting_time"
    COLLECTING_CONTACT_INFO = "collecting_contact_info"
    CONFIRMING = "confirming"
    BOOKED = "booked"
    CANCELLED = "cancelled"


_AFFIRMATIVE_RE = re.compile(r"\b(yes|yeah|yep|sure|confirm|sounds good|correct|book it|that works)\b", re.IGNORECASE)
_NEGATIVE_RE = re.compile(r"\b(no|nope|not that|different|change)\b", re.IGNORECASE)


def _redis_key(conversation_id: str) -> str:
    return f"booking_state:{conversation_id}"


@dataclass
class TransitionResult:
    new_state: BookingState
    response_text: str
    requires_input: bool


@dataclass
class BookingFSM:
    """Pure state-transition logic. Free-text interpretation of service/date/
    time (which needs LLM/DB access) happens upstream in booking_service,
    which populates `collected_data` before calling `transition` — this class
    only decides, given what's already collected, what state comes next and
    what to ask for. The exception is CONFIRMING, where a simple yes/no
    keyword match on `user_input` is enough and doesn't need an LLM call.
    """

    conversation_id: str
    current_state: BookingState = BookingState.IDLE
    collected_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "conversation_id": self.conversation_id,
            "current_state": self.current_state.value,
            "collected_data": self.collected_data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BookingFSM":
        return cls(
            conversation_id=data["conversation_id"],
            current_state=BookingState(data.get("current_state", BookingState.IDLE.value)),
            collected_data=data.get("collected_data") or {},
        )

    @classmethod
    async def load(cls, conversation_id: str) -> "BookingFSM":
        raw = await redis_client.get(_redis_key(conversation_id))
        if raw:
            return cls.from_dict(json.loads(raw))
        return cls(conversation_id=conversation_id)

    async def save(self) -> None:
        await redis_client.set(_redis_key(self.conversation_id), json.dumps(self.to_dict()), ex=BOOKING_STATE_TTL_SECONDS)

    async def clear(self) -> None:
        await redis_client.delete(_redis_key(self.conversation_id))

    def transition(self, intent: str, user_input: str) -> dict:
        handler = getattr(self, f"_handle_{self.current_state.value}")
        result = handler(intent, user_input)
        self.current_state = result.new_state
        return {
            "new_state": result.new_state.value,
            "response_text": result.response_text,
            "requires_input": result.requires_input,
        }

    def _handle_idle(self, intent: str, user_input: str) -> TransitionResult:
        return TransitionResult(
            BookingState.COLLECTING_SERVICE,
            "I'd be happy to help you book an appointment. What service are you looking for?",
            True,
        )

    def _handle_collecting_service(self, intent: str, user_input: str) -> TransitionResult:
        if not self.collected_data.get("service"):
            return TransitionResult(
                BookingState.COLLECTING_SERVICE,
                "Sorry, I didn't catch which service you'd like — could you tell me again?",
                True,
            )
        service = self.collected_data["service"]
        return TransitionResult(
            BookingState.COLLECTING_TIME,
            f"Great, {service}. What day and time works best for you?",
            True,
        )

    def _handle_collecting_time(self, intent: str, user_input: str) -> TransitionResult:
        if not self.collected_data.get("date") or not self.collected_data.get("time"):
            return TransitionResult(
                BookingState.COLLECTING_TIME,
                "What day and time works best for you?",
                True,
            )
        # Already have name+email from a prior pass through this flow (e.g.
        # the customer picked a different time after CONFIRMING said no) —
        # no need to ask again.
        if self.collected_data.get("customer_name") and self.collected_data.get("customer_email"):
            return self._confirmation_result()
        return TransitionResult(
            BookingState.COLLECTING_CONTACT_INFO,
            "Could I get your name and email address to confirm the booking?",
            True,
        )

    def _handle_collecting_contact_info(self, intent: str, user_input: str) -> TransitionResult:
        name = self.collected_data.get("customer_name")
        email = self.collected_data.get("customer_email")
        if name and email:
            return self._confirmation_result()
        if not name and not email:
            return TransitionResult(
                BookingState.COLLECTING_CONTACT_INFO,
                "Sorry, I didn't catch that — could I get your name and email address to confirm the booking?",
                True,
            )
        if not name:
            return TransitionResult(
                BookingState.COLLECTING_CONTACT_INFO,
                "Thanks! And what name should I put the booking under?",
                True,
            )
        return TransitionResult(
            BookingState.COLLECTING_CONTACT_INFO,
            "Thanks! And what's the best email address for the confirmation?",
            True,
        )

    def _confirmation_result(self) -> TransitionResult:
        service = self.collected_data.get("service", "your appointment")
        name = self.collected_data.get("customer_name", "")
        email = self.collected_data.get("customer_email", "")
        return TransitionResult(
            BookingState.CONFIRMING,
            f"Just to confirm — {service} on {self.collected_data.get('date')} at "
            f"{self.collected_data.get('time')} for {name} ({email}). Should I go ahead and book it?",
            True,
        )

    def _handle_confirming(self, intent: str, user_input: str) -> TransitionResult:
        text = user_input or ""
        if _AFFIRMATIVE_RE.search(text):
            return TransitionResult(BookingState.BOOKED, "", False)
        if _NEGATIVE_RE.search(text):
            return TransitionResult(
                BookingState.COLLECTING_TIME,
                "No problem — what day and time would work better?",
                True,
            )
        return TransitionResult(
            BookingState.CONFIRMING,
            "Sorry, should I go ahead and book that? (yes/no)",
            True,
        )

    def _handle_booked(self, intent: str, user_input: str) -> TransitionResult:
        return TransitionResult(BookingState.BOOKED, "", False)

    def _handle_cancelled(self, intent: str, user_input: str) -> TransitionResult:
        return TransitionResult(BookingState.IDLE, "", False)
