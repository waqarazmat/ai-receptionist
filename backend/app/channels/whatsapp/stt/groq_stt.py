"""Groq Whisper STT — whisper-large-v3-turbo.

Groq's transcription endpoint is OpenAI-compatible.  We send the raw OGG
file directly — no WAV conversion needed (Groq accepts ogg/m4a/webm).
The response includes a `language` field (ISO 639-1) which we surface so
voice_handler can fall back to text for unsupported languages.
"""

from pathlib import Path

import httpx
import structlog

from app.channels.whatsapp.stt.base import BaseSTTProvider, STTError, TranscriptResult

logger = structlog.get_logger()

_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
_MODEL = "whisper-large-v3-turbo"
_TIMEOUT = 60.0


class GroqWhisperSTT(BaseSTTProvider):
    provider_name = "groq"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def transcribe(self, audio_path: Path) -> TranscriptResult:
        """POST the raw OGG to Groq and return transcript + detected language."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            with audio_path.open("rb") as fh:
                response = await client.post(
                    _TRANSCRIPTION_URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    # verbose_json includes the detected language field
                    data={"model": _MODEL, "response_format": "verbose_json"},
                    files={"file": (audio_path.name, fh, "audio/ogg")},
                )

        if response.status_code != 200:
            raise STTError(
                f"Groq STT returned HTTP {response.status_code}: {response.text[:300]}"
            )

        data = response.json()
        text = (data.get("text") or "").strip()
        if not text:
            raise STTError("Groq returned an empty transcript")

        language = data.get("language")  # e.g. "english", "urdu" — Groq uses full names
        # Normalize to ISO 639-1 code where possible
        language_code = _groq_lang_to_iso(language)

        logger.info("groq_stt_ok", chars=len(text), model=_MODEL, language=language_code)
        return TranscriptResult(text=text, language=language_code)


# Groq returns full language names; map common ones to ISO 639-1 codes.
# Unmapped languages fall through as None so voice_handler treats them as unknown.
_GROQ_LANG_MAP: dict[str, str] = {
    "english": "en", "spanish": "es", "french": "fr", "german": "de",
    "arabic": "ar", "urdu": "ur", "hindi": "hi", "portuguese": "pt",
    "italian": "it", "dutch": "nl", "russian": "ru", "chinese": "zh",
    "japanese": "ja", "korean": "ko", "turkish": "tr", "polish": "pl",
}


def _groq_lang_to_iso(lang: str | None) -> str | None:
    if not lang:
        return None
    return _GROQ_LANG_MAP.get(lang.lower(), lang.lower()[:2])
