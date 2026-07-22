import secrets

import structlog

from app.config import settings
from app.db.redis import redis_client
from app.security.rate_limiter import (
    check_otp_attempt_limit,
    check_otp_request_limit,
    increment_otp_attempts,
    increment_otp_requests,
    is_otp_locked,
    record_otp_abuse,
)

logger = structlog.get_logger()

OTP_TTL_SECONDS = 600


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def store_otp(email: str, code: str) -> bool:
    """Store the OTP if the hourly request limit hasn't been exceeded.

    Returns False when rate-limited OR when the email is under a second-tier
    abuse lock (see rate_limiter.record_otp_abuse). Callers still return
    the generic "check your email" response either way — this function is
    the only place that decides whether to actually persist and send.
    """
    # Second-tier lock supersedes the per-email rate limit: an actively-abused
    # email short-circuits without leaking the fact via a different response.
    if await is_otp_locked(email):
        logger.warning("otp_locked", email=email)
        return False

    if not await check_otp_request_limit(email):
        # Rate-limit hit — count this toward the abuse threshold and, if the
        # threshold trips, lock the email out entirely.
        locked_now = await record_otp_abuse(email)
        if locked_now:
            logger.warning("otp_abuse_lock_triggered", email=email)
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
