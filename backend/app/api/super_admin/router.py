from fastapi import APIRouter, Depends

from app.api.deps import require_super_admin
from app.api.super_admin.audit_logs import router as audit_logs_router
from app.api.super_admin.dashboard import router as dashboard_router
from app.api.super_admin.organizations import router as organizations_router
from app.api.super_admin.setup_wizard import router as setup_wizard_router
from app.api.super_admin.users import router as users_router

# Separate router + separate dependency chain from org_staff (root CLAUDE.md
# security rule #5) — every route here requires require_super_admin.
router = APIRouter(dependencies=[Depends(require_super_admin)])

router.include_router(organizations_router)
router.include_router(setup_wizard_router)
router.include_router(dashboard_router)
router.include_router(audit_logs_router)
router.include_router(users_router)
