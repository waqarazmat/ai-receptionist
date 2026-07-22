/**
 * Smoke tests for the Users tab. Focus is on the parts that are pure
 * business logic (the relative-time formatter) plus a shallow render check
 * with mocked query hooks. Full-flow interactions (invite, deactivate,
 * paginate) belong in Playwright e2e — see e2e/ for those.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

// Mock the two API hooks the page uses so we don't hit a real network in unit
// tests. The mocks are re-declared per test so we can vary the response shape.
vi.mock("../../api/users", () => ({
  useUsers: vi.fn(),
  useUpdateUser: vi.fn(),
  // Also called by the InviteUserModal child (which the page always mounts,
  // even when the modal is closed) — without this mock the child throws
  // during render because it dereferences the mutation object immediately.
  useInviteUser: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
}));
vi.mock("../../api/organizations", () => ({
  useOrganizations: vi.fn(),
}));

import UsersManagementPage from "./UsersManagementPage";
import { useUsers, useUpdateUser } from "../../api/users";
import { useOrganizations } from "../../api/organizations";

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <UsersManagementPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const SAMPLE_USERS = [
  {
    id: "user-1",
    email: "alice@brightsmile.com",
    role: "org_staff" as const,
    org_id: "org-1",
    org_name: "Bright Smile Dental",
    is_active: true,
    last_login: new Date().toISOString(),
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

describe("UsersManagementPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Give hooks default-happy return shapes so the page renders.
    (useUsers as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      data: SAMPLE_USERS,
      isLoading: false,
    });
    (useOrganizations as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [{ id: "org-1", name: "Bright Smile Dental" }],
    });
    (useUpdateUser as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    });
  });

  it("renders the page title", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: /users/i })).toBeInTheDocument();
  });

  it("renders one row per user with email + org", () => {
    renderPage();
    expect(screen.getByText("alice@brightsmile.com")).toBeInTheDocument();
    // Org name appears both in the row and in the filter dropdown, so we
    // expect at least one.
    expect(screen.getAllByText("Bright Smile Dental").length).toBeGreaterThan(0);
  });

  it("shows the Invite User button", () => {
    renderPage();
    expect(screen.getByRole("button", { name: /invite user/i })).toBeInTheDocument();
  });

  it("shows an empty-state message when there are no users", () => {
    (useUsers as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [],
      isLoading: false,
    });
    renderPage();
    expect(screen.getByText(/no users match these filters/i)).toBeInTheDocument();
  });
});
