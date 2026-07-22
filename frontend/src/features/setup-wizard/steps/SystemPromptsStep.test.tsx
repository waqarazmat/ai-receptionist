import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../../../api/setup-wizard", () => ({
  useSaveSystemPrompts: vi.fn(),
}));

import { SystemPromptsStep } from "./SystemPromptsStep";
import { useSaveSystemPrompts } from "../../../api/setup-wizard";
import type { StepComponentProps } from "../types";

// The wizard passes a big SetupStateResponse — we only care about the parts
// this step reads, so a partial cast is fine and keeps the test focused.
function baseProps(): StepComponentProps {
  return {
    orgId: "org-1",
    setupState: {
      // These are the only two fields the step reads.
      basic_info: {
        name: "Acme Dental",
        industry: "Dental",
        timezone: "America/New_York",
        address: null,
        phone: null,
        email: null,
      },
      system_prompts: null,
      // Everything else the step doesn't touch — safe to fake as null.
      // Cast through unknown to keep TS happy without full-shape mocking.
    } as unknown as StepComponentProps["setupState"],
    onBack: vi.fn(),
    onNext: vi.fn(),
  };
}

function renderStep(props = baseProps()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    ...props,
    ...render(
      <QueryClientProvider client={client}>
        <SystemPromptsStep {...props} />
      </QueryClientProvider>,
    ),
  };
}

describe("SystemPromptsStep", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useSaveSystemPrompts as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    });
  });

  it("renders the four required prompt fields and the optional custom prompt", () => {
    renderStep();
    expect(screen.getByLabelText(/greeting message/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/ai personality/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/escalation/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/off-topic/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/custom system prompt/i)).toBeInTheDocument();
  });

  it("opens the template picker and lists industries", async () => {
    renderStep();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /load template/i }));
    // A few known templates should appear in the listbox.
    expect(screen.getByRole("button", { name: /dental practice/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /software/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /generic/i })).toBeInTheDocument();
  });

  it("substitutes {{org_name}} placeholders when a template is loaded", async () => {
    renderStep();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /load template/i }));
    await user.click(screen.getByRole("button", { name: /dental practice/i }));
    const textarea = screen.getByLabelText(/custom system prompt/i) as HTMLTextAreaElement;
    // Placeholder should have been replaced with the basic_info.name value.
    expect(textarea.value).toContain("Acme Dental");
    expect(textarea.value).not.toContain("{{org_name}}");
  });

  it("submits with system_prompt=null when the custom field is empty (backend-friendly)", async () => {
    const mutate = vi.fn();
    (useSaveSystemPrompts as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate,
      isPending: false,
    });
    renderStep();
    const user = userEvent.setup();
    // Fill required fields so the form actually submits.
    await user.type(screen.getByLabelText(/greeting message/i), "Hi.");
    await user.type(screen.getByLabelText(/ai personality/i), "Warm.");
    await user.type(screen.getByLabelText(/escalation/i), "Escalate on emergencies.");
    await user.type(screen.getByLabelText(/off-topic/i), "Dentistry only.");
    await user.click(screen.getByRole("button", { name: /save & continue/i }));
    expect(mutate).toHaveBeenCalledTimes(1);
    expect(mutate.mock.calls[0][0].system_prompt).toBeNull();
  });
});
