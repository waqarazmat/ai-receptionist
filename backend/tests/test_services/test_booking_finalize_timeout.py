"""Regression test: a slow/hanging Google Calendar must NOT freeze a booking.

Reproduces the reported bug — after the customer said "yes", the calendar
create_event call hung with no timeout, so the reply never came and the chat
sat on a "typing…" indicator forever. The fix bounds create_event with
asyncio.wait_for; on timeout the booking still completes without a calendar
event (google_event_id=None), and the confirmation text is returned promptly.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.booking.fsm import BookingFSM, BookingState
from app.services import booking_service


@pytest.mark.asyncio
async def test_hanging_calendar_does_not_freeze_booking():
    org_tz = ZoneInfo("Europe/Brussels")
    fsm = BookingFSM(conversation_id="c1", current_state=BookingState.CONFIRMING)
    fsm.collected_data = {"service": "consultation", "date": "2026-08-20", "time": "09:00"}

    db = MagicMock()
    contact = MagicMock(name="contact", email=None)
    contact.name = "Rayan"
    db.get = AsyncMock(return_value=contact)

    async def _hanging_create_event(**_kwargs):
        await asyncio.sleep(5)          # simulate Google hanging far past the timeout
        return "evt-never-returned"

    client = MagicMock()
    client.create_event = _hanging_create_event

    with patch.object(booking_service.settings, "CALENDAR_EVENT_TIMEOUT_SECONDS", 0.05), \
         patch.object(booking_service.slot_manager, "hold_slot", AsyncMock(return_value=True)), \
         patch.object(booking_service.slot_manager, "has_conflicting_appointment", AsyncMock(return_value=False)), \
         patch.object(booking_service.slot_manager, "release_slot", AsyncMock()), \
         patch.object(booking_service.GoogleCalendarClient, "for_org", AsyncMock(return_value=client)), \
         patch.object(booking_service.appointment_service, "create_appointment", AsyncMock()) as create_appt:
        result = await asyncio.wait_for(
            booking_service._finalize_booking(
                db, MagicMock(), MagicMock(), MagicMock(), fsm,
                {"consultation": {"duration_minutes": 30}}, org_tz, "Europe/Brussels",
            ),
            timeout=2.0,   # the whole thing must finish well under the 5s hang
        )

    # Booking completed with a confirmation, despite the calendar hanging.
    assert "booked your consultation" in result
    # The appointment was still saved — with NO calendar event id.
    create_appt.assert_awaited_once()
    assert create_appt.await_args.args[-1] is None   # google_event_id positional = None


@pytest.mark.asyncio
async def test_hanging_client_build_does_not_freeze_booking():
    """The freeze that survived the first fix: GoogleCalendarClient.for_org
    (building the client) hangs. The whole calendar interaction is now bounded,
    so the booking must still complete."""
    org_tz = ZoneInfo("Europe/Brussels")
    fsm = BookingFSM(conversation_id="c1", current_state=BookingState.CONFIRMING)
    fsm.collected_data = {"service": "consultation", "date": "2026-08-20", "time": "09:00"}

    db = MagicMock()
    contact = MagicMock(name="contact", email=None)
    contact.name = "Rayan"
    db.get = AsyncMock(return_value=contact)

    async def _hanging_for_org(*_a, **_k):
        await asyncio.sleep(5)          # building the client hangs
        return MagicMock()

    with patch.object(booking_service.settings, "CALENDAR_EVENT_TIMEOUT_SECONDS", 0.05), \
         patch.object(booking_service.slot_manager, "hold_slot", AsyncMock(return_value=True)), \
         patch.object(booking_service.slot_manager, "has_conflicting_appointment", AsyncMock(return_value=False)), \
         patch.object(booking_service.slot_manager, "release_slot", AsyncMock()), \
         patch.object(booking_service.GoogleCalendarClient, "for_org", _hanging_for_org), \
         patch.object(booking_service.appointment_service, "create_appointment", AsyncMock()) as create_appt:
        result = await asyncio.wait_for(
            booking_service._finalize_booking(
                db, MagicMock(), MagicMock(), MagicMock(), fsm,
                {"consultation": {"duration_minutes": 30}}, org_tz, "Europe/Brussels",
            ),
            timeout=2.0,
        )

    assert "booked your consultation" in result
    create_appt.assert_awaited_once()
    assert create_appt.await_args.args[-1] is None
