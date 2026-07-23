"""Abstract STT provider interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


class STTError(Exception):
    """Transcription failed. Callers should fall back to a text reply."""


@dataclass
class TranscriptResult:
    """Returned by every STT provider.

    `language` is the ISO 639-1 code detected by the model (e.g. "en", "ur",
    "ar").  It is None when the provider doesn't expose it.  voice_handler.py
    uses it to decide whether the configured TTS voice can handle the reply.
    """

    text: str
    language: str | None = field(default=None)


class BaseSTTProvider(ABC):
    """Speech-to-text abstraction.

    Implementations receive a local audio file path (the raw inbound OGG —
    both Groq and OpenAI Whisper accept OGG/OPUS natively, so no WAV
    conversion is needed before STT) and return a TranscriptResult.

    Raises STTError on any failure so voice_handler can degrade gracefully.
    """

    provider_name: str = "unknown"

    @abstractmethod
    async def transcribe(self, audio_path: Path) -> TranscriptResult:
        """Transcribe the audio at `audio_path`.

        Raises:
            STTError: on API failure, network error, or empty transcript.
        """
