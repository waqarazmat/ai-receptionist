"""Unit tests for the voice booking-confirmation read-back helpers.

These spell the caller's name + email back before a booking is committed, so an
ASR mis-hear can be caught. Pure functions — no DB / LLM / Redis.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.booking_service import (
    _build_voice_confirmation,
    _format_slot_options,
    _format_time_voice,
    _ordinal,
    _spell_email_for_voice,
    _spell_name_for_voice,
    _spell_token,
)


class TestOrdinal:
    def test_common_ordinals(self):
        assert _ordinal(1) == "1st"
        assert _ordinal(2) == "2nd"
        assert _ordinal(3) == "3rd"
        assert _ordinal(4) == "4th"

    def test_teens_are_all_th(self):
        assert _ordinal(11) == "11th"
        assert _ordinal(12) == "12th"
        assert _ordinal(13) == "13th"

    def test_twenties(self):
        assert _ordinal(21) == "21st"
        assert _ordinal(22) == "22nd"
        assert _ordinal(23) == "23rd"


class TestFormatTimeVoice:
    def test_drops_zero_minutes(self):
        assert _format_time_voice(datetime(2026, 8, 11, 21, 0)) == "9 PM"
        assert _format_time_voice(datetime(2026, 8, 11, 9, 0)) == "9 AM"

    def test_keeps_non_zero_minutes(self):
        assert _format_time_voice(datetime(2026, 8, 11, 10, 30)) == "10:30 AM"


class TestFormatSlotOptions:
    SLOTS = [datetime(2026, 8, 11, 21, 0), datetime(2026, 8, 12, 10, 30)]  # Tue, Wed

    def test_text_uses_compact_abbreviations(self):
        out = _format_slot_options(self.SLOTS, "text")
        assert "Tue Aug 11 at 9:00 PM" in out
        assert "Wed Aug 12 at 10:30 AM" in out

    def test_voice_uses_full_words_and_ordinals(self):
        out = _format_slot_options(self.SLOTS, "voice")
        assert "Tuesday, August 11th at 9 PM" in out
        assert "Wednesday, August 12th at 10:30 AM" in out
        # No abbreviations that read badly through TTS.
        assert "Tue " not in out and "Aug " not in out

    def test_default_channel_is_text(self):
        assert _format_slot_options(self.SLOTS) == _format_slot_options(self.SLOTS, "text")


class TestSpellToken:
    def test_letters_hyphenated_and_uppercased(self):
        assert _spell_token("john") == "J-O-H-N"

    def test_digits_are_spelled_too(self):
        assert _spell_token("ab12") == "A-B-1-2"

    def test_whitespace_is_dropped(self):
        assert _spell_token("a b") == "A-B"

    def test_empty_string(self):
        assert _spell_token("") == ""


class TestSpellNameForVoice:
    def test_two_part_name(self):
        assert _spell_name_for_voice("John Smith") == "J-O-H-N S-M-I-T-H"

    def test_single_name(self):
        assert _spell_name_for_voice("Mary") == "M-A-R-Y"

    def test_extra_spaces_collapse(self):
        assert _spell_name_for_voice("  John   Smith ") == "J-O-H-N S-M-I-T-H"


class TestSpellEmailForVoice:
    def test_dotted_local_part_and_spoken_domain(self):
        assert (
            _spell_email_for_voice("john.smith@gmail.com")
            == "J-O-H-N dot S-M-I-T-H at gmail dot com"
        )

    def test_simple_local_part(self):
        assert _spell_email_for_voice("mary@outlook.com") == "M-A-R-Y at outlook dot com"

    def test_local_part_with_digits(self):
        assert _spell_email_for_voice("jo42@x.io") == "J-O-4-2 at x dot io"

    def test_no_at_sign_spells_whole_thing(self):
        # Degenerate input (extraction should prevent this, but be safe).
        assert _spell_email_for_voice("john.smith") == "J-O-H-N dot S-M-I-T-H"


class TestBuildVoiceConfirmation:
    TZ = ZoneInfo("America/New_York")

    def _cd(self, **over):
        cd = {
            "service": "Cleaning",
            "date": "2026-08-11",
            "time": "14:00",
            "customer_name": "John Smith",
            "customer_email": "john.smith@gmail.com",
        }
        cd.update(over)
        return cd

    def test_includes_spelled_name_and_email(self):
        msg = _build_voice_confirmation(self._cd(), self.TZ)
        assert "J-O-H-N S-M-I-T-H" in msg
        assert "J-O-H-N dot S-M-I-T-H at gmail dot com" in msg

    def test_reads_service_and_human_friendly_datetime(self):
        msg = _build_voice_confirmation(self._cd(), self.TZ)
        assert "Cleaning" in msg
        # Formatted, not the raw ISO string.
        assert "2026-08-11" not in msg
        assert "14:00" not in msg
        # Full-word, TTS-friendly date/time: "Tuesday, August 11th at 2 PM".
        assert "Tuesday, August 11th at 2 PM" in msg

    def test_ends_with_correctness_question(self):
        msg = _build_voice_confirmation(self._cd(), self.TZ)
        assert msg.rstrip().endswith("Is that all correct?")

    def test_missing_email_omits_email_line(self):
        msg = _build_voice_confirmation(self._cd(customer_email=""), self.TZ)
        assert "email" not in msg.lower()
        assert "J-O-H-N S-M-I-T-H" in msg  # name still read back

    def test_unparseable_datetime_falls_back_to_raw(self):
        msg = _build_voice_confirmation(self._cd(date="whenever", time="soon"), self.TZ)
        # No crash; falls back to the raw tokens rather than a formatted date.
        assert "whenever at soon" in msg
