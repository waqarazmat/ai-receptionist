"""Monthly usage tracking for billing quota enforcement.

Redis-backed counters keyed to a calendar month (`YYYYMM`). Existing
per-hour rate limits in app.security.rate_limiter are independent — they
prevent bursts; this prevents plan overage. Both must pass for a message
to be billable.

If Redis is down we FAIL OPEN (default to "under quota") — losing a
customer's traffic because of a Redis blip is worse than serving a few
messages over quota. Reconciliation on the next successful check will
catch up.
"""

from datetime import datetime, timezone

from app.db.redis import redis_client

USAGE_KEY_TTL_SECONDS = 40 * 24 * 3600  # 40 days — comfortably past month-end


def _current_month_bucket() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m")


def _key(org_id: str) -> str:
    return f"msg_usage:{org_id}:{_current_month_bucket()}"


async def get_current_usage(org_id: str) -> int:
    """How many billable messages this org has consumed in the current
    calendar month. Zero for a brand-new org."""
    try:
        count = await redis_client.get(_key(org_id))
    except Exception:  # noqa: BLE001
        return 0
    return int(count or 0)


async def increment_usage(org_id: str) -> int:
    """Count one message. Returns the new count. Sets the key TTL on first
    write so cleanup is automatic — no cron needed to trim old months."""
    key = _key(org_id)
    try:
        if not await redis_client.set(key, 1, ex=USAGE_KEY_TTL_SECONDS, nx=True):
            return int(await redis_client.incr(key))
        return 1
    except Exception:  # noqa: BLE001 — usage tracking must not break the message path
        return 0


async def is_over_quota(org_id: str, quota: int) -> bool:
    return (await get_current_usage(org_id)) >= quota
