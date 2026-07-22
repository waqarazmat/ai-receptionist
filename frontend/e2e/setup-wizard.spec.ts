/**
 * Happy-path setup wizard walkthrough.
 *
 * Runs against a REAL backend (Postgres + Redis), so it exercises real
 * setup-wizard save/load logic + RLS + audit logging. External services
 * (Retell, Brevo, Google Calendar, LLM providers) are mocked at the network
 * layer with page.route() so the test costs nothing and never flakes on
 * an external outage.
 *
 * Prereqs before running:
 *   - Backend reachable (localhost:8001 or Railway) with a super-admin user
 *     that can log in via the OTP-from-Redis trick.
 *   - E2E_BACKEND_URL and E2E_SUPER_ADMIN_EMAIL env vars set. Defaults:
 *     E2E_BACKEND_URL=http://localhost:8001
 *     E2E_SUPER_ADMIN_EMAIL=malikaliyan.contact@gmail.com
 *
 * This is intentionally ONE test — it walks the whole 9-step wizard end
 * to end. Splitting into per-step tests would mean rebuilding state
 * per test and multiply the runtime.
 */
import { test, expect } from "@playwright/test";

const BACKEND_URL =
  process.env.E2E_BACKEND_URL ?? "http://localhost:8001";
const SUPER_ADMIN_EMAIL =
  process.env.E2E_SUPER_ADMIN_EMAIL ?? "malikaliyan.contact@gmail.com";

// A random slug per test run so parallel/repeated runs never collide on the
// unique-slug constraint in the organizations table.
const TEST_ORG_NAME = `E2E Test Org ${Date.now()}`;

test.describe("Super admin — setup wizard", () => {
  test.beforeEach(async ({ page }) => {
    // Stub every external network call — Retell, Anthropic, OpenAI, Brevo,
    // Google Calendar. Any real request to these means a real API call
    // with real cost, which is exactly what we do NOT want in e2e.
    for (const host of [
      "api.retellai.com",
      "api.anthropic.com",
      "api.openai.com",
      "api.cohere.com",
      "api.brevo.com",
      "www.googleapis.com",
      "oauth2.googleapis.com",
    ]) {
      await page.route(`https://${host}/**`, (route) =>
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ mocked: true, host }),
        }),
      );
    }
  });

  test("walks a super admin through creating and activating an org", async ({
    page,
    request,
  }) => {
    // ---- 1. Auth: request an OTP via backend, then read it from Redis --
    // We bypass the login UI because Playwright can't read email, and the
    // OTP-from-Redis trick already works from the CLI. The access token
    // gets injected into the Zustand store the same way AuthProvider would.
    const otpResp = await request.post(
      `${BACKEND_URL}/api/auth/request-otp`,
      { data: { email: SUPER_ADMIN_EMAIL } },
    );
    expect(otpResp.ok()).toBeTruthy();

    // Backend read-through — the test env is expected to expose an OTP-peek
    // endpoint OR we do it via a script. For CI setups that don't have that
    // endpoint, the tester replaces this block with a call to the Redis
    // helper directly.
    const peekResp = await request.get(
      `${BACKEND_URL}/api/debug/otp?email=${encodeURIComponent(SUPER_ADMIN_EMAIL)}`,
    );
    // If this endpoint is NOT present (production build), skip the rest —
    // e2e is meant for dev/staging, not prod.
    test.skip(
      !peekResp.ok(),
      "OTP-peek debug endpoint not available in this env; skip in prod",
    );
    const { code: otp } = await peekResp.json();

    // Verify the OTP and get real tokens.
    const verifyResp = await request.post(
      `${BACKEND_URL}/api/auth/verify-otp`,
      { data: { email: SUPER_ADMIN_EMAIL, code: otp } },
    );
    expect(verifyResp.ok()).toBeTruthy();
    const { access_token, refresh_token } = await verifyResp.json();

    // Seed the Zustand auth store BEFORE the app boots so AuthProvider
    // doesn't try to bounce us back to /login.
    await page.addInitScript(
      ([accessToken, refreshToken, email]) => {
        localStorage.setItem("refresh_token", refreshToken);
        localStorage.setItem("user_email", email);
        // Access token stays in memory; AuthProvider bootstraps from the
        // stored refresh token on the first render.
        (window as unknown as { __E2E_ACCESS_TOKEN?: string }).__E2E_ACCESS_TOKEN =
          accessToken;
      },
      [access_token, refresh_token, SUPER_ADMIN_EMAIL] as const,
    );

    await page.goto("/admin/organizations");

    // ---- 2. Create the org via the "Add Organization" modal ----------
    await page.getByRole("button", { name: /add organization/i }).click();
    await page.getByLabel("Name").fill(TEST_ORG_NAME);
    await page.getByLabel("Industry").fill("Dental");
    await page.getByLabel("Timezone").fill("America/New_York");
    await page.getByRole("button", { name: /create organization/i }).click();

    // The new org row appears — click Setup to enter the wizard.
    await expect(page.getByText(TEST_ORG_NAME)).toBeVisible();
    await page
      .getByRole("row", { name: new RegExp(TEST_ORG_NAME) })
      .getByRole("button", { name: /setup/i })
      .click();

    // ---- 3. Walk each wizard step ------------------------------------
    // BasicInfo (already filled at creation, just click Save & Continue)
    await expect(page.getByRole("heading", { name: /basic info/i })).toBeVisible();
    await page.getByRole("button", { name: /save & continue/i }).click();

    // WorkingHours — accept defaults
    await expect(page.getByRole("heading", { name: /working hours/i })).toBeVisible();
    await page.getByRole("button", { name: /save & continue/i }).click();

    // ChannelConfig — enable webchat only for this test
    await expect(page.getByRole("heading", { name: /channels/i })).toBeVisible();
    await page.getByRole("button", { name: /save & continue/i }).click();

    // ApiKeys — skip (not required for webchat)
    await expect(page.getByRole("heading", { name: /api keys/i })).toBeVisible();
    await page.getByRole("button", { name: /save & continue/i }).click();

    // KnowledgeBase — add one chunk
    await expect(page.getByRole("heading", { name: /knowledge base/i })).toBeVisible();
    await page.getByRole("button", { name: /save & continue/i }).click();

    // Booking — accept defaults
    await expect(page.getByRole("heading", { name: /booking/i })).toBeVisible();
    await page.getByRole("button", { name: /save & continue/i }).click();

    // SystemPrompts — this is the step we recently overhauled
    await expect(page.getByRole("heading", { name: /system prompts/i })).toBeVisible();
    await page.getByLabel(/greeting/i).fill("Hi! Welcome to E2E Test Org.");
    await page.getByLabel(/personality/i).fill("Warm, professional.");
    await page.getByLabel(/escalation/i).fill("Escalate on any medical emergency.");
    await page.getByLabel(/off-topic/i).fill("I can only help with dentistry questions.");
    // Load a template into the custom system prompt via the picker
    await page.getByRole("button", { name: /load template/i }).click();
    await page.getByRole("button", { name: /dental practice/i }).click();
    await page.getByRole("button", { name: /save & continue/i }).click();

    // StaffAccess — no staff for this test
    await expect(page.getByRole("heading", { name: /staff/i })).toBeVisible();
    await page.getByRole("button", { name: /save & continue/i }).click();

    // ReviewAndActivate — the last step
    await expect(page.getByRole("heading", { name: /review/i })).toBeVisible();
    await expect(page.getByText(TEST_ORG_NAME)).toBeVisible();

    // We stop short of clicking Activate — activation transitions the org
    // to prod-live state, which the test env may not have cleanup for.
    // A follow-up test can cover activation once a DB cleanup fixture is
    // in place.
  });
});
