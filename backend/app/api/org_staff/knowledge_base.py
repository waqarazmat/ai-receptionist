import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.knowledge_base import ChunkCreateRequest, ChunkListResponse, ChunkResponse, ChunkUpdateRequest
from app.services import knowledge_base_service

router = APIRouter()


@router.get("/knowledge-base", response_model=ChunkListResponse)
async def get_knowledge_base(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ChunkListResponse:
    kb, chunks = await knowledge_base_service.get_org_knowledge_base_with_chunks(db, current_user.org_id)
    return ChunkListResponse(
        knowledge_base_id=kb.id if kb else None,
        knowledge_base_name=kb.name if kb else None,
        chunks=chunks,
    )


@router.post("/knowledge-base/chunks", response_model=ChunkResponse, status_code=status.HTTP_201_CREATED)
async def add_chunk(
    body: ChunkCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ChunkResponse:
    kb = await knowledge_base_service.get_or_create_org_knowledge_base(db, current_user.org_id)
    return await knowledge_base_service.add_chunk(db, current_user.org_id, kb.id, body.content, title=body.title)


@router.put("/knowledge-base/chunks/{chunk_id}", response_model=ChunkResponse)
async def update_chunk(
    chunk_id: uuid.UUID,
    body: ChunkUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ChunkResponse:
    try:
        return await knowledge_base_service.update_chunk(
            db, chunk_id, body.content, title=body.title, org_id=current_user.org_id
        )
    except knowledge_base_service.ChunkNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chunk not found")


@router.delete("/knowledge-base/chunks/{chunk_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chunk(
    chunk_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    try:
        await knowledge_base_service.delete_chunk(db, chunk_id, org_id=current_user.org_id)
    except knowledge_base_service.ChunkNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chunk not found")
