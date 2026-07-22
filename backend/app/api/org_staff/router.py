from fastapi import APIRouter, Depends

from app.api.deps import require_org_staff
from app.api.org_staff.appointments import router as appointments_router
from app.api.org_staff.billing import router as billing_router
from app.api.org_staff.contacts import router as contacts_router
from app.api.org_staff.conversations import router as conversations_router
from app.api.org_staff.dashboard import router as dashboard_router
from app.api.org_staff.escalations import router as escalations_router
from app.api.org_staff.exports import router as exports_router
from app.api.org_staff.knowledge_base import router as knowledge_base_router
from app.api.org_staff.settings import router as settings_router
from app.api.org_staff.team import router as team_router

# Separate router + separate dependency chain from super_admin (root CLAUDE.md
# security rule #5) — every route here requires require_org_staff, and
# get_db_session (used throughout) sets the RLS tenant context per request.
router = APIRouter(dependencies=[Depends(require_org_staff)])

router.include_router(conversations_router)
router.include_router(escalations_router)
router.include_router(dashboard_router)
router.include_router(appointments_router)
router.include_router(contacts_router)
router.include_router(knowledge_base_router)
router.include_router(settings_router)
router.include_router(team_router)
router.include_router(exports_router)
router.include_router(billing_router)
