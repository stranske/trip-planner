import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { FeasibilitySummary, RuntimeScenarioComparison, WorkspaceData } from "../../api/workspace";
import { TripMap } from "./TripMap";

const sdk = vi.hoisted(() => ({
  markers: [] as Array<EventTarget & { map: unknown; title: string; position: unknown; zIndex: number | null }>,
  geocode: vi.fn(), load: vi.fn(), polylines: [] as Array<{ setMap: ReturnType<typeof vi.fn> }>,
}));
vi.mock("@googlemaps/js-api-loader", () => ({ setOptions: vi.fn(), importLibrary: sdk.load }));
beforeEach(() => {
  sdk.markers.length = 0; sdk.polylines.length = 0;
  sdk.geocode.mockReset().mockImplementation(async () => ({ results: [{ geometry: { location: { toJSON: () => ({ lat: 59.9, lng: 10.7 }) } } }] }));
  sdk.load.mockReset().mockImplementation(async (library: string) => {
    if (library === "maps") return {
      Map: class { fitBounds = vi.fn(); },
      Polyline: class { setMap = vi.fn(); constructor() { sdk.polylines.push(this); } },
    };
    if (library === "marker") return { AdvancedMarkerElement: class extends EventTarget {
      map: unknown; title: string; position: unknown; zIndex: number | null;
      constructor(options: { map: unknown; title: string; position: unknown; zIndex?: number }) {
        super(); Object.assign(this, options); this.map = options.map; this.title = options.title;
        this.position = options.position; this.zIndex = options.zIndex ?? null; sdk.markers.push(this);
      }
    } };
    if (library === "geocoding") return { Geocoder: class { geocode = sdk.geocode; } };
    if (library === "core") return { LatLngBounds: class { extend = vi.fn(); } };
    throw new Error("unexpected SDK library " + library);
  });
});

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

const planningLedger: WorkspaceData["planning_ledger"] = {
  entries: [
    {
      ledger_entry_id: "ledger:route-baseline",
      trip_id: "trip:scandinavia",
      session_state_id: "session:scandinavia",
      item_type: "option_considered",
      status: "active",
      category: "route_options",
      summary: "Keep rail-first route as the baseline until ferry timing is known.",
      detail: "",
      source_message_ids: [],
      source_refs: [],
      related_option_id: "route-option:rail-first",
      related_decision_id: null,
      supersedes_entry_id: null,
      metadata: {},
      created_at: "2026-05-10T00:00:00Z",
      updated_at: "2026-05-10T00:00:00Z",
    },
    {
      ledger_entry_id: "ledger:oslo-transfer",
      trip_id: "trip:scandinavia",
      session_state_id: "session:scandinavia",
      item_type: "open_question",
      status: "active",
      category: "questions",
      summary: "Remember Oslo rail transfer timing.",
      detail: "",
      source_message_ids: [],
      source_refs: [],
      related_option_id: null,
      related_decision_id: null,
      supersedes_entry_id: null,
      metadata: { bundle_id: "bundle-rail" },
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
};

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

function renderTripMap(
  onSelectScenario = vi.fn(),
  ledger?: WorkspaceData["planning_ledger"],
  onSelectSegment = vi.fn(),
  providerLoadState?: "pending" | "loading" | "ready" | "error"
) {
  function Harness() {
    const [scenario, setScenario] = useState("route-option:rail-first");
    const [activeScope, setActiveScope] = useState<"global" | "regional" | "local">("regional");
    const [selectedSegmentId, setSelectedSegmentId] = useState<string | null>(null);
    return (
      <TripMap
        comparison={comparison}
        scenarioComparisonSummary="Rail-first stays the easiest route to compare against."
        scenarioFocusAreas={["route_pace"]}
        activeScenarioId={scenario}
        onSelectScenario={(id) => { setScenario(id); onSelectScenario(id); }}
        bundles={bundles}
        feasibilitySummary={feasibilitySummary}
        tripPrimaryRegions={["Sweden", "Norway"]}
        tripMode="business"
        policyPosture="No approval packet yet"
        planningLedger={ledger}
        providerLoadState={providerLoadState}
        activeScope={activeScope}
        selectedSegmentId={selectedSegmentId}
        onScopeChange={setActiveScope}
        onSelectSegment={(segmentId) => {
          onSelectSegment(segmentId);
          setSelectedSegmentId(segmentId);
        }}
        compactLayout={false}
      />
    );
  }

  render(<Harness />);
  return { onSelectScenario, onSelectSegment };
}

describe("TripMap", () => {
  it("switches map scopes without changing the selected route option", () => {
    const { onSelectScenario, onSelectSegment } = renderTripMap();

    const scopeControls = screen.getByLabelText("Map view scope");
    expect(within(scopeControls).getByRole("button", { name: "Route" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );

    fireEvent.click(within(scopeControls).getByRole("button", { name: "Segment" }));

    expect(screen.getByLabelText("Local segment selector")).toBeInTheDocument();
    expect(screen.getByText("Segment-level planning view")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Oslo to Bergen/ }));
    expect(onSelectSegment).toHaveBeenCalledWith(
      "route-option:rail-first-oslo-1-route-option:rail-first-bergen-2"
    );

    fireEvent.click(within(scopeControls).getByRole("button", { name: "Whole trip" }));
    expect(screen.getByText("Approximate trip outline")).toBeInTheDocument();
    expect(onSelectScenario).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "2. Fjord-focus route" }));
    expect(onSelectScenario).toHaveBeenCalledWith("route-option:fjord-focus");
  });

  it("keeps provider diagnostics out of the normal traveler map", () => {
    renderTripMap();

    expect(screen.getByRole("heading", { name: "Route sketch for Rail-first route" })).toBeInTheDocument();
    expect(screen.getByLabelText("Map view confidence")).toHaveTextContent(
      "Regional route review"
    );
    expect(screen.getByText("Schematic preview — not a live map")).toBeInTheDocument();
    expect(screen.getByText("Route sketch mode")).toBeInTheDocument();
    expect(screen.queryByText(/Google Maps JavaScript/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Provider misconfigured/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Provider error/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /route geometry overlay/i })).not.toBeInTheDocument();
  });

  it("labels the keyed provider surface as a schematic preview when readiness is unproven", () => {
    vi.stubEnv("VITE_GOOGLE_MAPS_BROWSER_API_KEY", "test-key");

    renderTripMap();

    expect(screen.getByRole("heading", { name: "Route sketch for Rail-first route" })).toBeInTheDocument();
    expect(screen.getByText("Schematic preview — not a live map")).toBeInTheDocument();
    expect(screen.getByText("Route sketch mode")).toBeInTheDocument();
    expect(screen.getByLabelText("Selected route option route drawing")).toHaveClass("map-route-fallback");
    expect(screen.queryByText(/Google Maps JavaScript/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText("High confidence: the route has enough map detail for close review.")
    ).not.toBeInTheDocument();
  });

  it("mounts the provider-backed surface when readiness is observed", () => {
    vi.stubEnv("VITE_GOOGLE_MAPS_BROWSER_API_KEY", "test-key");

    renderTripMap(vi.fn(), undefined, vi.fn(), "ready");

    expect(screen.getByRole("heading", { name: "Map for Rail-first route" })).toBeInTheDocument();
    expect(screen.queryByText("Schematic preview — not a live map")).not.toBeInTheDocument();
    expect(screen.queryByText("Route sketch mode")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Selected route option route drawing")).toHaveClass(
      "map-route-google-maps-js"
    );
    expect(
      screen.getByRole("group", { name: "Simulated Google map for Rail-first route" })
    ).toHaveAttribute("data-provider-surface", "simulated-ready");
    expect(screen.queryByText(/Google Maps JavaScript/i)).not.toBeInTheDocument();
  });

  it("surfaces linked planning ledger entries as map focus cues", () => {
    renderTripMap(vi.fn(), planningLedger);

    expect(screen.getByLabelText("Route context map")).toHaveTextContent(
      "2 linked planning note"
    );
    expect(screen.getByLabelText("Linked planning notes")).toHaveTextContent(
      "Keep rail-first route as the baseline until ferry timing is known."
    );
    expect(screen.getByLabelText("Linked planning notes for selected marker")).toHaveTextContent(
      "Remember Oslo rail transfer timing."
    );
    expect(
      screen.getByRole("button", {
        name: /transport marker: Rail transfer anchors.*1 linked planning note/i,
      })
    ).toBeInTheDocument();
  });

  it("keeps a visible marker selected when refreshed scenario data has a new identity", () => {
    function RefreshHarness({ refreshed }: { refreshed: boolean }) {
      const [activeScope, setActiveScope] = useState<"global" | "regional" | "local">("regional");
      const [selectedSegmentId, setSelectedSegmentId] = useState<string | null>(null);
      const refreshedComparison = refreshed
        ? { ...comparison, scenarios: comparison.scenarios.map((scenario) => ({ ...scenario })) }
        : comparison;
      return (
        <TripMap
          comparison={refreshedComparison}
          scenarioComparisonSummary="Rail-first stays the easiest route to compare against."
          scenarioFocusAreas={["route_pace"]}
          activeScenarioId="route-option:rail-first"
          onSelectScenario={vi.fn()}
          bundles={bundles}
          feasibilitySummary={feasibilitySummary}
          tripPrimaryRegions={["Sweden", "Norway"]}
          tripMode="business"
          policyPosture="No approval packet yet"
          activeScope={activeScope}
          selectedSegmentId={selectedSegmentId}
          onScopeChange={setActiveScope}
          onSelectSegment={setSelectedSegmentId}
          compactLayout={false}
        />
      );
    }

    const view = render(<RefreshHarness refreshed={false} />);
    const markerButtons = screen.getAllByRole("button", { name: /marker:/i });
    const selectedMarker = markerButtons[markerButtons.length - 1];
    fireEvent.click(selectedMarker);
    expect(selectedMarker).toHaveAttribute("aria-pressed", "true");

    view.rerender(<RefreshHarness refreshed />);

    expect(screen.getByRole("button", { name: selectedMarker.getAttribute("aria-label")! })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
  });

  it("renders segment timing and confidence in traveler language", () => {
    renderTripMap();

    expect(screen.getByRole("heading", { name: "Segment focus" })).toBeInTheDocument();
    expect(screen.getByText(/Stockholm to Oslo · 210 min/)).toBeInTheDocument();
    expect(screen.getByText("Segment timing is estimated from ranked route data.")).toBeInTheDocument();
  });
});


describe("real Google Maps adapter", () => {
  it("selects canonical marker details and linked notes from an SDK click", async () => {
    vi.stubEnv("VITE_GOOGLE_MAPS_BROWSER_API_KEY", "test-key");
    const ledger = { ...planningLedger, entries: [{ ...planningLedger.entries[1], metadata: { marker_id: "oslo" } }] };
    renderTripMap(vi.fn(), ledger); // No providerLoadState override: mounts the actual adapter.
    const canvas = await screen.findByRole("group", { name: "Interactive Google map for Rail-first route" });
    await waitFor(() => expect(canvas).toHaveAttribute("data-google-maps-live", "true"));
    expect(screen.getByRole("button", { name: /transport marker: Rail transfer anchors/i })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Stockholm/ }).length).toBeGreaterThan(0);
    expect(sdk.markers.map((marker) => marker.title)).not.toContain("Rail transfer anchors");
    // Select another marker first: Oslo may be selected initially by its linked note.
    fireEvent.click(screen.getByRole("button", { name: /transport marker: Rail transfer anchors/i }));
    expect(screen.getByRole("heading", { name: "Rail transfer anchors" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Oslo" })).not.toBeInTheDocument();
    const oslo = sdk.markers.find((marker) => marker.title === "Oslo")!;
    expect(oslo).toBeDefined();
    act(() => { oslo.dispatchEvent(new Event("gmp-click")); });
    expect(screen.getByRole("heading", { name: "Oslo" })).toBeInTheDocument();
    expect(screen.getByLabelText("Linked planning notes for selected marker")).toHaveTextContent("Remember Oslo rail transfer timing.");
    expect(oslo.zIndex).toBe(1000);
    const removeListener = vi.spyOn(oslo, "removeEventListener");
    cleanup();
    expect(removeListener).toHaveBeenCalledWith("gmp-click", expect.any(Function));
    expect(sdk.markers.every((marker) => marker.map === null)).toBe(true);
    expect(sdk.polylines.every((line) => line.setMap.mock.calls.some(([map]) => map === null))).toBe(true);
    // The old SDK callback must be removed when the adapter is disposed.
    oslo.dispatchEvent(new Event("gmp-click"));
  });

  it("retains canonical controls when SDK loading fails", async () => {
    vi.stubEnv("VITE_GOOGLE_MAPS_BROWSER_API_KEY", "test-key");
    sdk.load.mockRejectedValueOnce(new Error("synthetic SDK failure"));
    renderTripMap();
    await waitFor(() => expect(sdk.load).toHaveBeenCalledWith("maps"));
    await waitFor(() => expect(screen.queryByRole("group", { name: "Interactive Google map for Rail-first route" })).not.toBeInTheDocument());
    expect(screen.getAllByRole("button", { name: /Stockholm/ }).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /transport marker: Rail transfer anchors/i })).toBeInTheDocument();
  });

  it("retains route and option context when geocoding fails and the scenario changes", async () => {
    vi.stubEnv("VITE_GOOGLE_MAPS_BROWSER_API_KEY", "test-key");
    sdk.geocode.mockRejectedValue(new Error("synthetic missing location"));
    renderTripMap();
    await waitFor(() => expect(sdk.load).toHaveBeenCalledWith("maps"));
    await waitFor(() => expect(screen.queryByRole("group", { name: "Interactive Google map for Rail-first route" })).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /Fjord-focus route/ }));
    await waitFor(() => expect(screen.getAllByText("Fjord-focus route").length).toBeGreaterThan(0));
    await waitFor(() => expect(screen.queryByRole("group", { name: "Interactive Google map for Fjord-focus route" })).not.toBeInTheDocument());
    expect(screen.getByRole("button", { name: /transport marker: Rail transfer anchors/i })).toBeInTheDocument();
    expect(sdk.markers).toHaveLength(0);
  });
});


it("replaces SDK overlays on a ready scenario change without losing option controls", async () => {
  vi.stubEnv("VITE_GOOGLE_MAPS_BROWSER_API_KEY", "test-key");
  renderTripMap();
  await waitFor(() => expect(screen.getByRole("group", { name: "Interactive Google map for Rail-first route" })).toHaveAttribute("data-google-maps-live", "true"));
  const previousMarkers = [...sdk.markers];
  fireEvent.click(screen.getByRole("button", { name: /Fjord-focus route/ }));
  await waitFor(() => expect(screen.getByRole("group", { name: "Interactive Google map for Fjord-focus route" })).toHaveAttribute("data-google-maps-live", "true"));
  expect(previousMarkers.every((marker) => marker.map === null)).toBe(true);
  expect(sdk.markers.some((marker) => marker.map !== null && marker.title === "Flam")).toBe(true);
  expect(screen.getByRole("button", { name: /transport marker: Rail transfer anchors/i })).toBeInTheDocument();
});
