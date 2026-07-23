"""OpenAI TTS — tts-1 model (lowest latency, good quality).

Returns mp3 bytes. The caller (voice_handler) converts to ogg/opus
via audio_converter.to_ogg_opus_mono before uploading to WhatsApp.
"""

import httpx
import structlog

from app.channels.whatsapp.tts.base import BaseTTSProvider, TTSError

logger = structlog.get_logger()

_TTS_URL = "https://api.openai.com/v1/audio/speech"
_MODEL = "tts-1"
_VOICE = "nova"   # friendly, natural-sounding; easy to change via a future settings field
_TIMEOUT = 60.0


class OpenAITTS(BaseTTSProvider):
    provider_name = "openai"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def synthesize(self, text: str) -> bytes:
        """POST to OpenAI's TTS endpoint and return mp3 bytes."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                _TTS_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": _MODEL,
                    "voice": _VOICE,
                    "input": text,
                    "response_format": "mp3",
                },
            )

        if response.status_code != 200:
            raise TTSError(
                f"OpenAI TTS returned HTTP {response.status_code}: {response.text[:300]}"
            )

        audio = response.content
        if not audio:
            raise TTSError("OpenAI TTS returned empty audio bytes")

        logger.info("openai_tts_ok", bytes=len(audio), model=_MODEL, voice=_VOICE)
        return audio
