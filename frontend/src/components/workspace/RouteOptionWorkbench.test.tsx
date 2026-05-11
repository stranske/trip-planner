import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { RuntimeScenarioComparison } from "../../api/workspace";
import { RouteOptionWorkbench } from "./RouteOptionWorkbench";

const comparison: RuntimeScenarioComparison = {
  title: "Scandinavia route comparison",
  summary: "Three route options are ready for side-by-side review.",
  lead_scenario_id: "route-option:rail-first",
  comparison_axes: [
    { key: "score", label: "Planner score", direction: "higher_better" },
    { key: "travel_minutes", label: "Travel minutes", direction: "lower_better" },
  ],
  scenarios: [
    {
      scenario_id: "route-option:rail-first",
      route_option_id: "route-option:rail-first",
      title: "Rail-first route",
      rank: 1,
      status: "recommended",
      state: "baseline",
      purpose: "Use Rail-first route as the route everything else is compared against.",
      confidence: 0.88,
      unresolved_questions: [],
      available_actions: [
        {
          action_type: "keep",
          label: "Keep for later",
          description: "Preserve this route as a backup option without making it the main plan.",
        },
      ],
      summary: "A low-friction rail sequence through the main cities.",
      comparison_note: "Lead route for the current workspace comparison set.",
      option_count: 3,
      route_sequence: ["stockholm", "oslo", "bergen"],
      route_summary: "stockholm -> oslo -> bergen",
      recommended_for_selection: true,
      feasible: true,
      metrics: {
        score: 0.88,
        travel_minutes: 420,
        transfers: 3,
        estimated_total: { currency: "USD", typical_amount: 3600 },
      },
      delta: {
        score_delta: 0,
        travel_minutes_delta: 0,
        transfers_delta: 0,
        estimated_total_delta: 0,
      },
      highlights: ["Balanced movement with clear rail legs."],
    },
    {
      scenario_id: "route-option:fjord-focus",
      route_option_id: "route-option:fjord-focus",
      title: "Fjord-focus route",
      rank: 2,
      status: "alternative",
      state: "active",
      purpose: "Compare Fjord-focus route as an active alternative.",
      confidence: 0.74,
      unresolved_questions: ["Can the longer scenic transfer still fit the trip pace?"],
      available_actions: [
        {
          action_type: "make_baseline",
          label: "Make baseline",
          description: "Use this route as the main plan while keeping alternatives visible.",
        },
        {
          action_type: "reject",
          label: "Reject",
          description: "Move this route to history so it stops competing with active options.",
        },
      ],
      summary: "A scenic route with more time near Bergen.",
      comparison_note: "Alternative route preserved for direct scenario comparison.",
      option_count: 4,
      route_sequence: ["oslo", "flam", "bergen"],
      route_summary: "oslo -> flam -> bergen",
      recommended_for_selection: false,
      feasible: true,
      metrics: {
        score: 0.74,
        travel_minutes: 510,
        transfers: 5,
        estimated_total: { currency: "USD", typical_amount: 3900 },
      },
      delta: {
        score_delta: -0.14,
        travel_minutes_delta: 90,
        transfers_delta: 2,
        estimated_total_delta: 300,
      },
      highlights: ["More scenery with more transfers."],
    },
    {
      scenario_id: "route-option:flight-hop",
      route_option_id: "route-option:flight-hop",
      title: "Flight-hop route",
      rank: 3,
      status: "alternative",
      state: "rejected",
      purpose: "Keep Flight-hop route in history so the rejection reason is not lost.",
      confidence: 0.38,
      unresolved_questions: ["Does the airport transfer burden defeat the route benefit?"],
      available_actions: [
        {
          action_type: "reopen",
          label: "Reopen",
          description: "Move this route back into the active comparison set.",
        },
      ],
      summary: "A faster route with more airport overhead.",
      comparison_note: "Alternative route preserved for direct scenario comparison.",
      option_count: 2,
      route_sequence: ["stockholm", "bergen", "oslo"],
      route_summary: "stockholm -> bergen -> oslo",
      recommended_for_selection: false,
      feasible: true,
      metrics: {
        score: 0.64,
        travel_minutes: 390,
        transfers: 6,
        estimated_total: { currency: "USD", typical_amount: 4200 },
      },
      delta: {
        score_delta: -0.24,
        travel_minutes_delta: -30,
        transfers_delta: 3,
        estimated_total_delta: 600,
      },
      highlights: ["Faster in minutes but harder to execute."],
    },
  ],
  source_refs: ["scenario-search:scandinavia"],
};

describe("RouteOptionWorkbench", () => {
  it("renders three route options and dispatches route actions", () => {
    const onSelectScenario = vi.fn();
    const onRouteOptionAction = vi.fn();

    render(
      <RouteOptionWorkbench
        comparison={comparison}
        selectedScenarioId="route-option:rail-first"
        busyLabel={null}
        errorMessage={null}
        onSelectScenario={onSelectScenario}
        onRouteOptionAction={onRouteOptionAction}
      />
    );

    expect(screen.getByLabelText("Route option comparison workbench")).toBeInTheDocument();
    expect(screen.getByLabelText("Rail-first route route option")).toHaveTextContent("Baseline");
    expect(screen.getByLabelText("Fjord-focus route route option")).toHaveTextContent(
      "74% confidence"
    );
    expect(screen.getByLabelText("Fjord-focus route route option")).toHaveTextContent(
      "Tradeoff summary"
    );
    expect(screen.getByLabelText("Fjord-focus route route option")).toHaveTextContent(
      "More scenery with more transfers."
    );
    expect(screen.getByLabelText("Fjord-focus route route option")).toHaveTextContent(
      "Open question: Can the longer scenic transfer still fit the trip pace?"
    );
    expect(screen.getByLabelText("Flight-hop route route option")).toHaveTextContent("Rejected");
    expect(
      within(screen.getByLabelText("Rail-first route route option")).getByRole("button", {
        name: "View route",
      })
    ).toHaveAttribute("title", "Show Rail-first route on the map and day plan.");

    fireEvent.click(
      within(screen.getByLabelText("Fjord-focus route route option")).getByRole("button", {
        name: "Make baseline",
      })
    );
    fireEvent.click(
      within(screen.getByLabelText("Flight-hop route route option")).getByRole("button", {
        name: "Reopen",
      })
    );
    fireEvent.click(
      within(screen.getByLabelText("Rail-first route route option")).getByRole("button", {
        name: "View route",
      })
    );

    expect(onRouteOptionAction).toHaveBeenCalledWith("route-option:fjord-focus", "make_baseline");
    expect(onRouteOptionAction).toHaveBeenCalledWith("route-option:flight-hop", "reopen");
    expect(onSelectScenario).toHaveBeenCalledWith("route-option:rail-first");
  });
});
