import time

from fastapi import APIRouter
from sqlalchemy import text

from app.db.engine import async_session_maker
from app.db.redis import redis_client

router = APIRouter()

_start_time = time.monotonic()


@router.get("/health")
async def health_check() -> dict:
    db_ok = False
    redis_ok = False

    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    try:
        redis_ok = bool(await redis_client.ping())
    except Exception:
        redis_ok = False

    return {
        "status": "healthy" if db_ok and redis_ok else "degraded",
        "db": db_ok,
        "redis": redis_ok,
        "uptime_seconds": int(time.monotonic() - _start_time),
    }
