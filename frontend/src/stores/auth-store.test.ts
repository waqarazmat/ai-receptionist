import { describe, it, expect, beforeEach } from "vitest";
import { useAuthStore, getStoredRefreshToken, getStoredUserEmail } from "./auth-store";
import type { User } from "../types/auth";

const SAMPLE_USER: User = {
  id: "user-123",
  email: "admin@example.com",
  role: "super_admin",
  org_id: null,
};

const TOKENS = { accessToken: "access-abc", refreshToken: "refresh-xyz" };

describe("auth-store", () => {
  beforeEach(() => {
    // Isolate every test — Zustand stores and localStorage both persist
    // across tests otherwise.
    localStorage.clear();
    useAuthStore.setState({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
    });
  });

  it("starts empty", () => {
    const s = useAuthStore.getState();
    expect(s.accessToken).toBeNull();
    expect(s.refreshToken).toBeNull();
    expect(s.user).toBeNull();
    expect(s.isAuthenticated).toBe(false);
  });

  it("login persists tokens + user and flips isAuthenticated", () => {
    useAuthStore.getState().login(TOKENS, SAMPLE_USER);
    const s = useAuthStore.getState();
    expect(s.accessToken).toBe("access-abc");
    expect(s.refreshToken).toBe("refresh-xyz");
    expect(s.user).toEqual(SAMPLE_USER);
    expect(s.isAuthenticated).toBe(true);
    // Refresh token + email persist to localStorage so a page reload keeps
    // the session alive (see comment in auth-store.ts about the deliberate
    // exception to the no-localStorage rule).
    expect(getStoredRefreshToken()).toBe("refresh-xyz");
    expect(getStoredUserEmail()).toBe("admin@example.com");
  });

  it("logout clears in-memory state AND localStorage", () => {
    useAuthStore.getState().login(TOKENS, SAMPLE_USER);
    useAuthStore.getState().logout();
    const s = useAuthStore.getState();
    expect(s.accessToken).toBeNull();
    expect(s.refreshToken).toBeNull();
    expect(s.user).toBeNull();
    expect(s.isAuthenticated).toBe(false);
    expect(getStoredRefreshToken()).toBeNull();
    expect(getStoredUserEmail()).toBeNull();
  });

  it("setTokens replaces tokens without touching the user object", () => {
    useAuthStore.getState().login(TOKENS, SAMPLE_USER);
    useAuthStore.getState().setTokens("new-access", "new-refresh");
    const s = useAuthStore.getState();
    expect(s.accessToken).toBe("new-access");
    expect(s.refreshToken).toBe("new-refresh");
    expect(s.user).toEqual(SAMPLE_USER); // unchanged
    // The persisted refresh token also updates — otherwise a page reload
    // after a token refresh would still hand out the old token.
    expect(getStoredRefreshToken()).toBe("new-refresh");
  });
});
