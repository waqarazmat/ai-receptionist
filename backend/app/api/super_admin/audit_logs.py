import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_db_session
from app.services.audit_service import list_audit_logs

router = APIRouter()


class AuditLogEntry(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    action: str
    target_type: str
    target_id: uuid.UUID | None
    details: dict
    ip_address: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    entries: list[AuditLogEntry]
    total: int
    page: int
    page_size: int


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def get_audit_logs(
    action: str | None = None,
    user_id: uuid.UUID | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_admin_db_session),
) -> AuditLogListResponse:
    entries, total = await list_audit_logs(
        db,
        action=action,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    return AuditLogListResponse(entries=entries, total=total, page=page, page_size=page_size)
