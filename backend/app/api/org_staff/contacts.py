import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.contact import ContactDetailResponse, ContactListResponse
from app.services import contact_service

router = APIRouter()


@router.get("/contacts", response_model=ContactListResponse)
async def list_contacts(
    search: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ContactListResponse:
    contacts = await contact_service.list_contacts(db, current_user.org_id, search)
    return ContactListResponse(contacts=contacts)


@router.get("/contacts/{contact_id}", response_model=ContactDetailResponse)
async def get_contact(
    contact_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ContactDetailResponse:
    try:
        return await contact_service.get_contact(db, current_user.org_id, contact_id)
    except contact_service.ContactNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
