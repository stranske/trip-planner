import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { FeasibilitySummary, RuntimeScenarioComparison, WorkspaceData } from "../../api/workspace";
import { TripMap } from "./TripMap";

const comparison: RuntimeScenarioComparison = {
  title: "Kyoto route comparison",
  summary: "Compare two route candidates.",
  lead_scenario_id: "scenario-1",
  comparison_axes: [],
  scenarios: [
    {
      scenario_id: "scenario-1",
      title: "Kyoto base",
      rank: 1,
      status: "lead",
      summary: "Primary route.",
      comparison_note: "Lead route.",
      option_count: 3,
      route_sequence: ["kyoto", "uji", "kyoto"],
      route_summary: "Kyoto -> Uji -> Kyoto",
      recommended_for_selection: true,
      feasible: true,
      metrics: {
        score: 0.9,
        travel_minutes: 180,
        transfers: 2,
        estimated_total: { currency: "JPY", typical_amount: 3400 },
      },
      delta: {
        score_delta: 0,
        travel_minutes_delta: 0,
        transfers_delta: 0,
        estimated_total_delta: 0,
      },
      highlights: ["Balanced route."],
    },
  ],
  source_refs: [],
};

const bundles: WorkspaceData["inventory_summary"]["bundles"] = [
  {
    bundle_id: "bundle-1",
    title: "Kyoto anchor",
    bundle_context: "route_level",
    summary: "Kyoto baseline",
    destination_names: ["Kyoto", "Uji"],
    option_count: 2,
    strengths: [],
    tradeoffs: [],
  },
];

const feasibilitySummary: FeasibilitySummary = {
  assessment_count: 2,
  recommended_bundle_count: 1,
  blocking_bundle_count: 0,
  attention_bundle_count: 0,
  notes: [],
  assessments: [],
};

describe("TripMap", () => {
  it("renders the fallback preview when Google Maps is unavailable", () => {
    render(
      <TripMap
        comparison={comparison}
        activeScenarioId="scenario-1"
        onSelectScenario={vi.fn()}
        bundles={bundles}
        feasibilitySummary={feasibilitySummary}
        providerOverride="fallback"
      />,
    );

    expect(screen.getByText("Fallback provider preview")).toBeInTheDocument();
    expect(screen.getByLabelText("Route context map")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: "Kyoto" })).toHaveLength(2);
  });

  it("renders a Google Maps iframe when the provider path is enabled", () => {
    render(
      <TripMap
        comparison={comparison}
        activeScenarioId="scenario-1"
        onSelectScenario={vi.fn()}
        bundles={bundles}
        feasibilitySummary={feasibilitySummary}
        providerOverride="google-maps"
        googleMapsApiKeyOverride="test-key"
      />,
    );

    expect(screen.getByText("Google Maps provider")).toBeInTheDocument();
    expect(screen.getByTitle("Google Maps route for Kyoto base")).toBeInTheDocument();
  });
});
