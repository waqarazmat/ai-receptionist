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

import pytest

from app.channels.voice.retell_handler import (
    _detect_named_language,
    _draft_multilingual_begin_message,
    _lang_disclosure,
    _lock_language_instruction,
    _mirror_language_instruction,
)


def _org(name: str = "Hassdent"):
    return SimpleNamespace(name=name, system_prompts={})


class TestMultilingualOpening:
    def test_intro_spoken_in_english_only(self):
        """The intro (disclosure + greeting) is spoken ONCE, in English — not
        repeated per language — so no Dutch/French disclosure appears."""
        msg = _draft_multilingual_begin_message(_org(), ["nl", "en", "fr"])
        assert _lang_disclosure("en") in msg       # "This call is handled by an AI assistant."
        assert _lang_disclosure("nl") not in msg   # NOT repeated in Dutch
        assert _lang_disclosure("fr") not in msg   # NOT repeated in French

    def test_includes_org_name(self):
        msg = _draft_multilingual_begin_message(_org("Smile Dental"), ["nl", "en"])
        assert "Smile Dental" in msg

    def test_asks_which_language_in_english_only(self):
        msg = _draft_multilingual_begin_message(_org(), ["nl", "en"])
        assert "Which language would you prefer?" in msg    # English choose prompt
        assert "Welke taal heeft uw voorkeur?" not in msg   # NOT repeated in Dutch

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
        assert "ask your question" in msg

    def test_intro_is_english_regardless_of_language_order(self):
        """English intro even when English isn't first in the supported list."""
        for langs in (["nl", "en", "fr"], ["fr", "nl", "en"]):
            msg = _draft_multilingual_begin_message(_org(), langs)
            assert _lang_disclosure("en") in msg

    def test_falls_back_to_first_language_when_english_unsupported(self):
        """An org WITHOUT English uses its first language's disclosure, with the
        English greeting/prompt copy as a safe fallback — and never crashes."""
        msg = _draft_multilingual_begin_message(_org(), ["ar", "tr"])
        assert _lang_disclosure("ar") in msg   # first language's disclosure
        assert "our services" in msg           # English greeting copy fallback

    def test_none_org_uses_neutral_name(self):
        msg = _draft_multilingual_begin_message(None, ["nl", "en"])
        assert "our office" in msg


class TestDetectNamedLanguage:
    S = ["nl", "en", "fr"]

    @pytest.mark.parametrize("text,expected", [
        ("yeah I want to continue in English", "en"),
        ("I want to talk in English", "en"),
        ("continue in Dutch please", "nl"),
        ("let's use French", "fr"),
        ("can we proceed in Nederlands", "nl"),
        ("could you switch to French for me", "fr"),
        ("English", "en"),
        ("Nederlands", "nl"),
    ])
    def test_natural_phrasing_naming_a_language_is_detected(self, text, expected):
        assert _detect_named_language(text, self.S) == expected

    @pytest.mark.parametrize("text", [
        "I have one question about pricing",   # "one" must NOT read as English
        "what are your opening hours",
        "can I book two appointments",         # "two" must NOT read as Dutch
        "hello there",
    ])
    def test_no_language_name_returns_none(self, text):
        assert _detect_named_language(text, self.S) is None

    def test_only_matches_supported_languages(self):
        # German named but org supports only nl/en/fr → None.
        assert _detect_named_language("let's do it in German", self.S) is None


class TestLockLanguageInstruction:
    def test_names_the_locked_language_and_forces_it(self):
        instr = _lock_language_instruction("nl")
        assert "Dutch" in instr
        assert "ONLY in Dutch" in instr

    def test_locks_even_when_caller_switches(self):
        instr = _lock_language_instruction("fr")
        low = instr.lower()
        assert "french" in low
        assert "even if" in low   # stays locked even if the caller switches

    def test_unknown_code_falls_back_to_code(self):
        # Never crashes on an unmapped code.
        assert "xx" in _lock_language_instruction("xx")


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
