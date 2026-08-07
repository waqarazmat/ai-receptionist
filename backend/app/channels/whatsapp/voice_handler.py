"""End-to-end WhatsApp voice note pipeline.

Flow for every inbound audio message:
    webhook → [Arq task] → handle_voice_note()
        1.  Fetch org credentials
        2.  Per-user rate limit  (voice notes cost STT + LLM + TTS money)
        3.  Check declared file_size BEFORE download (from Graph API metadata)
        4.  Download voice note
        5.  Check audio duration  (after download, before spending on STT)
        6.  STT  — raw OGG sent directly; no WAV conversion needed
        7.  Language guard  — fall back to text for unsupported languages
        8.  RAG / answer generation  (reuses existing text pipeline exactly)
        9.  TTS char cap  — long answers sent as text (better UX + cost control)
       10.  TTS synthesis  (with one retry on transient failure)
       11.  Convert TTS output → OGG/OPUS  (ffmpeg)
       12.  Upload + send as WhatsApp audio message
       → At every failure point: fall back to a text reply, never silence.

All I/O is async. ffmpeg calls run in asyncio.to_thread.
Temp files live in a per-request directory deleted in a finally block.
"""

import asyncio
import contextlib
import shutil
import time
import uuid
from pathlib import Path
from typing import AsyncIterator

import structlog

from app.channels.whatsapp.audio_converter import (
    AudioConversionError,
    probe_duration_seconds,
    to_ogg_opus_mono,  # only used on the TTS output leg (inbound OGG goes to STT as-is)
)
from app.channels.whatsapp.media_client import (
    MediaDownloadError,
    MediaUploadError,
    download_voice_note,
    send_audio_message,
    upload_voice_reply,
)
from app.channels.whatsapp.message_sender import (
    WhatsAppCredentialsError,
    get_credentials,
    send_text_message,
)
from app.channels.whatsapp.stt.base import STTError
from app.channels.whatsapp.stt.factory import get_stt_provider
from app.channels.whatsapp.tts.base import TTSError
from app.channels.whatsapp.tts.factory import get_tts_provider_by_name
from app.config import settings
from app.db.engine import async_session_maker
from app.db.redis import redis_client
from app.models.enums import Channel
from app.services import contact_service, conversation_service
from app.services.api_key_service import resolve_provider_key

logger = structlog.get_logger()

_STT_FALLBACK = (
    "Sorry, I had trouble understanding your voice message. "
    "Could you type out your question instead?"
)
_RATE_LIMITED_MSG = (
    "You're sending voice notes very quickly — please wait a moment before trying again."
)


# ── helpers ────────────────────────────────────────────────────────────────


@contextlib.asynccontextmanager
async def _scratch_dir() -> AsyncIterator[Path]:
    """Unique temp directory, always deleted after the job (even on exception)."""
    base = Path(settings.TEMP_AUDIO_DIR)
    base.mkdir(parents=True, exist_ok=True)
    session_dir = base / str(uuid.uuid4())
    session_dir.mkdir()
    try:
        yield session_dir
    finally:
        await asyncio.to_thread(shutil.rmtree, str(session_dir), ignore_errors=True)


async def _check_voice_rate_limit(contact_phone: str) -> bool:
    """Return True if this phone number is within the allowed voice-note rate.

    Uses a 1-minute fixed window in Redis (same pattern as other rate limits
    in this codebase). Fails open on Redis error so a cache blip doesn't
    block legitimate customers.
    """
    try:
        bucket = int(time.time() // 60)
        key = f"voice_rate:{contact_phone}:{bucket}"
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, 90)  # 90 s > 60 s window, safe margin
        return count <= settings.VOICE_NOTE_RATE_LIMIT_PER_MINUTE
    except Exception:  # noqa: BLE001
        return True  # fail open


def _language_supported(language: str | None) -> bool:
    """True if `language` is in VOICE_SUPPORTED_LANGUAGES.

    Set VOICE_SUPPORTED_LANGUAGES=["*"] to accept every language.
    None (unknown) is optimistically allowed — the TTS step will still
    attempt synthesis and fall back to text on failure.
    """
    allowed = settings.VOICE_SUPPORTED_LANGUAGES
    if "*" in allowed:
        return True
    if language is None:
        return True
    return language.lower() in {l.lower() for l in allowed}


def _pick_tts_provider(language: str | None) -> tuple[str, bool]:
    """Return (provider_name, is_fallback) for the given detected language.

    Logic (fully config-driven — no hardcoded language names):
      1. Check if TTS_PROVIDER supports `language` via TTS_PROVIDER_LANGUAGE_SUPPORT.
      2. If yes → use it (is_fallback=False).
      3. If no → try TTS_MULTILINGUAL_FALLBACK_PROVIDER.
      4. If that also can't handle it → return (fallback_name, True) anyway;
         voice_handler will attempt synthesis and catch any provider error.

    Returns (provider_name, is_fallback) where is_fallback=True signals that
    a log line should be emitted explaining why the switch happened.
    """
    support_map = settings.TTS_PROVIDER_LANGUAGE_SUPPORT  # dict[str, list[str]]
    default = (settings.TTS_PROVIDER or "openai").lower()
    fallback = (settings.TTS_MULTILINGUAL_FALLBACK_PROVIDER or "openai").lower()

    if language is None:
        # Unknown language → use default and let the provider handle it.
        return default, False

    lang = language.lower()

    default_langs = {l.lower() for l in support_map.get(default, [])}
    # Fail-closed: if the default provider has no entry in TTS_PROVIDER_LANGUAGE_SUPPORT,
    # we don't know what it supports — trigger fallback rather than risk sending audio in
    # a language the provider can't handle. An explicit entry is required to use the default.
    if default_langs and lang in default_langs:
        return default, False

    # Default can't handle it — switch to the multilingual fallback.
    return fallback, True


async def _with_retry(coro_factory, *, retries: int = 1, delay: float = 1.5):
    """Call `coro_factory()` and retry up to `retries` times on exception.

    Designed for transient 429/5xx from STT/TTS providers. One retry is
    almost always enough; more than one adds too much latency for a chat bot.
    """
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return await coro_factory()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < retries:
                await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]


# ── main pipeline ──────────────────────────────────────────────────────────


async def handle_voice_note(
    org_id: uuid.UUID,
    contact_phone: str,
    contact_name: str | None,
    media_id: str,
    wamid: str,
) -> None:
    """Orchestrate the full voice-note → voice-reply pipeline.

    Called by the Arq task `process_whatsapp_voice_message` after dedup.
    The customer always receives a reply — either audio or a text fallback.
    """
    t_start = time.monotonic()
    log = logger.bind(org_id=str(org_id), contact_phone=contact_phone, wamid=wamid)
    log.info("voice_pipeline_start", media_id=media_id)

    # ── 1. Credentials ───────────────────────────────────────────────────────
    try:
        access_token, phone_number_id = await get_credentials(org_id)
    except WhatsAppCredentialsError as exc:
        log.warning("voice_pipeline_no_credentials", error=str(exc))
        return  # No credentials → can't send anything; give up silently.

    # ── 2. Per-user rate limit ───────────────────────────────────────────────
    if not await _check_voice_rate_limit(contact_phone):
        log.warning(
            "voice_rate_limit_exceeded",
            limit=settings.VOICE_NOTE_RATE_LIMIT_PER_MINUTE,
        )
        await send_text_message(org_id, contact_phone, _RATE_LIMITED_MSG)
        return

    max_bytes = int(settings.MAX_VOICE_NOTE_FILE_SIZE_MB * 1_048_576)

    async with _scratch_dir() as tmpdir:
        # Raw inbound voice note (ogg/opus from Meta CDN)
        raw_path = tmpdir / "voice_note.ogg"
        # TTS synthesis output (mp3 from OpenAI, wav from Deepgram)
        tts_raw_path = tmpdir / "tts_out.bin"
        # Final reply converted to WhatsApp-compatible ogg/opus
        ogg_path = tmpdir / "tts_reply.ogg"

        # ── 3+4. Download (size checked from metadata BEFORE download) ───────
        try:
            t0 = time.monotonic()
            # download_voice_note now calls _resolve_media_metadata first and
            # checks file_size before streaming, so we reject oversized notes
            # before wasting bandwidth (gap #4 from the review).
            bytes_downloaded = await download_voice_note(
                media_id, access_token, raw_path, max_bytes
            )
            log.info(
                "voice_download_complete",
                bytes=bytes_downloaded,
                ms=round((time.monotonic() - t0) * 1000),
            )
        except MediaDownloadError as exc:
            log.warning("voice_download_failed", error=str(exc))
            await send_text_message(org_id, contact_phone, _STT_FALLBACK)
            return

        # ── 5. Duration check (after download, before billing STT) ──────────
        duration = await probe_duration_seconds(raw_path)
        if duration > 0 and duration > settings.MAX_VOICE_NOTE_DURATION_SECONDS:
            log.warning("voice_note_too_long", duration_s=duration)
            await send_text_message(
                org_id,
                contact_phone,
                f"Your voice note is {int(duration)}s — please keep it under "
                f"{settings.MAX_VOICE_NOTE_DURATION_SECONDS}s.",
            )
            return

        # ── 6. STT — raw OGG sent directly, no WAV conversion needed ────────
        # Both Groq and OpenAI Whisper accept ogg/opus natively. Converting to
        # WAV first (as the original code did) adds ~150-300ms latency and an
        # extra ffmpeg failure point with no quality benefit (gap #2).
        # Resolve the STT key for THIS org (tenant isolation): the org's own
        # groq/openai key, else the platform key only if ALLOW_PLATFORM_KEY_FALLBACK.
        # get_stt_provider() raises RuntimeError when no key is available or the
        # provider is unknown — that must NOT crash the task silently (this
        # pipeline's contract is "never silence, always fall back to text"), so a
        # missing/unconfigured key degrades to the same helpful text reply.
        stt_provider_name = (settings.STT_PROVIDER or "groq").lower().strip()
        async with async_session_maker() as db:
            stt_key = await resolve_provider_key(db, org_id, stt_provider_name)
        try:
            stt = get_stt_provider(stt_provider_name, stt_key)
        except RuntimeError as exc:
            log.warning("voice_stt_provider_unconfigured", org_id=str(org_id), error=str(exc))
            await send_text_message(org_id, contact_phone, _STT_FALLBACK)
            return
        try:
            t0 = time.monotonic()
            result = await _with_retry(lambda: stt.transcribe(raw_path))
            log.info(
                "voice_stt_complete",
                provider=stt.provider_name,
                chars=len(result.text),
                language=result.language,
                ms=round((time.monotonic() - t0) * 1000),
            )
        except STTError as exc:
            log.warning("voice_stt_failed", provider=stt.provider_name, error=str(exc))
            await send_text_message(org_id, contact_phone, _STT_FALLBACK)
            return

        log.info("voice_transcript", preview=result.text[:200])

        # ── 7. Language guard + TTS provider selection ──────────────────────
        # If STT detected a language outside VOICE_SUPPORTED_LANGUAGES, run RAG
        # but deliver the answer as text (TTS in that language would be poor UX).
        if not _language_supported(result.language):
            log.info(
                "voice_language_not_supported_text_fallback",
                detected=result.language,
                supported=settings.VOICE_SUPPORTED_LANGUAGES,
            )
            async with async_session_maker() as db:
                contact = await contact_service.get_or_create_contact_by_phone(
                    db, org_id, contact_phone, Channel.whatsapp, contact_name
                )
                conversation = await conversation_service.get_or_create_channel_conversation(
                    db, org_id, contact.id, Channel.whatsapp
                )
                response_text = await conversation_service.process_customer_message(
                    db, org_id, conversation.id, result.text
                )
            if response_text:
                await send_text_message(org_id, contact_phone, response_text)
            return

        # Language is supported — pick the right TTS provider for it.
        tts_provider_name, is_lang_fallback = _pick_tts_provider(result.language)
        if is_lang_fallback:
            log.info(
                "voice_tts_language_fallback",
                detected_language=result.language,
                default_provider=settings.TTS_PROVIDER,
                using_provider=tts_provider_name,
            )

        # ── 8. RAG / answer generation ───────────────────────────────────────
        t0 = time.monotonic()
        async with async_session_maker() as db:
            contact = await contact_service.get_or_create_contact_by_phone(
                db, org_id, contact_phone, Channel.whatsapp, contact_name
            )
            conversation = await conversation_service.get_or_create_channel_conversation(
                db, org_id, contact.id, Channel.whatsapp
            )
            # reply_channel="voice": this answer will be spoken back as a voice
            # note, so a booking confirmation spells the name/email (STT mis-hear
            # guard), same as the Retell voice channel.
            response_text = await conversation_service.process_customer_message(
                db, org_id, conversation.id, result.text, reply_channel="voice"
            )
        log.info("voice_rag_complete", ms=round((time.monotonic() - t0) * 1000))

        if response_text is None:
            log.info("voice_staff_takeover_no_reply")
            return

        # ── 9. TTS char cap ──────────────────────────────────────────────────
        # Long answers make poor voice UX and cost more on character-billed TTS
        # APIs. Anything over the cap gets sent as text instead (gap #8).
        if len(response_text) > settings.MAX_VOICE_REPLY_CHARS:
            log.info(
                "voice_reply_too_long_sending_text",
                chars=len(response_text),
                cap=settings.MAX_VOICE_REPLY_CHARS,
            )
            await send_text_message(org_id, contact_phone, response_text)
            return

        # ── 10. TTS (with one retry on transient failure) ────────────────────
        # Resolve the chosen TTS provider's key for THIS org (same isolation
        # rule as STT). RuntimeError from get_tts_provider_by_name (no key /
        # unknown provider) is caught here alongside TTSError so a config gap
        # falls back to a text reply cleanly instead of bubbling up as a 500.
        async with async_session_maker() as db:
            tts_key = await resolve_provider_key(db, org_id, tts_provider_name)
        try:
            tts = get_tts_provider_by_name(tts_provider_name, tts_key)
            t0 = time.monotonic()
            audio_bytes = await _with_retry(lambda: tts.synthesize(response_text))
            await asyncio.to_thread(tts_raw_path.write_bytes, audio_bytes)
            log.info(
                "voice_tts_complete",
                provider=tts.provider_name,
                bytes=len(audio_bytes),
                ms=round((time.monotonic() - t0) * 1000),
            )
        except (TTSError, RuntimeError) as exc:
            log.warning("voice_tts_failed", provider=tts_provider_name, error=str(exc))
            await send_text_message(org_id, contact_phone, response_text)
            return

        # ── 11. Convert TTS output → OGG/OPUS for WhatsApp ──────────────────
        # The exact MIME type audio/ogg; codecs=opus is required for WhatsApp
        # to show the reply as a voice bubble (with waveform), not a file
        # attachment (gap #1 — fixed in media_client.upload_voice_reply).
        try:
            t0 = time.monotonic()
            await to_ogg_opus_mono(tts_raw_path, ogg_path)
            log.info("voice_ogg_conversion_ms", ms=round((time.monotonic() - t0) * 1000))
        except AudioConversionError as exc:
            log.warning("voice_ogg_conversion_failed", error=str(exc))
            await send_text_message(org_id, contact_phone, response_text)
            return

        # ── 12. Upload + send ────────────────────────────────────────────────
        try:
            t0 = time.monotonic()
            reply_media_id = await upload_voice_reply(ogg_path, access_token, phone_number_id)
            log.info("voice_upload_ms", ms=round((time.monotonic() - t0) * 1000))

            wamid_out = await send_audio_message(org_id, contact_phone, reply_media_id)
            log.info(
                "voice_pipeline_complete",
                wamid_out=wamid_out,
                total_ms=round((time.monotonic() - t_start) * 1000),
            )
        except (MediaUploadError, Exception) as exc:  # noqa: BLE001
            log.warning("voice_audio_send_failed", error=str(exc))
            await send_text_message(org_id, contact_phone, response_text)
