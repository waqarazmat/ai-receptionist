import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.enums import ConversationStatus
from app.models.user import User
from app.schemas.conversation import ConversationListResponse, ConversationResponse
from app.schemas.message import MessageListResponse, MessageResponse, StaffMessageCreate
from app.services import conversation_service

router = APIRouter()


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    status_filter: ConversationStatus | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ConversationListResponse:
    conversations = await conversation_service.list_conversations(db, current_user.org_id, status_filter)
    return ConversationListResponse(conversations=conversations)


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ConversationResponse:
    try:
        return await conversation_service.get_conversation(db, current_user.org_id, conversation_id)
    except conversation_service.ConversationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse)
async def get_conversation_messages(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> MessageListResponse:
    # Confirms the conversation belongs to this org (raises 404 otherwise)
    # before returning its messages — defense in depth alongside RLS.
    try:
        await conversation_service.get_conversation(db, current_user.org_id, conversation_id)
    except conversation_service.ConversationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    messages = await conversation_service.get_conversation_messages(db, conversation_id)
    return MessageListResponse(messages=messages)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_staff_message(
    conversation_id: uuid.UUID,
    body: StaffMessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    try:
        await conversation_service.get_conversation(db, current_user.org_id, conversation_id)
    except conversation_service.ConversationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    return await conversation_service.send_staff_reply(db, conversation_id, body.content, current_user.id)


@router.post("/conversations/{conversation_id}/takeover", response_model=ConversationResponse)
async def take_over_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ConversationResponse:
    try:
        return await conversation_service.take_over_conversation(
            db, current_user.org_id, conversation_id, current_user.id
        )
    except conversation_service.ConversationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


@router.post("/conversations/{conversation_id}/release", response_model=ConversationResponse)
async def release_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ConversationResponse:
    try:
        return await conversation_service.release_conversation(db, current_user.org_id, conversation_id)
    except conversation_service.ConversationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


@router.post("/conversations/{conversation_id}/resolve", response_model=ConversationResponse)
async def resolve_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ConversationResponse:
    try:
        return await conversation_service.resolve_conversation(db, current_user.org_id, conversation_id)
    except conversation_service.ConversationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
