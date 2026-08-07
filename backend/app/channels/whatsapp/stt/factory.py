"""STT provider factory — builds the named implementation from an injected key.

The API key is passed in (resolved per-org by the caller — see
app/services/api_key_service.py) rather than read from settings here, so voice
transcription bills to each tenant's own key. Provider selection still comes
from STT_PROVIDER:
    STT_PROVIDER=groq    →  GroqWhisperSTT   (default, fastest)
    STT_PROVIDER=openai  →  OpenAIWhisperSTT
"""

from app.channels.whatsapp.stt.base import BaseSTTProvider


def get_stt_provider(provider_name: str, api_key: str | None) -> BaseSTTProvider:
    """Instantiate the STT provider named by `provider_name` using `api_key`.

    Raises RuntimeError if the provider is unknown or no key was resolved for it
    (e.g. the org has none and platform fallback is off/unset). Callers treat
    that as "can't transcribe" and fall back to a text reply — never silence.
    """
    provider = (provider_name or "groq").lower().strip()

    if provider not in ("groq", "openai"):
        raise RuntimeError(
            f"Unknown STT_PROVIDER={provider!r} — valid values: 'groq', 'openai'"
        )
    if not api_key:
        raise RuntimeError(
            f"STT provider {provider!r} has no API key for this org "
            "(no per-org key and no platform fallback available)"
        )

    if provider == "groq":
        from app.channels.whatsapp.stt.groq_stt import GroqWhisperSTT
        return GroqWhisperSTT(api_key)

    from app.channels.whatsapp.stt.openai_stt import OpenAIWhisperSTT
    return OpenAIWhisperSTT(api_key)
