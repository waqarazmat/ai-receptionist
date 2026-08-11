import socketio
from fastapi import FastAPI

from app.config import settings

# Two separate Engine.IO servers, not just two namespaces on one server.
# CORS is enforced at the Engine.IO HTTP handshake, which happens BEFORE the
# client declares which Socket.IO namespace it wants — so a single
# AsyncServer can't apply a different CORS policy per namespace. Splitting
# into two physical servers is what actually lets /chat and /inbox have
# different origin policies:
#
# - chat_sio (customer widget, /chat namespace) is embedded on arbitrary
#   third-party websites in production, so it must accept any origin.
# - inbox_sio (staff live inbox, /inbox namespace) is only ever used by our
#   own admin panel, so it stays restricted to CORS_ORIGINS.
#
# `transports=None` (the default) leaves both polling and websocket enabled
# on both servers.
def _client_manager(channel: str):
    """A Redis-backed client manager so emits fan out across multiple web
    workers/replicas; None (default) uses Socket.IO's in-process manager, which
    is correct and unchanged for a single worker. The two servers use DISTINCT
    Redis channels so /chat and /inbox pub/sub never cross. Enable via
    SOCKETIO_REDIS_MANAGER before scaling past one worker."""
    if settings.SOCKETIO_REDIS_MANAGER:
        return socketio.AsyncRedisManager(settings.REDIS_URL, channel=channel)
    return None


chat_sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    client_manager=_client_manager("socketio_chat"),
)
inbox_sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.CORS_ORIGINS,
    client_manager=_client_manager("socketio_inbox"),
)


def create_socket_asgi_app(fastapi_app: FastAPI) -> socketio.ASGIApp:
    """Wrap the FastAPI app so Socket.IO can intercept /socket.io/* requests
    and pass everything else through untouched — including the lifespan
    protocol, so startup/shutdown still runs on the wrapped app.

    chat_sio takes the default engine.io path ("/socket.io/...") so the
    widget (embedded on customer sites) needs no special client config.
    inbox_sio is mounted on a distinct path ("/socket.io-inbox/...") since
    two ASGI sub-apps can't share one HTTP path prefix with different CORS
    policies — the staff socket client passes a matching `path` option.
    """
    app_with_chat = socketio.ASGIApp(chat_sio, other_asgi_app=fastapi_app)
    app_with_both = socketio.ASGIApp(
        inbox_sio, other_asgi_app=app_with_chat, socketio_path="socket.io-inbox"
    )
    return app_with_both
