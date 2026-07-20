from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import OrgProfileResponse

router = APIRouter()


@router.get("/settings", response_model=OrgProfileResponse)
async def get_org_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> OrgProfileResponse:
    return await db.get(Organization, current_user.org_id)
