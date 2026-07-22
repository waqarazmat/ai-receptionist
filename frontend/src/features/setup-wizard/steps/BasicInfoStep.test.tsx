import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../../../api/setup-wizard", () => ({
  useSaveBasicInfo: vi.fn(),
}));

import { BasicInfoStep } from "./BasicInfoStep";
import { useSaveBasicInfo } from "../../../api/setup-wizard";
import type { StepComponentProps } from "../types";

function basePropsWith(basicInfo: unknown = null): StepComponentProps {
  return {
    orgId: "org-1",
    setupState: {
      basic_info: basicInfo,
    } as unknown as StepComponentProps["setupState"],
    onBack: vi.fn(),
    onNext: vi.fn(),
  };
}

function renderStep(props = basePropsWith()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    ...props,
    ...render(
      <QueryClientProvider client={client}>
        <BasicInfoStep {...props} />
      </QueryClientProvider>,
    ),
  };
}

describe("BasicInfoStep", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useSaveBasicInfo as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    });
  });

  it("renders empty when no basic_info has been saved yet", () => {
    renderStep();
    expect(
      (screen.getByLabelText(/organization name/i) as HTMLInputElement).value,
    ).toBe("");
  });

  it("prefills every field when basic_info exists", () => {
    renderStep(
      basePropsWith({
        name: "Bright Smile Dental",
        industry: "Dental",
        timezone: "America/New_York",
        address: "123 Main St",
        phone: "555-1234",
        email: "hello@brightsmile.com",
      }),
    );
    expect(
      (screen.getByLabelText(/organization name/i) as HTMLInputElement).value,
    ).toBe("Bright Smile Dental");
    expect((screen.getByLabelText(/address/i) as HTMLInputElement).value).toBe(
      "123 Main St",
    );
    expect((screen.getByLabelText(/phone/i) as HTMLInputElement).value).toBe(
      "555-1234",
    );
    expect(
      (screen.getByLabelText(/contact email/i) as HTMLInputElement).value,
    ).toBe("hello@brightsmile.com");
  });

  it("submits all six fields on save", async () => {
    const mutate = vi.fn();
    (useSaveBasicInfo as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate,
      isPending: false,
    });
    renderStep();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/organization name/i), "New Org");
    await user.selectOptions(screen.getByLabelText(/industry/i), "Dental");
    // `Intl.supportedValuesOf("timeZone")` returns different lists across
    // Node/jsdom versions — pick a timezone that's in every list.
    await user.selectOptions(screen.getByLabelText(/timezone/i), "America/New_York");
    await user.click(screen.getByRole("button", { name: /save & continue/i }));
    expect(mutate).toHaveBeenCalledTimes(1);
    const payload = mutate.mock.calls[0][0];
    expect(payload.name).toBe("New Org");
    expect(payload.industry).toBe("Dental");
    expect(payload.timezone).toBe("America/New_York");
    // Optional fields are empty strings when untouched — matches backend
    // schema (they're nullable but the form default is "").
    expect(payload.address).toBe("");
    expect(payload.phone).toBe("");
    expect(payload.email).toBe("");
  });
});
