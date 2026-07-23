"""Deepgram Aura-2 TTS — alternate provider.

Returns raw WAV bytes (linear16, 48 kHz). The caller converts to ogg/opus.
Deepgram's voice API is simple: POST JSON body with {"text": "..."}, stream
back audio.
"""

import httpx
import structlog

from app.channels.whatsapp.tts.base import BaseTTSProvider, TTSError

logger = structlog.get_logger()

_TTS_URL = "https://api.deepgram.com/v1/speak"
_MODEL = "aura-2-en-us"
_TIMEOUT = 60.0


class DeepgramTTS(BaseTTSProvider):
    provider_name = "deepgram"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def synthesize(self, text: str) -> bytes:
        """POST to Deepgram's speak endpoint and return WAV bytes."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                _TTS_URL,
                params={
                    "model": _MODEL,
                    "encoding": "linear16",
                    "sample_rate": "48000",
                    "container": "wav",
                },
                headers={
                    "Authorization": f"Token {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={"text": text},
            )

        if response.status_code != 200:
            raise TTSError(
                f"Deepgram TTS returned HTTP {response.status_code}: {response.text[:300]}"
            )

        audio = response.content
        if not audio:
            raise TTSError("Deepgram TTS returned empty audio bytes")

        logger.info("deepgram_tts_ok", bytes=len(audio), model=_MODEL)
        return audio
