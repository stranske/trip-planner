/**
 * The gate for issue 1838: a policy refusal is a verdict, not an outage.
 *
 * TPP answers a non-compliant proposal with submission state "failed" — the same word a
 * transport failure uses. Observed 2026-09-22 against a live service, the panel read that as
 * "Policy service unavailable" and offered a Retry that could never change the answer.
 * These tests use the summary shape that live service actually produced.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { WorkspaceData } from "../../../api/workspace";
import { PolicyPanel, derivePolicyPanelView } from "./PolicyPanel";

afterEach(() => {
  cleanup();
});

function workspaceWithSummary(summary: Record<string, unknown>): WorkspaceData {
  return {
    trip_record: { trip: { trip_id: "trip-chicago", mode: "business" } },
    proposal_state: {
      submission_status: "failed",
      evaluation_status: null,
      evaluation: null,
      summary,
    },
  } as unknown as WorkspaceData;
}

const handlers = { onPrepare: vi.fn(), onRetry: vi.fn(), onSatisfyPrecondition: vi.fn() };

describe("policy panel outcome", () => {
  it("shows a policy block as a verdict with TPP's reasons, not as an outage", () => {
    const view = derivePolicyPanelView(
      workspaceWithSummary({
        submission_status: "failed",
        submission_outcome: "blocked_by_policy",
        submission_blocking_codes: ["fare_comparison", "fare_evidence", "non_reimbursable"],
        submission_summary: "Proposal submission blocked by the current policy verdict.",
      }),
      handlers
    );
    render(<PolicyPanel view={view} />);

    expect(screen.getByTestId("policy-state-non-compliant")).toBeInTheDocument();
    const reasons = screen.getByTestId("policy-issue-codes");
    // TPP's own wording for each rule, so the traveller learns what is actually missing.
    expect(reasons).toHaveTextContent("Fare comparison requires selected and lowest fare data.");
    expect(reasons).toHaveTextContent("Screenshot or fare evidence must be attached to the request.");
    expect(reasons).toHaveTextContent("fare_comparison");

    expect(screen.queryByText("Policy service unavailable")).toBeNull();
    expect(screen.queryByRole("button", { name: "Retry policy check" })).toBeNull();
  });

  it("still reports a genuine transport failure as the service being unavailable", () => {
    // The inverse must not be relabelled: here no answer came back at all.
    const view = derivePolicyPanelView(
      workspaceWithSummary({
        submission_status: "failed",
        submission_outcome: "failed",
        submission_blocking_codes: [],
        submission_summary: "timed out",
      }),
      handlers
    );
    render(<PolicyPanel view={view} />);

    expect(screen.getByTestId("policy-state-service-unavailable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry policy check" })).toBeInTheDocument();
  });

  it("reads the outcome alone after a reload, when raw transport fields are withheld", () => {
    // The default payload keeps submission_status debug-only (#1130 / #1152), so a reloaded
    // page sees only submission_outcome. Both verdicts must still render correctly.
    const blocked = derivePolicyPanelView(
      workspaceWithSummary({
        submission_outcome: "blocked_by_policy",
        submission_blocking_codes: ["fare_evidence"],
        follow_up: {
          failure_reasons: [
            { code: "fare_evidence", message: "Screenshot or fare evidence must be attached to the request." },
          ],
        },
      }),
      handlers
    );
    expect(blocked.kind).toBe("non-compliant");

    const outage = derivePolicyPanelView(
      workspaceWithSummary({ submission_outcome: "failed" }),
      handlers
    );
    expect(outage.kind).toBe("service-unavailable");
  });

  it("shows an unknown rule code as-is rather than guessing what it means", () => {
    const view = derivePolicyPanelView(
      workspaceWithSummary({
        submission_status: "failed",
        submission_outcome: "blocked_by_policy",
        submission_blocking_codes: ["XYZ-999"],
      }),
      handlers
    );
    render(<PolicyPanel view={view} />);

    expect(screen.getByTestId("policy-issue-codes")).toHaveTextContent("XYZ-999");
  });
});
