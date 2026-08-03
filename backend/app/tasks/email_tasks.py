"""Background email delivery via Arq.

Use this task for any email that isn't OTP — appointment confirmations,
staff notifications, weekly digests, etc.  The request handler enqueues the
job and returns immediately; delivery (including EmailService's built-in
3-attempt retry and optional provider failover) happens in the worker process.

OTP emails ARE routed through here as well (see app/api/auth/router.py): the
login endpoint enqueues the send and returns immediately with a generic
message, so neither the response time nor its body reveals whether the email
is registered (email-enumeration protection). A delivery failure surfaces via
the dead-letter handling below rather than reaching the waiting user.

Dead-letter handling
--------------------
EmailService already exhausts all retries and the fallback provider before
raising EmailDeliveryError.  If that exception still reaches this task, it
means every delivery path is down.  We log the full send context at ERROR
level so the event appears in Sentry / Railway log drain and can be acted on
(or the email manually resent) by the operator.  If ALERT_WEBHOOK_URL is set
in the environment, a short alert is also POSTed to that Slack or Discord
incoming webhook URL.  The exception is then re-raised so arq marks the job
as failed in its result store.

Enqueue pattern (from any request handler or service):

    from app.tasks.queue import get_arq_pool

    pool = await get_arq_pool()
    await pool.enqueue_job(
        "send_email_task",
        to="user@example.com",
        subject="Appointment confirmed",
        html_body=email_service.render("appointment_confirmation.html", **ctx),
        email_type="appointment_confirmation",
    )
"""

import httpx
import structlog

from app.config import settings
from app.utils.email import EmailDeliveryError, email_service

logger = structlog.get_logger()


async def _post_alert(email_type: str, to: str, error: str) -> None:
    """POST a one-line failure notice to the configured incoming webhook.

    Both Slack and Discord incoming webhooks accept {"text": "..."}, so a
    single ALERT_WEBHOOK_URL field covers both.  Any failure here is logged
    at WARNING level and swallowed — an alert that crashes the task would
    defeat the purpose of the surrounding try/except.
    """
    url = settings.ALERT_WEBHOOK_URL
    if not url:
        return

    text = (
        f":rotating_light: *Email delivery failed* — all delivery paths exhausted\n"
        f"• *type:* `{email_type}`\n"
        f"• *to:* `{to}`\n"
        f"• *error:* {error}"
    )
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(url, json={"text": text})
            resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        # Deliberately broad: a misconfigured URL, a network blip, or a
        # non-2xx from the webhook service must not propagate — the caller
        # still needs to re-raise the original EmailDeliveryError.
        logger.warning("alert_webhook_failed", error=str(exc))


async def send_email_task(
    ctx: dict,
    *,
    to: str,
    subject: str,
    html_body: str,
    email_type: str,
    text_body: str | None = None,
    reply_to: str | None = None,
) -> None:
    """Arq task: deliver a transactional email in the background.

    Args:
        ctx:        Arq job context (unused directly; required by the protocol).
        to:         Recipient email address.
        subject:    Email subject line.
        html_body:  Rendered HTML body. Callers should use
                    email_service.render("template.html", **ctx) before enqueuing.
        email_type: Human-readable label logged with every outcome event so
                    ops can distinguish "appointment_confirmation" from
                    "staff_notification" etc. without parsing subject lines.
        text_body:  Optional plain-text fallback part.
        reply_to:   Optional Reply-To header.
    """
    log = logger.bind(to=to, subject=subject, email_type=email_type)

    try:
        await email_service.send_email(
            to=to,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            reply_to=reply_to,
        )
        log.info("background_email_sent")

    except EmailDeliveryError as exc:
        # EmailService has already exhausted its own retry cycle AND the
        # fallback provider (if configured).  Every delivery path is down.
        # Log everything needed to reconstruct the send manually, post an
        # alert to the ops webhook (if configured), then re-raise so arq
        # marks the job failed and Sentry captures the exception.
        log.error(
            "background_email_failed",
            error=str(exc),
            smtp_status_code=exc.status_code,
            to=to,
            subject=subject,
            email_type=email_type,
        )
        await _post_alert(email_type=email_type, to=to, error=str(exc))
        raise
