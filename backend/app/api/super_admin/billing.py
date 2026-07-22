"""Super-admin billing analytics — platform-wide + per-org drill-down.

Returns dict rather than a strict Pydantic response model because the shape
has heterogeneous nested types (dict of dicts of floats). The frontend
consumes it as `AnalyticsResponse | BillingResponse` typed on the client.
Keeping Pydantic out here avoids the ceremony of nine nested BaseModels
for a payload that changes as we tune the cost model.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_db_session
from app.services.billing_service import get_platform_billing

router = APIRouter()


@router.get("/billing/analytics")
async def billing_analytics(
    days: int = Query(default=30, ge=1, le=365),
    org_id: uuid.UUID | None = Query(default=None, description="Filter to one org; omit for platform-wide"),
    db: AsyncSession = Depends(get_admin_db_session),
) -> dict:
    return await get_platform_billing(db, days=days, org_id=org_id)
