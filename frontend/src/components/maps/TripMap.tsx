import type { FeasibilitySummary, RuntimeScenarioComparison, WorkspaceData } from "../../api/workspace";
import { useEffect, useMemo, useState } from "react";
import {
  buildTripMapSurfaceModel,
  formatEstimatedTotal,
  type MapMarker,
  type MapProviderLoadState,
} from "./mapSurface";

type InventoryBundle = WorkspaceData["inventory_summary"]["bundles"][number];
type TripMapScenario = RuntimeScenarioComparison["scenarios"][number];

export function TripMap({
  comparison,
  activeScenarioId,
  onSelectScenario,
  bundles,
  feasibilitySummary,
  compactLayout,
}: {
  comparison: RuntimeScenarioComparison;
  activeScenarioId: string | null;
  onSelectScenario: (scenarioId: string) => void;
  bundles: InventoryBundle[];
  feasibilitySummary: FeasibilitySummary;
  compactLayout: boolean;
}) {
  const activeScenario =
    comparison.scenarios.find((scenario) => scenario.scenario_id === activeScenarioId) ??
    comparison.scenarios[0] ??
    null;
  if (activeScenario == null) {
    return (
      <section className="status-card map-card">
        <p className="status-label">Map surface</p>
        <h2>Route context is not ready</h2>
        <p className="muted-copy">
          The workspace needs ranked scenario output before it can render a route-aware map
          preview.
        </p>
      </section>
    );
  }

  return (
    <ActiveTripMap
      activeScenario={activeScenario}
      comparison={comparison}
      onSelectScenario={onSelectScenario}
      bundles={bundles}
      feasibilitySummary={feasibilitySummary}
      compactLayout={compactLayout}
    />
  );
}

function ActiveTripMap({
  activeScenario,
  comparison,
  onSelectScenario,
  bundles,
  feasibilitySummary,
  compactLayout,
}: {
  activeScenario: TripMapScenario;
  comparison: RuntimeScenarioComparison;
  onSelectScenario: (scenarioId: string) => void;
  bundles: InventoryBundle[];
  feasibilitySummary: FeasibilitySummary;
  compactLayout: boolean;
}) {
  const providerLoadState =
    (import.meta.env.VITE_GOOGLE_MAPS_PROVIDER_STATE as MapProviderLoadState | undefined) ?? "ready";
  const mapSurface = buildTripMapSurfaceModel({
    activeScenario,
    bundles,
    feasibilitySummary,
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_BROWSER_API_KEY,
    providerLoadState,
  });
  const initialMarkerId = mapSurface.markers[0]?.id ?? null;
  const [selectedMarkerId, setSelectedMarkerId] = useState<string | null>(initialMarkerId);
  const selectedMarker = useMemo(
    () =>
      mapSurface.markers.find((marker) => marker.id === selectedMarkerId) ??
      mapSurface.markers[0] ??
      null,
    [mapSurface.markers, selectedMarkerId]
  );

  useEffect(() => {
    setSelectedMarkerId(initialMarkerId);
  }, [activeScenario.scenario_id, initialMarkerId]);

  return (
    <section className="status-card map-card">
      <p className="status-label">Map surface</p>
      <h2>Map preview for {activeScenario.title}</h2>
      <p>{activeScenario.summary}</p>
      <div className="map-provider-banner" aria-label="Map provider status">
        <span className={`map-provider-pill map-provider-pill-${mapSurface.provider.status}`}>
          {mapSurface.provider.label}
        </span>
        <p className="muted-copy">
          {compactLayout ? "Compact" : "Full"} review keeps the provider state and fallback path
          visible before the traveler studies the route.
        </p>
      </div>
      <p className="muted-copy">{mapSurface.provider.summary}</p>
      <div className="map-scenario-toggle" aria-label="Map scenario previews">
        {comparison.scenarios.map((scenario) => (
          <button
            key={scenario.scenario_id}
            type="button"
            className={`map-toggle-chip${
              scenario.scenario_id === activeScenario.scenario_id ? " map-toggle-chip-active" : ""
            }`}
            aria-pressed={scenario.scenario_id === activeScenario.scenario_id}
            onClick={() => onSelectScenario(scenario.scenario_id)}
          >
            {scenario.rank}. {scenario.title}
          </button>
        ))}
      </div>
      <div className="map-surface" aria-label="Route context map">
        <div
          className={`map-route map-route-${mapSurface.provider.kind}`}
          aria-label={`${mapSurface.provider.label} route overlay`}
        >
          <div className="map-provider-toolbar">
            <span className="map-provider-name">{mapSurface.provider.label}</span>
            <span>{mapSurface.routeSegments.length} segment(s)</span>
            <span>{mapSurface.markers.length} marker(s)</span>
          </div>
          {mapSurface.provider.kind === "google-maps-js" ? (
            <InteractiveProviderMap
              title={activeScenario.title}
              markers={mapSurface.markers}
              selectedMarker={selectedMarker}
              routeSegments={mapSurface.routeSegments}
              onSelectMarker={setSelectedMarkerId}
            />
          ) : (
            <FallbackRouteSchematic
              markers={mapSurface.markers}
              selectedMarker={selectedMarker}
              routeStops={mapSurface.routeStops}
              onSelectMarker={setSelectedMarkerId}
            />
          )}
          {mapSurface.routeWarning ? (
            <p className="map-warning" role="status">
              {mapSurface.routeWarning}
            </p>
          ) : null}
        </div>
        <div className="map-sidebar">
          <article className="decision-card">
            <h3>{mapSurface.provider.kind === "google-maps-js" ? "Live provider path" : "Fallback route path"}</h3>
            <p>{mapSurface.provider.summary}</p>
          </article>
          {selectedMarker ? (
            <article className="decision-card map-marker-detail" aria-live="polite">
              <p className="scenario-kicker">{selectedMarker.kind}</p>
              <h3>{selectedMarker.label}</h3>
              <p>{selectedMarker.summary}</p>
              <p className="muted-copy">{selectedMarker.detail}</p>
            </article>
          ) : null}
          <dl className="workspace-meta map-metrics">
            <div>
              <dt>Travel minutes</dt>
              <dd>{activeScenario.metrics.travel_minutes}</dd>
            </div>
            <div>
              <dt>Transfers</dt>
              <dd>{activeScenario.metrics.transfers}</dd>
            </div>
            <div>
              <dt>Options</dt>
              <dd>{activeScenario.option_count}</dd>
            </div>
            <div>
              <dt>Estimated total</dt>
              <dd>{formatEstimatedTotal(activeScenario.metrics.estimated_total)}</dd>
            </div>
          </dl>
          <article className="decision-card">
            <h3>Route summary</h3>
            <p>{activeScenario.route_summary}</p>
            <p className="muted-copy">{activeScenario.comparison_note}</p>
          </article>
          <article className="decision-card">
            <h3>Destination anchors</h3>
            <p>{mapSurface.feasibilitySummary}</p>
            <div className="map-anchor-list">
              {mapSurface.destinationAnchors.length === 0 ? (
                <span className="map-anchor-chip map-anchor-chip-muted">Awaiting option anchors</span>
              ) : (
                mapSurface.destinationAnchors.map((destination) => (
                  <span key={destination} className="map-anchor-chip">
                    {destination}
                  </span>
                ))
              )}
            </div>
          </article>
          <article className="decision-card">
            <h3>Scenario highlights</h3>
            <ul className="map-highlight-list">
              {activeScenario.highlights.slice(0, 3).map((highlight) => (
                <li key={highlight}>{highlight}</li>
              ))}
            </ul>
          </article>
          <article className="decision-card">
            <h3>Scenario review rail</h3>
            <div className="map-scenario-rail" aria-label="Map scenario review rail">
              {comparison.scenarios.map((scenario) => (
                <div
                  key={scenario.scenario_id}
                  className={`map-scenario-rail-card${
                    scenario.scenario_id === activeScenario.scenario_id
                      ? " map-scenario-rail-card-active"
                      : ""
                  }`}
                >
                  <p className="scenario-kicker">
                    {scenario.recommended_for_selection ? "recommended" : scenario.status}
                  </p>
                  <h4>{scenario.title}</h4>
                  <p>{scenario.metrics.travel_minutes} min · {scenario.metrics.transfers} transfers</p>
                </div>
              ))}
            </div>
          </article>
        </div>
      </div>
    </section>
  );
}

function InteractiveProviderMap({
  title,
  markers,
  selectedMarker,
  routeSegments,
  onSelectMarker,
}: {
  title: string;
  markers: MapMarker[];
  selectedMarker: MapMarker | null;
  routeSegments: ReturnType<typeof buildTripMapSurfaceModel>["routeSegments"];
  onSelectMarker: (markerId: string) => void;
}) {
  return (
    <div className="map-provider-canvas" role="group" aria-label={`Interactive map for ${title}`}>
      <svg className="map-route-geometry" viewBox="0 0 100 100" aria-hidden="true">
        {routeSegments.map((segment) => (
          <line
            key={segment.id}
            x1={segment.x1}
            y1={segment.y1}
            x2={segment.x2}
            y2={segment.y2}
            className={segment.warning ? "map-route-line map-route-line-warning" : "map-route-line"}
          />
        ))}
      </svg>
      {markers.map((marker) => (
        <button
          key={marker.id}
          type="button"
          className={`map-marker map-marker-${marker.kind}${
            selectedMarker?.id === marker.id ? " map-marker-selected" : ""
          }${marker.emphasized ? " map-marker-emphasized" : ""}`}
          style={{ left: `${marker.x}%`, top: `${marker.y}%` }}
          aria-label={markerAccessibleLabel(marker)}
          aria-pressed={selectedMarker?.id === marker.id}
          onClick={() => onSelectMarker(marker.id)}
        >
          <span>{markerLabel(marker.kind)}</span>
        </button>
      ))}
    </div>
  );
}

function FallbackRouteSchematic({
  markers,
  selectedMarker,
  routeStops,
  onSelectMarker,
}: {
  markers: MapMarker[];
  selectedMarker: MapMarker | null;
  routeStops: ReturnType<typeof buildTripMapSurfaceModel>["routeStops"];
  onSelectMarker: (markerId: string) => void;
}) {
  const stopMarkerIds = new Set(routeStops.map((stop) => `${stop.id}-marker`));
  const optionMarkers = markers.filter((marker) => !stopMarkerIds.has(marker.id));

  return (
    <>
      <div className="map-fallback-route">
        {routeStops.map((stop, index) => {
          const markerId = `${stop.id}-marker`;
          return (
            <button
              key={stop.id}
              type="button"
              className={`map-stop${selectedMarker?.id === markerId ? " map-stop-selected" : ""}`}
              aria-pressed={selectedMarker?.id === markerId}
              onClick={() => onSelectMarker(markerId)}
            >
              <span className="map-stop-marker">{index + 1}</span>
              <span className="map-stop-copy">
                <strong>{stop.label}</strong>
                <span>{stop.description}</span>
              </span>
            </button>
          );
        })}
      </div>
      <div className="map-option-marker-list" aria-label="Fallback option markers">
        {optionMarkers.map((marker) => (
          <button
            key={marker.id}
            type="button"
            className={`map-option-marker map-option-marker-${marker.kind}${
              selectedMarker?.id === marker.id ? " map-option-marker-selected" : ""
            }`}
            aria-pressed={selectedMarker?.id === marker.id}
            onClick={() => onSelectMarker(marker.id)}
          >
            <span>{markerLabel(marker.kind)}</span>
            {marker.label}
          </button>
        ))}
      </div>
    </>
  );
}

function markerAccessibleLabel(marker: MapMarker): string {
  return `${marker.kind} marker: ${marker.label}. ${marker.summary}`;
}

function markerLabel(kind: MapMarker["kind"]): string {
  switch (kind) {
    case "lodging":
      return "L";
    case "activity":
      return "A";
    case "transport":
      return "T";
    case "policy":
      return "!";
    case "stop":
    default:
      return "S";
  }
}
