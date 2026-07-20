from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.dashboard import OrgDashboardResponse
from app.services.dashboard_service import get_org_dashboard_stats

router = APIRouter()


@router.get("/dashboard", response_model=OrgDashboardResponse)
async def org_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> OrgDashboardResponse:
    stats = await get_org_dashboard_stats(db, current_user.org_id)
    return OrgDashboardResponse(**stats)
