"""Load test for the web-chat (Socket.IO) pipeline.

Simulates concurrent widget visitors: each Locust user opens a Socket.IO
connection to the /chat namespace (exactly like the widget's cw.js), then sends
messages and waits for the streamed reply, timing:

  * <scenario>:ttft      — time to FIRST token (perceived responsiveness)
  * <scenario>:complete  — time to response_complete (full reply)

Run the backend with LOAD_TEST_MOCK_LLM=true first (see README) so this measures
YOUR infra — Socket.IO, embeddings, pgvector, Redis, DB — without LLM cost or
provider rate limits. Then flip it off for a small real end-to-end pass.

Usage:
    export LOADTEST_ORG_ID=<an active org's UUID in the DB the backend uses>
    locust -f loadtest/locustfile.py --host http://localhost:8000
Open http://localhost:8089, set users + spawn rate, ramp: 5 -> 10 -> 25 -> 50 ...
"""

import os
import time

import socketio
from locust import User, between, events, task

ORG_ID = os.environ.get("LOADTEST_ORG_ID", "")
NAMESPACE = "/chat"
RESPONSE_TIMEOUT = 30.0  # seconds to wait for response_complete before failing


@events.test_start.add_listener
def _check_config(environment, **_kwargs):
    if not ORG_ID:
        raise RuntimeError(
            "Set LOADTEST_ORG_ID to an active org UUID before running "
            "(export LOADTEST_ORG_ID=...)."
        )


class WebChatUser(User):
    # A real visitor pauses between messages; keep it short so throughput is
    # driven by concurrency (the user count), not artificial think time.
    wait_time = between(0.5, 2.0)

    def on_start(self):
        import threading

        self.sio = socketio.Client(reconnection=False)
        self._first_token_at = None
        self._resp_len = 0
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
        self._resp_len += len((data or {}).get("token", ""))

    def _on_complete(self, data=None):
        self._done.set()

    def _send_and_wait(self, scenario: str, message: str):
        """Emit one message, wait for the full streamed reply, record TTFT +
        completion as two Locust requests."""
        if not self.sio.connected:
            return
        self._first_token_at = None
        self._resp_len = 0
        self._done.clear()

        t0 = time.time()
        self.sio.emit("send_message", {"message": message}, namespace=NAMESPACE)
        completed = self._done.wait(timeout=RESPONSE_TIMEOUT)
        t1 = time.time()

        if not completed:
            events.request.fire(
                request_type="ws", name=f"{scenario}:complete",
                response_time=(t1 - t0) * 1000, response_length=self._resp_len,
                exception=TimeoutError(f"no response_complete in {RESPONSE_TIMEOUT}s"), context={},
            )
            return

        if self._first_token_at is not None:
            events.request.fire(
                request_type="ws", name=f"{scenario}:ttft",
                response_time=(self._first_token_at - t0) * 1000,
                response_length=self._resp_len, exception=None, context={},
            )
        events.request.fire(
            request_type="ws", name=f"{scenario}:complete",
            response_time=(t1 - t0) * 1000, response_length=self._resp_len,
            exception=None, context={},
        )

    # ── Scenarios ────────────────────────────────────────────────────────────
    @task(7)
    def faq(self):
        # Exercises: classifier -> embed_text (REAL) -> hybrid_search (REAL) ->
        # streamed generation. This is the core read path and the likely ceiling.
        self._send_and_wait("faq", "What are your opening hours and where are you located?")

    @task(3)
    def booking_start(self):
        # Exercises the booking FSM + real slot generation (DB + Redis) without
        # finalizing (no Google Calendar / email side effects).
        self._send_and_wait("booking", "I want to book an appointment")
        self._send_and_wait("booking", "sometime next week please")
