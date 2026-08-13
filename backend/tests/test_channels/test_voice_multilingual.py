"""Tests for the multilingual voice opening + automatic language mirroring.

Behaviour under test:
  - Multi-language orgs get a multilingual intro: AI disclosure + greeting spoken
    in each supported language (capped), ending with a spoken prompt asking which
    language the caller would like — listing every supported language by name —
    and inviting them to just ask their question.
  - The system prompt tells the LLM to MIRROR the caller's language rather than
    lock to one, so a Dutch caller is answered in Dutch and an English caller in
    English.
  - The AI Act Art. 50 disclosure is present for every spoken language.
"""

from types import SimpleNamespace

from app.channels.voice.retell_handler import (
    _INTRO_MAX_SPOKEN_LANGS,
    _draft_multilingual_begin_message,
    _lang_disclosure,
    _mirror_language_instruction,
)


def _org(name: str = "Hassdent"):
    return SimpleNamespace(name=name, system_prompts={})


class TestMultilingualOpening:
    def test_includes_disclosure_for_each_spoken_language(self):
        """Compliance: the AI disclosure must lead the segment in BOTH languages."""
        msg = _draft_multilingual_begin_message(_org(), ["nl", "en"])
        assert _lang_disclosure("nl") in msg   # "...AI-assistent"
        assert _lang_disclosure("en") in msg   # "This call is handled by an AI assistant."

    def test_includes_org_name(self):
        msg = _draft_multilingual_begin_message(_org("Smile Dental"), ["nl", "en"])
        assert "Smile Dental" in msg

    def test_asks_which_language_in_both_spoken_languages(self):
        msg = _draft_multilingual_begin_message(_org(), ["nl", "en"])
        assert "Which language would you prefer?" in msg   # English choose prompt
        assert "Welke taal heeft uw voorkeur?" in msg      # Dutch choose prompt

    def test_lists_every_supported_language_by_english_name(self):
        """The spoken language list uses English names ("Dutch", not "Nederlands")."""
        msg = _draft_multilingual_begin_message(_org(), ["nl", "en", "fr"])
        assert "Dutch" in msg
        assert "English" in msg
        assert "French" in msg
        assert "Nederlands" not in msg

    def test_invites_caller_to_just_ask(self):
        """No one is trapped in the menu — the prompt says they can just ask."""
        msg = _draft_multilingual_begin_message(_org(), ["nl", "en"])
        assert "ask your question" in msg or "uw vraag stellen" in msg

    def test_caps_number_of_spoken_languages(self):
        """An org with many languages must not read them all aloud — only the
        first _INTRO_MAX_SPOKEN_LANGS are spoken (the rest are still mirrored)."""
        assert _INTRO_MAX_SPOKEN_LANGS == 2
        msg = _draft_multilingual_begin_message(_org(), ["en", "nl", "fr", "de"])
        # First two spoken...
        assert _lang_disclosure("en") in msg
        assert _lang_disclosure("nl") in msg
        # ...third/fourth are NOT in the spoken opening.
        assert _lang_disclosure("fr") not in msg
        assert _lang_disclosure("de") not in msg

    def test_unlisted_intro_language_falls_back_without_crashing(self):
        """A language with a disclosure but no intro copy (e.g. Arabic) still
        produces a valid opening (English greeting copy, its own disclosure)."""
        msg = _draft_multilingual_begin_message(_org(), ["ar", "en"])
        assert _lang_disclosure("ar") in msg
        assert "our services" in msg  # English fallback greeting copy present

    def test_none_org_uses_neutral_name(self):
        msg = _draft_multilingual_begin_message(None, ["nl", "en"])
        assert "our office" in msg


class TestMirrorLanguageInstruction:
    def test_lists_supported_language_names(self):
        instr = _mirror_language_instruction(["nl", "en"])
        assert "Dutch" in instr and "English" in instr

    def test_instructs_detection_and_mirroring(self):
        instr = _mirror_language_instruction(["nl", "en"])
        low = instr.lower()
        assert "detect" in low
        assert "same language" in low

    def test_default_is_first_supported_language(self):
        # Dutch-first: an unclear one-word reply should default to Dutch.
        instr = _mirror_language_instruction(["nl", "en"])
        assert "reply in Dutch" in instr
        # English-first flips the default.
        instr_en = _mirror_language_instruction(["en", "nl"])
        assert "reply in English" in instr_en

    def test_empty_list_is_safe(self):
        instr = _mirror_language_instruction([])
        assert "English" in instr
