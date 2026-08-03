"""Transactional email via a configurable SMTP relay.

Provider-agnostic by design: point SMTP_HOST/PORT/USERNAME/PASSWORD at any
standard relay (Amazon SES, Mailgun, Postmark, Resend SMTP, etc.) through
environment variables — no code change required to switch providers.

Failover: if SMTP_HOST_FALLBACK (and SMTP_FROM_ADDRESS_FALLBACK) are set,
EmailService will attempt the fallback provider once after the primary
exhausts all retries or fails on auth.  Either provider can be swapped
without touching this file.

Public API used by the rest of the codebase:

    from app.utils.email import send_otp_email, EmailDeliveryError

    await send_otp_email(to_email, otp_code)   # raises EmailDeliveryError on failure

For new email types, use the singleton directly:

    from app.utils.email import email_service

    await email_service.send_email(
        to="user@example.com",
        subject="Appointment confirmed",
        html_body=email_service.render("appointment_confirmation.html", **ctx),
        text_body="...",
    )
"""

import asyncio
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import aiosmtplib
import httpx
import jinja2
import structlog

from app.config import settings

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"

logger = structlog.get_logger()

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "email"
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=jinja2.select_autoescape(["html", "htm"]),
)

# Seconds to wait before attempt 2, then attempt 3.  Three total attempts is
# enough to survive a transient relay hiccup without adding painful latency.
_RETRY_DELAYS = (0.5, 1.5)


# ── Provider descriptor ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class _SmtpProvider:
    """All connection details for one SMTP relay, plus a human-readable label
    used in log events so ops can immediately see which relay sent (or failed)
    without decoding hostnames."""

    host: str
    port: int
    username: str | None
    password: str | None
    from_address: str
    from_name: str
    use_tls: bool
    label: str  # "primary" | "fallback"


def _primary_provider() -> _SmtpProvider:
    return _SmtpProvider(
        host=settings.SMTP_HOST or "",
        port=settings.SMTP_PORT,
        username=settings.SMTP_USERNAME or None,
        password=settings.SMTP_PASSWORD or None,
        from_address=settings.SMTP_FROM_ADDRESS or "",
        from_name=settings.SMTP_FROM_NAME,
        use_tls=settings.SMTP_USE_TLS,
        label="primary",
    )


def _fallback_provider() -> "_SmtpProvider | None":
    """Returns the fallback provider descriptor, or None if not configured.

    Both SMTP_HOST_FALLBACK and SMTP_FROM_ADDRESS_FALLBACK must be set —
    a host without a sender address (or vice-versa) is unusable.
    """
    if not settings.SMTP_HOST_FALLBACK or not settings.SMTP_FROM_ADDRESS_FALLBACK:
        return None
    return _SmtpProvider(
        host=settings.SMTP_HOST_FALLBACK,
        port=settings.SMTP_PORT_FALLBACK,
        username=settings.SMTP_USERNAME_FALLBACK or None,
        password=settings.SMTP_PASSWORD_FALLBACK or None,
        from_address=settings.SMTP_FROM_ADDRESS_FALLBACK,
        from_name=settings.SMTP_FROM_NAME,  # keep the same display name
        use_tls=settings.SMTP_USE_TLS,      # inherit TLS preference from primary
        label="fallback",
    )


# ── Exceptions ────────────────────────────────────────────────────────────────

class EmailDeliveryError(Exception):
    """Raised when the email cannot be delivered after all retry attempts
    (and the fallback provider, if configured, also failed).

    Carries the SMTP status code and response body (when available) so callers
    can log the real reason (bad credentials, unverified sender, quota, etc.)
    without needing to re-parse lower-level exceptions.
    """

    def __init__(self, message: str, status_code: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


# ── Service ───────────────────────────────────────────────────────────────────

class EmailService:
    """Async SMTP email sender backed by aiosmtplib.

    Delivery strategy:
    1. Try the primary provider up to 3 times (2 retries with backoff).
    2. If the primary is exhausted or auth-fails, and a fallback provider is
       configured, attempt the fallback once.
    3. If the fallback also fails (or is not configured), raise EmailDeliveryError.

    Every successful send logs which provider actually delivered the message
    (provider="primary" or provider="fallback") so silent degradation to the
    fallback is visible in structured logs.
    """

    # ── Template rendering ────────────────────────────────────────────────────

    def render(self, template_name: str, **ctx: object) -> str:
        """Render a Jinja2 template from app/templates/email/.

        Raises EmailDeliveryError if the template file does not exist so the
        failure surfaces clearly at the call site rather than as a silent
        empty-body send.
        """
        try:
            tmpl = _jinja_env.get_template(template_name)
            return tmpl.render(**ctx)
        except jinja2.TemplateNotFound as exc:
            raise EmailDeliveryError(
                f"Email template '{template_name}' not found in {_TEMPLATE_DIR}"
            ) from exc

    # ── Message building ──────────────────────────────────────────────────────

    def _build_message(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: str | None,
        reply_to: str | None,
        provider: _SmtpProvider,
    ) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = (
            f"{provider.from_name} <{provider.from_address}>"
            if provider.from_name
            else provider.from_address
        )
        msg["To"] = to
        if reply_to:
            msg["Reply-To"] = reply_to

        # Plain-text part first: email clients prefer the last matching part,
        # so HTML must come second to win in clients that support both.
        if text_body:
            msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        return msg

    # ── Low-level send helpers ────────────────────────────────────────────────

    async def _send_once(
        self,
        msg: MIMEMultipart,
        provider: _SmtpProvider,
        to: str,
        subject: str,
        attempt: int,
    ) -> None:
        """One SMTP send attempt.  Raises SMTPAuthenticationError (permanent)
        or SMTPException/OSError/TimeoutError (transient) on failure — callers
        decide whether to retry or escalate."""
        await aiosmtplib.send(
            msg,
            hostname=provider.host,
            port=provider.port,
            username=provider.username,
            password=provider.password,
            start_tls=provider.use_tls,
            timeout=15,
        )
        logger.info(
            "email_sent",
            to=to,
            subject=subject,
            provider=provider.label,
            smtp_host=provider.host,
            attempt=attempt,
        )

    async def _send_with_retries(
        self,
        msg: MIMEMultipart,
        provider: _SmtpProvider,
        to: str,
        subject: str,
    ) -> None:
        """Try `provider` up to 3 times (2 retries) with backoff.

        Raises EmailDeliveryError on auth failure (immediately, no retry) or
        after all attempts are exhausted.
        """
        total_attempts = len(_RETRY_DELAYS) + 1
        last_exc: BaseException | None = None

        for attempt, delay in enumerate((*_RETRY_DELAYS, None), start=1):
            try:
                await self._send_once(msg, provider, to, subject, attempt)
                return

            except aiosmtplib.SMTPAuthenticationError as exc:
                logger.error(
                    "email_auth_failed",
                    to=to,
                    subject=subject,
                    provider=provider.label,
                    smtp_host=provider.host,
                    error=str(exc),
                )
                raise EmailDeliveryError(
                    f"SMTP auth failed on {provider.label} provider "
                    f"({provider.host}) — check credentials: {exc}"
                ) from exc

            except (aiosmtplib.SMTPException, OSError, asyncio.TimeoutError) as exc:
                last_exc = exc
                logger.warning(
                    "email_send_attempt_failed",
                    to=to,
                    subject=subject,
                    provider=provider.label,
                    smtp_host=provider.host,
                    attempt=attempt,
                    total_attempts=total_attempts,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
                if delay is not None:
                    await asyncio.sleep(delay)

        raise EmailDeliveryError(
            f"{provider.label} SMTP provider ({provider.host}) failed after "
            f"{total_attempts} attempts: {last_exc}"
        ) from last_exc

    # ── Public send API ───────────────────────────────────────────────────────

    async def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
        reply_to: str | None = None,
    ) -> None:
        """Send an email.

        Transport order:
          1. Brevo HTTP API (when BREVO_API_KEY is set) — port 443, so it works
             even where the host blocks outbound SMTP ports (e.g. Railway).
          2. SMTP relay (primary, then optional fallback) — used when there's no
             API key, or as a last resort if the API call fails.

        Raises:
            EmailDeliveryError: when no transport succeeds. Never raises raw
                httpx / aiosmtplib / OS exceptions — always wraps them.
        """
        api_exc: EmailDeliveryError | None = None
        if settings.BREVO_API_KEY:
            try:
                await self._send_via_brevo_api(to, subject, html_body, text_body, reply_to)
                return
            except EmailDeliveryError as exc:
                api_exc = exc
                logger.warning(
                    "email_brevo_api_failed_falling_back_to_smtp",
                    to=to,
                    subject=subject,
                    error=str(exc),
                )

        # SMTP fallback. If SMTP isn't configured either, surface the API error
        # (if any) rather than a generic "not configured" message.
        if not (settings.SMTP_HOST and settings.SMTP_FROM_ADDRESS):
            if api_exc is not None:
                raise api_exc
            raise EmailDeliveryError(
                "No email transport configured. Set BREVO_API_KEY (HTTP API) "
                "or SMTP_HOST + SMTP_FROM_ADDRESS."
            )
        await self._send_via_smtp(to, subject, html_body, text_body, reply_to)

    # ── Brevo HTTP API transport (primary) ────────────────────────────────────

    async def _send_via_brevo_api(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: str | None,
        reply_to: str | None,
    ) -> None:
        """Send one email via Brevo's transactional API. Retries transient
        (network / 5xx) failures; a 4xx (bad key, unverified sender) raises
        immediately so it isn't pointlessly retried."""
        sender_email = settings.SMTP_FROM_ADDRESS or settings.OTP_FROM_EMAIL
        if not sender_email:
            raise EmailDeliveryError(
                "No sender address configured (set SMTP_FROM_ADDRESS or OTP_FROM_EMAIL)."
            )

        payload: dict = {
            "sender": {"name": settings.SMTP_FROM_NAME, "email": sender_email},
            "to": [{"email": to}],
            "subject": subject,
            "htmlContent": html_body,
        }
        if text_body:
            payload["textContent"] = text_body
        if reply_to:
            payload["replyTo"] = {"email": reply_to}
        headers = {
            "api-key": settings.BREVO_API_KEY,
            "content-type": "application/json",
            "accept": "application/json",
        }

        last_exc: EmailDeliveryError | None = None
        for attempt, delay in enumerate((*_RETRY_DELAYS, None), start=1):
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(BREVO_API_URL, json=payload, headers=headers)
            except (httpx.HTTPError, OSError) as exc:
                last_exc = EmailDeliveryError(f"Brevo API request failed: {exc}")
                logger.warning(
                    "email_brevo_api_attempt_failed",
                    to=to,
                    subject=subject,
                    attempt=attempt,
                    error=str(exc),
                )
            else:
                if resp.status_code in (200, 201):
                    message_id = None
                    try:
                        message_id = resp.json().get("messageId")
                    except ValueError:
                        pass
                    logger.info(
                        "email_sent",
                        to=to,
                        subject=subject,
                        provider="brevo_api",
                        attempt=attempt,
                        message_id=message_id,
                    )
                    return
                if 400 <= resp.status_code < 500:
                    # Permanent (bad key, unverified sender, invalid recipient) —
                    # don't retry, and don't fall through to more attempts.
                    logger.error(
                        "email_brevo_api_rejected",
                        to=to,
                        subject=subject,
                        status_code=resp.status_code,
                        response_body=resp.text[:300],
                    )
                    raise EmailDeliveryError(
                        f"Brevo API rejected the email (HTTP {resp.status_code}): {resp.text[:300]}",
                        status_code=resp.status_code,
                        body=resp.text[:500],
                    )
                # 5xx — transient, retry.
                last_exc = EmailDeliveryError(
                    f"Brevo API server error (HTTP {resp.status_code})",
                    status_code=resp.status_code,
                    body=resp.text[:500],
                )
                logger.warning(
                    "email_brevo_api_attempt_failed",
                    to=to,
                    subject=subject,
                    attempt=attempt,
                    status_code=resp.status_code,
                )

            if delay is not None:
                await asyncio.sleep(delay)

        raise last_exc or EmailDeliveryError("Brevo API send failed after retries")

    # ── SMTP transport (fallback) ─────────────────────────────────────────────

    async def _send_via_smtp(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
        reply_to: str | None = None,
    ) -> None:
        """Send over SMTP, failing over to the secondary relay if the primary
        is unavailable.

        Delivery order:
          1. Primary provider — up to 3 attempts with backoff.
          2. Fallback provider (if SMTP_HOST_FALLBACK is set) — 1 attempt.
          3. EmailDeliveryError if both fail (or fallback is not configured).

        Logs 'provider=primary' or 'provider=fallback' on every successful
        send so degradation to the fallback is visible in structured logs.

        Raises:
            EmailDeliveryError: when no provider succeeds.  Never raises raw
                aiosmtplib / OS exceptions — always wraps them so callers have
                a single exception type to catch.
        """
        primary = _primary_provider()
        if not primary.host or not primary.from_address:
            raise EmailDeliveryError(
                "SMTP is not configured. Set SMTP_HOST and SMTP_FROM_ADDRESS "
                "in your environment variables."
            )

        primary_msg = self._build_message(to, subject, html_body, text_body, reply_to, primary)

        # ── Primary attempt ───────────────────────────────────────────────────
        primary_exc: EmailDeliveryError | None = None
        try:
            await self._send_with_retries(primary_msg, primary, to, subject)
            return
        except EmailDeliveryError as exc:
            primary_exc = exc

        # ── Fallback attempt ──────────────────────────────────────────────────
        fallback = _fallback_provider()
        if fallback is None:
            raise primary_exc

        logger.warning(
            "email_falling_back_to_secondary",
            to=to,
            subject=subject,
            primary_host=primary.host,
            fallback_host=fallback.host,
            primary_error=str(primary_exc),
        )

        # Rebuild message with the fallback From address — some relays reject
        # messages whose From header doesn't match the authenticated sender.
        fallback_msg = self._build_message(to, subject, html_body, text_body, reply_to, fallback)

        try:
            # Single attempt on the fallback — it's a last resort, not a full
            # retry cycle, to keep total latency bounded.
            await self._send_once(fallback_msg, fallback, to, subject, attempt=1)
        except aiosmtplib.SMTPAuthenticationError as exc:
            fallback_err = EmailDeliveryError(
                f"SMTP auth failed on fallback provider ({fallback.host}): {exc}"
            )
            logger.error(
                "email_fallback_auth_failed",
                to=to,
                subject=subject,
                fallback_host=fallback.host,
                error=str(exc),
            )
            raise EmailDeliveryError(
                f"Both SMTP providers failed. Primary: {primary_exc}. Fallback auth error: {exc}"
            ) from fallback_err
        except (aiosmtplib.SMTPException, OSError, asyncio.TimeoutError) as exc:
            logger.error(
                "email_both_providers_failed",
                to=to,
                subject=subject,
                primary_host=primary.host,
                fallback_host=fallback.host,
                primary_error=str(primary_exc),
                fallback_error=str(exc),
            )
            raise EmailDeliveryError(
                f"Both SMTP providers failed. Primary: {primary_exc}. Fallback: {exc}"
            ) from exc


# ── Module-level singleton ────────────────────────────────────────────────────

email_service = EmailService()


# ── High-level helpers (keep call signatures stable) ─────────────────────────

async def send_otp_email(to_email: str, otp_code: str) -> None:
    """Send a one-time password email to `to_email`.

    Renders the otp.html Jinja2 template and delivers it via the configured
    SMTP relay (with automatic fallover to the secondary provider if configured).
    Raises EmailDeliveryError on any failure — callers must decide how to
    surface this to the user; do NOT swallow the error silently or the
    recipient will never know their code isn't coming.
    """
    html_body = email_service.render("otp.html", otp_code=otp_code)
    text_body = (
        f"Your verification code is {otp_code}.\n\n"
        "It expires in 10 minutes. If you didn't request this, "
        "you can safely ignore this email."
    )
    await email_service.send_email(
        to=to_email,
        subject="Your verification code",
        html_body=html_body,
        text_body=text_body,
    )
