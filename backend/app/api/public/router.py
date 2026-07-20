from fastapi import APIRouter

from app.api.public.webchat import router as webchat_router
from app.api.public.webhooks import router as webhooks_router
from app.channels.voice.retell_handler import ws_router as retell_ws_router

# No auth dependency here (unlike super_admin/org_staff routers) — these
# routes are public by nature (Meta/Retell call them directly) and secured
# via HMAC signature verification instead of a JWT (root CLAUDE.md rule #3).
# The Retell Custom LLM WebSocket is the one exception with no HMAC scheme of
# its own — see the comment on ws_router in retell_handler.py for how it's
# authorized instead. webchat_router (widget config + history) is public by
# design — it's read by anonymous site visitors before they're ever a
# "customer" the app has an identity for.
router = APIRouter()

router.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
router.include_router(retell_ws_router, prefix="/retell", tags=["voice"])
router.include_router(webchat_router, tags=["webchat"])
