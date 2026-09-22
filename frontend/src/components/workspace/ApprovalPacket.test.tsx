/**
 * The gate: a packet may never print a figure nobody quoted.
 *
 * This asserts on the rendered document, not on a formatting helper. An earlier gate on
 * this work asserted against an internal function and stayed green while the product was
 * reverted to invented constants, so every assertion here reads the DOM an approver would
 * be handed.
 *
 * The specific defect it locks out: `{currency: "USD", typical_amount: null}` is a truthy
 * object, and `Intl.NumberFormat.format(null)` renders "$0". A packet guarding only the
 * envelope therefore printed "$0" as the cost of an unpriced trip — a number an approver
 * can act on and that no source stands behind.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { WorkspaceData } from "../../api/workspace";
import { ApprovalPacket } from "./ApprovalPacket";

afterEach(() => {
  cleanup();
});

function workspaceWithScenarioTotal(
  estimatedTotal: { currency: string; typical_amount: number | null } | null
): WorkspaceData {
  return {
    trip_record: {
      trip: {
        trip_id: "trip-chicago",
        title: "Chicago client review",
        summary: "Two days on site.",
        status: "active",
        mode: "business",
        trip_frame: {
          start_date: "2026-10-05",
          end_date: "2026-10-07",
          duration_days: 3,
          primary_regions: ["Chicago"],
          traveler_party: { kind: "solo", traveler_count: 1 },
        },
      },
      artifact_refs: {},
    },
    session: { current_saved_scenario_id: null },
    saved_scenarios: [],
    proposal_state: null,
    budget_state: {
      summary: {
        currency: "USD",
        planned_total: 2000,
        remaining_total: 2000,
        category_summaries: [],
      },
    },
    runtime_scenario_comparison: {
      title: "Comparison",
      summary: "One scenario",
      lead_scenario_id: "scenario:chicago:1",
      comparison_axes: [],
      scenarios: [
        {
          scenario_id: "scenario:chicago:1",
          title: "Direct flight",
          rank: 1,
          status: "lead",
          summary: "Nonstop",
          comparison_note: "Lead",
          metrics: {
            score: 0.9,
            travel_minutes: 240,
            transfers: 0,
            estimated_total: estimatedTotal,
          },
          delta: {},
          highlights: [],
        },
      ],
      source_refs: [],
    },
  } as unknown as WorkspaceData;
}

describe("ApprovalPacket cost reporting", () => {
  it("prints 'Not priced' when the money envelope carries no amount", () => {
    render(
      <ApprovalPacket
        workspace={workspaceWithScenarioTotal({ currency: "USD", typical_amount: null })}
        onPrint={vi.fn()}
      />
    );

    expect(screen.getByTestId("approval-packet-trip-cost")).toHaveTextContent("Not priced");
    // The exact regression. "$0" must not appear anywhere in the document an approver reads.
    expect(screen.getByTestId("approval-packet-document").textContent).not.toMatch(/\$0\b/);
  });

  it("prints 'Not priced' when there is no money envelope at all", () => {
    render(<ApprovalPacket workspace={workspaceWithScenarioTotal(null)} onPrint={vi.fn()} />);

    expect(screen.getByTestId("approval-packet-trip-cost")).toHaveTextContent("Not priced");
    expect(screen.getByTestId("approval-packet-document").textContent).not.toMatch(/\$0\b/);
  });

  it("tells the traveller why there is no figure and what would supply one", () => {
    render(
      <ApprovalPacket
        workspace={workspaceWithScenarioTotal({ currency: "USD", typical_amount: null })}
        onPrint={vi.fn()}
      />
    );

    // A surface that goes silent when it cannot price is indistinguishable from a broken
    // one. It must report what is missing and what would resolve it, in the same place.
    const notice = screen.getByTestId("approval-packet-unpriced-notice");
    expect(notice).toHaveTextContent("no price");
    expect(notice).toHaveTextContent("Budget tab");
  });

  it("does not compare an absent cost against the budget cap", () => {
    render(
      <ApprovalPacket
        workspace={workspaceWithScenarioTotal({ currency: "USD", typical_amount: null })}
        onPrint={vi.fn()}
      />
    );

    // `planned_total - null` is `planned_total`, so the old code reported the full cap as
    // headroom under a cost it did not have.
    expect(screen.getByTestId("approval-packet-document").textContent).not.toMatch(
      /below the budget cap/
    );
  });

  it("prints a real figure when a source has quoted one", () => {
    render(
      <ApprovalPacket
        workspace={workspaceWithScenarioTotal({ currency: "USD", typical_amount: 1385 })}
        onPrint={vi.fn()}
      />
    );

    expect(screen.getByTestId("approval-packet-trip-cost")).toHaveTextContent("$1,385");
    expect(screen.queryByTestId("approval-packet-unpriced-notice")).toBeNull();
  });
});
