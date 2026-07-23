"""OpenAI Whisper STT — gpt-4o-mini-transcribe (fallback / alternative).

Sends raw OGG directly — no WAV pre-conversion needed.
"""

from pathlib import Path

import httpx
import structlog

from app.channels.whatsapp.stt.base import BaseSTTProvider, STTError, TranscriptResult

logger = structlog.get_logger()

_TRANSCRIPTION_URL = "https://api.openai.com/v1/audio/transcriptions"
_MODEL = "gpt-4o-mini-transcribe"
_TIMEOUT = 60.0


class OpenAIWhisperSTT(BaseSTTProvider):
    provider_name = "openai"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def transcribe(self, audio_path: Path) -> TranscriptResult:
        """POST the raw OGG to OpenAI and return transcript + detected language."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            with audio_path.open("rb") as fh:
                response = await client.post(
                    _TRANSCRIPTION_URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    data={"model": _MODEL, "response_format": "verbose_json"},
                    files={"file": (audio_path.name, fh, "audio/ogg")},
                )

        if response.status_code != 200:
            raise STTError(
                f"OpenAI STT returned HTTP {response.status_code}: {response.text[:300]}"
            )

        data = response.json()
        text = (data.get("text") or "").strip()
        if not text:
            raise STTError("OpenAI returned an empty transcript")

        # OpenAI verbose_json returns ISO 639-1 codes directly (e.g. "en", "ur")
        language = data.get("language")

        logger.info("openai_stt_ok", chars=len(text), model=_MODEL, language=language)
        return TranscriptResult(text=text, language=language)
