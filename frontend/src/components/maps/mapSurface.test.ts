import { describe, expect, it } from "vitest";

import { buildTripMapSurfaceModel, humanizeStop } from "./mapSurface";

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
    expect(model.destinationContext).toEqual(["Kyoto", "Uji", "JP 26", "JP 27"]);
    expect(model.policyPosture).toBe("Approval-ready");
    expect(model.scenarioComparisonSummary).toContain("Kyoto baseline remains preferred");
    expect(model.scenarioFocusAreas).toEqual(["route_coherence", "weather_resilience"]);
    expect(model.scenarioAffordances).toEqual([
      "Recommended scenario",
      "Feasibility-ready route",
      "2 mapped option marker(s)",
      "3 route stop(s)",
      "4 transfer checkpoint(s)",
      "Approval or feasibility warning active",
    ]);
    expect(model.routeStops.map((stop) => stop.label)).toEqual(["Kyoto", "Uji", "Kyoto"]);
    expect(model.routeSegments).toHaveLength(2);
    expect(model.workspaceView.activeScope).toBe("regional");
    expect(model.workspaceView.activeRouteOptionId).toBe("scenario:1");
    expect(model.workspaceView.selectedSegmentId).toBe(model.routeSegments[0].id);
    expect(model.workspaceView.placeMarkers).toEqual(model.markers);
    expect(model.workspaceView.roughRouteGeometry).toEqual(model.routeSegments);
    expect(model.workspaceView.confidence.level).toBe("high");
    expect(model.workspaceView.diagnostics.provider).toEqual(model.provider);
    expect(model.workspaceView.diagnostics.routeState).toBe("ready");
    expect(model.markers.map((marker) => marker.kind)).toEqual([
      "stop",
      "stop",
      "stop",
      "transport",
      "policy",
    ]);
  });

  it("switches between whole-trip and local map scopes without losing the route option", () => {
    const baseInput = {
      activeScenario: {
        scenario_id: "scenario:scope",
        title: "Kyoto local detail",
        rank: 1,
        status: "lead",
        summary: "Baseline",
        comparison_note: "Lead route",
        option_count: 2,
        route_sequence: ["kyoto", "uji", "nara"],
        route_summary: "kyoto -> uji -> nara",
        recommended_for_selection: true,
        feasible: true,
        metrics: {
          score: 0.91,
          travel_minutes: 180,
          transfers: 2,
          estimated_total: null,
        },
        delta: {
          score_delta: 0,
          travel_minutes_delta: 0,
          transfers_delta: 0,
          estimated_total_delta: null,
        },
        highlights: ["Short regional route."],
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
    };
    const globalModel = buildTripMapSurfaceModel({
      ...baseInput,
      activeScope: "global",
    });
    const secondSegmentId = globalModel.routeSegments[1].id;
    const localModel = buildTripMapSurfaceModel({
      ...baseInput,
      activeScope: "local",
      selectedSegmentId: secondSegmentId,
    });

    expect(globalModel.workspaceView.activeScope).toBe("global");
    expect(globalModel.workspaceView.activeRouteOptionId).toBe("scenario:scope");
    expect(globalModel.visibleRouteSegments).toHaveLength(2);
    expect(globalModel.scope.precisionLabel).toBe("Approximate trip outline");

    expect(localModel.workspaceView.activeScope).toBe("local");
    expect(localModel.workspaceView.activeRouteOptionId).toBe("scenario:scope");
    expect(localModel.workspaceView.selectedSegmentId).toBe(secondSegmentId);
    expect(localModel.visibleRouteSegments).toHaveLength(1);
    expect(localModel.visibleRouteStops.map((stop) => stop.label)).toEqual(["Uji", "Nara"]);
    expect(localModel.scope.precisionLabel).toBe("Segment-level planning view");
  });

  it("connects directly linked ledger entries to map markers and route segments", () => {
    const baseInput = {
      activeScenario: {
        scenario_id: "scenario:focus",
        route_option_id: "route-option:focus",
        title: "Kyoto route focus",
        rank: 1,
        status: "lead",
        summary: "Baseline",
        comparison_note: "Lead route",
        option_count: 2,
        route_sequence: ["kyoto", "uji", "nara"],
        route_summary: "kyoto -> uji -> nara",
        recommended_for_selection: true,
        feasible: true,
        metrics: {
          score: 0.91,
          travel_minutes: 180,
          transfers: 2,
          estimated_total: null,
        },
        delta: {
          score_delta: 0,
          travel_minutes_delta: 0,
          transfers_delta: 0,
          estimated_total_delta: null,
        },
        highlights: ["Short regional route."],
      },
      bundles: [
        {
          bundle_id: "bundle-uji-tea",
          title: "Uji tea anchors",
          bundle_context: "activity_route",
          summary: "Tea stops that should stay near the Uji leg.",
          destination_names: ["Uji"],
          option_count: 2,
          strengths: [],
          tradeoffs: [],
        },
      ],
      feasibilitySummary: {
        assessment_count: 0,
        recommended_bundle_count: 0,
        blocking_bundle_count: 0,
        attention_bundle_count: 0,
        notes: [],
        assessments: [],
      },
      googleMapsApiKey: "test-key",
    };
    const initialModel = buildTripMapSurfaceModel(baseInput);
    const focusedSegmentId = initialModel.routeSegments[1].id;

    const model = buildTripMapSurfaceModel({
      ...baseInput,
      planningLedger: {
        entries: [
          {
            ledger_entry_id: "ledger:route",
            trip_id: "trip:kyoto",
            session_state_id: "session:kyoto",
            item_type: "option_considered",
            status: "active",
            category: "route_options",
            summary: "Keep this route in view while checking lodging.",
            detail: "",
            source_message_ids: [],
            source_refs: [],
            related_option_id: "route-option:focus",
            related_decision_id: null,
            supersedes_entry_id: null,
            metadata: {},
            created_at: "2026-05-10T00:00:00Z",
            updated_at: "2026-05-10T00:00:00Z",
          },
          {
            ledger_entry_id: "ledger:segment",
            trip_id: "trip:kyoto",
            session_state_id: "session:kyoto",
            item_type: "open_question",
            status: "active",
            category: "questions",
            summary: "Check whether Uji to Nara is too much in one day.",
            detail: "",
            source_message_ids: [],
            source_refs: [],
            related_option_id: null,
            related_decision_id: null,
            supersedes_entry_id: null,
            metadata: { route_segment_id: focusedSegmentId },
            created_at: "2026-05-10T00:00:00Z",
            updated_at: "2026-05-10T00:00:00Z",
          },
          {
            ledger_entry_id: "ledger:marker",
            trip_id: "trip:kyoto",
            session_state_id: "session:kyoto",
            item_type: "assumption",
            status: "active",
            category: "assumption",
            summary: "Uji tea anchors should remain visible on the map.",
            detail: "",
            source_message_ids: [],
            source_refs: [],
            related_option_id: null,
            related_decision_id: null,
            supersedes_entry_id: null,
            metadata: { bundle_id: "bundle-uji-tea" },
            created_at: "2026-05-10T00:00:00Z",
            updated_at: "2026-05-10T00:00:00Z",
          },
        ],
        summary: {
          active_decisions: [],
          open_questions: [],
          active_options: [],
          rejected_options: [],
          constraints: [],
          assumptions: [],
          source_references: [],
        },
      },
    });

    expect(model.focusCues.map((cue) => cue.targetKind)).toEqual([
      "route",
      "segment",
      "marker",
    ]);
    expect(model.workspaceView.focusCues).toEqual(model.visibleFocusCues);
    expect(model.routeSegments[1].focusCues[0].summary).toContain("Uji to Nara");
    expect(
      model.markers.find(
        (marker) => marker.sourceId === "bundle-uji-tea" && marker.focusCues.length > 0
      )?.focusCues[0].summary
    ).toContain("Uji tea anchors");
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
    expect(model.workspaceView.confidence.level).toBe("medium");
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

  it("keeps route context visible while the provider is still loading", () => {
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
      providerLoadState: "loading",
    });

    expect(model.provider.kind).toBe("fallback");
    expect(model.provider.status).toBe("loading");
    expect(model.routeSegments).toHaveLength(1);
    expect(model.markers.length).toBeGreaterThan(0);
  });

  it("uses sparse route fallback when the active scenario does not include enough route stops", () => {
    const model = buildTripMapSurfaceModel({
      activeScenario: {
        scenario_id: "scenario:1",
        title: "Kyoto base",
        rank: 1,
        status: "lead",
        summary: "Baseline",
        comparison_note: "Lead route",
        option_count: 1,
        route_sequence: ["kyoto"],
        route_summary: "kyoto",
        recommended_for_selection: true,
        feasible: true,
        metrics: {
          score: 0.93,
          travel_minutes: 120,
          transfers: 1,
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
    });

    expect(model.routeState).toBe("sparse");
    expect(model.provider.kind).toBe("fallback");
    expect(model.provider.status).toBe("sparse-route");
    expect(model.workspaceView.confidence.level).toBe("low");
    expect(model.routeSegments).toHaveLength(0);
    expect(model.markers).toHaveLength(1);
  });

  it("emits lodging, activity, and transport markers from mixed bundle contexts", () => {
    const model = buildTripMapSurfaceModel({
      activeScenario: {
        scenario_id: "scenario:1",
        title: "Kyoto base",
        rank: 1,
        status: "lead",
        summary: "Baseline",
        comparison_note: "Lead route",
        option_count: 3,
        route_sequence: ["kyoto", "uji"],
        route_summary: "kyoto -> uji",
        recommended_for_selection: true,
        feasible: true,
        metrics: {
          score: 0.93,
          travel_minutes: 265,
          transfers: 2,
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
      bundles: [
        {
          bundle_id: "bundle-1",
          title: "Mixed transit stay",
          bundle_context: "transport_lodging_activity",
          summary: "Bundle summary",
          destination_names: ["Kyoto", "Uji"],
          option_count: 3,
          strengths: [],
          tradeoffs: [],
        },
      ],
      feasibilitySummary: {
        assessment_count: 1,
        recommended_bundle_count: 1,
        blocking_bundle_count: 0,
        attention_bundle_count: 0,
        notes: [],
        assessments: [],
      },
      googleMapsApiKey: "test-key",
    });

    const bundleMarkers = model.markers.filter((marker) => marker.id.startsWith("bundle-bundle-1-"));
    expect(bundleMarkers.map((marker) => marker.kind)).toEqual(["lodging", "activity", "transport"]);
  });
});
