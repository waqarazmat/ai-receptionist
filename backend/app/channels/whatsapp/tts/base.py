"""Abstract TTS provider interface."""

from abc import ABC, abstractmethod


class TTSError(Exception):
    """Speech synthesis failed. Callers should fall back to a text reply."""


class BaseTTSProvider(ABC):
    """Text-to-speech abstraction.

    Concrete implementations receive a plain-text string and return raw
    audio bytes (mp3, wav — format depends on the provider).  The bytes are
    then converted to OGG/OPUS by audio_converter.to_ogg_opus_mono before
    being sent as a WhatsApp audio message.

    Implementations must raise TTSError on any failure.
    """

    provider_name: str = "unknown"

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Convert `text` to audio and return the raw bytes.

        Raises:
            TTSError: on API failure, network error, or empty response.
        """
