from fastapi import APIRouter

from app.channels.voice.retell_handler import webhook_router as retell_webhook_router
from app.channels.whatsapp.webhook_handler import router as whatsapp_router

router = APIRouter()

router.include_router(whatsapp_router)
router.include_router(retell_webhook_router)
