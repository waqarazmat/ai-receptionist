import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Mock the two API hooks before importing the component under test — the
// component grabs them at module-load time.
vi.mock("../../api/users", () => ({
  useInviteUser: vi.fn(),
}));
vi.mock("../../api/organizations", () => ({
  useOrganizations: vi.fn(),
}));

import { InviteUserModal } from "./InviteUserModal";
import { useInviteUser } from "../../api/users";
import { useOrganizations } from "../../api/organizations";

function renderModal(onClose = vi.fn()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    onClose,
    ...render(
      <QueryClientProvider client={client}>
        <InviteUserModal isOpen={true} onClose={onClose} />
      </QueryClientProvider>,
    ),
  };
}

describe("InviteUserModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useOrganizations as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      data: [
        { id: "org-1", name: "Bright Smile Dental" },
        { id: "org-2", name: "genaitech" },
      ],
    });
  });

  it("renders the form fields", () => {
    (useInviteUser as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    });
    renderModal();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/organization/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /invite user/i })).toBeInTheDocument();
  });

  it("calls mutate with trimmed email and org_id when submitted", async () => {
    const mutate = vi.fn();
    (useInviteUser as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate,
      isPending: false,
    });
    renderModal();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/email/i), "  new@brightsmile.com  ");
    await user.selectOptions(screen.getByLabelText(/organization/i), "org-1");
    await user.click(screen.getByRole("button", { name: /invite user/i }));
    expect(mutate).toHaveBeenCalledTimes(1);
    expect(mutate.mock.calls[0][0]).toEqual({
      email: "new@brightsmile.com",
      org_id: "org-1",
    });
  });

  it("closes the modal when the invite mutation succeeds", async () => {
    const mutate = vi.fn((_data, { onSuccess }) => onSuccess?.());
    (useInviteUser as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate,
      isPending: false,
    });
    const { onClose } = renderModal();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/email/i), "new@brightsmile.com");
    await user.selectOptions(screen.getByLabelText(/organization/i), "org-1");
    await user.click(screen.getByRole("button", { name: /invite user/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state while the invite is in flight", () => {
    (useInviteUser as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate: vi.fn(),
      isPending: true,
    });
    renderModal();
    // Button component sets aria-busy or renders a spinner when isLoading;
    // asserting on disabled is the most robust cross-implementation signal.
    const submitBtn = screen.getByRole("button", { name: /invite user/i });
    expect(submitBtn).toBeDisabled();
  });
});
