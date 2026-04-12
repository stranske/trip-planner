import { describe, expect, it } from "vitest";

import type { FeasibilitySummary, RuntimeScenarioComparison, WorkspaceData } from "../../api/workspace";
import {
  buildGoogleMapsEmbedUrl,
  buildTripMapViewModel,
  resolveTripMapProvider,
} from "./tripMapModel";

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
    destination_names: ["Kyoto", "Uji", "Kyoto"],
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

describe("tripMapModel", () => {
  it("builds a provider-independent route model with deduped anchors", () => {
    const model = buildTripMapViewModel({
      comparison,
      activeScenarioId: "scenario-1",
      bundles,
      feasibilitySummary,
    });

    expect(model).not.toBeNull();
    expect(model?.stops.map((stop) => stop.label)).toEqual(["Kyoto", "Uji", "Kyoto"]);
    expect(model?.destinationAnchors).toEqual(["Kyoto", "Uji"]);
    expect(model?.feasibilityNote).toContain("2 destination anchors");
  });

  it("prefers Google Maps only when an API key is available", () => {
    expect(resolveTripMapProvider({ preferredProvider: "google-maps", googleMapsApiKey: "" })).toBe(
      "fallback",
    );
    expect(
      resolveTripMapProvider({ preferredProvider: "google-maps", googleMapsApiKey: "test-key" }),
    ).toBe("google-maps");
    expect(resolveTripMapProvider({ preferredProvider: "fallback", googleMapsApiKey: "test-key" })).toBe(
      "fallback",
    );
  });

  it("builds a Google Maps embed URL with route waypoints", () => {
    const model = buildTripMapViewModel({
      comparison,
      activeScenarioId: "scenario-1",
      bundles,
      feasibilitySummary,
    });

    expect(model).not.toBeNull();
    const url = buildGoogleMapsEmbedUrl({ apiKey: "abc123", model: model! });

    expect(url).toContain("google.com/maps/embed/v1/directions");
    expect(url).toContain("origin=Kyoto");
    expect(url).toContain("destination=Kyoto");
    expect(url).toContain("waypoints=Uji");
    expect(url).toContain("key=abc123");
  });
});
