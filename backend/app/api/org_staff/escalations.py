import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.escalation import EscalationListResponse, EscalationResponse
from app.services import escalation_service

router = APIRouter()


@router.get("/escalations", response_model=EscalationListResponse)
async def list_escalations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> EscalationListResponse:
    escalations = await escalation_service.list_escalations(db, current_user.org_id)
    return EscalationListResponse(escalations=escalations)


@router.post("/escalations/{escalation_id}/pickup", response_model=EscalationResponse)
async def pick_up_escalation(
    escalation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> EscalationResponse:
    try:
        return await escalation_service.pick_up_escalation(
            db, current_user.org_id, escalation_id, current_user.id
        )
    except escalation_service.EscalationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escalation not found")
