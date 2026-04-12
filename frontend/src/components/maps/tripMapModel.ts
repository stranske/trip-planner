import type {
  FeasibilitySummary,
  RuntimeScenarioComparison,
  WorkspaceData,
} from "../../api/workspace";

type TripMapScenario = RuntimeScenarioComparison["scenarios"][number];
type InventoryBundle = WorkspaceData["inventory_summary"]["bundles"][number];

export type TripMapProvider = "google-maps" | "fallback";

export type TripMapStop = {
  label: string;
  detail: string;
  query: string;
};

export type TripMapViewModel = {
  activeScenario: TripMapScenario;
  stops: TripMapStop[];
  destinationAnchors: string[];
  feasibilityNote: string;
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

function summarizeFeasibility(
  feasibilitySummary: FeasibilitySummary,
  bundleDestinations: string[],
): string {
  if (feasibilitySummary.assessment_count === 0) {
    return "No inventory bundles have produced route-feasibility signals yet.";
  }

  if (bundleDestinations.length === 0) {
    return `${feasibilitySummary.assessment_count} bundle checks are available, but destination anchors have not been attached yet.`;
  }

  return `${bundleDestinations.length} destination anchors are backed by ${feasibilitySummary.assessment_count} feasibility assessment(s).`;
}

export function buildTripMapViewModel({
  comparison,
  activeScenarioId,
  bundles,
  feasibilitySummary,
}: {
  comparison: RuntimeScenarioComparison;
  activeScenarioId: string | null;
  bundles: InventoryBundle[];
  feasibilitySummary: FeasibilitySummary;
}): TripMapViewModel | null {
  const activeScenario =
    comparison.scenarios.find((scenario) => scenario.scenario_id === activeScenarioId) ??
    comparison.scenarios[0] ??
    null;

  if (activeScenario == null) {
    return null;
  }

  const destinationAnchors = Array.from(
    new Set(
      bundles
        .flatMap((bundle) => bundle.destination_names)
        .map((destination) => destination.trim())
        .filter(Boolean),
    ),
  );

  const stops = activeScenario.route_sequence.map((stop, index) => {
    const label = humanizeStop(stop);
    let detail = "Intermediate route checkpoint preserved in the active scenario.";
    if (index === 0) {
      detail = "Current route origin for the workspace preview.";
    } else if (index === activeScenario.route_sequence.length - 1) {
      detail = "Current route destination anchor.";
    }

    return {
      label,
      detail,
      query: label,
    };
  });

  return {
    activeScenario,
    stops,
    destinationAnchors,
    feasibilityNote: summarizeFeasibility(feasibilitySummary, destinationAnchors),
  };
}

export function resolveTripMapProvider({
  googleMapsApiKey,
  preferredProvider,
}: {
  googleMapsApiKey?: string | null;
  preferredProvider?: string | null;
}): TripMapProvider {
  if (preferredProvider === "fallback") {
    return "fallback";
  }

  if ((preferredProvider === "google-maps" || preferredProvider == null) && googleMapsApiKey) {
    return "google-maps";
  }

  return "fallback";
}

export function buildGoogleMapsEmbedUrl({
  apiKey,
  model,
}: {
  apiKey: string;
  model: TripMapViewModel;
}): string | null {
  if (model.stops.length === 0) {
    return null;
  }

  const params = new URLSearchParams({
    key: apiKey,
    origin: model.stops[0].query,
    destination: model.stops[model.stops.length - 1].query,
    mode: "transit",
  });

  const waypointStops = model.stops.slice(1, -1).map((stop) => stop.query);
  if (waypointStops.length > 0) {
    params.set("waypoints", waypointStops.join("|"));
  }

  return `https://www.google.com/maps/embed/v1/directions?${params.toString()}`;
}
