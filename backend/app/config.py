from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> repo root .env (backend/ has no .env of its own)
ROOT_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str
    REDIS_URL: str

    JWT_SECRET_KEY: str
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    MASTER_ENCRYPTION_KEY: str

    BREVO_API_KEY: str
    OTP_FROM_EMAIL: str

    SUPER_ADMIN_EMAIL: str

    # Optional — when unset, website crawling uses the httpx+BeautifulSoup
    # fallback only (see app/services/crawler_service.py).
    FIRECRAWL_API_KEY: str | None = None

    # Path to a Google service account JSON key. Calendar access is granted
    # per-org by the org sharing their calendar with this service account's
    # client_email — no OAuth redirect flow. Optional — when unset, calendar
    # features degrade gracefully (see app/booking/google_calendar.py).
    GOOGLE_SERVICE_ACCOUNT_FILE: str | None = None

    # WhatsApp (Meta Cloud API) — platform-level. One Meta App backs every
    # org's WhatsApp number, so the webhook signing secret and verify token
    # are shared across the whole platform; each org's own access token and
    # phone_number_id are configured per-org (org_api_keys / channel_configs).
    WHATSAPP_APP_SECRET: str | None = None
    WHATSAPP_VERIFY_TOKEN: str | None = None
    WHATSAPP_GRAPH_API_VERSION: str = "v21.0"

    # Retell voice — platform-level API key for Retell's management REST API
    # (creating/updating agents). Distinct from each org's own Retell key in
    # org_api_keys, which is only used to verify inbound call webhooks. Optional
    # — when unset, auto-provisioning of agents degrades gracefully (the agent
    # id is still saved; the Custom LLM URL must then be set by hand in Retell).
    RETELL_API_KEY: str | None = None

    # The backend's externally-reachable base origin (no trailing slash), e.g.
    # an ngrok tunnel in dev or the Railway URL in prod. Used to build the
    # Retell Custom LLM WebSocket URL and webhook URL we push into Retell when
    # provisioning an agent. Defaults to localhost, which Retell can't reach —
    # set this before provisioning.
    APP_PUBLIC_URL: str = "http://localhost:8000"

    APP_ENV: str = "development"
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # Sentry error tracking — optional. When set, unhandled exceptions and
    # explicit logger.error() calls stream to Sentry with request context.
    # Leave blank in dev; set on Railway once a project exists in Sentry.
    SENTRY_DSN: str | None = None
    # Fraction of transactions sampled for performance monitoring.
    # 0.0 = errors only (cheapest). 0.1 = 10% of requests traced.
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0

    # IP-level request rate limit for public endpoints (applies BEFORE any
    # per-org / per-email limits). Guards against enumeration bots and DoS.
    IP_RATE_LIMIT_PER_MINUTE: int = 240

    # Extra abuse-lockout on top of MAX_OTP_REQUESTS_PER_HOUR: if the same
    # email keeps trying after being rate-limited, lock that email out
    # entirely for a while. Prevents someone iterating through valid emails
    # to trigger legitimate users' OTP quotas.
    OTP_ABUSE_LOCK_THRESHOLD: int = 3
    OTP_ABUSE_LOCK_SECONDS: int = 3600

    # ── WhatsApp Voice Note pipeline (STT + TTS) ───────────────────────────
    # These are platform-level keys, distinct from per-org LLM keys stored in
    # org_api_keys. STT/TTS are billed to the platform, not individual orgs.

    # "groq" (default, faster + cheaper) or "openai"
    STT_PROVIDER: str = "groq"
    # "openai" (default) or "deepgram"
    TTS_PROVIDER: str = "openai"

    # Groq API key — required when STT_PROVIDER=groq
    GROQ_API_KEY: str | None = None

    # Platform-level OpenAI key — used for STT (gpt-4o-mini-transcribe) when
    # STT_PROVIDER=openai, and for TTS (tts-1) when TTS_PROVIDER=openai.
    # Separate from per-org keys in org_api_keys (those drive the RAG/LLM pipeline).
    OPENAI_API_KEY: str | None = None

    # Deepgram API key — required when TTS_PROVIDER=deepgram
    DEEPGRAM_API_KEY: str | None = None

    # Voice notes larger than this (MB) are rejected before download.
    MAX_VOICE_NOTE_FILE_SIZE_MB: float = 16.0
    # Voice notes longer than this (seconds) are rejected after download.
    MAX_VOICE_NOTE_DURATION_SECONDS: int = 120

    # Directory for per-request audio scratch files. Cleaned up after every job.
    TEMP_AUDIO_DIR: str = "/tmp/voice_notes"

    # Replies longer than this are sent as text instead of TTS audio — long
    # voice notes are bad UX and cost more per character on TTS providers.
    MAX_VOICE_REPLY_CHARS: int = 500

    # ISO 639-1 codes the pipeline accepts. Languages outside this list get a
    # text reply instead of audio. Set to ["*"] to disable the check.
    VOICE_SUPPORTED_LANGUAGES: list[str] = ["en", "fr", "nl", "de"]

    # Which languages each TTS provider can actually speak.
    # Consulted at runtime to decide whether to fall back to the multilingual
    # provider when the default one can't handle the detected language.
    # Adding a new language later is a config change only — no code change.
    TTS_PROVIDER_LANGUAGE_SUPPORT: dict[str, list[str]] = {
        "openai": ["en", "fr", "nl", "de", "es", "it", "pt", "pl", "ru", "zh", "ja", "ko", "ar", "hi", "tr"],
        # Deepgram Aura-2 only has English voices as of 2025-07.
        "deepgram": ["en"],
    }

    # When TTS_PROVIDER can't handle the detected language, automatically
    # retry with this provider instead of falling back to a text reply.
    TTS_MULTILINGUAL_FALLBACK_PROVIDER: str = "openai"

    # Max voice notes a single WhatsApp number may send per minute.
    # Guards against accidental loops or deliberate abuse (each note costs
    # you STT + LLM + TTS money).
    VOICE_NOTE_RATE_LIMIT_PER_MINUTE: int = 5


settings = Settings()
