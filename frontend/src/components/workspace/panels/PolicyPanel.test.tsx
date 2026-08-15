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

  it("service-unavailable retry invokes onRetry", () => {
    const onRetry = vi.fn();

    render(
      <PolicyPanel
        view={{
          kind: "service-unavailable",
          message: "The travel policy service did not respond.",
          onRetry,
        }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Retry policy check" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("not-evaluated blocking precondition replaces prepare action", () => {
    const onPrepare = vi.fn();
    const onSatisfy = vi.fn();

    render(
      <PolicyPanel
        view={{
          kind: "not-evaluated",
          onPrepare,
          blockingPrecondition: {
            message: "Approval packets are only available for business trips.",
            actionLabel: "Open Plan to review trip mode",
            onSatisfy,
          },
        }}
      />
    );

    expect(
      screen.getByText("Approval packets are only available for business trips.")
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Prepare approval packet" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open Plan to review trip mode" }));
    expect(onSatisfy).toHaveBeenCalledOnce();
    expect(onPrepare).not.toHaveBeenCalled();
  });

  it("announces statusMessage in the live region", () => {
    render(
      <PolicyPanel
        view={{
          kind: "compliant",
          summary: "Trip meets policy requirements.",
        }}
        statusMessage="Policy check completed."
      />
    );

    const liveRegion = screen.getByTestId("policy-status-live-region");
    expect(liveRegion).toHaveTextContent("Policy check completed.");
  });

  it("lists all non-compliant issue codes", () => {
    render(
      <PolicyPanel
        view={{
          kind: "non-compliant",
          issueCodes: ["hotel-cap-exceeded", "missing-receipt-policy"],
          summary: "Blocking policy issues were found.",
        }}
      />
    );

    const issueList = screen.getByTestId("policy-issue-codes");
    expect(issueList).toHaveTextContent("hotel-cap-exceeded");
    expect(issueList).toHaveTextContent("missing-receipt-policy");
  });
});
