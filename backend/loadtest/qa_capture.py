"""Question-driven capture run — send YOUR questions, save EVERY answer.

Unlike locustfile.py (which measures infra with its own canned questions), this
harness reads a CSV of *your* questions and, under concurrent load, sends each
one through the real web-chat pipeline (Socket.IO /chat -> intent -> retrieval ->
the org's LLM) and writes the bot's full reply to an output CSV.

"Every answer captured" mode: a question asked 300 times under load produces 300
rows with that same id, so you can see whether the answer stays consistent when
the system is busy. NO grading is done here — you evaluate the CSV yourself.

Input  (QUESTIONS_FILE, default loadtest/questions.csv)
    A CSV with a `question` column (required) and an `id` column (optional; if
    absent, questions are numbered by their row order). Any other columns are
    ignored, so you can keep your own expected-answer column in the same file.

Output (OUTPUT_FILE, default loadtest/results/qa_capture.csv)
    Columns: id, question, response, response_time_ms, ttft_ms, status
    Written live (durable if the run is interrupted), then re-sorted by id at the
    end so all rows for a given question sit together.

Usage:
    export LOADTEST_ORG_ID=2e9eb993-a26e-4f01-ae3c-ed45c0e987ee   # Hassdent (default)
    export QUESTIONS_FILE=loadtest/questions.csv
    locust -f loadtest/qa_capture.py --host http://localhost:8000
    # open http://localhost:8089, set users + spawn rate (e.g. 100 users @ 10/s)

Run against an org whose LLM key is REAL, or every "answer" will be the static
fallback line. Leave LOAD_TEST_MOCK_LLM unset/false on the backend so replies are
genuine (the mock returns a fixed string).
"""

import csv
import os
import threading
import time

import socketio
from locust import User, between, events, task

# Hassdent's org UUID — the org this capture run targets by default. Override
# with LOADTEST_ORG_ID to point at another org (e.g. Bright Smile Dental).
DEFAULT_ORG_ID = "2e9eb993-a26e-4f01-ae3c-ed45c0e987ee"

ORG_ID = os.environ.get("LOADTEST_ORG_ID", DEFAULT_ORG_ID)
QUESTIONS_FILE = os.environ.get("QUESTIONS_FILE", os.path.join("loadtest", "questions.csv"))
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", os.path.join("loadtest", "results", "qa_capture.csv"))
NAMESPACE = "/chat"
RESPONSE_TIMEOUT = 30.0  # seconds to wait for response_complete before recording a timeout

OUTPUT_COLUMNS = ["id", "question", "response", "response_time_ms", "ttft_ms", "status"]

# Populated at test_start; read-only for the duration of the run.
QUESTIONS: list[dict] = []

# One shared writer guarded by a lock — response callbacks fire on each client's
# background WS thread, so every row write must be serialized.
_write_lock = threading.Lock()
_out_fh = None
_out_writer = None


def _load_questions(path: str) -> list[dict]:
    """Read the question CSV into [{id, question}, ...]. `question` column is
    required (matched case-insensitively); `id` falls back to the row number."""
    if not os.path.exists(path):
        raise RuntimeError(f"QUESTIONS_FILE not found: {path} (cwd={os.getcwd()})")

    rows: list[dict] = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise RuntimeError(f"{path} is empty or has no header row.")
        # Map the real header names to our expected keys, case-insensitively.
        lower = {name.lower().strip(): name for name in reader.fieldnames}
        q_col = lower.get("question")
        id_col = lower.get("id")
        if not q_col:
            raise RuntimeError(f"{path} needs a 'question' column. Found: {reader.fieldnames}")
        for i, row in enumerate(reader, start=1):
            question = (row.get(q_col) or "").strip()
            if not question:
                continue  # skip blank lines
            qid = (row.get(id_col) or "").strip() if id_col else ""
            rows.append({"id": qid or str(i), "question": question})
    if not rows:
        raise RuntimeError(f"No questions found in {path}.")
    return rows


def _id_sort_key(value: str):
    """Sort numeric ids numerically (1,2,10 not 1,10,2); everything else by text."""
    try:
        return (0, int(value), "")
    except (TypeError, ValueError):
        return (1, 0, str(value))


@events.test_start.add_listener
def _setup(environment, **_kwargs):
    global QUESTIONS, _out_fh, _out_writer
    if not ORG_ID:
        raise RuntimeError("Set LOADTEST_ORG_ID to an active org UUID before running.")

    QUESTIONS = _load_questions(QUESTIONS_FILE)

    out_dir = os.path.dirname(OUTPUT_FILE)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    _out_fh = open(OUTPUT_FILE, "w", newline="", encoding="utf-8")
    _out_writer = csv.DictWriter(_out_fh, fieldnames=OUTPUT_COLUMNS)
    _out_writer.writeheader()
    _out_fh.flush()

    print(
        f"[qa_capture] {len(QUESTIONS)} questions from {QUESTIONS_FILE} -> "
        f"org {ORG_ID}; writing every answer to {OUTPUT_FILE}"
    )


@events.test_stop.add_listener
def _teardown(environment, **_kwargs):
    """Close the live file, then re-sort it by id so a question's rows group
    together (stable sort keeps each question's rows in completion order)."""
    global _out_fh
    with _write_lock:
        if _out_fh is not None:
            _out_fh.flush()
            _out_fh.close()
            _out_fh = None

    if not os.path.exists(OUTPUT_FILE):
        return
    with open(OUTPUT_FILE, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    rows.sort(key=lambda r: _id_sort_key(r.get("id", "")))
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[qa_capture] wrote {len(rows)} answers to {OUTPUT_FILE} (sorted by id)")


def _write_row(row: dict) -> None:
    with _write_lock:
        if _out_writer is not None and _out_fh is not None:
            _out_writer.writerow(row)
            _out_fh.flush()


class CaptureUser(User):
    # A real visitor pauses between messages; keep it short so throughput is
    # driven by the user count, not artificial think time.
    wait_time = between(0.5, 2.0)

    def on_start(self):
        import random

        self._rng = random.Random()
        self.sio = socketio.Client(reconnection=False)
        self._first_token_at = None
        self._chunks: list[str] = []
        self._done = threading.Event()

        self.sio.on("response_token", self._on_token, namespace=NAMESPACE)
        self.sio.on("response_complete", self._on_complete, namespace=NAMESPACE)

        t0 = time.time()
        try:
            self.sio.connect(
                self.host,
                auth={"org_id": ORG_ID},
                namespaces=[NAMESPACE],
                transports=["websocket"],
                socketio_path="socket.io",
                wait_timeout=10,
            )
            events.request.fire(
                request_type="ws", name="connect", response_time=(time.time() - t0) * 1000,
                response_length=0, exception=None, context={},
            )
        except Exception as exc:  # noqa: BLE001
            events.request.fire(
                request_type="ws", name="connect", response_time=(time.time() - t0) * 1000,
                response_length=0, exception=exc, context={},
            )

    def on_stop(self):
        try:
            self.sio.disconnect()
        except Exception:  # noqa: BLE001
            pass

    def _on_token(self, data):
        if self._first_token_at is None:
            self._first_token_at = time.time()
        self._chunks.append((data or {}).get("token", ""))

    def _on_complete(self, data=None):
        self._done.set()

    @task
    def ask_question(self):
        """Pick one of your questions, send it, capture the full reply as a row."""
        if not self.sio.connected or not QUESTIONS:
            return
        item = self._rng.choice(QUESTIONS)

        self._first_token_at = None
        self._chunks = []
        self._done.clear()

        t0 = time.time()
        self.sio.emit("send_message", {"message": item["question"]}, namespace=NAMESPACE)
        completed = self._done.wait(timeout=RESPONSE_TIMEOUT)
        t1 = time.time()

        response = "".join(self._chunks)
        ttft_ms = round((self._first_token_at - t0) * 1000) if self._first_token_at else ""
        total_ms = round((t1 - t0) * 1000)

        if not completed:
            status = "timeout"      # partial text (if any) is still saved
        elif not response:
            status = "empty"
        else:
            status = "ok"

        _write_row({
            "id": item["id"],
            "question": item["question"],
            "response": response,
            "response_time_ms": total_ms,
            "ttft_ms": ttft_ms,
            "status": status,
        })

        # Also feed Locust's own stats so the run still shows throughput/latency.
        events.request.fire(
            request_type="ws", name="ask:complete", response_time=total_ms,
            response_length=len(response),
            exception=None if status == "ok" else Exception(status), context={},
        )
