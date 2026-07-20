from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import settings

_pool: ArqRedis | None = None


def get_redis_settings() -> RedisSettings:
    """Arq Redis settings tuned for a REMOTE Redis (Railway/Upstash over the
    public internet), shared by the enqueue pool here and the worker
    (app/tasks/worker.py).

    arq's default conn_timeout is 1s, which doubles as the redis-py
    socket_timeout — far too tight over the internet: a single slow poll
    (DNS/TCP/TLS blip) raises TimeoutError and aborts the whole worker (seen
    as `redis.exceptions.TimeoutError: Timeout connecting to server`). Widen
    the timeout and add connection retries so a transient blip is retried
    instead of crashing the process."""
    rs = RedisSettings.from_dsn(settings.REDIS_URL)
    rs.conn_timeout = 15
    rs.conn_retries = 10
    rs.conn_retry_delay = 1
    return rs


async def get_arq_pool() -> ArqRedis:
    """Lazily-created, process-wide Arq Redis pool for enqueueing on-demand
    jobs from the API layer (as opposed to the cron jobs defined directly on
    WorkerSettings). Cached so each webhook request doesn't open a fresh
    Redis connection."""
    global _pool
    if _pool is None:
        _pool = await create_pool(get_redis_settings())
    return _pool
