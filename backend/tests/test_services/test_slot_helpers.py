"""Tests for the working-hours helpers used to reject closed days at booking time."""
from datetime import date
from types import SimpleNamespace

from app.booking import slot_manager


def _org(hours):
    return SimpleNamespace(working_hours={"hours": hours})


_MON_FRI = {
    "monday": {"open": "09:00", "close": "18:00"},
    "tuesday": {"open": "09:00", "close": "18:00"},
    "wednesday": {"open": "09:00", "close": "18:00"},
    "thursday": {"open": "09:00", "close": "18:00"},
    "friday": {"open": "09:00", "close": "13:00"},
}


def test_open_days_phrase_contiguous_is_a_range():
    assert slot_manager.open_days_phrase(_org(_MON_FRI)) == "Monday to Friday"


def test_open_days_phrase_with_gaps_is_a_list():
    org = _org({
        "monday": {"open": "09:00", "close": "18:00"},
        "wednesday": {"open": "09:00", "close": "18:00"},
        "friday": {"open": "09:00", "close": "13:00"},
    })
    assert slot_manager.open_days_phrase(org) == "Monday, Wednesday and Friday"


def test_is_open_on_respects_configured_days():
    org = _org(_MON_FRI)
    assert slot_manager.is_open_on(org, date(2026, 8, 17)) is True   # Monday
    assert slot_manager.is_open_on(org, date(2026, 8, 16)) is False  # Sunday (omitted → closed)
    assert slot_manager.is_open_on(org, date(2026, 8, 15)) is False  # Saturday
