"""Tests for state-aware sticky-booking routing.

Regression cover for the "stuck in booking" bug: while collecting the service or
time, a genuine question / greeting must be answered normally (not re-looped
through the FSM), while the name/email and confirm steps stay sticky.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.booking.fsm import BookingFSM, BookingState
from app.services import booking_service
from app.services.booking_service import STICKY_BOOKING_STATES, should_route_to_booking


class TestBookingInquiryDetection:
    """Availability/slot/appointment questions (often mis-tagged as faq) must
    open the booking flow instead of being deflected ("I can't check availability")."""

    @pytest.mark.parametrize("text", [
        "do you have any open slots available?",
        "can you check if you are open on Friday, three PM?",
        "any openings tomorrow?",
        "can I make an appointment",
        "do you have availability next week",
        "open slot at 3pm?",
    ])
    def test_availability_questions_are_booking_inquiries(self, text):
        assert booking_service._looks_like_booking_inquiry(text) is True

    @pytest.mark.parametrize("text", [
        "are you open on Sundays?",
        "what are your opening hours?",
        "do you have parking available?",
        "where are you located?",
        "how much is a cleaning?",
        "are you open today?",
    ])
    def test_non_booking_questions_stay_faq(self, text):
        assert booking_service._looks_like_booking_inquiry(text) is False

    def test_idle_availability_question_routes_into_booking(self):
        # faq intent + availability wording → still opens the booking flow.
        assert should_route_to_booking(
            False, BookingState.IDLE, "faq", "do you have any open slots available?"
        ) is True

    def test_idle_hours_question_stays_faq(self):
        assert should_route_to_booking(
            False, BookingState.IDLE, "faq", "are you open on Sundays?"
        ) is False


class TestShouldRouteToBooking:
    # ── booking-shaped intents always route in (start or continue a booking) ──
    def test_booking_request_routes_in_even_when_idle(self):
        assert should_route_to_booking(False, BookingState.IDLE, "booking_request") is True

    def test_booking_info_routes_in(self):
        assert should_route_to_booking(True, BookingState.COLLECTING_TIME, "booking_info") is True

    # ── the reported bug: genuine QUESTIONS in early states are NOT trapped ──
    def test_question_in_collecting_service_is_answered_not_looped(self):
        # "which services do you offer?" while collecting the service breaks out.
        assert should_route_to_booking(
            True, BookingState.COLLECTING_SERVICE, "faq", "which services do you offer?"
        ) is False

    def test_question_in_collecting_time_is_answered(self):
        assert should_route_to_booking(
            True, BookingState.COLLECTING_TIME, "faq", "do you take DKV insurance?"
        ) is False

    # ── the SECOND bug: a bare service/time ANSWER must stay in the booking ──
    # (it classifies as faq/off_topic but isn't a question), or the booking leaks
    # out to the general LLM, which role-plays a fake booking.
    def test_time_answer_in_collecting_time_stays_in_booking(self):
        assert should_route_to_booking(
            True, BookingState.COLLECTING_TIME, "off_topic", "yeah sun aug 09 at 1:00PM"
        ) is True

    def test_bare_time_stays_in_booking(self):
        assert should_route_to_booking(
            True, BookingState.COLLECTING_TIME, "faq", "tomorrow at 9am"
        ) is True

    def test_service_answer_in_collecting_service_stays_in_booking(self):
        # "cleaning" is a service answer, not a question — keep the booking alive.
        assert should_route_to_booking(
            True, BookingState.COLLECTING_SERVICE, "off_topic", "cleaning"
        ) is True

    def test_time_proposal_phrased_as_question_stays_in_booking(self):
        # "would 1pm work?" reads as a question but carries a concrete time — the
        # scheduling signal wins so we don't drop the booking.
        assert should_route_to_booking(
            True, BookingState.COLLECTING_TIME, "faq", "would 1pm work?"
        ) is True

    # ── the THIRD bug: a question the classifier tags as a BOOKING intent must
    # still break out to be answered, not trap the customer re-hearing "what time?"
    def test_booking_info_question_in_time_breaks_out(self):
        assert should_route_to_booking(
            True, BookingState.COLLECTING_TIME, "booking_info",
            "can I book for my whole family on the same day?",
        ) is False

    def test_booking_request_question_in_service_breaks_out(self):
        assert should_route_to_booking(
            True, BookingState.COLLECTING_SERVICE, "booking_request", "how soon can I get in?"
        ) is False

    def test_booking_info_time_answer_still_stays_in(self):
        # a booking-intent reply that IS a real time must still stay in the FSM
        assert should_route_to_booking(
            True, BookingState.COLLECTING_TIME, "booking_info", "next tuesday at 2pm"
        ) is True

    # ── name/email + confirm stay sticky (answers look like off_topic/faq) ──
    def test_off_topic_in_contact_info_stays_sticky(self):
        # a bare name/email classifies as off_topic but must reach the FSM
        assert should_route_to_booking(True, BookingState.COLLECTING_CONTACT_INFO, "off_topic") is True

    def test_faq_in_confirming_stays_sticky(self):
        assert should_route_to_booking(True, BookingState.CONFIRMING, "faq") is True

    # ── not in a booking: only booking intents route in ──
    def test_faq_when_no_booking_is_not_routed(self):
        assert should_route_to_booking(False, BookingState.IDLE, "faq") is False

    def test_sticky_states_are_contact_info_and_confirming(self):
        assert set(STICKY_BOOKING_STATES) == {
            BookingState.COLLECTING_CONTACT_INFO,
            BookingState.CONFIRMING,
        }


class TestBookingSessionState:
    @pytest.mark.asyncio
    async def test_active_mid_flow_reports_state(self):
        fsm = BookingFSM(conversation_id="c", current_state=BookingState.COLLECTING_SERVICE)
        with patch.object(booking_service.BookingFSM, "load", new=AsyncMock(return_value=fsm)):
            active, state = await booking_service.booking_session_state(uuid.uuid4())
        assert active is True
        assert state == BookingState.COLLECTING_SERVICE

    @pytest.mark.asyncio
    async def test_idle_is_not_active(self):
        fsm = BookingFSM(conversation_id="c", current_state=BookingState.IDLE)
        with patch.object(booking_service.BookingFSM, "load", new=AsyncMock(return_value=fsm)):
            active, state = await booking_service.booking_session_state(uuid.uuid4())
        assert active is False
        assert state == BookingState.IDLE

    @pytest.mark.asyncio
    async def test_booked_is_not_active(self):
        fsm = BookingFSM(conversation_id="c", current_state=BookingState.BOOKED)
        with patch.object(booking_service.BookingFSM, "load", new=AsyncMock(return_value=fsm)):
            active, _ = await booking_service.booking_session_state(uuid.uuid4())
        assert active is False
