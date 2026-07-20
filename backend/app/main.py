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
from app.tasks.queue import get_arq_pool
from app.utils.logging import configure_logging

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


app = FastAPI(title="AI Receptionist API", lifespan=lifespan)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(admin_router, prefix="/api/admin", tags=["super-admin"])
app.include_router(org_staff_router, prefix="/api/org", tags=["org-staff"])
app.include_router(public_router, prefix="/api/public", tags=["public"])
app.include_router(health_router, tags=["health"])

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
