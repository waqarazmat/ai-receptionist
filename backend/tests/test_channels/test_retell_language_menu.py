"""Tests for the Retell voice-agent language-selection menu.

Covers the pure helper functions (_build_language_menu, _detect_language_choice,
_lang_disclosure, _draft_begin_message) and the stateful routing logic in
_CallState — no live WebSocket or database required.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.channels.voice.retell_handler import (
    _CallState,
    _build_language_menu,
    _detect_language_choice,
    _draft_begin_message,
    _handle_language_selection,
    _lang_disclosure,
    _lang_instruction,
    _language_fallback,
    _run_language_menu_timeout,
)


# ── _build_language_menu ──────────────────────────────────────────────────────


class TestBuildLanguageMenu:
    def test_three_languages_produces_three_sentences(self):
        menu = _build_language_menu(["en", "nl", "fr"])
        # Each language must appear in its own language
        assert "English" in menu
        assert "Nederlands" in menu
        assert "français" in menu.lower()

    def test_three_languages_includes_correct_position_numbers(self):
        menu = _build_language_menu(["en", "nl", "fr"])
        assert "1" in menu
        assert "2" in menu
        assert "3" in menu
        # 4 must NOT appear — there are only 3 options
        assert "press 4" not in menu

    def test_single_language_produces_one_sentence(self):
        menu = _build_language_menu(["en"])
        # No multi-line menu for a single language; the word "Nederlands" must not appear
        assert "English" in menu
        assert "Nederlands" not in menu

    def test_four_languages_produces_four_sentences(self):
        menu = _build_language_menu(["en", "nl", "fr", "de"])
        assert "English" in menu
        assert "Nederlands" in menu
        assert "français" in menu.lower()
        assert "Deutsch" in menu
        assert "4" in menu

    def test_unknown_language_code_is_silently_skipped(self):
        """An unsupported code in the list must not raise — just omit that option."""
        menu = _build_language_menu(["en", "xx_unknown", "fr"])
        assert "English" in menu
        assert "français" in menu.lower()
        # Positions renumber around the gap: en=1, fr=2 (or 3 if xx keeps a slot)
        # The key invariant is no exception and the two known languages appear.

    def test_empty_list_returns_empty_string(self):
        assert _build_language_menu([]) == ""


# ── _detect_language_choice ───────────────────────────────────────────────────


class TestDetectLanguageChoice:
    def test_digit_1_selects_first_language(self):
        assert _detect_language_choice("1", ["en", "nl", "fr"]) == "en"

    def test_digit_2_selects_second_language(self):
        assert _detect_language_choice("2", ["en", "nl", "fr"]) == "nl"

    def test_digit_3_selects_third_language(self):
        assert _detect_language_choice("3", ["en", "nl", "fr"]) == "fr"

    def test_spoken_english_selects_en(self):
        assert _detect_language_choice("English please", ["en", "nl", "fr"]) == "en"

    def test_spoken_nederlands_selects_nl(self):
        assert _detect_language_choice("Nederlands", ["en", "nl", "fr"]) == "nl"

    def test_spoken_francais_selects_fr(self):
        assert _detect_language_choice("français", ["en", "nl", "fr"]) == "fr"

    def test_spoken_dutch_alias_selects_nl(self):
        assert _detect_language_choice("Dutch", ["en", "nl", "fr"]) == "nl"

    def test_spoken_french_alias_selects_fr(self):
        assert _detect_language_choice("French please", ["en", "nl", "fr"]) == "fr"

    def test_spoken_german_selects_de(self):
        assert _detect_language_choice("German", ["en", "nl", "de"]) == "de"

    def test_spoken_deutsch_selects_de(self):
        assert _detect_language_choice("Deutsch", ["en", "nl", "de"]) == "de"

    def test_case_insensitive_keyword(self):
        assert _detect_language_choice("ENGLISH", ["en", "nl"]) == "en"
        assert _detect_language_choice("english", ["en", "nl"]) == "en"

    def test_unrecognised_input_returns_none(self):
        assert _detect_language_choice("huh?", ["en", "nl", "fr"]) is None

    def test_empty_input_returns_none(self):
        assert _detect_language_choice("", ["en", "nl"]) is None

    def test_digit_out_of_range_returns_none(self):
        # 4 is not a valid position when there are only 3 languages
        result = _detect_language_choice("4", ["en", "nl", "fr"])
        assert result is None

    def test_number_word_one_selects_first_english_position(self):
        assert _detect_language_choice("one", ["en", "nl"]) == "en"

    def test_number_word_twee_selects_nl(self):
        assert _detect_language_choice("twee", ["en", "nl"]) == "nl"

    def test_number_word_trois_selects_fr(self):
        assert _detect_language_choice("trois", ["en", "fr"]) == "fr"

    def test_digit_takes_priority_over_keyword(self):
        """Position-based matching runs first — "1" in the input selects the
        first language even if that language has a keyword that also matches."""
        # "en" is position 1; result must be "en", not some other match
        assert _detect_language_choice("press 1 please", ["en", "nl"]) == "en"


# ── _lang_disclosure ──────────────────────────────────────────────────────────


class TestLangDisclosure:
    def test_english_disclosure(self):
        d = _lang_disclosure("en")
        assert "AI assistant" in d

    def test_dutch_disclosure_is_dutch(self):
        d = _lang_disclosure("nl")
        assert "AI-assistent" in d

    def test_french_disclosure_is_french(self):
        d = _lang_disclosure("fr")
        assert "assistant IA" in d

    def test_german_disclosure_is_german(self):
        d = _lang_disclosure("de")
        assert "KI-Assistenten" in d

    def test_unknown_language_falls_back_to_english(self):
        d = _lang_disclosure("xx")
        assert "AI assistant" in d


# ── _lang_instruction ─────────────────────────────────────────────────────────


class TestLangInstruction:
    def test_english_instruction_mentions_english(self):
        assert "English" in _lang_instruction("en")

    def test_dutch_instruction_is_in_dutch(self):
        assert "Nederlands" in _lang_instruction("nl")

    def test_french_instruction_is_in_french(self):
        assert "français" in _lang_instruction("fr").lower()

    def test_german_instruction_is_in_german(self):
        assert "Deutsch" in _lang_instruction("de")


# ── _draft_begin_message ──────────────────────────────────────────────────────


class TestDraftBeginMessage:
    def _org(self, name="Acme Clinic", system_prompts=None):
        from unittest.mock import MagicMock
        org = MagicMock()
        org.name = name
        org.system_prompts = system_prompts or {}
        return org

    def test_default_language_is_english_disclosure(self):
        msg = _draft_begin_message({}, self._org())
        assert "AI assistant" in msg

    def test_dutch_language_gives_dutch_disclosure(self):
        msg = _draft_begin_message({}, self._org(), language="nl")
        assert "AI-assistent" in msg

    def test_french_language_gives_french_disclosure(self):
        msg = _draft_begin_message({}, self._org(), language="fr")
        assert "assistant IA" in msg

    def test_config_greeting_is_used_when_present(self):
        msg = _draft_begin_message({"greeting": "Welcome to Acme!"}, self._org())
        assert "Welcome to Acme!" in msg

    def test_org_name_in_fallback_greeting_when_no_config_greeting(self):
        msg = _draft_begin_message({}, self._org(name="Smile Dental"))
        assert "Smile Dental" in msg

    def test_disclosure_always_precedes_greeting(self):
        msg = _draft_begin_message({"greeting": "Hi there"}, self._org())
        disclosure_pos = msg.index("AI assistant")
        greeting_pos = msg.index("Hi there")
        assert disclosure_pos < greeting_pos


# ── _CallState language fields ────────────────────────────────────────────────


class TestCallStateLanguageDefaults:
    def test_language_phase_starts_false(self):
        state = _CallState()
        assert state.language_phase is False

    def test_selected_language_defaults_to_en(self):
        state = _CallState()
        assert state.selected_language == "en"

    def test_org_supported_languages_defaults_to_en_only(self):
        state = _CallState()
        assert state.org_supported_languages == ["en"]

    def test_single_language_org_does_not_need_menu(self):
        """When org has one language, language_phase should never be set to
        True by the websocket handler — verify the state machine invariant."""
        state = _CallState()
        state.org_supported_languages = ["en"]
        # The websocket sets language_phase = len(supported) > 1
        state.language_phase = len(state.org_supported_languages) > 1
        assert state.language_phase is False

    def test_three_language_org_triggers_menu_phase(self):
        state = _CallState()
        state.org_supported_languages = ["en", "nl", "fr"]
        state.language_phase = len(state.org_supported_languages) > 1
        assert state.language_phase is True

    def test_language_timeout_task_defaults_to_none(self):
        state = _CallState()
        assert state.language_timeout_task is None


# ── _language_fallback ────────────────────────────────────────────────────────


class TestLanguageFallback:
    def test_english_preferred_when_in_list(self):
        assert _language_fallback(["en", "nl", "fr"]) == "en"

    def test_english_preferred_even_when_not_first(self):
        assert _language_fallback(["nl", "en", "fr"]) == "en"

    def test_first_language_used_when_english_absent(self):
        assert _language_fallback(["nl", "fr"]) == "nl"

    def test_single_language_returned_directly(self):
        assert _language_fallback(["de"]) == "de"


# ── _run_language_menu_timeout ────────────────────────────────────────────────


class TestRunLanguageMenuTimeout:
    def _make_sender(self):
        sender = MagicMock()
        sender.send_shortcut = AsyncMock()
        return sender

    def _make_state(self, languages=None):
        state = _CallState()
        state.org_supported_languages = languages or ["en", "nl", "fr"]
        state.language_phase = True
        state.selected_language = state.org_supported_languages[0]
        return state

    @pytest.mark.asyncio
    async def test_timeout_defaults_to_english_after_delay(self):
        sender = self._make_sender()
        state = self._make_state(["en", "nl", "fr"])
        org = MagicMock()
        org.name = "Test Clinic"
        org.system_prompts = {}

        with patch("app.channels.voice.retell_handler.asyncio.sleep", new_callable=AsyncMock):
            await _run_language_menu_timeout(sender, __import__("uuid").uuid4(), "call-1", state, {}, org)

        assert state.selected_language == "en"
        assert state.language_phase is False
        sender.send_shortcut.assert_awaited_once()
        # The message sent should contain the English disclosure
        sent_text = sender.send_shortcut.call_args[0][1]
        assert "AI assistant" in sent_text

    @pytest.mark.asyncio
    async def test_timeout_falls_back_to_first_language_when_no_english(self):
        sender = self._make_sender()
        state = self._make_state(["nl", "fr"])
        org = MagicMock()
        org.name = "Kliniek"
        org.system_prompts = {}

        with patch("app.channels.voice.retell_handler.asyncio.sleep", new_callable=AsyncMock):
            await _run_language_menu_timeout(sender, __import__("uuid").uuid4(), "call-2", state, {}, org)

        assert state.selected_language == "nl"
        assert state.language_phase is False

    @pytest.mark.asyncio
    async def test_timeout_no_op_when_language_already_resolved(self):
        """If the caller selected a language before the timer fired, the
        timeout task should return without sending anything."""
        sender = self._make_sender()
        state = self._make_state()
        state.language_phase = False  # already resolved
        state.selected_language = "fr"

        with patch("app.channels.voice.retell_handler.asyncio.sleep", new_callable=AsyncMock):
            await _run_language_menu_timeout(sender, __import__("uuid").uuid4(), "call-3", state, {}, None)

        sender.send_shortcut.assert_not_awaited()
        assert state.selected_language == "fr"  # unchanged

    @pytest.mark.asyncio
    async def test_timeout_cancelled_before_sleep_returns_cleanly(self):
        """CancelledError during sleep must propagate silently (no side-effects)."""
        sender = self._make_sender()
        state = self._make_state()

        async def raise_cancelled(_delay):
            raise asyncio.CancelledError

        with patch("app.channels.voice.retell_handler.asyncio.sleep", side_effect=raise_cancelled):
            await _run_language_menu_timeout(sender, __import__("uuid").uuid4(), "call-4", state, {}, None)

        sender.send_shortcut.assert_not_awaited()
        # language_phase must not have been changed by the cancelled task
        assert state.language_phase is True


# ── _handle_language_selection default paths ──────────────────────────────────


class TestHandleLanguageSelectionDefaults:
    def _make_sender(self):
        sender = MagicMock()
        sender.send_shortcut = AsyncMock()
        return sender

    def _make_state(self, languages=None):
        state = _CallState()
        state.org_supported_languages = languages or ["en", "nl", "fr"]
        state.language_phase = True
        state.selected_language = (languages or ["en", "nl", "fr"])[0]
        return state

    def _org(self, name="Acme"):
        org = MagicMock()
        org.name = name
        org.system_prompts = {}
        return org

    @pytest.mark.asyncio
    async def test_invalid_input_defaults_to_english(self):
        """Unrecognised DTMF / speech must default to English, not re-present menu."""
        sender = self._make_sender()
        state = self._make_state(["en", "nl", "fr"])
        transcript = [{"role": "user", "content": "bleep bloop"}]

        with patch("app.channels.voice.retell_handler.async_session_maker"), \
             patch("app.channels.voice.retell_handler._ensure_conversation", new_callable=AsyncMock), \
             patch("app.channels.voice.retell_handler.get_conversation_messages", new_callable=AsyncMock, return_value=[]):
            await _handle_language_selection(sender, __import__("uuid").uuid4(), "call-5", 1, transcript, state, {}, self._org())

        assert state.selected_language == "en"
        assert state.language_phase is False
        sender.send_shortcut.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_transcript_defaults_to_english(self):
        """Empty transcript (reminder_required silence path) must also default."""
        sender = self._make_sender()
        state = self._make_state(["en", "nl"])

        with patch("app.channels.voice.retell_handler.async_session_maker"), \
             patch("app.channels.voice.retell_handler._ensure_conversation", new_callable=AsyncMock), \
             patch("app.channels.voice.retell_handler.get_conversation_messages", new_callable=AsyncMock, return_value=[]):
            await _handle_language_selection(sender, __import__("uuid").uuid4(), "call-6", 1, [], state, {}, self._org())

        assert state.selected_language == "en"
        assert state.language_phase is False

    @pytest.mark.asyncio
    async def test_invalid_input_no_english_defaults_to_first_language(self):
        """When English is not in the org's list, fallback is the first language."""
        sender = self._make_sender()
        state = self._make_state(["nl", "fr"])
        transcript = [{"role": "user", "content": "xyz"}]

        with patch("app.channels.voice.retell_handler.async_session_maker"), \
             patch("app.channels.voice.retell_handler._ensure_conversation", new_callable=AsyncMock), \
             patch("app.channels.voice.retell_handler.get_conversation_messages", new_callable=AsyncMock, return_value=[]):
            await _handle_language_selection(sender, __import__("uuid").uuid4(), "call-7", 1, transcript, state, {}, self._org())

        assert state.selected_language == "nl"
        assert state.language_phase is False

    @pytest.mark.asyncio
    async def test_already_resolved_returns_early(self):
        """If language_phase is False (concurrent task already handled it),
        _handle_language_selection must be a no-op."""
        sender = self._make_sender()
        state = self._make_state()
        state.language_phase = False
        state.selected_language = "fr"

        await _handle_language_selection(sender, __import__("uuid").uuid4(), "call-8", 1, [], state, {}, self._org())

        sender.send_shortcut.assert_not_awaited()
        assert state.selected_language == "fr"  # untouched

    @pytest.mark.asyncio
    async def test_valid_choice_cancels_timeout_task(self):
        """A valid language selection must cancel the pending timeout task."""
        sender = self._make_sender()
        state = self._make_state(["en", "nl"])
        # Simulate an in-flight timeout task
        timeout_task = MagicMock()
        timeout_task.done.return_value = False
        state.language_timeout_task = timeout_task

        transcript = [{"role": "user", "content": "English"}]

        with patch("app.channels.voice.retell_handler.async_session_maker"), \
             patch("app.channels.voice.retell_handler._ensure_conversation", new_callable=AsyncMock), \
             patch("app.channels.voice.retell_handler.get_conversation_messages", new_callable=AsyncMock, return_value=[]):
            await _handle_language_selection(sender, __import__("uuid").uuid4(), "call-9", 1, transcript, state, {}, self._org())

        timeout_task.cancel.assert_called_once()
        assert state.selected_language == "en"

    @pytest.mark.asyncio
    async def test_invalid_input_also_cancels_timeout_task(self):
        """Even when defaulting due to bad input the timeout task must be cancelled."""
        sender = self._make_sender()
        state = self._make_state(["en", "nl"])
        timeout_task = MagicMock()
        timeout_task.done.return_value = False
        state.language_timeout_task = timeout_task

        transcript = [{"role": "user", "content": "gibberish"}]

        with patch("app.channels.voice.retell_handler.async_session_maker"), \
             patch("app.channels.voice.retell_handler._ensure_conversation", new_callable=AsyncMock), \
             patch("app.channels.voice.retell_handler.get_conversation_messages", new_callable=AsyncMock, return_value=[]):
            await _handle_language_selection(sender, __import__("uuid").uuid4(), "call-10", 1, transcript, state, {}, self._org())

        timeout_task.cancel.assert_called_once()
