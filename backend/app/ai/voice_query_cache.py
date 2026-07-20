"""Per-org query cache for the voice channel's RAG lookup.

Two-layer design:

  1. **Cheap normalized-string match** (this module). Runs BEFORE embedding.
     A hit skips both the sentence-transformers CPU inference (~50-200 ms)
     AND the Postgres hybrid search (~30-150 ms). Miss cost is one Redis GET.

  2. Semantic (embedding-similarity) cache — deliberately NOT implemented
     here yet. The audit conversation noted the trap: to compare embeddings
     you have to embed the incoming query first, which means a semantic
     layer only saves the DB search, not the embedding step. On voice, the
     embedding is the slower half — so the string-match layer is where the
     real win is. Revisit only if hit-rate data shows the normalized string
     match missing near-duplicates the caller actually asks in practice.

Cache key is org-scoped (`voice_qcache:{org_id}:{normalized}`) so tenants
never see each other's answers. TTL is 5 minutes: voice queries are highly
repetitive within a single call (customer rephrasing the same question) and
across a busy hour (many callers asking the same FAQ), but knowledge base
edits by staff need to invalidate quickly enough to not surprise them.
"""

from __future__ import annotations

import json
import re

import structlog

from app.db.redis import redis_client

logger = structlog.get_logger()

_KEY_PREFIX = "voice_qcache"
_TTL_SECONDS = 300

# Strip anything that isn't a word char or whitespace, collapse whitespace,
# lowercase. Deliberately naive — good enough to collapse "What are your hours?"
# and "what are your hours" to the same key without pulling in stemming.
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize(query: str) -> str:
    q = query.lower().strip()
    q = _PUNCT_RE.sub(" ", q)
    q = _WHITESPACE_RE.sub(" ", q).strip()
    return q


def _key(org_id: str, normalized: str) -> str:
    return f"{_KEY_PREFIX}:{org_id}:{normalized}"


async def get_cached_chunks(org_id: str, query: str) -> list[dict] | None:
    """Return cached chunk payloads (list of {content, score}) or None on miss.
    Never raises — a Redis hiccup just degrades to a cache miss."""
    normalized = _normalize(query)
    if not normalized:
        return None
    try:
        raw = await redis_client.get(_key(org_id, normalized))
    except Exception as exc:  # noqa: BLE001
        logger.warning("voice_qcache_get_failed", org_id=org_id, error=str(exc))
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        # Corrupt entry — treat as miss so the caller re-populates fresh.
        return None


async def set_cached_chunks(org_id: str, query: str, chunks: list) -> None:
    """Persist the chunk payloads under the normalized query key. Only stores
    content + score (not chunk_id / embedding) because that's all downstream
    prompt-building needs. Never raises."""
    normalized = _normalize(query)
    if not normalized:
        return
    payload = json.dumps(
        [{"content": c.content, "score": getattr(c, "score", 0.0)} for c in chunks]
    )
    try:
        await redis_client.set(_key(org_id, normalized), payload, ex=_TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001
        logger.warning("voice_qcache_set_failed", org_id=org_id, error=str(exc))
