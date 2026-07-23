"""TTS provider factory — returns the configured implementation.

Switch providers without touching business logic:
    TTS_PROVIDER=openai    →  OpenAITTS    (default)
    TTS_PROVIDER=deepgram  →  DeepgramTTS

`get_tts_provider()` returns the default configured provider.
`get_tts_provider_by_name(name)` instantiates any named provider directly —
used by voice_handler.py when the default provider can't speak the detected
language and a multilingual fallback provider is needed.
"""

from app.channels.whatsapp.tts.base import BaseTTSProvider
from app.config import settings


def get_tts_provider() -> BaseTTSProvider:
    """Instantiate and return the TTS provider named by TTS_PROVIDER."""
    return get_tts_provider_by_name(settings.TTS_PROVIDER or "openai")


def get_tts_provider_by_name(name: str) -> BaseTTSProvider:
    """Instantiate a TTS provider by explicit name.

    Raises RuntimeError if the provider is unknown or its API key is missing.
    """
    provider = name.lower().strip()

    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise RuntimeError(
                "TTS provider 'openai' requested but OPENAI_API_KEY is not set"
            )
        from app.channels.whatsapp.tts.openai_tts import OpenAITTS
        return OpenAITTS(settings.OPENAI_API_KEY)

    if provider == "deepgram":
        if not settings.DEEPGRAM_API_KEY:
            raise RuntimeError(
                "TTS provider 'deepgram' requested but DEEPGRAM_API_KEY is not set"
            )
        from app.channels.whatsapp.tts.deepgram_tts import DeepgramTTS
        return DeepgramTTS(settings.DEEPGRAM_API_KEY)

    raise RuntimeError(
        f"Unknown TTS provider {name!r} — valid values: 'openai', 'deepgram'"
    )
