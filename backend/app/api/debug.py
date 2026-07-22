"""Dev-only debug endpoints. GATED at import time on APP_ENV=development —
none of these routes are registered when APP_ENV=production, so an attacker
who somehow guessed a path would get a 404 identical to any other missing
route. Used by e2e tests and local admin scripts.

Never add a route here that returns a secret without checking the env gate
first — even accidentally shipping this router to prod is meant to be a
no-op, but layering doesn't hurt.
"""

from fastapi import APIRouter, HTTPException, Query, status

from app.config import settings
from app.db.redis import redis_client

router = APIRouter()


@router.get("/otp")
async def peek_otp(email: str = Query(..., description="Email whose OTP to peek at.")) -> dict:
    """Return the current OTP for `email` from Redis. Used by the Playwright
    e2e suite to bypass Brevo (Playwright can't read Gmail).

    Belt-and-suspenders: even though the router itself is only mounted when
    APP_ENV=development, we also refuse to answer in production here. If
    someone ever imports and mounts this router unconditionally, this check
    keeps the endpoint safe.
    """
    if settings.APP_ENV != "development":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    code = await redis_client.get(f"otp:{email}")
    if code is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No OTP pending for this email.")
    ttl = await redis_client.ttl(f"otp:{email}")
    return {"email": email, "code": code, "ttl_seconds": ttl}
