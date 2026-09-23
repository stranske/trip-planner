/**
 * The gate for issue 1837: the approval packet may only say what a source said.
 *
 * Every assertion reads the rendered document an approver is handed. The defects it locks
 * out were all observed in a printed packet on 2026-09-22: a $0 budget cap the trip was
 * "above", a compliance percentage the policy service never produced, the cost attributed
 * to the policy engine, no traveller name, and "Not evaluated" after a reload for a trip
 * that had been reviewed.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { TripPricesState, WorkspaceData } from "../../api/workspace";
import { ApprovalPacket } from "./ApprovalPacket";

afterEach(() => {
  cleanup();
});

const SOURCE = { kind: "manual", attributed_to: "Priya Raman", captured_at: "2026-09-22T10:00:00+00:00" };

const PRICED: TripPricesState = {
  components: [
    {
      component: "transport",
      label: "Flights and ground travel",
      currency: "USD",
      typical_amount: 486,
      note: "United.com economy",
      lowest_amount: 470,
      evidence_attested: true,
      cabin_class: "economy",
      flight_hours: 4.25,
      price_source: SOURCE,
    },
    {
      component: "lodging",
      label: "Accommodation",
      currency: "USD",
      typical_amount: 612,
      note: "Hyatt corporate rate",
      price_source: SOURCE,
    },
    { component: "other", label: "Other costs", currency: "USD", typical_amount: null, note: "", price_source: null },
  ],
  total: { typical_amount: 1098, currency: "USD", price_source: SOURCE },
  priced_component_count: 2,
  unpriced_component_count: 1,
};

function workspace(
  overrides: { summary?: Record<string, unknown>; budget?: Record<string, unknown>; proposal?: boolean } = {}
): WorkspaceData {
  return {
    trip_record: {
      trip: {
        trip_id: "trip-chicago",
        title: "Chicago client review",
        summary: "Quarterly review with the client team.",
        mode: "business",
        trip_frame: {
          origin: "Seattle",
          start_date: "2026-10-05",
          end_date: "2026-10-07",
          duration_days: 3,
          primary_regions: ["Chicago, IL"],
          traveler_party: { kind: "solo", traveler_count: 1 },
        },
      },
    },
    session: { current_saved_scenario_id: null },
    saved_scenarios: [],
    proposal_state:
      overrides.proposal === false
        ? null
        : { evaluation: { evaluation_result: null }, summary: overrides.summary ?? {} },
    budget_state: {
      summary: {
        currency: "USD",
        has_budget_plan: false,
        planned_total: 0,
        remaining_total: 0,
        category_summaries: [],
        ...overrides.budget,
      },
    },
    runtime_scenario_comparison: { scenarios: [] },
  } as unknown as WorkspaceData;
}

function documentText(): string {
  return screen.getByTestId("approval-packet-document").textContent ?? "";
}

describe("ApprovalPacket", () => {
  it("names the requester and the whole journey, origin first", () => {
    render(<ApprovalPacket workspace={workspace()} prices={PRICED} requesterName="Priya Raman" onPrint={vi.fn()} />);

    expect(screen.getByTestId("approval-packet-requester")).toHaveTextContent("Priya Raman");
    expect(screen.getByTestId("approval-packet-journey")).toHaveTextContent("Seattle → Chicago, IL");
  });

  it("itemises every entered cost with its source and who entered it", () => {
    render(<ApprovalPacket workspace={workspace()} prices={PRICED} requesterName="Priya Raman" onPrint={vi.fn()} />);

    const costs = screen.getByTestId("approval-packet-costs");
    expect(costs).toHaveTextContent("Flights and ground travel");
    expect(costs).toHaveTextContent("$486");
    expect(costs).toHaveTextContent("United.com economy");
    expect(costs).toHaveTextContent("Entered by Priya Raman on 2026-09-22");
    expect(costs).toHaveTextContent("$612");
    expect(screen.getByTestId("approval-packet-trip-cost")).toHaveTextContent("$1,098");
    expect(costs).toHaveTextContent("1 item(s) not priced");
    // The cost belongs to the traveller's sources, never to the policy engine.
    expect(documentText()).not.toMatch(/from tpp/i);
  });

  it("prints the flight details the policy checks, as the traveller gave them", () => {
    render(<ApprovalPacket workspace={workspace()} prices={PRICED} onPrint={vi.fn()} />);

    const fare = screen.getByTestId("approval-packet-fare-detail");
    expect(fare).toHaveTextContent("Lowest fare found for the same journey: $470");
    expect(fare).toHaveTextContent("Cabin: economy");
    expect(fare).toHaveTextContent("the traveller holds a screenshot or quote");
  });

  it("does not invent a budget cap when none was set", () => {
    render(<ApprovalPacket workspace={workspace()} prices={PRICED} onPrint={vi.fn()} />);

    expect(screen.getByTestId("approval-packet-budget")).toHaveTextContent(
      "No budget cap is set for this trip in the planner."
    );
    // The exact regression: an unset default printed as "$0" and compared against.
    expect(documentText()).not.toMatch(/\$0\b/);
    expect(documentText()).not.toMatch(/above the budget cap/);
  });

  it("compares against a cap the traveller actually set", () => {
    render(
      <ApprovalPacket
        workspace={workspace({ budget: { has_budget_plan: true, planned_total: 2000 } })}
        prices={PRICED}
        onPrint={vi.fn()}
      />
    );

    expect(screen.getByTestId("approval-packet-budget")).toHaveTextContent(
      "Budget cap $2,000: this trip is $902 under it."
    );
  });

  it("never prints a compliance score, which the policy service does not produce", () => {
    render(
      <ApprovalPacket
        workspace={workspace({ summary: { evaluation_result_status: "non_compliant" } })}
        prices={PRICED}
        onPrint={vi.fn()}
      />
    );

    expect(documentText()).not.toMatch(/compliance score/i);
    expect(documentText()).not.toMatch(/\d+%/);
  });

  it("prints a policy block with TPP's own reasons, from the reloaded payload", () => {
    // The shape a page load serves: outcome and codes in the summary, no evaluation record.
    render(
      <ApprovalPacket
        workspace={workspace({
          summary: {
            submission_outcome: "blocked_by_policy",
            submission_blocking_codes: ["fare_evidence"],
            follow_up: {
              failure_reasons: [
                { code: "fare_evidence", message: "Screenshot or fare evidence must be attached to the request." },
              ],
            },
          },
        })}
        prices={PRICED}
        onPrint={vi.fn()}
      />
    );

    expect(screen.getByTestId("approval-packet-verdict")).toHaveTextContent("Blocked by travel policy");
    expect(screen.getByTestId("approval-packet-policy-reasons")).toHaveTextContent(
      "Screenshot or fare evidence must be attached to the request."
    );
    expect(documentText()).not.toMatch(/Not evaluated/);
  });

  it("prints a passed policy check", () => {
    render(
      <ApprovalPacket
        workspace={workspace({ summary: { evaluation_result_status: "compliant" } })}
        prices={PRICED}
        onPrint={vi.fn()}
      />
    );

    expect(screen.getByTestId("approval-packet-verdict")).toHaveTextContent("Passed the travel policy check");
  });

  it("says plainly when the trip has no price", () => {
    render(<ApprovalPacket workspace={workspace({ proposal: false })} prices={null} onPrint={vi.fn()} />);

    expect(screen.getByTestId("approval-packet-unpriced-notice")).toHaveTextContent("This trip has no price.");
    expect(documentText()).not.toMatch(/\$0\b/);
  });

  it("leaves room for the approver's decision", () => {
    render(<ApprovalPacket workspace={workspace()} prices={PRICED} onPrint={vi.fn()} />);

    const signoff = screen.getByRole("region", { name: "Approver decision" });
    expect(signoff).toHaveTextContent("Approver");
    expect(signoff).toHaveTextContent("Signature");
    expect(signoff).toHaveTextContent("Approved / Not approved");
  });
});
