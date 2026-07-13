import type {
  FeasibilitySummary,
  RuntimeScenarioComparison,
  WorkspaceData,
} from "../../api/workspace";

type TripMapScenario = RuntimeScenarioComparison["scenarios"][number];
type InventoryBundle = WorkspaceData["inventory_summary"]["bundles"][number];
type PlanningLedgerState = NonNullable<WorkspaceData["planning_ledger"]>;
type PlanningLedgerEntry = PlanningLedgerState["entries"][number];

export type MapProviderLoadState = "ready" | "loading" | "error";

export type MapSurfaceProvider =
  | {
      kind: "google-maps-js";
      label: "Google Maps configured";
      status: "configured";
      apiKey: string;
      summary: string;
    }
  | {
      kind: "fallback";
      label: string;
      status: "fallback" | "misconfigured" | "provider-error" | "loading" | "sparse-route";
      summary: string;
    };

export type RouteStop = {
  id: string;
  sourceId: string;
  label: string;
  description: string;
  sourceRefs: string[];
  x: number;
  y: number;
  latitude?: number;
  longitude?: number;
};

export type MapMarkerKind = "stop" | "lodging" | "activity" | "transport" | "policy";

export type MapFocusCue = {
  ledgerEntryId: string;
  label: string;
  summary: string;
  status: PlanningLedgerEntry["status"];
  itemType: PlanningLedgerEntry["item_type"];
  targetKind: "route" | "segment" | "marker";
  targetId: string;
  markerId: string | null;
  segmentId: string | null;
};

export type MapMarker = {
  id: string;
  sourceId: string;
  kind: MapMarkerKind;
  label: string;
  summary: string;
  detail: string;
  x: number;
  y: number;
  latitude?: number;
  longitude?: number;
  emphasized: boolean;
  focusCues: MapFocusCue[];
};

export type RouteSegment = {
  id: string;
  fromStopId: string;
  toStopId: string;
  fromLabel: string;
  toLabel: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  warning: string | null;
  durationMinutes: number | null;
  distanceKm: number | null;
  confidence: MapGeometryConfidence;
  unavailableReason: string | null;
  focusCues: MapFocusCue[];
};

export type MapViewScope = "global" | "regional" | "local";
export type MapGeometryConfidence = "high" | "medium" | "low";

export type MapWorkspaceView = {
  activeScope: MapViewScope;
  activeRouteOptionId: string;
  selectedSegmentId: string | null;
  placeMarkers: MapMarker[];
  roughRouteGeometry: RouteSegment[];
  focusCues: MapFocusCue[];
  confidence: {
    level: MapGeometryConfidence;
    summary: string;
  };
  diagnostics: {
    provider: MapSurfaceProvider;
    routeState: "ready" | "sparse";
    routeWarning: string | null;
  };
};

export type MapScopePresentation = {
  activeScope: MapViewScope;
  label: string;
  summary: string;
  precisionLabel: string;
};

export const MAP_SCOPE_OPTIONS: Array<{
  scope: MapViewScope;
  label: string;
  title: string;
}> = [
  {
    scope: "global",
    label: "Whole trip",
    title: "Show the broad outline across all trip anchors.",
  },
  {
    scope: "regional",
    label: "Route",
    title: "Show the selected route option and its main travel legs.",
  },
  {
    scope: "local",
    label: "Segment",
    title: "Focus on one travel leg and nearby planning markers.",
  },
];

export type TripMapSurfaceModel = {
  provider: MapSurfaceProvider;
  routeStops: RouteStop[];
  routeSegments: RouteSegment[];
  markers: MapMarker[];
  visibleRouteStops: RouteStop[];
  visibleRouteSegments: RouteSegment[];
  visibleMarkers: MapMarker[];
  focusCues: MapFocusCue[];
  visibleFocusCues: MapFocusCue[];
  destinationAnchors: string[];
  destinationContext: string[];
  scenarioFocusAreas: string[];
  scenarioComparisonSummary: string;
  scenarioAffordances: string[];
  policyPosture: string | null;
  feasibilitySummary: string;
  routeState: "ready" | "sparse";
  routeWarning: string | null;
  scope: MapScopePresentation;
  scopeOptions: typeof MAP_SCOPE_OPTIONS;
  workspaceView: MapWorkspaceView;
};

export function humanizeStop(stop: string): string {
  return stop
    .replace(/^dest-city-/, "")
    .replace(/^dest-/, "")
    .replace(/^city-/, "")
    .split(/[-_]/g)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function formatEstimatedTotal(
  value: RuntimeScenarioComparison["scenarios"][number]["metrics"]["estimated_total"]
): string {
  if (value == null) {
    return "Pending";
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: value.currency,
    maximumFractionDigits: 0,
  }).format(value.typical_amount);
}

export function summarizeFeasibility(
  feasibilitySummary: FeasibilitySummary,
  bundleDestinations: string[]
): string {
  if (feasibilitySummary.assessment_count === 0) {
    return "No inventory bundles have produced route-feasibility signals yet.";
  }

  if (bundleDestinations.length === 0) {
    return `${feasibilitySummary.assessment_count} bundle checks are available, but destination anchors have not been attached yet.`;
  }

  return `${bundleDestinations.length} destination anchors are backed by ${feasibilitySummary.assessment_count} feasibility assessment(s).`;
}

function describeStop(index: number, routeLength: number): string {
  if (index === 0) {
    return "Current route origin for the workspace preview.";
  }
  if (index === routeLength - 1) {
    return "Current route destination anchor.";
  }
  return "Intermediate route checkpoint preserved in the active scenario.";
}

function coordinateForRouteIndex(index: number, routeLength: number): Pick<RouteStop, "x" | "y"> {
  if (routeLength <= 1) {
    return { x: 50, y: 50 };
  }

  const progress = index / (routeLength - 1);
  const wave = index % 2 === 0 ? -1 : 1;
  return {
    x: 12 + progress * 76,
    y: 52 + wave * 18,
  };
}

function coordinateForMarker(index: number, total: number): { x: number; y: number } {
  if (total <= 0) {
    return { x: 50, y: 50 };
  }

  const progress = (index + 1) / (total + 1);
  return {
    x: 18 + progress * 64,
    y: index % 2 === 0 ? 28 : 74,
  };
}

function markerKindsForBundle(bundle: InventoryBundle): MapMarkerKind[] {
  const context = bundle.bundle_context.toLowerCase();
  const kinds: MapMarkerKind[] = [];
  if (context.includes("lodging")) {
    kinds.push("lodging");
  }
  if (context.includes("activity")) {
    kinds.push("activity");
  }
  if (context.includes("transport") || context.includes("route")) {
    kinds.push("transport");
  }
  if (kinds.length === 0) {
    kinds.push("activity");
  }
  return Array.from(new Set(kinds));
}

function deriveRouteWarning(activeScenario: TripMapScenario, feasibilitySummary: FeasibilitySummary): string | null {
  if (!activeScenario.feasible) {
    return "This scenario is flagged as not feasible by upstream route analysis.";
  }
  if (feasibilitySummary.blocking_bundle_count > 0) {
    return `${feasibilitySummary.blocking_bundle_count} inventory bundle(s) carry blocking feasibility signals.`;
  }
  if (feasibilitySummary.attention_bundle_count > 0) {
    return `${feasibilitySummary.attention_bundle_count} inventory bundle(s) need route attention.`;
  }
  if (activeScenario.metrics.transfers >= 6) {
    return "High transfer count; review travel burden before selecting this scenario.";
  }
  return null;
}

function normalizeLabel(value: string): string {
  const trimmed = value.trim();
  if (trimmed === "") {
    return "";
  }
  if (trimmed.includes("-") || trimmed.includes("_")) {
    return humanizeStop(trimmed);
  }
  return trimmed;
}

function buildDestinationContext({
  bundles,
  routeStops,
  tripPrimaryRegions,
}: {
  bundles: InventoryBundle[];
  routeStops: RouteStop[];
  tripPrimaryRegions: string[];
}): string[] {
  const fromBundles = bundles.flatMap((bundle) => bundle.destination_names).map(normalizeLabel).filter(Boolean);
  const fromRoute = routeStops.map((stop) => stop.label.trim()).filter(Boolean);
  const fromTripFrame = tripPrimaryRegions.map(normalizeLabel).filter(Boolean);
  return Array.from(new Set([...fromRoute, ...fromBundles, ...fromTripFrame]));
}

function buildRouteStops(activeScenario: TripMapScenario): RouteStop[] {
  const providerMarkers = activeScenario.map_view?.place_markers ?? [];
  if (providerMarkers.length > 0) {
    return providerMarkers.map((marker, index) => ({
      id: marker.id,
      sourceId: marker.source_id,
      label: marker.label,
      description: marker.description ?? describeStop(index, providerMarkers.length),
      sourceRefs: marker.source_refs ?? [],
      x: marker.x * 100,
      y: marker.y * 100,
      latitude: marker.latitude,
      longitude: marker.longitude,
    }));
  }

  return activeScenario.route_sequence.map((stop, index) => {
    const coordinate = coordinateForRouteIndex(index, activeScenario.route_sequence.length);
    return {
      id: `${activeScenario.scenario_id}-${stop}-${index}`,
      sourceId: stop,
      label: humanizeStop(stop),
      description: describeStop(index, activeScenario.route_sequence.length),
      sourceRefs: [],
      x: coordinate.x,
      y: coordinate.y,
    };
  });
}

function buildRouteSegments(
  activeScenario: TripMapScenario,
  routeStops: RouteStop[],
  routeWarning: string | null
): RouteSegment[] {
  const providerSegments = activeScenario.map_view?.rough_route_geometry ?? [];
  if (providerSegments.length > 0) {
    const stopById = new Map(routeStops.map((stop) => [stop.id, stop]));
    return providerSegments
      .filter(
        (segment) => stopById.has(segment.from_marker_id) && stopById.has(segment.to_marker_id)
      )
      .map((segment) => ({
        id: segment.id,
        fromStopId: segment.from_marker_id,
        toStopId: segment.to_marker_id,
        fromLabel: segment.from_label,
        toLabel: segment.to_label,
        x1: segment.x1 * 100,
        y1: segment.y1 * 100,
        x2: segment.x2 * 100,
        y2: segment.y2 * 100,
        warning: segment.warning ?? routeWarning,
        durationMinutes: segment.duration_minutes ?? null,
        distanceKm: segment.distance_km ?? null,
        confidence: segment.confidence ?? activeScenario.map_view?.confidence.level ?? "medium",
        unavailableReason: segment.unavailable_reason ?? null,
        focusCues: [],
      }));
  }

  return routeStops.slice(0, -1).map((stop, index) => {
    const nextStop = routeStops[index + 1];
    const fallbackMinutes =
      routeStops.length > 1
        ? Math.max(0, Math.round(activeScenario.metrics.travel_minutes / (routeStops.length - 1)))
        : null;
    return {
      id: `${stop.id}-${nextStop.id}`,
      fromStopId: stop.id,
      toStopId: nextStop.id,
      fromLabel: stop.label,
      toLabel: nextStop.label,
      x1: stop.x,
      y1: stop.y,
      x2: nextStop.x,
      y2: nextStop.y,
      warning: index === 0 ? routeWarning : null,
      durationMinutes: fallbackMinutes,
      distanceKm: null,
      confidence: activeScenario.feasible ? "medium" : "low",
      unavailableReason:
        "Provider distance is not available; duration is estimated from ranked scenario timing.",
      focusCues: [],
    };
  });
}

function buildMarkers({
  activeScenario,
  bundles,
  routeStops,
  routeWarning,
  policyPosture,
}: {
  activeScenario: TripMapScenario;
  bundles: InventoryBundle[];
  routeStops: RouteStop[];
  routeWarning: string | null;
  policyPosture: string | null;
}): MapMarker[] {
  const stopMarkers = routeStops.map((stop, index) => ({
    id: `${stop.id}-marker`,
    sourceId: stop.sourceId,
    kind: "stop" as const,
    label: stop.label,
    summary: index === 0 ? "Route origin" : index === routeStops.length - 1 ? "Route destination" : "Route stop",
    detail: stop.description,
    x: stop.x,
    y: stop.y,
    latitude: stop.latitude,
    longitude: stop.longitude,
    emphasized: index === 0 || index === routeStops.length - 1,
    focusCues: [],
  }));
  const bundleMarkers = bundles.flatMap((bundle, index) => {
    const coordinate = coordinateForMarker(index, bundles.length);
    const markerKinds = markerKindsForBundle(bundle);
    const destinations = bundle.destination_names.filter(Boolean).join(", ") || "No destination anchors";
    return markerKinds.map((kind, markerIndex) => ({
      id: `bundle-${bundle.bundle_id}-${kind}`,
      sourceId: bundle.bundle_id,
      kind,
      label: bundle.title,
      summary: `${bundle.option_count} option(s) anchored to ${destinations}`,
      detail: bundle.summary,
      x: coordinate.x + markerIndex * 3,
      y: coordinate.y + markerIndex * 3,
      emphasized: activeScenario.recommended_for_selection && index === 0 && markerIndex === 0,
      focusCues: [],
    }));
  });
  const policyMarker =
    routeWarning == null
      ? []
      : [
          {
            id: `${activeScenario.scenario_id}-policy-warning`,
            sourceId: activeScenario.scenario_id,
            kind: "policy" as const,
            label: "Route burden warning",
            summary: routeWarning,
            detail: [
              activeScenario.comparison_note,
              policyPosture ? `Approval posture: ${policyPosture}.` : "",
            ]
              .filter(Boolean)
              .join(" "),
            x: 82,
            y: 18,
            emphasized: true,
            focusCues: [],
          },
        ];

  return [...stopMarkers, ...bundleMarkers, ...policyMarker];
}

function buildScenarioAffordances({
  activeScenario,
  routeState,
  routeWarning,
  policyPosture,
}: {
  activeScenario: TripMapScenario;
  routeState: "ready" | "sparse";
  routeWarning: string | null;
  policyPosture: string | null;
}): string[] {
  const affordances = [
    activeScenario.recommended_for_selection ? "Recommended scenario" : "Alternative scenario",
    activeScenario.feasible ? "Feasibility-ready route" : "Feasibility warning",
    `${activeScenario.option_count} mapped option marker(s)`,
    `${activeScenario.route_sequence.length} route stop(s)`,
  ];
  if (activeScenario.metrics.transfers > 0) {
    affordances.push(`${activeScenario.metrics.transfers} transfer checkpoint(s)`);
  }
  if (routeState === "sparse") {
    affordances.push("Sparse route fallback");
  }
  if (routeWarning) {
    affordances.push(
      policyPosture ? "Approval or feasibility warning active" : "Feasibility warning active"
    );
  }
  return affordances;
}

function scopePresentationFor({
  activeScope,
  selectedSegment,
}: {
  activeScope: MapViewScope;
  selectedSegment: RouteSegment | null;
}): MapScopePresentation {
  if (activeScope === "global") {
    return {
      activeScope,
      label: "Whole-trip outline",
      summary: "Shows the broad shape of the trip so the main anchors stay visible.",
      precisionLabel: "Approximate trip outline",
    };
  }

  if (activeScope === "local") {
    return {
      activeScope,
      label: selectedSegment
        ? `${selectedSegment.fromLabel} to ${selectedSegment.toLabel}`
        : "Local segment",
      summary: selectedSegment
        ? `Focuses on the ${selectedSegment.fromLabel} to ${selectedSegment.toLabel} travel leg, timing estimate, and nearby planning markers.`
        : "Add another route stop before the map can focus on a local segment.",
      precisionLabel: selectedSegment ? "Segment-level planning view" : "Segment detail pending",
    };
  }

  return {
    activeScope,
    label: "Selected route option",
    summary: "Shows the selected route option across its regional travel legs and comparison context.",
    precisionLabel: "Regional route review",
  };
}

function visibleMapContentFor({
  activeScope,
  routeStops,
  routeSegments,
  markers,
  selectedSegmentId,
}: {
  activeScope: MapViewScope;
  routeStops: RouteStop[];
  routeSegments: RouteSegment[];
  markers: MapMarker[];
  selectedSegmentId: string | null | undefined;
}): {
  routeStops: RouteStop[];
  routeSegments: RouteSegment[];
  markers: MapMarker[];
  selectedSegment: RouteSegment | null;
} {
  if (activeScope !== "local" || routeSegments.length === 0) {
    return {
      routeStops,
      routeSegments,
      markers,
      selectedSegment: selectedSegmentId
        ? routeSegments.find((segment) => segment.id === selectedSegmentId) ?? routeSegments[0] ?? null
        : routeSegments[0] ?? null,
    };
  }

  const selectedSegment =
    routeSegments.find((segment) => segment.id === selectedSegmentId) ?? routeSegments[0];
  const visibleStopIds = new Set([selectedSegment.fromStopId, selectedSegment.toStopId]);
  const visibleStops = routeStops.filter((stop) => visibleStopIds.has(stop.id));
  const visibleStopMarkerIds = new Set(visibleStops.map((stop) => `${stop.id}-marker`));

  return {
    routeStops: visibleStops.length > 0 ? visibleStops : routeStops,
    routeSegments: [selectedSegment],
    markers: markers.filter((marker) => marker.kind !== "stop" || visibleStopMarkerIds.has(marker.id)),
    selectedSegment,
  };
}

function normalizedRef(value: unknown): string {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

function normalizeRefList(values: unknown): string[] {
  if (typeof values === "string") {
    return [values];
  }
  if (Array.isArray(values)) {
    return values.filter((value): value is string => typeof value === "string");
  }
  return [];
}

function entryMapRefs(entry: PlanningLedgerEntry): string[] {
  const metadata = entry.metadata ?? {};
  const refs = [
    entry.related_option_id,
    entry.related_decision_id,
    ...entry.source_refs,
    ...entry.source_message_ids,
    metadata["map_marker_id"],
    metadata["marker_id"],
    metadata["map_marker_ids"],
    metadata["marker_ids"],
    metadata["route_segment_id"],
    metadata["map_segment_id"],
    metadata["selected_segment_id"],
    metadata["route_segment_ids"],
    metadata["map_segment_ids"],
    metadata["route_option_id"],
    metadata["scenario_id"],
    metadata["bundle_id"],
    metadata["destination"],
    metadata["destination_id"],
    metadata["place_id"],
  ];
  return Array.from(
    new Set(refs.flatMap(normalizeRefList).map((ref) => ref.trim()).filter(Boolean))
  );
}

function labelForLedgerEntry(entry: PlanningLedgerEntry): string {
  switch (entry.item_type) {
    case "option_rejected":
      return "Rejected option";
    case "option_considered":
      return "Route option";
    case "decision":
      return "Decision";
    case "assumption":
      return "Assumption";
    case "constraint":
      return "Constraint";
    case "open_question":
      return "Open question";
    case "source_reference":
      return "Source";
    default:
      return "Planning note";
  }
}

function buildMapFocusCues({
  activeScenario,
  markers,
  routeSegments,
  planningLedger,
}: {
  activeScenario: TripMapScenario;
  markers: MapMarker[];
  routeSegments: RouteSegment[];
  planningLedger?: PlanningLedgerState | null;
}): MapFocusCue[] {
  const entries = planningLedger?.entries ?? [];
  if (entries.length === 0) {
    return [];
  }

  const routeIds = new Set(
    [activeScenario.scenario_id, activeScenario.route_option_id].filter(
      (value): value is string => Boolean(value)
    )
  );
  const markerById = new Map(markers.map((marker) => [marker.id, marker]));
  const markerBySourceId = new Map(markers.map((marker) => [marker.sourceId, marker]));
  const markerByLabel = new Map(markers.map((marker) => [normalizedRef(marker.label), marker]));
  const segmentById = new Map(routeSegments.map((segment) => [segment.id, segment]));
  const cues: MapFocusCue[] = [];
  const seen = new Set<string>();

  for (const entry of entries) {
    if (entry.status === "superseded") {
      continue;
    }
    const summary = entry.summary.trim();
    if (summary === "") {
      continue;
    }

    const refs = entryMapRefs(entry);
    let target:
      | { targetKind: "marker"; targetId: string; markerId: string; segmentId: null }
      | { targetKind: "segment"; targetId: string; markerId: null; segmentId: string }
      | { targetKind: "route"; targetId: string; markerId: null; segmentId: null }
      | null = null;

    for (const ref of refs) {
      const marker =
        markerById.get(ref) ??
        markerBySourceId.get(ref) ??
        markerByLabel.get(normalizedRef(ref));
      if (marker) {
        target = {
          targetKind: "marker",
          targetId: marker.id,
          markerId: marker.id,
          segmentId: null,
        };
        break;
      }
    }

    if (target == null) {
      for (const ref of refs) {
        const segment = segmentById.get(ref);
        if (segment) {
          target = {
            targetKind: "segment",
            targetId: segment.id,
            markerId: null,
            segmentId: segment.id,
          };
          break;
        }
      }
    }

    if (target == null) {
      for (const ref of refs) {
        if (routeIds.has(ref)) {
          target = {
            targetKind: "route",
            targetId: ref,
            markerId: null,
            segmentId: null,
          };
          break;
        }
      }
    }

    if (target == null) {
      continue;
    }

    const key = `${entry.ledger_entry_id}:${target.targetKind}:${target.targetId}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    cues.push({
      ledgerEntryId: entry.ledger_entry_id,
      label: labelForLedgerEntry(entry),
      summary,
      status: entry.status,
      itemType: entry.item_type,
      ...target,
    });
  }

  return cues.slice(0, 8);
}

function attachFocusCues({
  markers,
  routeSegments,
  focusCues,
}: {
  markers: MapMarker[];
  routeSegments: RouteSegment[];
  focusCues: MapFocusCue[];
}): { markers: MapMarker[]; routeSegments: RouteSegment[] } {
  const cuesByMarkerId = new Map<string, MapFocusCue[]>();
  const cuesBySegmentId = new Map<string, MapFocusCue[]>();
  for (const cue of focusCues) {
    if (cue.markerId) {
      cuesByMarkerId.set(cue.markerId, [...(cuesByMarkerId.get(cue.markerId) ?? []), cue]);
    }
    if (cue.segmentId) {
      cuesBySegmentId.set(cue.segmentId, [...(cuesBySegmentId.get(cue.segmentId) ?? []), cue]);
    }
  }

  return {
    markers: markers.map((marker) => {
      const markerFocusCues = cuesByMarkerId.get(marker.id) ?? [];
      return {
        ...marker,
        emphasized: marker.emphasized || markerFocusCues.length > 0,
        focusCues: markerFocusCues,
      };
    }),
    routeSegments: routeSegments.map((segment) => ({
      ...segment,
      focusCues: cuesBySegmentId.get(segment.id) ?? [],
    })),
  };
}

function visibleFocusCuesFor({
  focusCues,
  visibleMarkers,
  visibleRouteSegments,
}: {
  focusCues: MapFocusCue[];
  visibleMarkers: MapMarker[];
  visibleRouteSegments: RouteSegment[];
}): MapFocusCue[] {
  const visibleMarkerIds = new Set(visibleMarkers.map((marker) => marker.id));
  const visibleSegmentIds = new Set(visibleRouteSegments.map((segment) => segment.id));
  return focusCues.filter((cue) => {
    if (cue.targetKind === "route") {
      return true;
    }
    if (cue.markerId) {
      return visibleMarkerIds.has(cue.markerId);
    }
    if (cue.segmentId) {
      return visibleSegmentIds.has(cue.segmentId);
    }
    return false;
  });
}

function deriveMapConfidence({
  routeState,
  provider,
}: {
  routeState: "ready" | "sparse";
  provider: MapSurfaceProvider;
}): MapWorkspaceView["confidence"] {
  if (routeState === "sparse") {
    return {
      level: "low",
      summary: "Low confidence: the route needs more stops before the map can show its shape.",
    };
  }
  if (provider.kind === "fallback") {
    return {
      level: "medium",
      summary: "Medium confidence: this is an approximate sketch from the current route stops.",
    };
  }
  return {
    level: "high",
    summary: "High confidence: the route has enough map detail for close review.",
  };
}

export function buildTripMapSurfaceModel({
  activeScenario,
  bundles,
  feasibilitySummary,
  scenarioComparisonSummary,
  scenarioFocusAreas,
  tripPrimaryRegions = [],
  tripMode = null,
  policyPosture = null,
  googleMapsApiKey,
  providerLoadState = "ready",
  activeScope = "regional",
  selectedSegmentId,
  planningLedger,
}: {
  activeScenario: TripMapScenario;
  bundles: InventoryBundle[];
  feasibilitySummary: FeasibilitySummary;
  scenarioComparisonSummary?: string | null;
  scenarioFocusAreas?: string[];
  tripPrimaryRegions?: string[];
  tripMode?: string | null;
  policyPosture?: string | null;
  googleMapsApiKey?: string | null;
  providerLoadState?: MapProviderLoadState;
  activeScope?: MapViewScope;
  selectedSegmentId?: string | null;
  planningLedger?: PlanningLedgerState | null;
}): TripMapSurfaceModel {
  const routeStops = buildRouteStops(activeScenario);
  const destinationContext = buildDestinationContext({
    bundles,
    routeStops,
    tripPrimaryRegions,
  });
  const destinationAnchors = Array.from(
    new Set(
      bundles
        .flatMap((bundle) => bundle.destination_names)
        .map((destination) => normalizeLabel(destination))
        .filter(Boolean)
    )
  );
  const trimmedApiKey = googleMapsApiKey?.trim() ?? "";
  const routeWarning = deriveRouteWarning(activeScenario, feasibilitySummary);
  const resolvedPolicyPosture = tripMode === "leisure" ? null : policyPosture;
  const routeSegments = buildRouteSegments(activeScenario, routeStops, routeWarning);
  const baseMarkers = buildMarkers({
    activeScenario,
    bundles,
    routeStops,
    routeWarning,
    policyPosture: resolvedPolicyPosture,
  });
  const focusCues = buildMapFocusCues({
    activeScenario,
    markers: baseMarkers,
    routeSegments,
    planningLedger,
  });
  const focusedMapContent = attachFocusCues({
    markers: baseMarkers,
    routeSegments,
    focusCues,
  });
  const markers = focusedMapContent.markers;
  const focusedRouteSegments = focusedMapContent.routeSegments;
  const routeState = routeStops.length >= 2 ? "ready" : "sparse";
  const scenarioAffordances = buildScenarioAffordances({
    activeScenario,
    routeState,
    routeWarning,
    policyPosture: resolvedPolicyPosture,
  });
  let provider: MapSurfaceProvider;

  if (routeState === "sparse") {
    provider = {
      kind: "fallback",
      label: "Sparse route fallback",
      status: "sparse-route",
      summary:
        "The route needs at least an origin and destination before the provider-backed map can render route geometry.",
    };
  } else if (trimmedApiKey === "") {
    provider = {
      kind: "fallback",
      label: "Provider misconfigured",
      status: "misconfigured",
      summary:
        "Google Maps JavaScript is not configured in this environment, so the workspace is showing the bounded textual route fallback.",
    };
  } else if (providerLoadState === "error") {
    provider = {
      kind: "fallback",
      label: "Provider error fallback",
      status: "provider-error",
      summary:
        "Google Maps JavaScript failed to load, so the workspace kept the route context available in fallback mode.",
    };
  } else if (providerLoadState === "loading") {
    provider = {
      kind: "fallback",
      label: "Provider loading",
      status: "loading",
      summary:
        "Google Maps JavaScript is loading; the workspace keeps route context visible until the adapter is ready.",
    };
  } else {
    provider = {
      kind: "google-maps-js",
      label: "Google Maps configured",
      status: "configured",
      apiKey: trimmedApiKey,
      summary:
        "Google Maps JavaScript is configured and will be marked live only after the SDK and trip locations load successfully.",
    };
  }
  const visibleMapContent = visibleMapContentFor({
    activeScope,
    routeStops,
    routeSegments: focusedRouteSegments,
    markers,
    selectedSegmentId,
  });
  const visibleFocusCues = visibleFocusCuesFor({
    focusCues,
    visibleMarkers: visibleMapContent.markers,
    visibleRouteSegments: visibleMapContent.routeSegments,
  });
  const scope = scopePresentationFor({
    activeScope,
    selectedSegment: visibleMapContent.selectedSegment,
  });
  const workspaceView: MapWorkspaceView = {
    activeScope,
    activeRouteOptionId: activeScenario.route_option_id ?? activeScenario.scenario_id,
    selectedSegmentId: visibleMapContent.selectedSegment?.id ?? null,
    placeMarkers: visibleMapContent.markers,
    roughRouteGeometry: visibleMapContent.routeSegments,
    focusCues: visibleFocusCues,
    confidence: deriveMapConfidence({ routeState, provider }),
    diagnostics: {
      provider,
      routeState,
      routeWarning,
    },
  };

  return {
    provider,
    routeStops,
    routeSegments: focusedRouteSegments,
    markers,
    visibleRouteStops: visibleMapContent.routeStops,
    visibleRouteSegments: visibleMapContent.routeSegments,
    visibleMarkers: visibleMapContent.markers,
    focusCues,
    visibleFocusCues,
    destinationAnchors,
    destinationContext,
    scenarioFocusAreas: scenarioFocusAreas?.filter(Boolean) ?? [],
    scenarioComparisonSummary:
      scenarioComparisonSummary?.trim() ||
      "Scenario comparison summary is still syncing to this workspace review surface.",
    scenarioAffordances,
    policyPosture: resolvedPolicyPosture,
    feasibilitySummary: summarizeFeasibility(feasibilitySummary, destinationAnchors),
    routeState,
    routeWarning,
    scope,
    scopeOptions: MAP_SCOPE_OPTIONS,
    workspaceView,
  };
}
