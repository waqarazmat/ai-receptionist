"""Org-staff billing page — what plan am I on, how much have I used, how
much has it cost this month."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_org_staff
from app.models.user import User
from app.services.billing_service import get_org_billing

router = APIRouter()


@router.get("/billing/current")
async def current_billing(
    current_user: User = Depends(require_org_staff),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    if current_user.org_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No organization is associated with this account.",
        )
    return await get_org_billing(db, current_user.org_id)
