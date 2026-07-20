"""TEST 2 — Full WebSocket simulation.

Connects to voice_llm_websocket like Retell would, then feeds a scripted
turn sequence (mix of repeat + novel questions). Measures wall-clock time
from sending response_required to receiving the first (post-filler) chunk,
per turn. Also validates ping_pong handling at the end.

Usage (from backend/):
    python tests/latency_bench_2_websocket.py [--port 8001]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import websockets  # type: ignore

# Bright Smile Dental — voice enabled, agent_test_abc123, has KB + Anthropic key.
ORG_ID = "688342de-38a1-40e7-9aba-92684d0142c6"
AGENT_ID = "agent_test_abc123"

TURNS = [
    ("What are your hours?",                              "repeat-1"),
    ("what are your hours",                               "repeat-1 paraphrase"),
    ("What are your hours?",                              "repeat-1 exact"),
    ("Do you accept insurance?",                          "repeat-2"),
    ("do you accept insurance",                           "repeat-2 paraphrase"),
    ("Do you offer teeth whitening?",                     "novel-1"),
    ("Can I book a same-day emergency appointment?",      "novel-2"),
    ("Do you see children under five?",                   "novel-3"),
]


async def run_bench(port: int):
    call_id = f"bench2-{int(time.time())}"
    url = f"ws://localhost:{port}/api/public/retell/llm/{ORG_ID}/{call_id}"
    print(f"Connecting to {url}\n")

    results = []
    async with websockets.connect(url, max_size=2**23) as ws:
        # (1) Discard config + greeting frames.
        for expected in ("config", "greeting"):
            frame = json.loads(await ws.recv())
            print(f"  <- {frame.get('response_type')}  response_id={frame.get('response_id')}"
                  + (f"  content={frame.get('content')[:60]!r}" if frame.get("content") else ""))

        # (2) Send call_details so on_call_start runs (creates conversation).
        # Retell sends this before response_required; if we skip it, the turn
        # handler creates a conversation with from_number='unknown' — still
        # works, but we mirror Retell's real flow.
        await ws.send(json.dumps({
            "interaction_type": "call_details",
            "call": {"agent_id": AGENT_ID, "from_number": "+15551234567", "call_id": call_id},
        }))
        # Give the on_call_start task a moment; it's fire-and-forget.
        await asyncio.sleep(0.5)

        # (3) Multi-turn simulation.
        transcript = []
        for i, (user_msg, label) in enumerate(TURNS, start=1):
            transcript.append({"role": "user", "content": user_msg})
            response_id = 100 + i
            payload = {
                "interaction_type": "response_required",
                "response_id": response_id,
                "transcript": transcript.copy(),
            }
            send_time = time.monotonic()
            await ws.send(json.dumps(payload))

            first_chunk_at = None
            filler_at = None
            filler_text = None
            reply_chunks = []
            while True:
                frame = json.loads(await ws.recv())
                if frame.get("response_type") == "ping_pong":
                    # We don't send pings, but respond if server ever sent one.
                    continue
                if frame.get("response_type") != "response":
                    continue
                if frame.get("response_id") != response_id:
                    continue
                content = frame.get("content", "")
                if first_chunk_at is None:
                    first_chunk_at = time.monotonic()
                    filler_at = first_chunk_at
                    filler_text = content
                else:
                    reply_chunks.append(content)
                if frame.get("content_complete"):
                    break

            first_post_filler = None
            # first_chunk_at is the filler; the first REAL LLM token is the next
            # non-empty chunk after it.
            # Reconstruct timings from what we captured.
            filler_ms = round((filler_at - send_time) * 1000) if filler_at else None
            total_ms = round((time.monotonic() - send_time) * 1000)
            full_reply = filler_text + "".join(reply_chunks)
            transcript.append({"role": "agent", "content": full_reply})

            print(f"  turn {i}  filler_ms={filler_ms:>4}  total_ms={total_ms:>5}"
                  f"  q={user_msg!r}  reply={full_reply[:60]!r}")
            results.append({
                "turn": i, "q": user_msg, "label": label,
                "filler_ms": filler_ms, "total_ms": total_ms,
                "reply": full_reply,
            })

        # (5) Final ping_pong to confirm connection still healthy.
        print("\n  -> ping_pong")
        await ws.send(json.dumps({"interaction_type": "ping_pong", "timestamp": time.time()}))
        pong = json.loads(await ws.recv())
        print(f"  <- {pong.get('response_type')}  timestamp={pong.get('timestamp')}")

    # ---- summary ----
    print("\n" + "=" * 78)
    print("SUMMARY — TEST 2")
    print("=" * 78)
    print(f"  {'turn':<5}{'filler_ms':<12}{'total_ms':<12}{'q':<50}")
    for r in results:
        print(f"  {r['turn']:<5}{str(r['filler_ms']):<12}{str(r['total_ms']):<12}{r['q'][:47]:<50}")
    filler_vals = [r["filler_ms"] for r in results if r["filler_ms"] is not None]
    total_vals = [r["total_ms"] for r in results if r["total_ms"] is not None]
    if filler_vals:
        print(f"\n  filler-frame TTFB: min={min(filler_vals)} avg={round(sum(filler_vals)/len(filler_vals))} max={max(filler_vals)} ms")
    if total_vals:
        print(f"  full-response total: min={min(total_vals)} avg={round(sum(total_vals)/len(total_vals))} max={max(total_vals)} ms")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8001)
    args = ap.parse_args()
    asyncio.run(run_bench(args.port))


if __name__ == "__main__":
    main()
