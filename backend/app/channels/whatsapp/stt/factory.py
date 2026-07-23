"""STT provider factory — returns the configured implementation.

Switch providers without touching business logic:
    STT_PROVIDER=groq    →  GroqWhisperSTT   (default, fastest)
    STT_PROVIDER=openai  →  OpenAIWhisperSTT
"""

from app.channels.whatsapp.stt.base import BaseSTTProvider
from app.config import settings


def get_stt_provider() -> BaseSTTProvider:
    """Instantiate and return the STT provider named by STT_PROVIDER."""
    provider = (settings.STT_PROVIDER or "groq").lower().strip()

    if provider == "groq":
        if not settings.GROQ_API_KEY:
            raise RuntimeError(
                "STT_PROVIDER=groq but GROQ_API_KEY is not set in environment"
            )
        from app.channels.whatsapp.stt.groq_stt import GroqWhisperSTT
        return GroqWhisperSTT(settings.GROQ_API_KEY)

    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise RuntimeError(
                "STT_PROVIDER=openai but OPENAI_API_KEY is not set in environment"
            )
        from app.channels.whatsapp.stt.openai_stt import OpenAIWhisperSTT
        return OpenAIWhisperSTT(settings.OPENAI_API_KEY)

    raise RuntimeError(
        f"Unknown STT_PROVIDER={provider!r} — valid values: 'groq', 'openai'"
    )
