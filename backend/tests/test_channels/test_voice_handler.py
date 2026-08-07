"""Tests for voice_handler.py — multilingual TTS provider routing."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.channels.whatsapp.voice_handler import (
    _language_supported,
    _pick_tts_provider,
)


@pytest.fixture(autouse=True)
def _stub_provider_key():
    """Per-org STT/TTS key resolution hits the DB; these orchestrator tests mock
    the session, so stub the resolver to hand back a dummy key. Tests that need
    the "no key" path override this inside their own patch block."""
    with patch(
        "app.channels.whatsapp.voice_handler.resolve_provider_key",
        new_callable=AsyncMock,
        return_value="test-key",
    ):
        yield


# ── _language_supported ───────────────────────────────────────────────────────


class TestLanguageSupported:
    def test_english_is_supported_by_default(self):
        with patch("app.channels.whatsapp.voice_handler.settings") as mock_settings:
            mock_settings.VOICE_SUPPORTED_LANGUAGES = ["en", "fr", "nl", "de"]
            assert _language_supported("en") is True

    def test_french_is_supported_by_default(self):
        with patch("app.channels.whatsapp.voice_handler.settings") as mock_settings:
            mock_settings.VOICE_SUPPORTED_LANGUAGES = ["en", "fr", "nl", "de"]
            assert _language_supported("fr") is True

    def test_dutch_is_supported_by_default(self):
        with patch("app.channels.whatsapp.voice_handler.settings") as mock_settings:
            mock_settings.VOICE_SUPPORTED_LANGUAGES = ["en", "fr", "nl", "de"]
            assert _language_supported("nl") is True

    def test_unsupported_language_returns_false(self):
        with patch("app.channels.whatsapp.voice_handler.settings") as mock_settings:
            mock_settings.VOICE_SUPPORTED_LANGUAGES = ["en", "fr", "nl", "de"]
            assert _language_supported("ur") is False

    def test_wildcard_allows_any_language(self):
        with patch("app.channels.whatsapp.voice_handler.settings") as mock_settings:
            mock_settings.VOICE_SUPPORTED_LANGUAGES = ["*"]
            assert _language_supported("ur") is True
            assert _language_supported("zh") is True

    def test_none_language_is_allowed(self):
        with patch("app.channels.whatsapp.voice_handler.settings") as mock_settings:
            mock_settings.VOICE_SUPPORTED_LANGUAGES = ["en", "fr"]
            assert _language_supported(None) is True

    def test_case_insensitive(self):
        with patch("app.channels.whatsapp.voice_handler.settings") as mock_settings:
            mock_settings.VOICE_SUPPORTED_LANGUAGES = ["en", "FR"]
            assert _language_supported("EN") is True
            assert _language_supported("fr") is True


# ── _pick_tts_provider ────────────────────────────────────────────────────────


class TestPickTtsProvider:
    def _mock_settings(self, *, default="openai", fallback="openai", support_map=None):
        mock = MagicMock()
        mock.TTS_PROVIDER = default
        mock.TTS_MULTILINGUAL_FALLBACK_PROVIDER = fallback
        mock.TTS_PROVIDER_LANGUAGE_SUPPORT = support_map or {
            "openai": ["en", "fr", "nl", "de", "es"],
            "deepgram": ["en"],
        }
        return mock

    def test_english_uses_default_provider_no_fallback(self):
        with patch("app.channels.whatsapp.voice_handler.settings", self._mock_settings(default="openai")):
            provider, is_fallback = _pick_tts_provider("en")
            assert provider == "openai"
            assert is_fallback is False

    def test_french_uses_default_openai_no_fallback(self):
        with patch("app.channels.whatsapp.voice_handler.settings", self._mock_settings(default="openai")):
            provider, is_fallback = _pick_tts_provider("fr")
            assert provider == "openai"
            assert is_fallback is False

    def test_french_with_deepgram_default_falls_back_to_openai(self):
        """Deepgram only supports English — French should route to the multilingual fallback."""
        with patch(
            "app.channels.whatsapp.voice_handler.settings",
            self._mock_settings(default="deepgram", fallback="openai"),
        ):
            provider, is_fallback = _pick_tts_provider("fr")
            assert provider == "openai"
            assert is_fallback is True

    def test_dutch_with_deepgram_default_falls_back_to_openai(self):
        with patch(
            "app.channels.whatsapp.voice_handler.settings",
            self._mock_settings(default="deepgram", fallback="openai"),
        ):
            provider, is_fallback = _pick_tts_provider("nl")
            assert provider == "openai"
            assert is_fallback is True

    def test_english_with_deepgram_default_no_fallback(self):
        """Deepgram supports English — should NOT fall back."""
        with patch(
            "app.channels.whatsapp.voice_handler.settings",
            self._mock_settings(default="deepgram", fallback="openai"),
        ):
            provider, is_fallback = _pick_tts_provider("en")
            assert provider == "deepgram"
            assert is_fallback is False

    def test_unknown_language_uses_default_no_fallback(self):
        """None language → use default and let the provider decide."""
        with patch("app.channels.whatsapp.voice_handler.settings", self._mock_settings(default="openai")):
            provider, is_fallback = _pick_tts_provider(None)
            assert provider == "openai"
            assert is_fallback is False

    def test_provider_with_no_declared_support_map_entry_triggers_fallback(self):
        """Fail-closed: if default provider has no support-map entry, trigger fallback.

        An unlisted provider must NOT be assumed capable — that's the exact bug
        this feature exists to prevent (silently sending audio in the wrong language).
        A future provider typo or a new provider added without a support-map entry
        should route to the known-good multilingual fallback, not the unknown provider.
        """
        settings_mock = self._mock_settings(default="custom", fallback="openai", support_map={
            "openai": ["en", "fr"],
            # "custom" has no entry — should trigger fallback, not be treated as "supports all"
        })
        with patch("app.channels.whatsapp.voice_handler.settings", settings_mock):
            provider, is_fallback = _pick_tts_provider("ur")
            assert provider == "openai"   # fell back to the declared multilingual fallback
            assert is_fallback is True    # flag was set so the log line fires


# ── handle_voice_note integration tests ──────────────────────────────────────


import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path


def _make_fake_scratch():
    """Return a fake _scratch_dir context manager backed by a real temp dir."""
    tmpdir = Path(tempfile.mkdtemp())

    @asynccontextmanager
    async def _ctx():
        yield tmpdir

    return tmpdir, _ctx


def _base_patches(*, stt_language: str | None, stt_text: str):
    """Shared patch context for the orchestrator integration tests.

    Mocks everything except the TTS layer so tests can assert on what
    get_tts_provider_by_name is called with.
    """
    from app.channels.whatsapp.stt.base import TranscriptResult

    stt_result = TranscriptResult(text=stt_text, language=stt_language)

    stt_mock = MagicMock()
    stt_mock.transcribe = AsyncMock(return_value=stt_result)
    stt_mock.provider_name = "groq"

    contact_mock = MagicMock(id=uuid.uuid4())
    conv_mock = MagicMock(id=uuid.uuid4())

    return stt_mock, contact_mock, conv_mock


@pytest.mark.asyncio
async def test_unsupported_language_falls_back_to_text():
    """Orchestrator: STT detects an unsupported language → RAG runs, reply sent as text, TTS skipped."""
    from app.channels.whatsapp.voice_handler import handle_voice_note

    org_id = uuid.uuid4()
    contact_phone = "+32499000001"
    tmpdir, fake_scratch = _make_fake_scratch()

    try:
        stt_mock, contact_mock, conv_mock = _base_patches(
            stt_language="tr",  # Turkish — not in default VOICE_SUPPORTED_LANGUAGES
            stt_text="Merhaba, nasılsınız?",
        )

        with (
            patch("app.channels.whatsapp.voice_handler.get_credentials", new_callable=AsyncMock, return_value=("tok", "ph_id")),
            patch("app.channels.whatsapp.voice_handler._check_voice_rate_limit", new_callable=AsyncMock, return_value=True),
            patch("app.channels.whatsapp.voice_handler.download_voice_note", new_callable=AsyncMock, return_value=1000),
            patch("app.channels.whatsapp.voice_handler.probe_duration_seconds", new_callable=AsyncMock, return_value=5.0),
            patch("app.channels.whatsapp.voice_handler.get_stt_provider", return_value=stt_mock),
            patch("app.channels.whatsapp.voice_handler.async_session_maker") as mock_sm,
            patch("app.channels.whatsapp.voice_handler.contact_service") as mock_cs,
            patch("app.channels.whatsapp.voice_handler.conversation_service") as mock_cvs,
            patch("app.channels.whatsapp.voice_handler.send_text_message", new_callable=AsyncMock) as mock_text,
            patch("app.channels.whatsapp.voice_handler.get_tts_provider_by_name") as mock_tts_factory,
            patch("app.channels.whatsapp.voice_handler._scratch_dir", fake_scratch),
        ):
            mock_sm.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_sm.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_cs.get_or_create_contact_by_phone = AsyncMock(return_value=contact_mock)
            mock_cvs.get_or_create_channel_conversation = AsyncMock(return_value=conv_mock)
            mock_cvs.process_customer_message = AsyncMock(return_value="Üzgünüm, sadece İngilizce konuşabiliyorum.")

            await handle_voice_note(org_id, contact_phone, "Test User", "media_abc", "wamid_abc")

        mock_tts_factory.assert_not_called()
        mock_text.assert_called_once_with(org_id, contact_phone, "Üzgünüm, sadece İngilizce konuşabiliyorum.")
    finally:
        shutil.rmtree(str(tmpdir), ignore_errors=True)


@pytest.mark.asyncio
async def test_french_with_deepgram_default_wires_openai_tts():
    """Orchestrator: STT detects French, TTS_PROVIDER=deepgram → get_tts_provider_by_name called with 'openai'.

    This is the class-of-bug test: the helper functions (_language_supported, _pick_tts_provider)
    are correct, but the orchestrator wiring (what name is passed to get_tts_provider_by_name at
    line 332) is what actually matters. A unit test on the helpers alone won't catch a future
    regression where the wiring is broken.
    """
    from app.channels.whatsapp.voice_handler import handle_voice_note

    org_id = uuid.uuid4()
    contact_phone = "+32499000002"
    tmpdir, fake_scratch = _make_fake_scratch()

    try:
        stt_mock, contact_mock, conv_mock = _base_patches(
            stt_language="fr",
            stt_text="Bonjour, quels sont vos horaires?",
        )

        # TTS mock that records what provider name it was instantiated with
        tts_instance = MagicMock()
        tts_instance.provider_name = "openai"
        tts_instance.synthesize = AsyncMock(return_value=b"fake_mp3_bytes")

        # fake OGG conversion + upload/send so the pipeline completes
        fake_ogg = tmpdir / "tts_reply.ogg"
        fake_ogg.write_bytes(b"fake_ogg")

        settings_override = MagicMock()
        settings_override.TTS_PROVIDER = "deepgram"
        settings_override.TTS_MULTILINGUAL_FALLBACK_PROVIDER = "openai"
        settings_override.TTS_PROVIDER_LANGUAGE_SUPPORT = {
            "openai": ["en", "fr", "nl", "de"],
            "deepgram": ["en"],
        }
        settings_override.VOICE_SUPPORTED_LANGUAGES = ["en", "fr", "nl", "de"]
        settings_override.MAX_VOICE_NOTE_FILE_SIZE_MB = 16.0
        settings_override.MAX_VOICE_NOTE_DURATION_SECONDS = 120
        settings_override.MAX_VOICE_REPLY_CHARS = 500
        settings_override.VOICE_NOTE_RATE_LIMIT_PER_MINUTE = 5

        with (
            patch("app.channels.whatsapp.voice_handler.settings", settings_override),
            patch("app.channels.whatsapp.voice_handler.get_credentials", new_callable=AsyncMock, return_value=("tok", "ph_id")),
            patch("app.channels.whatsapp.voice_handler._check_voice_rate_limit", new_callable=AsyncMock, return_value=True),
            patch("app.channels.whatsapp.voice_handler.download_voice_note", new_callable=AsyncMock, return_value=1000),
            patch("app.channels.whatsapp.voice_handler.probe_duration_seconds", new_callable=AsyncMock, return_value=5.0),
            patch("app.channels.whatsapp.voice_handler.get_stt_provider", return_value=stt_mock),
            patch("app.channels.whatsapp.voice_handler.async_session_maker") as mock_sm,
            patch("app.channels.whatsapp.voice_handler.contact_service") as mock_cs,
            patch("app.channels.whatsapp.voice_handler.conversation_service") as mock_cvs,
            patch("app.channels.whatsapp.voice_handler.get_tts_provider_by_name", return_value=tts_instance) as mock_tts_factory,
            patch("app.channels.whatsapp.voice_handler.to_ogg_opus_mono", new_callable=AsyncMock),
            patch("app.channels.whatsapp.voice_handler.upload_voice_reply", new_callable=AsyncMock, return_value="reply_media_id"),
            patch("app.channels.whatsapp.voice_handler.send_audio_message", new_callable=AsyncMock, return_value="wamid_out"),
            patch("app.channels.whatsapp.voice_handler._scratch_dir", fake_scratch),
        ):
            mock_sm.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_sm.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_cs.get_or_create_contact_by_phone = AsyncMock(return_value=contact_mock)
            mock_cvs.get_or_create_channel_conversation = AsyncMock(return_value=conv_mock)
            mock_cvs.process_customer_message = AsyncMock(return_value="Nous sommes ouverts de 9h à 18h.")

            await handle_voice_note(org_id, contact_phone, "Client FR", "media_fr", "wamid_fr")

        # Key assertion: the orchestrator wired the correct provider name + the
        # per-org resolved key into the factory.
        mock_tts_factory.assert_called_once_with("openai", "test-key")
        # And the TTS provider was actually invoked (not short-circuited to text)
        tts_instance.synthesize.assert_called_once_with("Nous sommes ouverts de 9h à 18h.")
    finally:
        shutil.rmtree(str(tmpdir), ignore_errors=True)


@pytest.mark.asyncio
async def test_missing_fallback_api_key_sends_text_not_500():
    """Orchestrator: fallback provider has no API key → RuntimeError caught, reply sent as text.

    Reproduces the config-mismatch scenario: TTS_PROVIDER=deepgram + OPENAI_API_KEY unset.
    French note comes in, _pick_tts_provider picks openai, get_tts_provider_by_name raises
    RuntimeError. The pipeline must catch this and send text rather than propagate a 500.
    """
    from app.channels.whatsapp.voice_handler import handle_voice_note

    org_id = uuid.uuid4()
    contact_phone = "+32499000003"
    tmpdir, fake_scratch = _make_fake_scratch()

    try:
        stt_mock, contact_mock, conv_mock = _base_patches(
            stt_language="fr",
            stt_text="Bonjour!",
        )

        settings_override = MagicMock()
        settings_override.TTS_PROVIDER = "deepgram"
        settings_override.TTS_MULTILINGUAL_FALLBACK_PROVIDER = "openai"
        settings_override.TTS_PROVIDER_LANGUAGE_SUPPORT = {
            "openai": ["en", "fr", "nl", "de"],
            "deepgram": ["en"],
        }
        settings_override.VOICE_SUPPORTED_LANGUAGES = ["en", "fr", "nl", "de"]
        settings_override.MAX_VOICE_NOTE_FILE_SIZE_MB = 16.0
        settings_override.MAX_VOICE_NOTE_DURATION_SECONDS = 120
        settings_override.MAX_VOICE_REPLY_CHARS = 500
        settings_override.VOICE_NOTE_RATE_LIMIT_PER_MINUTE = 5

        with (
            patch("app.channels.whatsapp.voice_handler.settings", settings_override),
            patch("app.channels.whatsapp.voice_handler.get_credentials", new_callable=AsyncMock, return_value=("tok", "ph_id")),
            patch("app.channels.whatsapp.voice_handler._check_voice_rate_limit", new_callable=AsyncMock, return_value=True),
            patch("app.channels.whatsapp.voice_handler.download_voice_note", new_callable=AsyncMock, return_value=1000),
            patch("app.channels.whatsapp.voice_handler.probe_duration_seconds", new_callable=AsyncMock, return_value=5.0),
            patch("app.channels.whatsapp.voice_handler.get_stt_provider", return_value=stt_mock),
            patch("app.channels.whatsapp.voice_handler.async_session_maker") as mock_sm,
            patch("app.channels.whatsapp.voice_handler.contact_service") as mock_cs,
            patch("app.channels.whatsapp.voice_handler.conversation_service") as mock_cvs,
            # Simulate missing OPENAI_API_KEY — factory raises RuntimeError
            patch(
                "app.channels.whatsapp.voice_handler.get_tts_provider_by_name",
                side_effect=RuntimeError("TTS provider 'openai' requested but OPENAI_API_KEY is not set"),
            ),
            patch("app.channels.whatsapp.voice_handler.send_text_message", new_callable=AsyncMock) as mock_text,
            patch("app.channels.whatsapp.voice_handler._scratch_dir", fake_scratch),
        ):
            mock_sm.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_sm.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_cs.get_or_create_contact_by_phone = AsyncMock(return_value=contact_mock)
            mock_cvs.get_or_create_channel_conversation = AsyncMock(return_value=conv_mock)
            mock_cvs.process_customer_message = AsyncMock(return_value="Bonjour, comment puis-je vous aider?")

            # Must not raise — should degrade to text
            await handle_voice_note(org_id, contact_phone, "Client FR", "media_missing_key", "wamid_missing_key")

        mock_text.assert_called_once_with(
            org_id, contact_phone, "Bonjour, comment puis-je vous aider?"
        )
    finally:
        shutil.rmtree(str(tmpdir), ignore_errors=True)


@pytest.mark.asyncio
async def test_no_org_stt_key_falls_back_to_text_not_silence():
    """Tenant isolation path: the org has no STT key and there's no platform
    fallback → resolve_provider_key returns None → the REAL get_stt_provider
    raises RuntimeError → the pipeline degrades to a text reply ("never
    silence"), never crashing the task with no reply at all."""
    from app.channels.whatsapp.voice_handler import handle_voice_note

    org_id = uuid.uuid4()
    contact_phone = "+32499000005"
    tmpdir, fake_scratch = _make_fake_scratch()

    try:
        stt_mock, contact_mock, conv_mock = _base_patches(stt_language="en", stt_text="hi")

        with (
            patch("app.channels.whatsapp.voice_handler.get_credentials", new_callable=AsyncMock, return_value=("tok", "ph_id")),
            patch("app.channels.whatsapp.voice_handler._check_voice_rate_limit", new_callable=AsyncMock, return_value=True),
            patch("app.channels.whatsapp.voice_handler.download_voice_note", new_callable=AsyncMock, return_value=1000),
            patch("app.channels.whatsapp.voice_handler.probe_duration_seconds", new_callable=AsyncMock, return_value=5.0),
            # No key for this org, no platform fallback → None (overrides the autouse stub).
            patch("app.channels.whatsapp.voice_handler.resolve_provider_key", new_callable=AsyncMock, return_value=None),
            patch("app.channels.whatsapp.voice_handler.async_session_maker") as mock_sm,
            # Real get_stt_provider runs — with a None key it raises RuntimeError.
            patch("app.channels.whatsapp.voice_handler.send_text_message", new_callable=AsyncMock) as mock_text,
            patch("app.channels.whatsapp.voice_handler.get_tts_provider_by_name") as mock_tts_factory,
            patch("app.channels.whatsapp.voice_handler._scratch_dir", fake_scratch),
        ):
            mock_sm.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_sm.return_value.__aexit__ = AsyncMock(return_value=False)
            # Must NOT raise — degrades to a text reply.
            await handle_voice_note(org_id, contact_phone, "Test", "media_nostt", "wamid_nostt")

        mock_tts_factory.assert_not_called()  # never reached TTS
        mock_text.assert_called_once()
        assert "voice message" in mock_text.call_args[0][2].lower()  # the _STT_FALLBACK text
    finally:
        shutil.rmtree(str(tmpdir), ignore_errors=True)


@pytest.mark.asyncio
async def test_voice_reply_path_requests_spoken_booking_readback():
    """The spoken path must tell the pipeline reply_channel="voice" so a booking
    confirmation spells the name/email back (STT mis-hear guard), matching the
    Retell voice channel. The unsupported-language text fallback stays "text"."""
    from app.channels.whatsapp.voice_handler import handle_voice_note

    org_id = uuid.uuid4()
    contact_phone = "+32499000004"
    tmpdir, fake_scratch = _make_fake_scratch()

    try:
        stt_mock, contact_mock, conv_mock = _base_patches(
            stt_language="en",
            stt_text="Yeah, John Smith, john dot smith at gmail dot com",
        )
        tts_instance = MagicMock()
        tts_instance.provider_name = "openai"
        tts_instance.synthesize = AsyncMock(return_value=b"fake_mp3")

        settings_override = MagicMock()
        settings_override.TTS_PROVIDER = "openai"
        settings_override.TTS_MULTILINGUAL_FALLBACK_PROVIDER = "openai"
        settings_override.TTS_PROVIDER_LANGUAGE_SUPPORT = {"openai": ["en", "fr", "nl", "de"]}
        settings_override.VOICE_SUPPORTED_LANGUAGES = ["en", "fr", "nl", "de"]
        settings_override.MAX_VOICE_NOTE_FILE_SIZE_MB = 16.0
        settings_override.MAX_VOICE_NOTE_DURATION_SECONDS = 120
        settings_override.MAX_VOICE_REPLY_CHARS = 500
        settings_override.VOICE_NOTE_RATE_LIMIT_PER_MINUTE = 5

        with (
            patch("app.channels.whatsapp.voice_handler.settings", settings_override),
            patch("app.channels.whatsapp.voice_handler.get_credentials", new_callable=AsyncMock, return_value=("tok", "ph_id")),
            patch("app.channels.whatsapp.voice_handler._check_voice_rate_limit", new_callable=AsyncMock, return_value=True),
            patch("app.channels.whatsapp.voice_handler.download_voice_note", new_callable=AsyncMock, return_value=1000),
            patch("app.channels.whatsapp.voice_handler.probe_duration_seconds", new_callable=AsyncMock, return_value=5.0),
            patch("app.channels.whatsapp.voice_handler.get_stt_provider", return_value=stt_mock),
            patch("app.channels.whatsapp.voice_handler.async_session_maker") as mock_sm,
            patch("app.channels.whatsapp.voice_handler.contact_service") as mock_cs,
            patch("app.channels.whatsapp.voice_handler.conversation_service") as mock_cvs,
            patch("app.channels.whatsapp.voice_handler.get_tts_provider_by_name", return_value=tts_instance),
            patch("app.channels.whatsapp.voice_handler.to_ogg_opus_mono", new_callable=AsyncMock),
            patch("app.channels.whatsapp.voice_handler.upload_voice_reply", new_callable=AsyncMock, return_value="rmid"),
            patch("app.channels.whatsapp.voice_handler.send_audio_message", new_callable=AsyncMock, return_value="wamid_out"),
            patch("app.channels.whatsapp.voice_handler._scratch_dir", fake_scratch),
        ):
            mock_sm.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_sm.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_cs.get_or_create_contact_by_phone = AsyncMock(return_value=contact_mock)
            mock_cvs.get_or_create_channel_conversation = AsyncMock(return_value=conv_mock)
            mock_cvs.process_customer_message = AsyncMock(return_value="Is that all correct?")

            await handle_voice_note(org_id, contact_phone, "John", "media_en", "wamid_en")

        assert mock_cvs.process_customer_message.call_args.kwargs.get("reply_channel") == "voice"
    finally:
        shutil.rmtree(str(tmpdir), ignore_errors=True)
