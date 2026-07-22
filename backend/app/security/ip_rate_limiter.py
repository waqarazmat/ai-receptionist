"""IP-address rate limiting.

Runs BEFORE the per-org / per-email limits — those are business rules; this
one is an anti-abuse floor. Sits on Redis so multiple pods share state.

Deliberately fixed-window (`SET NX ex=60`, `INCR`) rather than sliding-log:
the operational simplicity is worth more than the ±1s boundary looseness.
Rejected requests never touch the app — return 429 straight from middleware
so a bot enumerating endpoints doesn't drag DB or LLM latency down.

Health and public webhook endpoints skip the limiter:
  - /health is polled by Railway's healthcheck at high frequency
  - /api/public/webhooks/* are called by Meta/Retell servers, not user IPs
"""

import structlog
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import settings
from app.db.redis import redis_client

logger = structlog.get_logger()

# Paths that bypass the limit entirely.
_SKIP_PREFIXES = ("/health", "/api/public/webhooks", "/socket.io", "/socket.io-inbox")


def _client_ip(request: Request) -> str:
    """Prefer X-Forwarded-For's leftmost entry when we're behind a proxy
    (Railway, Cloudflare, ngrok all add this). Falls back to the socket
    peer if the header is missing — that's still the right value in dev."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class IPRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        ip = _client_ip(request)
        # Bucket per calendar minute — a client hitting the wall at :59 gets a
        # fresh window at :00, not a rolling 60s ban. Matches how per-org and
        # per-email limits already work in rate_limiter.py.
        key = f"iplimit:{ip}"
        try:
            count_raw = await redis_client.get(key)
            count = int(count_raw or 0)
            if count >= settings.IP_RATE_LIMIT_PER_MINUTE:
                logger.warning(
                    "ip_rate_limit_exceeded",
                    ip=ip,
                    path=path,
                    count=count,
                    limit=settings.IP_RATE_LIMIT_PER_MINUTE,
                )
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please slow down and retry."},
                    headers={"Retry-After": "60"},
                )
            # SET NX seeds the counter with its TTL; INCR after keeps the TTL
            # intact for the remainder of the window.
            if not await redis_client.set(key, 1, ex=60, nx=True):
                await redis_client.incr(key)
        except Exception as exc:  # noqa: BLE001 — Redis outage must not fail requests
            logger.warning("ip_rate_limit_redis_error", ip=ip, error=str(exc))

        return await call_next(request)
