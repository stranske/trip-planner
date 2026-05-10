import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { FeasibilitySummary, RuntimeScenarioComparison, WorkspaceData } from "../../api/workspace";
import { TripMap } from "./TripMap";

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
      available_actions: [],
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
      unresolved_questions: ["Can the scenic transfer still fit the trip pace?"],
      available_actions: [],
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
  ],
  source_refs: ["scenario-search:scandinavia"],
};

const bundles: WorkspaceData["inventory_summary"]["bundles"] = [
  {
    bundle_id: "bundle-rail",
    title: "Rail transfer anchors",
    bundle_context: "transport_route",
    summary: "Rail transfers attached to the current route.",
    destination_names: ["Stockholm", "Oslo", "Bergen"],
    option_count: 3,
    strengths: [],
    tradeoffs: [],
  },
];

const feasibilitySummary: FeasibilitySummary = {
  assessment_count: 1,
  recommended_bundle_count: 1,
  blocking_bundle_count: 0,
  attention_bundle_count: 0,
  notes: [],
  assessments: [],
};

afterEach(() => {
  cleanup();
});

function renderTripMap(onSelectScenario = vi.fn()) {
  render(
    <TripMap
      comparison={comparison}
      scenarioComparisonSummary="Rail-first stays the easiest route to compare against."
      scenarioFocusAreas={["route_pace"]}
      activeScenarioId="route-option:rail-first"
      onSelectScenario={onSelectScenario}
      bundles={bundles}
      feasibilitySummary={feasibilitySummary}
      tripPrimaryRegions={["Sweden", "Norway"]}
      policyPosture="No approval packet yet"
      compactLayout={false}
    />
  );
  return onSelectScenario;
}

describe("TripMap", () => {
  it("switches map scopes without changing the selected route option", () => {
    const onSelectScenario = renderTripMap();

    const scopeControls = screen.getByLabelText("Map view scope");
    expect(within(scopeControls).getByRole("button", { name: "Route" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );

    fireEvent.click(within(scopeControls).getByRole("button", { name: "Segment" }));

    expect(screen.getByLabelText("Local segment selector")).toBeInTheDocument();
    expect(screen.getByText("Segment-level planning view")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Oslo to Bergen" }));
    expect(screen.getByLabelText("Oslo to Bergen route drawing")).toHaveTextContent(
      "1 shown segment"
    );

    fireEvent.click(within(scopeControls).getByRole("button", { name: "Whole trip" }));
    expect(screen.getByText("Approximate trip outline")).toBeInTheDocument();
    expect(onSelectScenario).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "2. Fjord-focus route" }));
    expect(onSelectScenario).toHaveBeenCalledWith("route-option:fjord-focus");
  });

  it("keeps provider diagnostics out of the normal traveler map", () => {
    renderTripMap();

    expect(screen.getByLabelText("Map view confidence")).toHaveTextContent(
      "Approximate route shape"
    );
    expect(screen.queryByText(/Google Maps JavaScript/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Provider misconfigured/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Provider error/i)).not.toBeInTheDocument();
  });
});
