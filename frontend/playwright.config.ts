import { defineConfig, devices } from "@playwright/test";

/**
 * E2E tests live in `e2e/` (NOT under `src/`) so Vitest and Playwright never
 * try to pick each other's tests up.
 *
 * These tests assume:
 *   - a backend is reachable at BASE_URL (defaults to localhost:5173 which
 *     Vite's dev server serves)
 *   - a super-admin can log in via the OTP-out-of-band trick (see auth.setup.ts)
 *
 * They will NOT hit real Retell, Brevo, or Google Calendar — those external
 * dependencies are mocked at the network level via page.route().
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false, // Setup wizard mutates shared DB state; parallel runs collide
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [["html", { open: "never" }], ["list"]],

  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5173",
    trace: "on-first-retry",
    // Screenshot on failure — helps triage flakes without re-running.
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: process.env.CI
    ? {
        // In CI, spin up Vite ourselves.
        command: "npm run dev",
        url: "http://localhost:5173",
        reuseExistingServer: false,
        timeout: 60_000,
      }
    : {
        // Locally, reuse the dev server if it's already running (which it
        // usually is when a dev is iterating on tests).
        command: "npm run dev",
        url: "http://localhost:5173",
        reuseExistingServer: true,
        timeout: 60_000,
      },
});
