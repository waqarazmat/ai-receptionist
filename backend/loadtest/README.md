# Web-chat load testing

Load-tests the Socket.IO web-chat pipeline the same way the widget hits it:
open `/chat`, send messages, wait for the streamed reply. Measures **time-to-first-token**
and **time-to-complete** under concurrency, so you can find where it falls over.

## ⚠️ Before you start
- **Which database?** The backend writes conversations/messages to whatever
  `DATABASE_URL` points at. If your local `.env` points at the **prod Railway
  Postgres**, this test pollutes prod tables. Prefer a **local Postgres**, or use a
  dedicated test org and run `cleanup.py` afterwards (see bottom).
- **Use a test org**, never a real customer's. It just needs to exist and be
  `is_active=true`. In mock mode it needs **no LLM keys**. A few KB chunks make the
  FAQ scenario realistic (otherwise FAQ escalates on an empty match — still valid load).
- The per-org message rate limit (~500/hr) will trip on a big run and return a static
  reply. Raise it for the test org or keep runs short if you care about that ceiling.

## 1. Install
```bash
pip install -r loadtest/requirements.txt
```

## 2. Run the backend in MOCK mode (find your infra ceiling first)
Mock mode returns canned LLM responses — no API keys, no cost, no provider rate
limits — so you measure Socket.IO + embeddings + pgvector + Redis + DB in isolation.
```bash
# from backend/
LOAD_TEST_MOCK_LLM=true uvicorn app.main:app --host 0.0.0.0 --port 8000
```
(Windows PowerShell: `$env:LOAD_TEST_MOCK_LLM="true"; uvicorn app.main:app --port 8000`)

Confirm it logs mock mode on the first message (no `llm_call` / `llm_stream` lines).

## 3. Run Locust
```bash
export LOADTEST_ORG_ID=<active-org-uuid>
locust -f loadtest/locustfile.py --host http://localhost:8000
```
Open http://localhost:8089. Start at **5 users**, spawn rate 5, hold ~2 min; then
step **10 → 25 → 50 → 100 …**, watching for the "knee":

- `faq:ttft` / `faq:complete` p95 climbing sharply
- failures appearing (timeouts, connect errors)
- backend CPU pinned at 100% on one core → the synchronous `embed_text()` blocking
  the event loop (the predicted first bottleneck; fix = offload to a threadpool)

## 4. What to watch while it runs
- **Locust**: RPS, p50/p95/p99 per request name, failure count.
- **Backend host**: CPU/mem (one core maxed = event-loop block).
- **Postgres**: `SELECT count(*) FROM pg_stat_activity;` — watch for pool exhaustion.
- **Redis**: `redis-cli INFO clients`.

## 5. Real end-to-end pass (after mock)
Restart the backend **without** `LOAD_TEST_MOCK_LLM` (test org now needs a real,
spend-capped LLM key), and run Locust at **low** concurrency (5–10). This measures
true user-perceived latency and real cost per conversation — don't crank it up, it
spends real money and hits provider 429s fast.

## Headless / CI example
```bash
LOADTEST_ORG_ID=<uuid> locust -f loadtest/locustfile.py --host http://localhost:8000 \
  --headless -u 50 -r 5 -t 3m --csv results/webchat
```

## Cleanup (if you ran against a shared DB)
```bash
python loadtest/cleanup.py <ORG_ID>
```
Deletes only that org's conversations/messages and the `Web Visitor` contacts the
harness created.
