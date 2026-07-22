/**
 * Test the query-parameter mapping for the Users API. This is pure logic —
 * we don't need a running backend or a mocked axios; we just intercept the
 * outgoing request and inspect its params.
 *
 * These tests catch: a filter renaming that doesn't reach the backend,
 * booleans getting stringified wrong, `undefined` filters accidentally
 * being sent as empty strings and breaking backend query-param parsing.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("./client", () => ({
  apiClient: { get: vi.fn() },
}));

import { apiClient } from "./client";
import { useUsers } from "./users";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useUsers query-param mapping", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (apiClient.get as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { users: [] },
    });
  });

  it("omits every filter when the object is empty", async () => {
    renderHook(() => useUsers({}), { wrapper });
    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith("/api/admin/users", { params: {} }),
    );
  });

  it("forwards q, org_id, and role when provided", async () => {
    renderHook(
      () => useUsers({ q: "brightsmile", org_id: "org-1", role: "org_staff" }),
      { wrapper },
    );
    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith("/api/admin/users", {
        params: { q: "brightsmile", org_id: "org-1", role: "org_staff" },
      }),
    );
  });

  it("stringifies is_active=true correctly (not the JS boolean)", async () => {
    renderHook(() => useUsers({ is_active: true }), { wrapper });
    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith("/api/admin/users", {
        params: { is_active: "true" },
      }),
    );
  });

  it("stringifies is_active=false correctly (this is the one that breaks silently otherwise)", async () => {
    renderHook(() => useUsers({ is_active: false }), { wrapper });
    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith("/api/admin/users", {
        params: { is_active: "false" },
      }),
    );
  });

  it("does not send is_active at all when undefined", async () => {
    renderHook(() => useUsers({ is_active: undefined }), { wrapper });
    await waitFor(() => expect(apiClient.get).toHaveBeenCalled());
    const call = (apiClient.get as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(call[1].params).not.toHaveProperty("is_active");
  });
});
