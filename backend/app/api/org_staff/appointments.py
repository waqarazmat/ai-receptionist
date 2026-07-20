import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.enums import AppointmentStatus
from app.models.user import User
from app.schemas.appointment import AppointmentListResponse, AppointmentResponse
from app.services import appointment_service

router = APIRouter()


@router.get("/appointments", response_model=AppointmentListResponse)
async def list_appointments(
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    status_filter: AppointmentStatus | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> AppointmentListResponse:
    appointments = await appointment_service.list_appointments(
        db, current_user.org_id, start_date, end_date, status_filter
    )
    return AppointmentListResponse(appointments=appointments)


@router.get("/appointments/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> AppointmentResponse:
    try:
        return await appointment_service.get_appointment(db, current_user.org_id, appointment_id)
    except appointment_service.AppointmentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")


@router.put("/appointments/{appointment_id}/cancel", response_model=AppointmentResponse)
async def cancel_appointment(
    appointment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> AppointmentResponse:
    try:
        return await appointment_service.cancel_appointment(db, current_user.org_id, appointment_id)
    except appointment_service.AppointmentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
