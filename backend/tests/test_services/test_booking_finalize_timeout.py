"""Regression tests: the booking confirmation must NEVER wait on Google Calendar
or the confirmation email.

Reproduces the reported bug — after "yes", the calendar step hung with no bound,
so the reply never came and the chat sat on a "typing…" indicator forever. The
fix decouples the slow side effects: _finalize_booking saves the appointment,
returns the confirmation immediately, and does the calendar event + email in a
background task. So the reply is instant regardless of how slow/hung Google is.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.booking.fsm import BookingFSM, BookingState
from app.services import booking_service


def test_confirming_affirmative_regexes_are_imported_in_booking_service():
    """Regression: process_booking_intent's CONFIRMING branch references
    _AFFIRMATIVE_RE / _NEGATIVE_RE. They live in fsm.py and were NOT imported
    into booking_service, so EVERY booking confirmation ("yes") crashed with a
    NameError → the reply never came → the chat hung on "typing…". Guard that
    they're now importable from booking_service's namespace."""
    assert booking_service._AFFIRMATIVE_RE.search("yes")
    assert booking_service._NEGATIVE_RE.search("no")


def _confirming_fsm():
    fsm = BookingFSM(conversation_id="c1", current_state=BookingState.CONFIRMING)
    fsm.collected_data = {
        "service": "consultation", "date": "2026-08-20", "time": "09:00",
        "customer_name": "Rayan", "customer_email": "rayan@example.com",
    }
    return fsm


async def _finalize_with_mocks(spawn_mock):
    org_tz = ZoneInfo("Europe/Brussels")
    fsm = _confirming_fsm()
    db = MagicMock()
    contact = MagicMock(name="contact", email="rayan@example.com")
    contact.name = "Rayan"
    db.get = AsyncMock(return_value=contact)
    appointment = MagicMock(id="appt-123")

    with patch.object(booking_service.slot_manager, "hold_slot", AsyncMock(return_value=True)), \
         patch.object(booking_service.slot_manager, "has_conflicting_appointment", AsyncMock(return_value=False)), \
         patch.object(booking_service.slot_manager, "release_slot", AsyncMock()), \
         patch.object(booking_service.appointment_service, "create_appointment",
                      AsyncMock(return_value=appointment)) as create_appt, \
         patch.object(booking_service, "_spawn_booking_side_effects", spawn_mock):
        result = await asyncio.wait_for(
            booking_service._finalize_booking(
                db, MagicMock(), MagicMock(), MagicMock(), fsm,
                {"consultation": {"duration_minutes": 30}}, org_tz, "Europe/Brussels",
            ),
            timeout=2.0,
        )
    return result, create_appt


@pytest.mark.asyncio
async def test_reply_is_immediate_and_appointment_saved_without_event_id():
    """The confirmation returns right away; the appointment is saved with NO
    calendar event id (it's backfilled later, in the background)."""
    # Capture the scheduled coroutine and close it (don't run it — it would hit
    # the real calendar/DB). Closing avoids an "unawaited coroutine" warning.
    scheduled = []
    spawn = MagicMock(side_effect=lambda coro: (scheduled.append(coro), coro.close()))

    result, create_appt = await _finalize_with_mocks(spawn)

    assert "booked your consultation" in result
    create_appt.assert_awaited_once()
    assert create_appt.await_args.args[-1] is None   # google_event_id = None at save time
    spawn.assert_called_once()                        # calendar + email deferred to background


@pytest.mark.asyncio
async def test_reply_does_not_await_the_background_side_effects():
    """Even if the background side effects would take forever, the reply is not
    blocked — _finalize_booking never awaits them."""
    async def _forever():
        await asyncio.sleep(60)

    # Real spawn helper actually schedules the task; we hand it a coroutine that
    # would hang forever. The reply must still come back well under the hang.
    with patch.object(booking_service, "_run_booking_side_effects", lambda *a, **k: _forever()):
        result, _ = await _finalize_with_mocks(booking_service._spawn_booking_side_effects)

    assert "booked your consultation" in result

    # Clean up the still-pending background task we scheduled.
    for t in list(booking_service._booking_side_effect_tasks):
        t.cancel()
