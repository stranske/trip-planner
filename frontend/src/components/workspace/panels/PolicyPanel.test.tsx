import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PolicyPanel, type PolicyPanelView } from "./PolicyPanel";

describe("PolicyPanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("empty state offers an action", () => {
    const onPrepare = vi.fn();

    render(
      <PolicyPanel
        view={{
          kind: "not-evaluated",
          onPrepare,
        }}
      />
    );

    expect(screen.getByRole("heading", { name: "Policy not yet evaluated" })).toBeInTheDocument();
    const action = screen.getByRole("button", { name: "Prepare approval packet" });
    expect(action).toBeEnabled();

    fireEvent.click(action);
    expect(onPrepare).toHaveBeenCalledOnce();
  });

  it("renders four distinct policy states", () => {
    const views: PolicyPanelView[] = [
      {
        kind: "not-evaluated",
        onPrepare: vi.fn(),
      },
      {
        kind: "compliant",
        summary: "Trip meets policy requirements.",
      },
      {
        kind: "non-compliant",
        issueCodes: ["hotel-cap-exceeded", "missing-receipt-policy"],
        summary: "Blocking policy issues were found.",
      },
      {
        kind: "service-unavailable",
        message: "The travel policy service did not respond.",
        onRetry: vi.fn(),
      },
    ];

    const headings = [
      "Policy not yet evaluated",
      "Policy compliant",
      "Policy non-compliant",
      "Policy service unavailable",
    ];

    for (const [index, view] of views.entries()) {
      const { unmount } = render(<PolicyPanel view={view} />);
      expect(screen.getByRole("heading", { name: headings[index] })).toBeInTheDocument();
      expect(screen.getByTestId(`policy-state-${view.kind}`)).toBeInTheDocument();
      unmount();
    }
  });
});
