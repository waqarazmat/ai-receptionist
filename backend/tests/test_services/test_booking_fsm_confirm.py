"""Regression tests for booking-confirmation robustness.

Two bugs on voice bookings this guards against:
  1. Common confirmations ("okay", "perfect", "go ahead") were not recognized as
     "yes", so the FSM looped "should I book that? (yes/no)".
  2. A caller correcting an ASR mis-hear of their name ("my name is USAMA") was
     treated as neither yes nor no and looped the same prompt.

These tests cover the FSM-level yes/no handling. The name/email correction
re-read-back lives in booking_service.process_booking_intent (it needs DB + LLM),
and is exercised there.
"""

from app.booking.fsm import BookingFSM, BookingState


def _fsm_in_confirming(**collected):
    fsm = BookingFSM(conversation_id="c1", current_state=BookingState.CONFIRMING)
    fsm.collected_data = {
        "service": "consultation", "date": "2026-08-12", "time": "09:00",
        "customer_name": "Osama", "customer_email": "o@example.com", **collected,
    }
    return fsm


class TestConfirmAffirmatives:
    def _books(self, phrase: str) -> bool:
        fsm = _fsm_in_confirming()
        result = fsm.transition("booking_request", phrase)
        return result["new_state"] == BookingState.BOOKED.value

    def test_plain_yes_books(self):
        assert self._books("yes") is True

    def test_okay_books(self):
        assert self._books("okay") is True

    def test_go_ahead_books(self):
        assert self._books("ok go ahead") is True

    def test_perfect_books(self):
        assert self._books("perfect, thanks") is True

    def test_thats_right_books(self):
        assert self._books("yeah that's right") is True


class TestConfirmNegativesAndUnclear:
    def test_no_returns_to_time_selection(self):
        fsm = _fsm_in_confirming()
        result = fsm.transition("booking_request", "no")
        assert result["new_state"] == BookingState.COLLECTING_TIME.value

    def test_change_returns_to_time_selection(self):
        fsm = _fsm_in_confirming()
        result = fsm.transition("booking_request", "change the time please")
        assert result["new_state"] == BookingState.COLLECTING_TIME.value

    def test_unclear_reprompts_and_stays_confirming(self):
        fsm = _fsm_in_confirming()
        result = fsm.transition("booking_request", "hmm let me think")
        assert result["new_state"] == BookingState.CONFIRMING.value

    def test_yes_with_change_is_not_a_pure_yes(self):
        """'yes but change my name' must NOT book — the negative word means the
        caller wants a correction, which process_booking_intent handles upstream."""
        from app.booking.fsm import _AFFIRMATIVE_RE, _NEGATIVE_RE
        text = "yes but change my name"
        pure_yes = bool(_AFFIRMATIVE_RE.search(text)) and not bool(_NEGATIVE_RE.search(text))
        assert pure_yes is False
