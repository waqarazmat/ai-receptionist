import asyncio
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.ai.embeddings import load_model as load_embedding_model
from app.api.auth.router import router as auth_router
from app.api.health import router as health_router
from app.api.org_staff.router import router as org_staff_router
from app.api.public.router import router as public_router
from app.api.super_admin.router import router as admin_router
from app.config import settings
from app.db.redis import redis_client
from app.security.ip_rate_limiter import IPRateLimitMiddleware
from app.security.security_headers import SecurityHeadersMiddleware
from app.tasks.queue import get_arq_pool
from app.utils.logging import configure_logging

# Sentry — initialised BEFORE FastAPI so the SDK's FastAPI/Starlette
# integration can hook into every route. Silently a no-op if SENTRY_DSN
# is unset (dev). In production a stray exception is now a Sentry issue
# with request context + user id + org id automatically attached.
if settings.SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.asyncio import AsyncioIntegration
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.APP_ENV,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        # PII must not leave the app — logs and request bodies can contain
        # OTP codes, JWTs, encrypted keys, contact PII. Sentry's `send_default_pii`
        # is off by default; we assert it explicitly so a future SDK
        # major-version doesn't silently flip the default.
        send_default_pii=False,
        integrations=[
            FastApiIntegration(),
            StarletteIntegration(),
            SqlalchemyIntegration(),
            AsyncioIntegration(),
        ],
    )

configure_logging()
logger = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers["X-Request-ID"] = request_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_client.ping()
    # Loaded once here, not per-request — encode() is CPU-bound so run it off
    # the event loop even though this only happens once at startup.
    await asyncio.to_thread(load_embedding_model)
    # Warm the Arq pool here too — otherwise the first inbound webhook pays
    # for establishing the Redis connection on the request's critical path,
    # which risks a slow/timed-out response to Meta.
    await get_arq_pool()
    logger.info("startup_complete", app_env=settings.APP_ENV)
    yield
    await redis_client.aclose()
    logger.info("shutdown_complete")


# Hide the interactive schema surface in production — /docs and /redoc list
# every endpoint (including super-admin routes) and expose their pydantic
# schemas. Handy in dev, unnecessary attack-surface in prod. This does NOT
# affect functional routes; only the discovery/UI endpoints are gated.
_is_prod = settings.APP_ENV == "production"
app = FastAPI(
    title="AI Receptionist API",
    lifespan=lifespan,
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)

# Middleware order matters — Starlette runs them OUTSIDE-IN, so the LAST
# add_middleware is the OUTERMOST wrapper (runs first on a request). We want:
#   1. Security headers (outermost — always sets headers on the response, even 429s)
#   2. IP rate limit (short-circuits abusive traffic before it touches CORS)
#   3. CORS
#   4. RequestID (innermost — needs request context set)
# Add them in reverse of that order:
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(IPRateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(admin_router, prefix="/api/admin", tags=["super-admin"])
app.include_router(org_staff_router, prefix="/api/org", tags=["org-staff"])
app.include_router(public_router, prefix="/api/public", tags=["public"])
app.include_router(health_router, tags=["health"])

# Debug router — mounted ONLY in development. The e2e Playwright suite
# reads OTP codes from Redis through it (bypasses Brevo). Never mount in
# prod: it'd expose an endpoint that returns OTP codes given an email.
if settings.APP_ENV == "development":
    from app.api.debug import router as debug_router

    app.include_router(debug_router, prefix="/api/debug", tags=["debug"])

# Imported for side effect: registers @sio.on(...) handlers (connect,
# send_message, join_org_room, etc.) on the shared AsyncServer instance.
# NOTE: deliberately `from X import Y`, not `import app.foo.bar` — the
# project's top-level package is itself named `app`, so a bare dotted import
# here would rebind this module's local `app` name to the *package*,
# clobbering the FastAPI instance below before it gets wrapped.
from app.channels.webchat import handler as _webchat_handler  # noqa: E402, F401
from app.realtime import events as _realtime_events  # noqa: E402, F401
from app.realtime.socket_manager import create_socket_asgi_app  # noqa: E402

# Wrap the FastAPI app so Socket.IO can intercept /socket.io/* traffic while
# everything else (including the lifespan above) still reaches `app` as-is.
# `uvicorn app.main:app` picks up this wrapped app since it's still bound to
# the name `app`.
app = create_socket_asgi_app(app)
