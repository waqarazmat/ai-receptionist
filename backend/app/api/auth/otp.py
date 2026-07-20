import secrets

import structlog

from app.config import settings
from app.db.redis import redis_client
from app.security.rate_limiter import (
    check_otp_attempt_limit,
    check_otp_request_limit,
    increment_otp_attempts,
    increment_otp_requests,
)

logger = structlog.get_logger()

OTP_TTL_SECONDS = 600


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def store_otp(email: str, code: str) -> bool:
    """Store the OTP if the hourly request limit hasn't been exceeded.

    Returns False when rate-limited — the caller still returns its generic
    "check your email" response either way, it just skips sending the email.
    """
    if not await check_otp_request_limit(email):
        return False
    await increment_otp_requests(email)
    await redis_client.set(f"otp:{email}", code, ex=OTP_TTL_SECONDS)

    if settings.APP_ENV == "development":
        logger.info("DEV OTP", otp_code=code, email=email)

    return True


async def verify_otp(email: str, code: str) -> bool:
    if not await check_otp_attempt_limit(email, code):
        # Attempt cap hit for this code — invalidate it so a fresh one must be requested.
        await redis_client.delete(f"otp:{email}")
        return False

    await increment_otp_attempts(email, code)

    stored_code = await redis_client.get(f"otp:{email}")
    if stored_code is None or not secrets.compare_digest(stored_code, code):
        return False

    await redis_client.delete(f"otp:{email}")
    return True
