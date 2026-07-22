# E2E tests (Playwright)

## Running

```bash
# Local — assumes backend on :8001 (or Railway) and Vite dev on :5173.
# Test runner will auto-start Vite if not already running.
npm run test:e2e

# Interactive UI mode for debugging a single failing test
npm run test:e2e:ui
```

## What's here

- `setup-wizard.spec.ts` — end-to-end walkthrough of the 9-step wizard
  against a real backend (Postgres + Redis are real; Retell/Brevo/Google
  Calendar are stubbed at the network layer with `page.route()`).

## What's NOT here (yet)

Full coverage of the wizard is a bigger project than the initial scaffold.
The existing spec is the happy-path — filling in the minimum required fields
on each step, saving, and reaching the Activate button. To grow the suite:

- Voice-provisioning path (create-agent + re-provision buttons)
- Retell webhook simulation
- Booking FSM through a real Google Calendar mock
- WhatsApp inbound message through the Arq queue
- Widget end-user flow (message → LLM stream → typed response)

Each of those would be its own `.spec.ts` file. Keep them focused —
Playwright tests are expensive to run and slow to debug when they cover too
much per test.

## Test infrastructure notes

- **Parallelism is disabled** (`workers: 1`, `fullyParallel: false` in
  `playwright.config.ts`). The setup wizard mutates shared state (org
  records, chunks, OTP keys in Redis) so two parallel wizard runs against
  the same backend collide.
- **OTP is out-of-band.** Playwright can't read Gmail. The `auth.setup.ts`
  file (added lazily on first e2e run) hits the same OTP-from-Redis trick
  the rest of this project uses, via a small Node helper that reads the
  Railway REDIS_URL.
- **External services are mocked with `page.route()`.** No test should ever
  actually hit api.retellai.com, api.anthropic.com, or Brevo — those cost
  money and can be flaky. Real integration tests belong in backend
  `tests/test_api/`, not here.

## When a test fails

1. Look at the trace in `playwright-report/` (auto-generated).
2. Check if the test is racing with backend state — the wizard's setup_state
   query has stale-time behaviour that can fool the assertion.
3. If a test needs a real external service, it belongs in the backend test
   suite, not here.
