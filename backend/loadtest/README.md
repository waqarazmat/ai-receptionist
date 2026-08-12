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

---

# Question-driven capture (`qa_capture.py`)

Same load engine, different goal: instead of canned scenarios, it sends **your own
questions** (from a CSV) and saves **every bot answer** to an output CSV. No grading
is done — you review the answers yourself. A question asked 300 times under load
produces 300 rows with that id, so you can see if the answer drifts when the system
is busy.

**This is the harness wired for Hassdent** (default `LOADTEST_ORG_ID`).

### 1. Put your questions in `loadtest/questions.csv`
A `question` column is required; `id` is optional (rows are auto-numbered if absent).
Extra columns (e.g. your own `expected_answer`) are ignored, so keep your answer key
in the same file if you like.
```csv
id,question,expected_answer
1,What are your opening hours?,
2,Do you offer teeth whitening?,
```

### 2. Run the backend with REAL answers
Leave `LOAD_TEST_MOCK_LLM` **unset** (mock mode returns a fixed string, so every
"answer" would be identical). The target org must have a working LLM key or replies
fall back to the static line.
```bash
# from backend/  — use the project venv that has locust:
.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. Run the capture
```bash
# Hassdent is the default org; override LOADTEST_ORG_ID for another org.
.venv/Scripts/python.exe -m locust -f loadtest/qa_capture.py --host http://localhost:8000
```
Open http://localhost:8089, set users + spawn rate, and run. Or headless:
```bash
.venv/Scripts/python.exe -m locust -f loadtest/qa_capture.py --host http://localhost:8000 \
  --headless -u 100 -r 10 -t 3m
```

### 4. Read the output
`loadtest/results/qa_capture.csv` — columns `id, question, response,
response_time_ms, ttft_ms, status`, **sorted by id** so all rows for a question sit
together. `status` is `ok` / `timeout` / `empty`. Written live (safe if you Ctrl-C),
re-sorted when the run stops.

Override paths with `QUESTIONS_FILE` and `OUTPUT_FILE` env vars.
