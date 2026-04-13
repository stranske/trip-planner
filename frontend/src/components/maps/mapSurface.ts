import type {
  FeasibilitySummary,
  RuntimeScenarioComparison,
  WorkspaceData,
} from "../../api/workspace";

type TripMapScenario = RuntimeScenarioComparison["scenarios"][number];
type InventoryBundle = WorkspaceData["inventory_summary"]["bundles"][number];

export type MapSurfaceProvider =
  | {
      kind: "google-maps";
      label: "Google Maps";
      status: "live";
      iframeSrc: string;
      summary: string;
    }
  | {
      kind: "fallback";
      label: "Fallback schematic";
      status: "fallback";
      summary: string;
    };

export type RouteStop = {
  id: string;
  label: string;
  description: string;
};

export type TripMapSurfaceModel = {
  provider: MapSurfaceProvider;
  routeStops: RouteStop[];
  destinationAnchors: string[];
  feasibilitySummary: string;
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

export function buildGoogleMapsEmbedUrl(routeLabels: string[], apiKey: string): string {
  const origin = routeLabels[0] ?? "";
  const destination = routeLabels[routeLabels.length - 1] ?? origin;
  const waypointLabels = routeLabels.slice(1, -1);
  const params = new URLSearchParams({
    key: apiKey,
    origin,
    destination,
    mode: "transit",
  });

  if (waypointLabels.length > 0) {
    params.set("waypoints", waypointLabels.join("|"));
  }

  return `https://www.google.com/maps/embed/v1/directions?${params.toString()}`;
}

export function buildTripMapSurfaceModel({
  activeScenario,
  bundles,
  feasibilitySummary,
  googleMapsApiKey,
}: {
  activeScenario: TripMapScenario;
  bundles: InventoryBundle[];
  feasibilitySummary: FeasibilitySummary;
  googleMapsApiKey?: string | null;
}): TripMapSurfaceModel {
  const destinationAnchors = Array.from(
    new Set(
      bundles
        .flatMap((bundle) => bundle.destination_names)
        .map((destination) => destination.trim())
        .filter(Boolean)
    )
  );
  const routeStops = activeScenario.route_sequence.map((stop, index) => ({
    id: `${activeScenario.scenario_id}-${stop}-${index}`,
    label: humanizeStop(stop),
    description: describeStop(index, activeScenario.route_sequence.length),
  }));
  const trimmedApiKey = googleMapsApiKey?.trim() ?? "";
  const routeLabels = routeStops.map((stop) => stop.label);
  const provider =
    trimmedApiKey !== "" && routeLabels.length >= 2
      ? ({
          kind: "google-maps",
          label: "Google Maps",
          status: "live",
          iframeSrc: buildGoogleMapsEmbedUrl(routeLabels, trimmedApiKey),
          summary: "Google Maps is rendering the current route with the workspace fallback kept in reserve.",
        } satisfies MapSurfaceProvider)
      : ({
          kind: "fallback",
          label: "Fallback schematic",
          status: "fallback",
          summary:
            trimmedApiKey === ""
              ? "Google Maps is not configured in this environment, so the workspace is showing the bounded textual route fallback."
              : "The route needs at least an origin and destination before the live provider view can render.",
        } satisfies MapSurfaceProvider);

  return {
    provider,
    routeStops,
    destinationAnchors,
    feasibilitySummary: summarizeFeasibility(feasibilitySummary, destinationAnchors),
  };
}
