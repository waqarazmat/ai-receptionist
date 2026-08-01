"""Tests for the Retell voice-agent end-call detection logic.

Covers:
  - _is_explicit_hangup: phrase-matching before the LLM is called
  - _is_post_goodbye_ack: "double goodbye" pattern detection
  - _handle_turn fast paths: end_call_shortcut sent, LLM not invoked
  - LLM [END_CALL] marker path: marker stripped, end_call frame sent
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.channels.voice.retell_handler import (
    _CallState,
    _END_CALL_MARKER,
    _is_explicit_hangup,
    _is_post_goodbye_ack,
)


# ── _is_explicit_hangup ───────────────────────────────────────────────────────


class TestIsExplicitHangup:
    def test_hang_up_detected(self):
        assert _is_explicit_hangup("please hang up") is True

    def test_end_the_call_detected(self):
        assert _is_explicit_hangup("end the call please") is True

    def test_cut_this_call_detected(self):
        assert _is_explicit_hangup("cut this call") is True

    def test_disconnect_detected(self):
        assert _is_explicit_hangup("disconnect") is True

    def test_thats_all_detected(self):
        assert _is_explicit_hangup("that's all, thanks") is True

    def test_gotta_go_detected(self):
        assert _is_explicit_hangup("okay gotta go") is True

    def test_no_more_questions_detected(self):
        assert _is_explicit_hangup("no more questions") is True

    def test_normal_question_not_detected(self):
        assert _is_explicit_hangup("what are your opening hours?") is False

    def test_empty_string_not_detected(self):
        assert _is_explicit_hangup("") is False

    def test_goodbye_alone_not_detected(self):
        # "goodbye" on its own is NOT an explicit hang-up request — it's an
        # ambiguous farewell that should go through normal LLM flow (or the
        # post-goodbye-ack path on the *next* turn).
        assert _is_explicit_hangup("goodbye") is False

    def test_case_insensitive(self):
        assert _is_explicit_hangup("HANG UP NOW") is True
        assert _is_explicit_hangup("End The Call") is True


# ── _is_post_goodbye_ack ──────────────────────────────────────────────────────


def _t(role: str, content: str) -> dict:
    return {"role": role, "content": content}


class TestIsPostGoodbyeAck:
    def test_okay_after_goodbye_detected(self):
        transcript = [
            _t("user", "thanks, bye"),
            _t("agent", "Goodbye! Have a great day and don't hesitate to call again."),
            _t("user", "okay"),
        ]
        assert _is_post_goodbye_ack("okay", transcript) is True

    def test_thanks_after_goodbye_detected(self):
        transcript = [
            _t("agent", "Thank you for calling! Goodbye and take care."),
            _t("user", "thanks"),
        ]
        assert _is_post_goodbye_ack("thanks", transcript) is True

    def test_bye_after_goodbye_detected(self):
        transcript = [
            _t("agent", "Goodbye! Have a wonderful evening."),
            _t("user", "bye"),
        ]
        assert _is_post_goodbye_ack("bye", transcript) is True

    def test_ack_without_prior_goodbye_not_detected(self):
        """'okay' after a non-farewell AI turn must not trigger end-call."""
        transcript = [
            _t("agent", "We are open Monday to Friday from nine AM to five PM."),
            _t("user", "okay"),
        ]
        assert _is_post_goodbye_ack("okay", transcript) is False

    def test_new_question_not_detected(self):
        """A new question after a goodbye AI turn must NOT trigger end-call."""
        transcript = [
            _t("agent", "Goodbye! Have a great day."),
            _t("user", "actually, what are your weekend hours?"),
        ]
        assert _is_post_goodbye_ack("actually, what are your weekend hours?", transcript) is False

    def test_empty_transcript_not_detected(self):
        assert _is_post_goodbye_ack("okay", []) is False

    def test_case_insensitive_ack(self):
        transcript = [_t("agent", "Goodbye, take care!")]
        assert _is_post_goodbye_ack("OKAY", transcript) is True

    def test_goodbye_with_punctuation_ack(self):
        transcript = [_t("agent", "Have a great day! Goodbye.")]
        assert _is_post_goodbye_ack("okay!", transcript) is True

    def test_most_recent_ai_turn_checked(self):
        """Only the most recent AI turn matters — an old goodbye followed by a
        new non-farewell AI turn must NOT trigger end-call."""
        transcript = [
            _t("agent", "Goodbye! Have a great day."),   # old — should be ignored
            _t("user", "actually one more thing"),
            _t("agent", "Of course, how can I help?"),   # most recent — no goodbye
            _t("user", "okay"),
        ]
        assert _is_post_goodbye_ack("okay", transcript) is False


# ── _handle_turn fast paths (end-call sent, LLM skipped) ─────────────────────


def _make_state() -> _CallState:
    state = _CallState()
    state.org_name = "Test Clinic"
    state.org_prompts = {}
    state.org_supported_languages = ["en"]
    state.selected_language = "en"
    state.from_number = "+32471000001"
    return state


def _make_sender():
    sender = MagicMock()
    sender.send_end_call_shortcut = AsyncMock()
    sender.send_shortcut = AsyncMock()
    sender.send_chunk = AsyncMock()
    sender.send = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_explicit_hangup_sends_end_call_skips_llm():
    """'end the call' must trigger send_end_call_shortcut immediately without
    touching the LLM pipeline."""
    import uuid
    from app.channels.voice.retell_handler import _handle_turn

    transcript = [{"role": "user", "content": "end the call please"}]
    sender = _make_sender()
    state = _make_state()

    with (
        patch("app.channels.voice.retell_handler._ensure_conversation", new_callable=AsyncMock,
              return_value=uuid.uuid4()),
        patch("app.channels.voice.retell_handler.async_session_maker"),
        patch("app.channels.voice.retell_handler.stream_llm_with_fallback") as mock_llm,
        patch("app.channels.voice.retell_handler.add_message", new_callable=AsyncMock),
    ):
        await _handle_turn(sender, uuid.uuid4(), "call-1", 1, transcript, state)

    sender.send_end_call_shortcut.assert_awaited_once()
    # LLM must NOT have been called
    mock_llm.assert_not_called()
    # Logged with correct reason
    # (we just verify the shortcut was sent; log verification is structural)


@pytest.mark.asyncio
async def test_explicit_hangup_goodbye_text_is_polite():
    """The goodbye spoken to the caller must be a proper sentence, not empty."""
    import uuid
    from app.channels.voice.retell_handler import _handle_turn

    transcript = [{"role": "user", "content": "hang up"}]
    sender = _make_sender()
    state = _make_state()

    with (
        patch("app.channels.voice.retell_handler._ensure_conversation", new_callable=AsyncMock,
              return_value=uuid.uuid4()),
        patch("app.channels.voice.retell_handler.async_session_maker"),
        patch("app.channels.voice.retell_handler.stream_llm_with_fallback"),
        patch("app.channels.voice.retell_handler.add_message", new_callable=AsyncMock),
    ):
        await _handle_turn(sender, uuid.uuid4(), "call-2", 1, transcript, state)

    call_args = sender.send_end_call_shortcut.call_args
    goodbye_text = call_args[0][1]  # second positional arg is the text
    assert len(goodbye_text) > 5
    assert goodbye_text.strip() != ""


@pytest.mark.asyncio
async def test_post_goodbye_ack_sends_end_call_skips_llm():
    """'okay' after the AI said goodbye must trigger end-call without the LLM."""
    import uuid
    from app.channels.voice.retell_handler import _handle_turn

    transcript = [
        {"role": "agent", "content": "Goodbye! Have a great day and feel free to call again."},
        {"role": "user", "content": "okay"},
    ]
    sender = _make_sender()
    state = _make_state()

    with (
        patch("app.channels.voice.retell_handler._ensure_conversation", new_callable=AsyncMock,
              return_value=uuid.uuid4()),
        patch("app.channels.voice.retell_handler.async_session_maker"),
        patch("app.channels.voice.retell_handler.stream_llm_with_fallback") as mock_llm,
        patch("app.channels.voice.retell_handler.add_message", new_callable=AsyncMock),
    ):
        await _handle_turn(sender, uuid.uuid4(), "call-3", 1, transcript, state)

    sender.send_end_call_shortcut.assert_awaited_once()
    mock_llm.assert_not_called()


@pytest.mark.asyncio
async def test_normal_question_does_not_trigger_end_call():
    """A normal question must NOT trigger end-call — the LLM should handle it."""
    import uuid
    from app.channels.voice.retell_handler import _handle_turn

    transcript = [{"role": "user", "content": "what are your opening hours?"}]
    sender = _make_sender()
    state = _make_state()
    state.llm_client_future = None  # force sync fallback path

    async def fake_stream(*args, **kwargs):
        yield "We are open nine AM to five PM."
        return

    with (
        patch("app.channels.voice.retell_handler._ensure_conversation", new_callable=AsyncMock,
              return_value=uuid.uuid4()),
        patch("app.channels.voice.retell_handler.async_session_maker"),
        patch("app.channels.voice.retell_handler._run_rag", new_callable=AsyncMock, return_value=[]),
        patch("app.channels.voice.retell_handler._fetch_prior_history", new_callable=AsyncMock, return_value=[]),
        patch("app.channels.voice.retell_handler._ensure_contact_name", new_callable=AsyncMock, return_value=None),
        patch("app.channels.voice.retell_handler._persist_customer_message", new_callable=AsyncMock),
        patch("app.channels.voice.retell_handler.get_org_llm_clients", new_callable=AsyncMock,
              return_value=[MagicMock()]),
        patch("app.channels.voice.retell_handler.check_message_rate_limit", new_callable=AsyncMock,
              return_value=True),
        patch("app.channels.voice.retell_handler.increment_message_count", new_callable=AsyncMock),
        patch("app.channels.voice.retell_handler.stream_llm_with_fallback", side_effect=fake_stream),
        patch("app.channels.voice.retell_handler.add_message", new_callable=AsyncMock),
        patch("app.channels.voice.retell_handler._maybe_update_contact_name", new_callable=AsyncMock),
    ):
        await _handle_turn(sender, uuid.uuid4(), "call-4", 1, transcript, state)

    # end_call_shortcut must NOT have been called
    sender.send_end_call_shortcut.assert_not_awaited()


# ── [END_CALL] marker — LLM natural conclusion path ──────────────────────────


def test_end_call_marker_constant_is_correct():
    """Sanity-check the marker string matches what the system prompt documents."""
    assert _END_CALL_MARKER == "[END_CALL]"


@pytest.mark.asyncio
async def test_llm_end_call_marker_triggers_end_call_frame():
    """When the LLM appends [END_CALL] the close frame must include end_call:true
    and the marker must be stripped from the persisted transcript."""
    import uuid
    from app.channels.voice.retell_handler import _handle_turn

    transcript = [{"role": "user", "content": "okay thanks, bye"}]
    sender = _make_sender()
    state = _make_state()
    state.llm_client_future = None

    persisted_ai_texts = []

    async def capture_add_message(db, conv_id, role, content, channel):
        from app.models.enums import MessageRole
        if role == MessageRole.ai:
            persisted_ai_texts.append(content)

    async def fake_stream(*args, **kwargs):
        yield "Glad I could help! Goodbye, have a great day!"
        yield "\n[END_CALL]"
        return

    with (
        patch("app.channels.voice.retell_handler._ensure_conversation", new_callable=AsyncMock,
              return_value=uuid.uuid4()),
        patch("app.channels.voice.retell_handler.async_session_maker"),
        patch("app.channels.voice.retell_handler._run_rag", new_callable=AsyncMock, return_value=[]),
        patch("app.channels.voice.retell_handler._fetch_prior_history", new_callable=AsyncMock, return_value=[]),
        patch("app.channels.voice.retell_handler._ensure_contact_name", new_callable=AsyncMock, return_value=None),
        patch("app.channels.voice.retell_handler._persist_customer_message", new_callable=AsyncMock),
        patch("app.channels.voice.retell_handler.get_org_llm_clients", new_callable=AsyncMock,
              return_value=[MagicMock()]),
        patch("app.channels.voice.retell_handler.check_message_rate_limit", new_callable=AsyncMock,
              return_value=True),
        patch("app.channels.voice.retell_handler.increment_message_count", new_callable=AsyncMock),
        patch("app.channels.voice.retell_handler.stream_llm_with_fallback", side_effect=fake_stream),
        patch("app.channels.voice.retell_handler.add_message", side_effect=capture_add_message),
        patch("app.channels.voice.retell_handler._maybe_update_contact_name", new_callable=AsyncMock),
    ):
        await _handle_turn(sender, uuid.uuid4(), "call-5", 1, transcript, state)

    # The close frame sent to Retell must include end_call: true
    end_call_frames = [
        call for call in sender.send.call_args_list
        if isinstance(call[0][0], dict) and call[0][0].get("end_call") is True
    ]
    assert len(end_call_frames) == 1, "Expected exactly one end_call frame"
    assert end_call_frames[0][0][0].get("content_complete") is True

    # [END_CALL] must be stripped from what was persisted
    assert persisted_ai_texts, "AI message was not persisted"
    for text in persisted_ai_texts:
        assert "[END_CALL]" not in text, f"Marker should be stripped, got: {text!r}"
