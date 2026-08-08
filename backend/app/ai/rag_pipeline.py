import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_chunk import KnowledgeChunk

logger = structlog.get_logger()

# Lowered from 0.3 after live testing against a real crawled KB: several
# genuinely-relevant queries (e.g. "how do I get to your office", "what are
# your services") scored 0.30-0.37, right at the old cutoff — a small margin
# was tipping legitimate FAQ answers into escalation.
DEFAULT_CONFIDENCE_THRESHOLD = 0.25
RRF_K = 60


@dataclass
class ChunkResult:
    chunk_id: uuid.UUID
    content: str
    score: float


async def hybrid_search(
    db: AsyncSession,
    org_id: uuid.UUID,
    query_text: str,
    query_embedding: list[float],
    top_k: int = 5,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> list[ChunkResult]:
    """Semantic (pgvector) + full-text search, merged via reciprocal rank fusion.

    RRF only decides ORDER — its fused score reflects relative rank, not actual
    relevance, so with a small knowledge base an entirely unrelated query can
    still land a chunk "first" and score near the RRF max. The confidence gate
    below is therefore based on real cosine similarity of the top semantic
    match, not the RRF score. If that's below `confidence_threshold`, returns
    an empty list — callers should treat that as "no good answer" and
    escalate rather than let the LLM improvise.
    """
    candidate_pool = max(top_k * 2, 10)

    semantic_stmt = (
        select(
            KnowledgeChunk.id,
            KnowledgeChunk.content,
            KnowledgeChunk.embedding.cosine_distance(query_embedding).label("distance"),
        )
        .where(KnowledgeChunk.org_id == org_id)
        .order_by("distance")
        .limit(candidate_pool)
    )
    semantic_rows = (await db.execute(semantic_stmt)).all()

    # 'simple' (not 'english') so full-text search is language-neutral: no
    # English stemming that would mangle Dutch/other-language content, and no
    # English stop-word list dropping meaningful foreign words. The multilingual
    # embedding leg carries cross-lingual matching; FTS here is the exact-keyword
    # backstop, which 'simple' handles correctly for any language.
    fts_condition = text(
        "to_tsvector('simple', content) @@ plainto_tsquery('simple', :query)"
    ).bindparams(query=query_text)
    fts_order = text(
        "ts_rank_cd(to_tsvector('simple', content), plainto_tsquery('simple', :query)) DESC"
    ).bindparams(query=query_text)

    fts_stmt = (
        select(KnowledgeChunk.id, KnowledgeChunk.content)
        .where(KnowledgeChunk.org_id == org_id, fts_condition)
        .order_by(fts_order)
        .limit(candidate_pool)
    )
    fts_rows = (await db.execute(fts_stmt)).all()

    fused_scores: dict[uuid.UUID, float] = {}
    content_by_id: dict[uuid.UUID, str] = {}
    # cosine_distance is 0 (identical) to 2 (opposite); similarity = 1 - distance.
    # This is the real relevance signal — unlike the RRF score, it's meaningful
    # in isolation and doesn't inflate just because the candidate pool is small.
    similarity_by_id: dict[uuid.UUID, float] = {}

    for rank, row in enumerate(semantic_rows):
        fused_scores[row.id] = fused_scores.get(row.id, 0.0) + 1.0 / (RRF_K + rank + 1)
        content_by_id[row.id] = row.content
        similarity_by_id[row.id] = 1.0 - row.distance

    for rank, row in enumerate(fts_rows):
        fused_scores[row.id] = fused_scores.get(row.id, 0.0) + 1.0 / (RRF_K + rank + 1)
        content_by_id[row.id] = row.content

    if not fused_scores:
        return []

    ranked = sorted(fused_scores.items(), key=lambda item: item[1], reverse=True)[:top_k]

    results = [
        ChunkResult(
            chunk_id=chunk_id,
            # A chunk that only matched via full-text (not in the semantic
            # candidate pool) has no similarity computed — default to 0.0,
            # which correctly biases toward escalating rather than guessing.
            content=content_by_id[chunk_id],
            score=max(similarity_by_id.get(chunk_id, 0.0), 0.0),
        )
        for chunk_id, _rrf_score in ranked
    ]

    # "Best score" = highest actual similarity in the set, not just results[0]
    # — RRF order and similarity order can disagree (e.g. an FTS-only match
    # can rank first by fusion while scoring a default 0.0 similarity).
    best_score = max(r.score for r in results)
    logger.info(
        "rag_hybrid_search",
        org_id=str(org_id),
        query=query_text,
        best_score=round(best_score, 4),
        threshold=confidence_threshold,
        passed=best_score >= confidence_threshold,
        scores=[round(r.score, 4) for r in results],
    )
    if best_score < confidence_threshold:
        return []

    return results
