import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import embed_batch, embed_text
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_chunk import KnowledgeChunk
from app.services.crawler_service import crawl_website


class ChunkNotFoundError(Exception):
    pass


class KnowledgeBaseNotFoundError(Exception):
    pass


async def create_knowledge_base(db: AsyncSession, org_id: uuid.UUID, name: str) -> KnowledgeBase:
    kb = KnowledgeBase(org_id=org_id, name=name)
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return kb


async def get_knowledge_base(db: AsyncSession, org_id: uuid.UUID, kb_id: uuid.UUID) -> KnowledgeBase:
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None or kb.org_id != org_id:
        raise KnowledgeBaseNotFoundError(str(kb_id))
    return kb


async def import_from_website(db: AsyncSession, org_id: uuid.UUID, kb_id: uuid.UUID, url: str) -> dict:
    result = await crawl_website(url)
    chunks = result["chunks"]

    errors: list[str] = []
    chunks_created = 0
    replaced_chunks = 0

    if chunks:
        # Re-crawling replaces the PRIOR crawl's chunks rather than adding
        # alongside them — otherwise chunks from two different crawls (e.g.
        # re-crawling a different URL into the same KB) mix together, and RAG
        # can surface the wrong business's address/contact info. Only delete
        # once we have new chunks to put in their place (a failed/empty crawl
        # shouldn't wipe out an existing, working knowledge base). Chunks
        # without source_url in metadata were added manually and are kept.
        existing_crawled_chunks = (
            await db.execute(
                select(KnowledgeChunk).where(
                    KnowledgeChunk.org_id == org_id,
                    KnowledgeChunk.knowledge_base_id == kb_id,
                    KnowledgeChunk.metadata_["source_url"].astext.isnot(None),
                )
            )
        ).scalars().all()
        replaced_chunks = len(existing_crawled_chunks)
        for old_chunk in existing_crawled_chunks:
            await db.delete(old_chunk)
        if replaced_chunks:
            await db.flush()

        try:
            embeddings = embed_batch([chunk["content"] for chunk in chunks])
        except Exception as exc:
            errors.append(f"Embedding failed: {exc}")
            embeddings = []

        for chunk, embedding in zip(chunks, embeddings, strict=True):
            db.add(
                KnowledgeChunk(
                    knowledge_base_id=kb_id,
                    org_id=org_id,
                    content=chunk["content"],
                    embedding=embedding,
                    metadata_={"title": chunk["title"], "source_url": chunk["source_url"]},
                )
            )
            chunks_created += 1
        await db.commit()

    return {
        "provider": result["provider"],
        "pages_crawled": result["pages_crawled"],
        "chunks_created": chunks_created,
        "replaced_chunks": replaced_chunks,
        "errors": errors,
    }


async def add_chunk(
    db: AsyncSession, org_id: uuid.UUID, kb_id: uuid.UUID, content: str, title: str | None = None
) -> KnowledgeChunk:
    chunk = KnowledgeChunk(
        knowledge_base_id=kb_id,
        org_id=org_id,
        content=content,
        embedding=embed_text(content),
        metadata_={"title": title} if title else {},
    )
    db.add(chunk)
    await db.commit()
    await db.refresh(chunk)
    return chunk


async def update_chunk(
    db: AsyncSession, chunk_id: uuid.UUID, content: str, title: str | None = None, org_id: uuid.UUID | None = None
) -> KnowledgeChunk:
    # org_id is optional (not every caller has it — e.g. the setup wizard's
    # admin session, which bypasses RLS entirely) but should be passed
    # whenever available for explicit defense-in-depth per root CLAUDE.md;
    # when omitted, RLS (org_staff's session-scoped app.tenant_id) is the
    # sole tenant-isolation layer.
    chunk = await db.get(KnowledgeChunk, chunk_id)
    if chunk is None or (org_id is not None and chunk.org_id != org_id):
        raise ChunkNotFoundError(str(chunk_id))
    chunk.content = content
    chunk.embedding = embed_text(content)
    if title is not None:
        chunk.metadata_ = {**(chunk.metadata_ or {}), "title": title}
    await db.commit()
    await db.refresh(chunk)
    return chunk


async def delete_chunk(db: AsyncSession, chunk_id: uuid.UUID, org_id: uuid.UUID | None = None) -> None:
    chunk = await db.get(KnowledgeChunk, chunk_id)
    if chunk is None or (org_id is not None and chunk.org_id != org_id):
        raise ChunkNotFoundError(str(chunk_id))
    await db.delete(chunk)
    await db.commit()


async def get_or_create_org_knowledge_base(
    db: AsyncSession, org_id: uuid.UUID, default_name: str = "Knowledge Base"
) -> KnowledgeBase:
    kb = (await db.execute(select(KnowledgeBase).where(KnowledgeBase.org_id == org_id))).scalars().first()
    if kb is None:
        kb = KnowledgeBase(org_id=org_id, name=default_name)
        db.add(kb)
        await db.commit()
        await db.refresh(kb)
    return kb


async def get_org_knowledge_base_with_chunks(
    db: AsyncSession, org_id: uuid.UUID
) -> tuple[KnowledgeBase | None, list[KnowledgeChunk]]:
    kb = (await db.execute(select(KnowledgeBase).where(KnowledgeBase.org_id == org_id))).scalars().first()
    if kb is None:
        return None, []
    return kb, await list_chunks(db, org_id, kb.id)


async def list_chunks(db: AsyncSession, org_id: uuid.UUID, kb_id: uuid.UUID) -> list[KnowledgeChunk]:
    result = await db.execute(
        select(KnowledgeChunk).where(KnowledgeChunk.org_id == org_id, KnowledgeChunk.knowledge_base_id == kb_id)
    )
    return list(result.scalars().all())


async def replace_knowledge_base(
    db: AsyncSession, org_id: uuid.UUID, name: str, chunk_contents: list[str]
) -> KnowledgeBase:
    """Create-or-replace the org's knowledge base: upsert the KnowledgeBase row
    and fully replace its chunks (simplest correct behavior for a setup-wizard
    step that can be revisited — avoids accumulating stale duplicate chunks).
    """
    kb = (
        await db.execute(select(KnowledgeBase).where(KnowledgeBase.org_id == org_id, KnowledgeBase.name == name))
    ).scalar_one_or_none()

    if kb is None:
        kb = KnowledgeBase(org_id=org_id, name=name)
        db.add(kb)
        await db.flush()
    else:
        existing_chunks = (
            await db.execute(select(KnowledgeChunk).where(KnowledgeChunk.knowledge_base_id == kb.id))
        ).scalars()
        for chunk in existing_chunks:
            await db.delete(chunk)
        await db.flush()

    if chunk_contents:
        embeddings = embed_batch(chunk_contents)
        for content, embedding in zip(chunk_contents, embeddings, strict=True):
            db.add(
                KnowledgeChunk(
                    knowledge_base_id=kb.id,
                    org_id=org_id,
                    content=content,
                    embedding=embedding,
                )
            )

    await db.commit()
    await db.refresh(kb)
    return kb


async def get_knowledge_base_chunks(db: AsyncSession, org_id: uuid.UUID) -> tuple[KnowledgeBase | None, list[str]]:
    kb = (await db.execute(select(KnowledgeBase).where(KnowledgeBase.org_id == org_id))).scalars().first()
    if kb is None:
        return None, []

    chunks = (
        await db.execute(select(KnowledgeChunk.content).where(KnowledgeChunk.knowledge_base_id == kb.id))
    ).scalars().all()
    return kb, list(chunks)
