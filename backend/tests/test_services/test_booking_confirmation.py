"""Unit tests for the voice booking-confirmation read-back helpers.

These spell the caller's name + email back before a booking is committed, so an
ASR mis-hear can be caught. Pure functions — no DB / LLM / Redis.
"""

from zoneinfo import ZoneInfo

from app.services.booking_service import (
    _build_voice_confirmation,
    _spell_email_for_voice,
    _spell_name_for_voice,
    _spell_token,
)


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
        assert "Tuesday" in msg and "2:00 PM" in msg

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
