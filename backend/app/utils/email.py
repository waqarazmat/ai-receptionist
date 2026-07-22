import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


class EmailDeliveryError(Exception):
    """Raised when the transactional email API call fails. Wraps the underlying
    httpx error and Brevo's response body (if any) so the caller can log the
    real reason (bad api-key, unverified sender, quota exhausted, etc.)
    without callers having to re-parse httpx internals."""

    def __init__(self, message: str, status_code: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


async def send_otp_email(to_email: str, otp_code: str) -> None:
    """Send an OTP code via the Brevo transactional email API.

    Raises EmailDeliveryError on any failure (network error OR Brevo returning
    a non-2xx). Callers must decide how to degrade — do NOT let a Brevo error
    silently swallow the user's OTP request; they'll never know their code
    isn't coming.
    """
    payload = {
        "sender": {"email": settings.OTP_FROM_EMAIL, "name": "AI Receptionist"},
        "to": [{"email": to_email}],
        "subject": "Your verification code",
        "htmlContent": (
            f"<p>Your verification code is <strong>{otp_code}</strong>.</p>"
            "<p>It expires in 10 minutes. If you didn't request this, "
            "you can ignore this email.</p>"
        ),
        # Brevo requires either htmlContent or textContent; providing both
        # gives clients that strip HTML (some corporate MTAs) a usable body.
        "textContent": (
            f"Your verification code is {otp_code}.\n\n"
            "It expires in 10 minutes. If you didn't request this, you can "
            "ignore this email."
        ),
    }
    headers = {
        "api-key": settings.BREVO_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(BREVO_SEND_URL, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        # Network-level failure (DNS, TLS, timeout). No response to inspect.
        logger.warning(
            "brevo_send_network_error",
            to_email=to_email,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise EmailDeliveryError(f"Brevo network error: {exc}") from exc

    if response.is_success:
        # Brevo returns { "messageId": "..." } on success — record it so we
        # can correlate a bounce or delivery event back to a request later.
        message_id: str | None = None
        try:
            message_id = response.json().get("messageId")
        except Exception:  # noqa: BLE001 — non-JSON success body is unlikely but survivable
            pass
        logger.info("brevo_send_ok", to_email=to_email, message_id=message_id)
        return

    # Non-2xx. Brevo's error body carries the real reason (bad api-key,
    # unverified sender, invalid recipient format, quota exhausted, etc.).
    # Log the raw text so operators don't need to reverse-engineer failures
    # from a status code alone.
    body_text = response.text[:2000]
    logger.warning(
        "brevo_send_failed",
        to_email=to_email,
        status_code=response.status_code,
        response_body=body_text,
    )
    raise EmailDeliveryError(
        f"Brevo returned {response.status_code}",
        status_code=response.status_code,
        body=body_text,
    )
