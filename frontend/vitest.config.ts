/// <reference types="vitest" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    // Keep tests deterministic and fast — no watching by default when run
    // as `npm run test:run`, no coverage unless explicitly asked for.
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    // Exclude node_modules AND the widget package (widget has its own tests
    // if we ever add them; wrong tool would try to run this against Preact).
    exclude: ["node_modules", "dist", "e2e"],
    // Fail loud on unhandled promises — the most common source of a flaky
    // test suite in TanStack Query + Zustand code.
    dangerouslyIgnoreUnhandledErrors: false,
  },
});
