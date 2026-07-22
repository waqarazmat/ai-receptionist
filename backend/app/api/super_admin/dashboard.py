from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_db_session
from app.schemas.dashboard import AnalyticsResponse, DashboardResponse
from app.services.analytics_service import get_platform_analytics
from app.services.dashboard_service import get_dashboard_stats

router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(db: AsyncSession = Depends(get_admin_db_session)) -> DashboardResponse:
    stats = await get_dashboard_stats(db)
    return DashboardResponse(**stats)


@router.get("/dashboard/analytics", response_model=AnalyticsResponse)
async def dashboard_analytics(
    days: int = Query(default=30, ge=1, le=365, description="Rollup window in days"),
    db: AsyncSession = Depends(get_admin_db_session),
) -> AnalyticsResponse:
    """Platform-wide analytics for the super-admin dashboard.

    Serves the KPI cards, messages-per-day chart, channel breakdown donut,
    and per-org table in one round-trip. Cheap enough at current scale to
    fetch on every dashboard mount; if it ever gets slow, cache in Redis
    keyed by `days` with a 5-minute TTL.
    """
    data = await get_platform_analytics(db, days=days)
    return AnalyticsResponse(**data)
