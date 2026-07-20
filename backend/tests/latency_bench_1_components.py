"""TEST 1 — Component-level latency bench.

Directly exercises the two hot paths in the voice pipeline in-process:
  A) _run_rag  → embed + hybrid_search (+ string-match cache)
  B) _stream_anthropic → TTFT (measures persistent SDK / TLS reuse)

No WebSocket, no Retell, no phone. All in one process. Structured logs
from the app fire naturally; a clean summary table prints at the end.

Usage (from backend/):
    python tests/latency_bench_1_components.py
"""

import asyncio
import os
import sys
import time
import uuid
from pathlib import Path

# Ensure `app.*` imports resolve when run as a script.
BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv
load_dotenv(str(BACKEND.parent / ".env"))

import structlog

from app.ai.embeddings import load_model
from app.ai.llm_router import get_org_llm_client, stream_llm
from app.ai.prompts.receptionist_system import get_system_prompt
from app.channels.voice.retell_handler import _run_rag
from app.db.engine import async_session_maker
from app.db.redis import redis_client

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(colors=False),
    ]
)
logger = structlog.get_logger()

ORG_ID = uuid.UUID("688342de-38a1-40e7-9aba-92684d0142c6")  # Bright Smile Dental
CALL_ID = f"bench1-{int(time.time())}"

REPEAT_QUERIES = [
    "What are your hours?",
    "what are your hours",             # normalization: same key
    "What are your hours?",            # exact repeat
    "Do you accept insurance?",
    "do you accept insurance",         # normalization: same key
]
NOVEL_QUERIES = [
    "Do you offer teeth whitening?",
    "Can I book a same-day emergency appointment?",
    "Is parking available at your clinic?",
    "Do you see children under five?",
    "Are digital X-rays part of a cleaning?",
]
ALL_QUERIES = REPEAT_QUERIES + NOVEL_QUERIES


async def bench_rag():
    print("\n" + "=" * 70)
    print("A) _run_rag — 10 queries (5 repeat/paraphrased + 5 novel)")
    print("=" * 70)

    # Flush any prior cache entries so hit/miss reflects THIS run.
    async for k in redis_client.scan_iter(match=f"voice_qcache:{ORG_ID}:*"):
        await redis_client.delete(k)

    results = []
    for i, q in enumerate(ALL_QUERIES, start=1):
        t0 = time.monotonic()
        chunks = await _run_rag(ORG_ID, CALL_ID, q)
        total_ms = round((time.monotonic() - t0) * 1000)
        results.append((i, q, len(chunks), total_ms))
        print(f"  turn {i:2}  total={total_ms:4} ms  chunks={len(chunks)}  q={q!r}")
    return results


async def bench_llm_ttft():
    print("\n" + "=" * 70)
    print("B) _stream_anthropic — 6 TTFT runs (same process, same SDK)")
    print("=" * 70)
    print("If persistent SDK/TLS reuse works, run 1 pays the handshake and")
    print("runs 2-6 should be markedly faster.\n")

    async with async_session_maker() as db:
        client = await get_org_llm_client(db, ORG_ID, model_tier="fast")
    print(f"  provider={client.provider.value}  model={client.model}  sdk={type(client.sdk).__name__}")

    system_prompt = get_system_prompt(
        {
            "org_name": "Bright Smile Dental",
            "personality": "warm, patient, and reassuring",
            "escalation_rules": "If distressed or asking about billing, connect to front desk.",
            "knowledge_context": "- Our hours are Monday to Friday nine AM to five PM.\n\n- We accept most major insurance plans.",
        },
        voice_mode=True,
    )

    prompts = [
        "What are your hours?",
        "Do you take walk-ins?",
        "How much is a cleaning?",
        "Can I book for next Tuesday?",
        "Do you have parking?",
        "Is emergency care available?",
    ]

    ttfts = []
    for i, user_msg in enumerate(prompts, start=1):
        start = time.monotonic()
        first_token_at = None
        collected = []
        try:
            async for tok in stream_llm(client, [{"role": "user", "content": user_msg}], system_prompt):
                if first_token_at is None:
                    first_token_at = time.monotonic()
                collected.append(tok)
        except Exception as exc:  # noqa: BLE001
            print(f"  turn {i}  ERROR: {exc}")
            ttfts.append((i, user_msg, None, None))
            continue
        ttft_ms = round((first_token_at - start) * 1000) if first_token_at else None
        total_ms = round((time.monotonic() - start) * 1000)
        preview = ("".join(collected))[:60].replace("\n", " ")
        ttfts.append((i, user_msg, ttft_ms, total_ms))
        print(f"  turn {i}  ttft={ttft_ms:4} ms  total={total_ms:4} ms  reply={preview!r}")
    return ttfts, client


async def main():
    print(f"Bright Smile Dental org_id={ORG_ID}  call_id={CALL_ID}")
    # Model must be loaded to embed (this backend does it in lifespan, but a
    # standalone script has no lifespan — call it explicitly).
    print("Loading embedding model...")
    t0 = time.monotonic()
    await asyncio.to_thread(load_model)
    print(f"  loaded in {round((time.monotonic()-t0)*1000)} ms\n")

    rag_results = await bench_rag()
    llm_results, client = await bench_llm_ttft()

    print("\n" + "=" * 70)
    print("SUMMARY — TEST 1")
    print("=" * 70)
    print("\nRAG (component A):")
    print(f"  {'turn':<5}{'q':<50}{'chunks':<8}{'ms':<6}")
    for i, q, ch, ms in rag_results:
        print(f"  {i:<5}{q[:47]:<50}{ch:<8}{ms:<6}")
    print("\nLLM TTFT (component B):")
    print(f"  {'turn':<5}{'ttft_ms':<10}{'total_ms':<10}{'q':<40}")
    for i, q, ttft, total in llm_results:
        print(f"  {i:<5}{str(ttft):<10}{str(total):<10}{q[:37]:<40}")

    valid_ttfts = [t for _, _, t, _ in llm_results if t is not None]
    if len(valid_ttfts) >= 2:
        print(f"\n  first TTFT  = {valid_ttfts[0]} ms  (pays TLS handshake)")
        avg_rest = sum(valid_ttfts[1:]) / len(valid_ttfts[1:])
        print(f"  avg TTFT 2-{len(valid_ttfts)} = {round(avg_rest)} ms  (reused SDK/connection)")
        print(f"  Δ (persistent-connection saving) ≈ {valid_ttfts[0] - round(avg_rest)} ms")

    await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
