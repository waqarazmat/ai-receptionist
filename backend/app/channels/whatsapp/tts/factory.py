"""TTS provider factory — builds the named implementation from an injected key.

The API key is passed in (resolved per-org by the caller — see
app/services/api_key_service.py) rather than read from settings here, so speech
synthesis bills to each tenant's own key:
    TTS_PROVIDER=openai    →  OpenAITTS    (default)
    TTS_PROVIDER=deepgram  →  DeepgramTTS

`get_tts_provider_by_name(name, api_key)` is called by voice_handler.py, which
picks the provider name (the default, or a multilingual fallback when the
default provider can't speak the detected language) and resolves that provider's
per-org key.
"""

from app.channels.whatsapp.tts.base import BaseTTSProvider


def get_tts_provider_by_name(name: str, api_key: str | None) -> BaseTTSProvider:
    """Instantiate a TTS provider by explicit name using `api_key`.

    Raises RuntimeError if the provider is unknown or no key was resolved for it
    (org has none and platform fallback is off/unset). voice_handler catches
    that and falls back to a text reply instead of silence.
    """
    provider = (name or "").lower().strip()

    if provider not in ("openai", "deepgram"):
        raise RuntimeError(
            f"Unknown TTS provider {name!r} — valid values: 'openai', 'deepgram'"
        )
    if not api_key:
        raise RuntimeError(
            f"TTS provider {provider!r} has no API key for this org "
            "(no per-org key and no platform fallback available)"
        )

    if provider == "openai":
        from app.channels.whatsapp.tts.openai_tts import OpenAITTS
        return OpenAITTS(api_key)

    from app.channels.whatsapp.tts.deepgram_tts import DeepgramTTS
    return DeepgramTTS(api_key)
