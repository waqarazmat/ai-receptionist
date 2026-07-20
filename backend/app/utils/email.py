import httpx

from app.config import settings

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


async def send_otp_email(to_email: str, otp_code: str) -> None:
    """Send an OTP code via the Brevo transactional email API.

    Raises httpx.HTTPError on failure — callers decide how to degrade
    (the auth router must still return its generic response either way).
    """
    payload = {
        "sender": {"email": settings.OTP_FROM_EMAIL},
        "to": [{"email": to_email}],
        "subject": "Your verification code",
        "htmlContent": (
            f"<p>Your verification code is <strong>{otp_code}</strong>.</p>"
            "<p>It expires in 10 minutes. If you didn't request this, you can ignore this email.</p>"
        ),
    }
    headers = {
        "api-key": settings.BREVO_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(BREVO_SEND_URL, json=payload, headers=headers)
        response.raise_for_status()
