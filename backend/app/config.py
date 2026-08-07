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

    # ── Transactional email — primary SMTP relay ──────────────────────────────
    # Point these at any standard SMTP relay — Amazon SES, Mailgun, Postmark,
    # Resend, etc. — by setting env vars. No code change required to switch
    # providers, only credentials.
    # Brevo HTTP API (transactional email over HTTPS, port 443). Cloud hosts
    # (Railway) commonly block/throttle outbound SMTP ports, so when this key is
    # set EmailService sends via the API FIRST and only falls back to SMTP if
    # the API call fails. Unset it to force pure SMTP. See app/utils/email.py.
    BREVO_API_KEY: str | None = None
    # Sender address for the Brevo API path; falls back to SMTP_FROM_ADDRESS.
    OTP_FROM_EMAIL: str | None = None

    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_ADDRESS: str | None = None
    SMTP_FROM_NAME: str = "AI Receptionist"
    # True = STARTTLS (port 587, most relays). False = no STARTTLS upgrade
    # (use port 465 with implicit TLS configured at the relay, or port 25 in dev).
    SMTP_USE_TLS: bool = True

    # ── Transactional email — fallback SMTP relay ─────────────────────────────
    # Optional. When set, EmailService will attempt delivery through this relay
    # after the primary exhausts all retries or fails on auth. Unset = failover
    # disabled (current behaviour unchanged). Use a *different* provider from
    # the primary so a single vendor outage doesn't take out both paths.
    SMTP_HOST_FALLBACK: str | None = None
    SMTP_PORT_FALLBACK: int = 587
    SMTP_USERNAME_FALLBACK: str | None = None
    SMTP_PASSWORD_FALLBACK: str | None = None
    SMTP_FROM_ADDRESS_FALLBACK: str | None = None

    SUPER_ADMIN_EMAIL: str

    # Optional — when unset, website crawling uses the httpx+BeautifulSoup
    # fallback only (see app/services/crawler_service.py).
    FIRECRAWL_API_KEY: str | None = None

    # The platform's ONE shared Google service account. Calendar access is
    # granted per-org by each org sharing their calendar with this service
    # account's client_email (they only give us their calendar ID) — no OAuth
    # redirect flow, and NOT a JSON key per org.
    #
    # Two ways to supply it (see app/booking/google_calendar.py):
    #   GOOGLE_SERVICE_ACCOUNT_JSON  — the raw JSON key contents. Preferred in
    #       production/Railway, where a gitignored key file wouldn't be deployed.
    #   GOOGLE_SERVICE_ACCOUNT_FILE  — a path to the JSON key file. Convenient
    #       for local dev.
    # JSON takes precedence when both are set. Optional — when neither is set,
    # calendar features degrade gracefully (booking still works, no event).
    GOOGLE_SERVICE_ACCOUNT_JSON: str | None = None
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

    # Appointment reminders — the "soon" email/reminder fires this many minutes
    # before the appointment start (in addition to the ~24h-before reminder).
    # The reminder cron runs every 15 min, so effective firing is within one
    # tick of this target.
    REMINDER_LEAD_MINUTES: int = 60

    # Alerting webhook — optional. Paste a Slack or Discord incoming webhook
    # URL here. When set, critical background task failures (e.g. email
    # delivery exhausting all retries) POST a short message to this URL in
    # addition to the existing structlog ERROR. Both Slack and Discord accept
    # the same {"text": "..."} payload for incoming webhooks, so one field
    # covers both. Leave blank to keep log-only behavior.
    ALERT_WEBHOOK_URL: str | None = None

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

    # ── GDPR data retention ────────────────────────────────────────────────
    # How long to keep conversation + message rows before pruning. Applies when
    # an org has no per-tenant data_retention_days set. Medical/legal orgs are
    # defaulted to a shorter window at creation time by org_service.
    DEFAULT_CONVERSATION_RETENTION_DAYS: int = 365
    # Shorter default for regulated verticals (medical, dental, legal).
    # Applied automatically at org creation; can still be overridden per-org.
    REGULATED_VERTICAL_RETENTION_DAYS: int = 90

    # ── Tenant key isolation ───────────────────────────────────────────────
    # When True, a provider key falls back to the platform-level env key below
    # if the org hasn't configured its own (convenient for onboarding/dev). When
    # False (strict isolation), an org with no key for a provider degrades
    # gracefully instead of ever using a shared key — no org runs on another
    # org's or the platform's key. Governs STT/TTS (voice pipeline) AND the LLM
    # router's platform fallback. See app/services/api_key_service.py.
    ALLOW_PLATFORM_KEY_FALLBACK: bool = True

    # ── WhatsApp Voice Note pipeline (STT + TTS) ───────────────────────────
    # The keys below are PLATFORM-level FALLBACKS only. The pipeline prefers each
    # org's own key (encrypted in org_api_keys: groq for STT, deepgram/openai for
    # TTS) so speech billing is per-tenant; these env keys are used only when the
    # org has none AND ALLOW_PLATFORM_KEY_FALLBACK is True.

    # "groq" (default, faster + cheaper) or "openai"
    STT_PROVIDER: str = "groq"
    # "openai" (default) or "deepgram"
    TTS_PROVIDER: str = "openai"

    # Groq API key — platform fallback for STT when STT_PROVIDER=groq
    GROQ_API_KEY: str | None = None

    # Platform-fallback OpenAI key — STT (gpt-4o-mini-transcribe) when
    # STT_PROVIDER=openai, and TTS (tts-1) when TTS_PROVIDER=openai. Per-org
    # OpenAI keys in org_api_keys (which also drive the RAG/LLM pipeline) take
    # precedence over this.
    OPENAI_API_KEY: str | None = None

    # Deepgram API key — platform fallback for TTS when TTS_PROVIDER=deepgram
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
