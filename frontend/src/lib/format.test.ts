import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { formatRelative } from "./format";

// Freeze "now" so every test knows exactly what the bucket boundaries land on.
const NOW = new Date("2026-07-22T12:00:00Z").getTime();

describe("formatRelative", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns 'Never' for null input", () => {
    expect(formatRelative(null)).toBe("Never");
  });

  it("returns 'Never' for an unparseable date (defensive against bad server data)", () => {
    expect(formatRelative("not-a-date")).toBe("Never");
  });

  it("returns 'just now' for the current moment", () => {
    expect(formatRelative(new Date(NOW).toISOString())).toBe("just now");
  });

  it("returns 'just now' for a future timestamp (clock skew between client and server)", () => {
    expect(formatRelative(new Date(NOW + 30_000).toISOString())).toBe("just now");
  });

  it("uses minutes for < 1 hour", () => {
    expect(formatRelative(new Date(NOW - 5 * 60_000).toISOString())).toBe("5m ago");
    expect(formatRelative(new Date(NOW - 59 * 60_000).toISOString())).toBe("59m ago");
  });

  it("uses hours for < 1 day", () => {
    expect(formatRelative(new Date(NOW - 3 * 3600_000).toISOString())).toBe("3h ago");
    expect(formatRelative(new Date(NOW - 23 * 3600_000).toISOString())).toBe("23h ago");
  });

  it("uses days for < 30 days", () => {
    expect(formatRelative(new Date(NOW - 5 * 86400_000).toISOString())).toBe("5d ago");
  });

  it("uses months for < 12 months", () => {
    expect(formatRelative(new Date(NOW - 65 * 86400_000).toISOString())).toBe("2mo ago");
  });

  it("falls back to a locale date for a year or more", () => {
    // 400 days ago — should not match any of the relative buckets.
    const out = formatRelative(new Date(NOW - 400 * 86400_000).toISOString());
    expect(out).not.toMatch(/ago$/);
    expect(out).not.toBe("Never");
    // Locale format varies by runtime, so just assert it's a non-empty string.
    expect(out.length).toBeGreaterThan(0);
  });
});
