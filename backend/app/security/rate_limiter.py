from datetime import datetime, timezone

from app.db.redis import redis_client

MAX_OTP_REQUESTS_PER_HOUR = 5
OTP_REQUEST_WINDOW_SECONDS = 3600

MAX_OTP_ATTEMPTS_PER_CODE = 3
OTP_ATTEMPT_WINDOW_SECONDS = 600

DEFAULT_MAX_MESSAGES_PER_HOUR = 500
MESSAGE_COUNT_WINDOW_SECONDS = 3600


async def check_otp_request_limit(email: str) -> bool:
    """True if the email is still under the hourly OTP request cap."""
    count = await redis_client.get(f"otp_requests:{email}")
    return int(count or 0) < MAX_OTP_REQUESTS_PER_HOUR


async def increment_otp_requests(email: str) -> None:
    key = f"otp_requests:{email}"
    # SET NX seeds the counter with its TTL; once it exists, INCR leaves the
    # original TTL untouched so this is a fixed 1-hour window, not a rolling one.
    if not await redis_client.set(key, 1, ex=OTP_REQUEST_WINDOW_SECONDS, nx=True):
        await redis_client.incr(key)


async def check_otp_attempt_limit(email: str, otp_code: str) -> bool:
    """True if this specific code is still under its verification-attempt cap."""
    count = await redis_client.get(f"otp_attempts:{email}:{otp_code}")
    return int(count or 0) < MAX_OTP_ATTEMPTS_PER_CODE


async def increment_otp_attempts(email: str, otp_code: str) -> None:
    key = f"otp_attempts:{email}:{otp_code}"
    if not await redis_client.set(key, 1, ex=OTP_ATTEMPT_WINDOW_SECONDS, nx=True):
        await redis_client.incr(key)


def _current_hour_bucket() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H")


async def check_message_rate_limit(org_id: str, max_per_hour: int = DEFAULT_MAX_MESSAGES_PER_HOUR) -> bool:
    """True if the org is still under its per-calendar-hour message cap.

    When the cap is hit, the caller should fall back to a static response
    instead of calling the org's LLM provider (root CLAUDE.md rule #7).
    """
    count = await redis_client.get(f"msg_count:{org_id}:{_current_hour_bucket()}")
    return int(count or 0) < max_per_hour


async def increment_message_count(org_id: str) -> None:
    key = f"msg_count:{org_id}:{_current_hour_bucket()}"
    if not await redis_client.set(key, 1, ex=MESSAGE_COUNT_WINDOW_SECONDS, nx=True):
        await redis_client.incr(key)
