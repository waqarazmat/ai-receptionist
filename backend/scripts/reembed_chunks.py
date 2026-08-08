"""Re-embed every knowledge_chunk with the CURRENT embedding model.

Run this ONCE after changing EMBEDDING_MODEL_NAME (e.g. switching to the
multilingual model) and deploying it. Query vectors and stored chunk vectors
must come from the same model, so until this finishes retrieval is degraded —
run it right after the deploy that ships the new model.

Idempotent: safe to run repeatedly (it just re-writes the same vectors). Works
in batches so a large KB doesn't hold one giant transaction.

Usage (from backend/, against whatever DATABASE_URL points to):
    PYTHONPATH=. python scripts/reembed_chunks.py
"""

import asyncio

from sqlalchemy import select

from app.ai.embeddings import EMBEDDING_DIMENSIONS, embed_batch, load_model
from app.config import settings
from app.db.engine import async_session_maker, engine
from app.db.redis import redis_client
from app.models.knowledge_chunk import KnowledgeChunk

BATCH_SIZE = 64


async def main() -> None:
    print(f"Loading embedding model: {settings.EMBEDDING_MODEL_NAME} …")
    load_model()

    total = 0
    async with async_session_maker() as db:
        ids = (await db.execute(select(KnowledgeChunk.id))).scalars().all()
    print(f"{len(ids)} chunks to re-embed ({EMBEDDING_DIMENSIONS}-dim), batch size {BATCH_SIZE}.")

    for start in range(0, len(ids), BATCH_SIZE):
        batch_ids = ids[start : start + BATCH_SIZE]
        async with async_session_maker() as db:
            rows = (
                await db.execute(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(batch_ids)))
            ).scalars().all()
            vectors = embed_batch([r.content for r in rows])
            for row, vec in zip(rows, vectors, strict=True):
                row.embedding = vec
            await db.commit()
        total += len(rows)
        print(f"  re-embedded {total}/{len(ids)}")

    # Voice RAG cache holds results keyed by (org, normalized query); every
    # vector just changed, so drop the whole cache rather than serve stale hits.
    try:
        async for key in redis_client.scan_iter(match="voice_qcache:*", count=500):
            await redis_client.delete(key)
    except Exception as exc:  # noqa: BLE001
        print(f"  (voice cache clear skipped: {exc})")

    await engine.dispose()
    print(f"Done. Re-embedded {total} chunks with {settings.EMBEDDING_MODEL_NAME}.")


if __name__ == "__main__":
    asyncio.run(main())
