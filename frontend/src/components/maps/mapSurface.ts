import type {
  FeasibilitySummary,
  RuntimeScenarioComparison,
  WorkspaceData,
} from "../../api/workspace";

type TripMapScenario = RuntimeScenarioComparison["scenarios"][number];
type InventoryBundle = WorkspaceData["inventory_summary"]["bundles"][number];

export type MapProviderLoadState = "ready" | "loading" | "error";

export type MapSurfaceProvider =
  | {
      kind: "google-maps-js";
      label: "Google Maps JavaScript adapter";
      status: "live";
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
  label: string;
  description: string;
  x: number;
  y: number;
};

export type MapMarkerKind = "stop" | "lodging" | "activity" | "transport" | "policy";

export type MapMarker = {
  id: string;
  kind: MapMarkerKind;
  label: string;
  summary: string;
  detail: string;
  x: number;
  y: number;
  emphasized: boolean;
};

export type RouteSegment = {
  id: string;
  fromLabel: string;
  toLabel: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  warning: string | null;
};

export type TripMapSurfaceModel = {
  provider: MapSurfaceProvider;
  routeStops: RouteStop[];
  routeSegments: RouteSegment[];
  markers: MapMarker[];
  destinationAnchors: string[];
  destinationContext: string[];
  scenarioFocusAreas: string[];
  scenarioComparisonSummary: string;
  scenarioAffordances: string[];
  policyPosture: string;
  feasibilitySummary: string;
  routeState: "ready" | "sparse";
  routeWarning: string | null;
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

function buildRouteSegments(routeStops: RouteStop[], routeWarning: string | null): RouteSegment[] {
  return routeStops.slice(0, -1).map((stop, index) => {
    const nextStop = routeStops[index + 1];
    return {
      id: `${stop.id}-${nextStop.id}`,
      fromLabel: stop.label,
      toLabel: nextStop.label,
      x1: stop.x,
      y1: stop.y,
      x2: nextStop.x,
      y2: nextStop.y,
      warning: index === 0 ? routeWarning : null,
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
  policyPosture: string;
}): MapMarker[] {
  const stopMarkers = routeStops.map((stop, index) => ({
    id: `${stop.id}-marker`,
    kind: "stop" as const,
    label: stop.label,
    summary: index === 0 ? "Route origin" : index === routeStops.length - 1 ? "Route destination" : "Route stop",
    detail: stop.description,
    x: stop.x,
    y: stop.y,
    emphasized: index === 0 || index === routeStops.length - 1,
  }));
  const bundleMarkers = bundles.flatMap((bundle, index) => {
    const coordinate = coordinateForMarker(index, bundles.length);
    const markerKinds = markerKindsForBundle(bundle);
    const destinations = bundle.destination_names.filter(Boolean).join(", ") || "No destination anchors";
    return markerKinds.map((kind, markerIndex) => ({
      id: `bundle-${bundle.bundle_id}-${kind}`,
      kind,
      label: bundle.title,
      summary: `${bundle.option_count} option(s) anchored to ${destinations}`,
      detail: bundle.summary,
      x: coordinate.x + markerIndex * 3,
      y: coordinate.y + markerIndex * 3,
      emphasized: activeScenario.recommended_for_selection && index === 0 && markerIndex === 0,
    }));
  });
  const policyMarker =
    routeWarning == null
      ? []
      : [
          {
            id: `${activeScenario.scenario_id}-policy-warning`,
            kind: "policy" as const,
            label: "Route burden warning",
            summary: routeWarning,
            detail: `${activeScenario.comparison_note} Policy posture: ${policyPosture}.`,
            x: 82,
            y: 18,
            emphasized: true,
          },
        ];

  return [...stopMarkers, ...bundleMarkers, ...policyMarker];
}

function buildScenarioAffordances({
  activeScenario,
  routeState,
  routeWarning,
}: {
  activeScenario: TripMapScenario;
  routeState: "ready" | "sparse";
  routeWarning: string | null;
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
    affordances.push("Policy or feasibility warning active");
  }
  return affordances;
}

export function buildTripMapSurfaceModel({
  activeScenario,
  bundles,
  feasibilitySummary,
  scenarioComparisonSummary,
  scenarioFocusAreas,
  tripPrimaryRegions = [],
  policyPosture = "review pending",
  googleMapsApiKey,
  providerLoadState = "ready",
}: {
  activeScenario: TripMapScenario;
  bundles: InventoryBundle[];
  feasibilitySummary: FeasibilitySummary;
  scenarioComparisonSummary?: string | null;
  scenarioFocusAreas?: string[];
  tripPrimaryRegions?: string[];
  policyPosture?: string;
  googleMapsApiKey?: string | null;
  providerLoadState?: MapProviderLoadState;
}): TripMapSurfaceModel {
  const routeStops = activeScenario.route_sequence.map((stop, index) => {
    const coordinate = coordinateForRouteIndex(index, activeScenario.route_sequence.length);
    return {
      id: `${activeScenario.scenario_id}-${stop}-${index}`,
      label: humanizeStop(stop),
      description: describeStop(index, activeScenario.route_sequence.length),
      x: coordinate.x,
      y: coordinate.y,
    };
  });
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
  const routeSegments = buildRouteSegments(routeStops, routeWarning);
  const markers = buildMarkers({
    activeScenario,
    bundles,
    routeStops,
    routeWarning,
    policyPosture,
  });
  const routeState = routeStops.length >= 2 ? "ready" : "sparse";
  const scenarioAffordances = buildScenarioAffordances({
    activeScenario,
    routeState,
    routeWarning,
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
      label: "Google Maps JavaScript adapter",
      status: "live",
      apiKey: trimmedApiKey,
      summary:
        "Google Maps JavaScript is the active presentation adapter; route, marker, and warning state still comes from workspace runtime data.",
    };
  }

  return {
    provider,
    routeStops,
    routeSegments,
    markers,
    destinationAnchors,
    destinationContext,
    scenarioFocusAreas: scenarioFocusAreas?.filter(Boolean) ?? [],
    scenarioComparisonSummary:
      scenarioComparisonSummary?.trim() ||
      "Scenario comparison summary is still syncing to this workspace review surface.",
    scenarioAffordances,
    policyPosture,
    feasibilitySummary: summarizeFeasibility(feasibilitySummary, destinationAnchors),
    routeState,
    routeWarning,
  };
}
