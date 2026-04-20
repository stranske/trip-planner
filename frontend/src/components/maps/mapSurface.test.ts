import { describe, expect, it } from "vitest";

import {
  buildTripMapSurfaceModel,
  humanizeStop,
} from "./mapSurface";

describe("mapSurface", () => {
  it("normalizes route stop labels for provider-independent map shaping", () => {
    expect(humanizeStop("dest-city-new-york")).toBe("New York");
    expect(humanizeStop("kyoto_station")).toBe("Kyoto Station");
  });

  it("selects the live Google Maps JavaScript adapter when a key and route are available", () => {
    const model = buildTripMapSurfaceModel({
      activeScenario: {
        scenario_id: "scenario:1",
        title: "Kyoto base",
        rank: 1,
        status: "lead",
        summary: "Baseline",
        comparison_note: "Lead route",
        option_count: 2,
        route_sequence: ["kyoto", "uji", "kyoto"],
        route_summary: "kyoto -> uji -> kyoto",
        recommended_for_selection: true,
        feasible: true,
        metrics: {
          score: 0.93,
          travel_minutes: 265,
          transfers: 4,
          estimated_total: { currency: "JPY", typical_amount: 3400 },
        },
        delta: {
          score_delta: 0,
          travel_minutes_delta: 0,
          transfers_delta: 0,
          estimated_total_delta: 0,
        },
        highlights: ["Low-friction baseline."],
      },
      bundles: [
        {
          bundle_id: "bundle-1",
          title: "Kyoto anchor",
          bundle_context: "route_level",
          summary: "Bundle summary",
          destination_names: ["Kyoto", "Uji"],
          option_count: 2,
          strengths: [],
          tradeoffs: [],
        },
      ],
      feasibilitySummary: {
        assessment_count: 2,
        recommended_bundle_count: 1,
        blocking_bundle_count: 0,
        attention_bundle_count: 1,
        notes: [],
        assessments: [],
      },
      scenarioComparisonSummary: "Kyoto baseline remains preferred with Osaka preserved for fallback.",
      scenarioFocusAreas: ["route_coherence", "weather_resilience"],
      tripPrimaryRegions: ["JP-26", "JP-27"],
      policyPosture: "Approval-ready",
      googleMapsApiKey: "test-key",
    });

    expect(model.provider.kind).toBe("google-maps-js");
    expect(model.destinationAnchors).toEqual(["Kyoto", "Uji"]);
    expect(model.destinationContext).toEqual(["Kyoto", "Uji", "JP-26", "JP-27"]);
    expect(model.policyPosture).toBe("Approval-ready");
    expect(model.scenarioComparisonSummary).toContain("Kyoto baseline remains preferred");
    expect(model.scenarioFocusAreas).toEqual(["route_coherence", "weather_resilience"]);
    expect(model.routeStops.map((stop) => stop.label)).toEqual(["Kyoto", "Uji", "Kyoto"]);
    expect(model.routeSegments).toHaveLength(2);
    expect(model.markers.map((marker) => marker.kind)).toEqual([
      "stop",
      "stop",
      "stop",
      "transport",
      "policy",
    ]);
  });

  it("falls back when Google Maps is not configured", () => {
    const model = buildTripMapSurfaceModel({
      activeScenario: {
        scenario_id: "scenario:1",
        title: "Kyoto base",
        rank: 1,
        status: "lead",
        summary: "Baseline",
        comparison_note: "Lead route",
        option_count: 2,
        route_sequence: ["kyoto", "uji"],
        route_summary: "kyoto -> uji",
        recommended_for_selection: true,
        feasible: true,
        metrics: {
          score: 0.93,
          travel_minutes: 265,
          transfers: 4,
          estimated_total: null,
        },
        delta: {
          score_delta: 0,
          travel_minutes_delta: 0,
          transfers_delta: 0,
          estimated_total_delta: null,
        },
        highlights: ["Low-friction baseline."],
      },
      bundles: [],
      feasibilitySummary: {
        assessment_count: 0,
        recommended_bundle_count: 0,
        blocking_bundle_count: 0,
        attention_bundle_count: 0,
        notes: [],
        assessments: [],
      },
    });

    expect(model.provider.kind).toBe("fallback");
    expect(model.provider.summary).toContain("bounded textual route fallback");
    expect(model.provider.status).toBe("misconfigured");
    expect(model.scenarioComparisonSummary).toBe(
      "Scenario comparison summary is still syncing to this workspace review surface."
    );
  });

  it("keeps route context visible when the provider reports a load error", () => {
    const model = buildTripMapSurfaceModel({
      activeScenario: {
        scenario_id: "scenario:1",
        title: "Kyoto base",
        rank: 1,
        status: "lead",
        summary: "Baseline",
        comparison_note: "Lead route",
        option_count: 2,
        route_sequence: ["kyoto", "uji"],
        route_summary: "kyoto -> uji",
        recommended_for_selection: true,
        feasible: true,
        metrics: {
          score: 0.93,
          travel_minutes: 265,
          transfers: 4,
          estimated_total: null,
        },
        delta: {
          score_delta: 0,
          travel_minutes_delta: 0,
          transfers_delta: 0,
          estimated_total_delta: null,
        },
        highlights: ["Low-friction baseline."],
      },
      bundles: [],
      feasibilitySummary: {
        assessment_count: 0,
        recommended_bundle_count: 0,
        blocking_bundle_count: 0,
        attention_bundle_count: 0,
        notes: [],
        assessments: [],
      },
      googleMapsApiKey: "test-key",
      providerLoadState: "error",
    });

    expect(model.provider.kind).toBe("fallback");
    expect(model.provider.status).toBe("provider-error");
    expect(model.routeSegments).toHaveLength(1);
  });
});
