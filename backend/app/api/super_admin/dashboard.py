from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_db_session
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import get_dashboard_stats

router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(db: AsyncSession = Depends(get_admin_db_session)) -> DashboardResponse:
    stats = await get_dashboard_stats(db)
    return DashboardResponse(**stats)
