import type { FeasibilitySummary, RuntimeScenarioComparison, WorkspaceData } from "../../api/workspace";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { importLibrary, setOptions } from "@googlemaps/js-api-loader";
import {
  buildTripMapSurfaceModel,
  formatEstimatedTotal,
  type MapMarker,
  type MapProviderLoadState,
  type MapViewScope,
} from "./mapSurface";

type InventoryBundle = WorkspaceData["inventory_summary"]["bundles"][number];
type TripMapScenario = RuntimeScenarioComparison["scenarios"][number];
const SCHEMATIC_PREVIEW_BADGE_TEXT = "Schematic preview — not a live map";

export function TripMap({
  comparison,
  scenarioComparisonSummary,
  scenarioFocusAreas,
  activeScenarioId,
  onSelectScenario,
  bundles,
  feasibilitySummary,
  tripPrimaryRegions,
  tripMode,
  policyPosture,
  planningLedger,
  providerLoadState,
  activeScope,
  selectedSegmentId,
  onScopeChange,
  onSelectSegment,
  compactLayout,
}: {
  comparison: RuntimeScenarioComparison;
  scenarioComparisonSummary?: string | null;
  scenarioFocusAreas?: string[];
  activeScenarioId: string | null;
  onSelectScenario: (scenarioId: string) => void;
  bundles: InventoryBundle[];
  feasibilitySummary: FeasibilitySummary;
  tripPrimaryRegions: string[];
  tripMode: string;
  policyPosture: string | null;
  planningLedger?: WorkspaceData["planning_ledger"];
  /** Observed SDK lifecycle state; configuration alone must not mark the map live. */
  providerLoadState?: MapProviderLoadState;
  activeScope: MapViewScope;
  selectedSegmentId: string | null;
  onScopeChange: (scope: MapViewScope) => void;
  onSelectSegment: (segmentId: string | null) => void;
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
      scenarioComparisonSummary={scenarioComparisonSummary}
      scenarioFocusAreas={scenarioFocusAreas}
      tripPrimaryRegions={tripPrimaryRegions}
      tripMode={tripMode}
      policyPosture={policyPosture}
      planningLedger={planningLedger}
      providerLoadState={providerLoadState}
      activeScope={activeScope}
      selectedSegmentId={selectedSegmentId}
      onScopeChange={onScopeChange}
      onSelectSegment={onSelectSegment}
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
  scenarioComparisonSummary,
  scenarioFocusAreas,
  tripPrimaryRegions,
  tripMode,
  policyPosture,
  planningLedger,
  providerLoadState,
  activeScope,
  selectedSegmentId,
  onScopeChange,
  onSelectSegment,
  compactLayout,
}: {
  activeScenario: TripMapScenario;
  comparison: RuntimeScenarioComparison;
  onSelectScenario: (scenarioId: string) => void;
  bundles: InventoryBundle[];
  feasibilitySummary: FeasibilitySummary;
  scenarioComparisonSummary?: string | null;
  scenarioFocusAreas?: string[];
  tripPrimaryRegions: string[];
  tripMode: string;
  policyPosture: string | null;
  planningLedger?: WorkspaceData["planning_ledger"];
  providerLoadState?: MapProviderLoadState;
  activeScope: MapViewScope;
  selectedSegmentId: string | null;
  onScopeChange: (scope: MapViewScope) => void;
  onSelectSegment: (segmentId: string | null) => void;
  compactLayout: boolean;
}) {
  const googleMapsApiKey =
    import.meta.env.VITE_GOOGLE_MAPS_BROWSER_API_KEY ||
    import.meta.env.VITE_GOOGLE_MAPS_EMBED_API_KEY;
  const [observedProviderLoadState, setObservedProviderLoadState] =
    useState<MapProviderLoadState>("pending");
  const effectiveProviderLoadState = providerLoadState ?? observedProviderLoadState;
  const observesProviderInternally = providerLoadState === undefined;

  const mapSurface = buildTripMapSurfaceModel({
    activeScenario,
    bundles,
    feasibilitySummary,
    scenarioComparisonSummary,
    scenarioFocusAreas,
    tripPrimaryRegions,
    tripMode,
    policyPosture,
    googleMapsApiKey,
    providerLoadState: effectiveProviderLoadState,
    activeScope,
    selectedSegmentId,
    planningLedger,
  });
  const initialMarkerId =
    mapSurface.visibleMarkers.find((marker) => marker.focusCues.length > 0)?.id ??
    mapSurface.visibleMarkers[0]?.id ??
    null;
  const visibleMarkerIds = JSON.stringify(mapSurface.visibleMarkers.map((marker) => marker.id));
  const visibleMarkerIdSet = useMemo(() => new Set(JSON.parse(visibleMarkerIds) as string[]), [visibleMarkerIds]);
  const [selectedMarkerId, setSelectedMarkerId] = useState<string | null>(initialMarkerId);
  const selectedMarker = useMemo(
    () =>
      mapSurface.visibleMarkers.find((marker) => marker.id === selectedMarkerId) ??
      mapSurface.visibleMarkers[0] ??
      null,
    [mapSurface.visibleMarkers, selectedMarkerId]
  );

  useEffect(() => {
    setSelectedMarkerId((current) =>
      current !== null && visibleMarkerIdSet.has(current)
        ? current
        : initialMarkerId
    );
  }, [activeScenario.scenario_id, initialMarkerId, visibleMarkerIdSet]);

  function handleScopeChange(nextScope: MapViewScope) {
    onScopeChange(nextScope);
    if (nextScope === "local" && mapSurface.workspaceView.selectedSegmentId == null) {
      onSelectSegment(mapSurface.routeSegments[0]?.id ?? null);
    }
  }

  const selectedSegment =
    mapSurface.routeSegments.find(
      (segment) => segment.id === mapSurface.workspaceView.selectedSegmentId
    ) ?? null;
  const isFallbackSketch = mapSurface.provider.kind === "fallback";
  const mapHeading = isFallbackSketch
    ? `Route sketch for ${activeScenario.title}`
    : `Map for ${activeScenario.title}`;

  return (
    <section className="status-card map-card">
      <p className="status-label">Trip map</p>
      <h2>{mapHeading}</h2>
      <p>{activeScenario.summary}</p>
      <div className="map-provider-banner" aria-label="Map view confidence">
        <span
          className={`map-provider-pill map-confidence-pill-${mapSurface.workspaceView.confidence.level}`}
        >
          {mapSurface.scope.precisionLabel}
        </span>
        <p className="muted-copy">{mapSurface.scope.summary}</p>
      </div>
      <p className="muted-copy">{mapSurface.workspaceView.confidence.summary}</p>
      <div className="map-scope-controls" aria-label="Map view scope">
        {mapSurface.scopeOptions.map((option) => (
          <button
            key={option.scope}
            type="button"
            title={option.title}
            className={`map-scope-button${
              option.scope === mapSurface.scope.activeScope ? " map-scope-button-active" : ""
            }`}
            aria-pressed={option.scope === mapSurface.scope.activeScope}
            onClick={() => handleScopeChange(option.scope)}
          >
            {option.label}
          </button>
        ))}
      </div>
      {activeScope === "local" && mapSurface.routeSegments.length > 0 ? (
        <div className="map-segment-selector" aria-label="Local segment selector">
          {mapSurface.routeSegments.map((segment) => (
            <button
              key={segment.id}
              type="button"
              className={`map-segment-button${
                segment.id === mapSurface.workspaceView.selectedSegmentId
                  ? " map-segment-button-active"
                  : ""
              }`}
              title={`Focus the day plan on ${segment.fromLabel} to ${segment.toLabel}.`}
              aria-pressed={segment.id === mapSurface.workspaceView.selectedSegmentId}
              onClick={() => onSelectSegment(segment.id)}
            >
              {segment.fromLabel} to {segment.toLabel}
              {segment.durationMinutes != null ? ` · ${segment.durationMinutes} min` : ""}
            </button>
          ))}
        </div>
      ) : null}
      <div className="map-scenario-toggle" aria-label="Map scenario previews">
        {comparison.scenarios.map((scenario) => (
          <button
            key={scenario.scenario_id}
            type="button"
            className={`map-toggle-chip${
              scenario.scenario_id === activeScenario.scenario_id ? " map-toggle-chip-active" : ""
            }`}
            title={`Preview ${scenario.title} on the map.`}
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
          aria-label={`${mapSurface.scope.label} route drawing`}
        >
          <div className="map-provider-toolbar">
            <span className="map-provider-name">{mapSurface.scope.label}</span>
            {isFallbackSketch ? (
              <span className="map-preview-badge" aria-label={SCHEMATIC_PREVIEW_BADGE_TEXT}>
                {SCHEMATIC_PREVIEW_BADGE_TEXT}
              </span>
            ) : null}
            {isFallbackSketch ? (
              <span className="map-preview-badge map-preview-badge-warning">
                Route sketch mode
              </span>
            ) : null}
            <span>{mapSurface.visibleRouteSegments.length} shown segment(s)</span>
            <span>{mapSurface.visibleMarkers.length} shown marker(s)</span>
            {mapSurface.visibleFocusCues.length > 0 ? (
              <span>{mapSurface.visibleFocusCues.length} linked planning note(s)</span>
            ) : null}
          </div>
          {googleMapsApiKey && mapSurface.routeState === "ready" && observesProviderInternally ? (
            <GoogleMapsProviderMap
              apiKey={googleMapsApiKey}
              title={activeScenario.title}
              routeSegments={mapSurface.visibleRouteSegments}
              visible={mapSurface.provider.kind === "google-maps-js"}
              onProviderLoadStateChange={setObservedProviderLoadState}
            >
              <FallbackRouteSchematic
                markers={mapSurface.visibleMarkers}
                selectedMarker={selectedMarker}
                routeStops={mapSurface.visibleRouteStops}
                onSelectMarker={setSelectedMarkerId}
              />
            </GoogleMapsProviderMap>
          ) : googleMapsApiKey &&
            mapSurface.routeState === "ready" &&
            mapSurface.provider.kind === "google-maps-js" ? (
            <div
              className="map-provider-canvas"
              role="group"
              aria-label={`Simulated Google map for ${activeScenario.title}`}
              data-provider-surface="simulated-ready"
            />
          ) : (
            <FallbackRouteSchematic
              markers={mapSurface.visibleMarkers}
              selectedMarker={selectedMarker}
              routeStops={mapSurface.visibleRouteStops}
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
            <h3>Map view</h3>
            <p>{mapSurface.scope.summary}</p>
            <p className="muted-copy">{mapSurface.workspaceView.confidence.summary}</p>
            {mapSurface.visibleFocusCues.length > 0 ? (
              <ul className="map-ledger-focus-list" aria-label="Linked planning notes">
                {mapSurface.visibleFocusCues.slice(0, 4).map((cue) => (
                  <li key={cue.ledgerEntryId}>
                    <span>{cue.label}</span>
                    {cue.summary}
                  </li>
                ))}
              </ul>
            ) : null}
          </article>
          {selectedMarker ? (
            <article className="decision-card map-marker-detail" aria-live="polite">
              <p className="scenario-kicker">{selectedMarker.kind}</p>
              <h3>{selectedMarker.label}</h3>
              <p>{selectedMarker.summary}</p>
              <p className="muted-copy">{selectedMarker.detail}</p>
              {selectedMarker.focusCues.length > 0 ? (
                <ul
                  className="map-ledger-focus-list"
                  aria-label="Linked planning notes for selected marker"
                >
                  {selectedMarker.focusCues.map((cue) => (
                    <li key={cue.ledgerEntryId}>
                      <span>{cue.label}</span>
                      {cue.summary}
                    </li>
                  ))}
                </ul>
              ) : null}
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
          {selectedSegment ? (
            <article className="decision-card">
              <h3>Segment focus</h3>
              <p>
                {selectedSegment.fromLabel} to {selectedSegment.toLabel}
                {selectedSegment.durationMinutes != null
                  ? ` · ${selectedSegment.durationMinutes} min`
                  : ""}
                {selectedSegment.distanceKm != null
                  ? ` · ${selectedSegment.distanceKm.toFixed(1)} km`
                  : ""}
              </p>
              <p className="muted-copy">
                {selectedSegment.confidence === "high"
                  ? "Provider detail is available for close segment review."
                  : selectedSegment.confidence === "medium"
                    ? "Segment timing is estimated from ranked route data."
                    : "Segment detail needs more route or provider evidence."}
              </p>
              {selectedSegment.unavailableReason ? (
                <p className="muted-copy">{selectedSegment.unavailableReason}</p>
              ) : null}
            </article>
          ) : null}
          <article className="decision-card">
            <h3>Scenario comparison</h3>
            <p>{mapSurface.scenarioComparisonSummary}</p>
            {mapSurface.scenarioFocusAreas.length > 0 ? (
              <ul className="map-highlight-list">
                {mapSurface.scenarioFocusAreas.slice(0, 3).map((focusArea) => (
                  <li key={focusArea}>{focusArea.replace(/_/g, " ")}</li>
                ))}
              </ul>
            ) : null}
          </article>
          <article className="decision-card">
            <h3>Selected scenario affordances</h3>
            <ul className="map-highlight-list">
              {mapSurface.scenarioAffordances.map((affordance) => (
                <li key={affordance}>{affordance}</li>
              ))}
            </ul>
          </article>
          <article className="decision-card">
            <h3>Route summary</h3>
            <p>{activeScenario.route_summary}</p>
            <p className="muted-copy">{activeScenario.comparison_note}</p>
          </article>
          <article className="decision-card">
            <h3>Destination context</h3>
            {mapSurface.policyPosture ? (
              <p className="muted-copy" data-testid="policy-posture">
                Approval posture: {mapSurface.policyPosture}
              </p>
            ) : null}
            <p>{mapSurface.feasibilitySummary}</p>
            <div className="map-anchor-list">
              {mapSurface.destinationContext.length === 0 ? (
                <span className="map-anchor-chip map-anchor-chip-muted">Awaiting option anchors</span>
              ) : (
                mapSurface.destinationContext.map((destination) => (
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

function GoogleMapsProviderMap({
  apiKey,
  title,
  routeSegments,
  visible,
  onProviderLoadStateChange,
  children,
}: {
  apiKey: string;
  title: string;
  routeSegments: ReturnType<typeof buildTripMapSurfaceModel>["routeSegments"];
  visible: boolean;
  onProviderLoadStateChange: (state: MapProviderLoadState) => void;
  children: ReactNode;
}) {
  const [canvas, setCanvas] = useState<HTMLDivElement | null>(null);
  const [providerSurfaceState, setProviderSurfaceState] =
    useState<MapProviderLoadState>("pending");
  const routeKey = routeSegments
    .map((segment) => `${segment.id}:${segment.fromLabel}:${segment.toLabel}`)
    .join("|");

  useEffect(() => {
    if (canvas === null) {
      return;
    }
    let cancelled = false;
    const overlays: Array<{ setMap: (map: unknown) => void }> = [];
    onProviderLoadStateChange("loading");
    setProviderSurfaceState("loading");

    async function renderProviderMap() {
      try {
        setOptions({ key: apiKey, v: "weekly" });
        const [maps, markerLib, geocoding, core] = await Promise.all([
          importLibrary("maps"),
          importLibrary("marker"),
          importLibrary("geocoding"),
          importLibrary("core"),
        ]);
        if (cancelled) {
          return;
        }

        const map = new maps.Map(canvas, {
          center: { lat: 20, lng: 0 },
          mapId: "DEMO_MAP_ID",
          zoom: 2,
          streetViewControl: false,
          mapTypeControl: false,
        });
        const geocoder = new geocoding.Geocoder();
        const locations = new Map<string, { lat: number; lng: number }>();

        for (const routeLabel of Array.from(
          new Set(routeSegments.flatMap((segment) => [segment.fromLabel, segment.toLabel]))
        )) {
          if (cancelled) {
            overlays.forEach((overlay) => overlay.setMap(null));
            return;
          }
          try {
            const response = await geocoder.geocode({ address: routeLabel });
            const location = response.results[0]?.geometry.location;
            if (location) {
              locations.set(routeLabel, location.toJSON());
            }
          } catch {
            // Skip labels that fail geocoding; partial route context is still useful.
          }
        }
        if (cancelled) {
          overlays.forEach((overlay) => overlay.setMap(null));
          return;
        }
        if (locations.size === 0) {
          onProviderLoadStateChange("error");
          setProviderSurfaceState("error");
          return;
        }

        const bounds = new core.LatLngBounds();
        for (const [label, location] of locations) {
          if (cancelled) {
            overlays.forEach((overlay) => overlay.setMap(null));
            return;
          }
          const advancedMarker = new markerLib.AdvancedMarkerElement({
            map,
            position: location,
            title: label,
          });
          overlays.push(advancedMarker);
          bounds.extend(location);
        }
        for (const segment of routeSegments) {
          const from = locations.get(segment.fromLabel);
          const to = locations.get(segment.toLabel);
          if (from && to) {
            const polyline = new maps.Polyline({
              map,
              path: [from, to],
              geodesic: true,
              strokeColor: segment.warning ? "#b42318" : "#2563eb",
              strokeOpacity: 0.9,
              strokeWeight: 4,
            });
            overlays.push(polyline);
          }
        }
        if (cancelled) {
          overlays.forEach((overlay) => overlay.setMap(null));
          return;
        }
        map.fitBounds(bounds, 48);
        onProviderLoadStateChange("ready");
        setProviderSurfaceState("ready");
      } catch {
        if (!cancelled) {
          onProviderLoadStateChange("error");
          setProviderSurfaceState("error");
        }
      }
    }

    void renderProviderMap();
    return () => {
      cancelled = true;
      overlays.forEach((overlay) => overlay.setMap(null));
    };
  }, [apiKey, canvas, onProviderLoadStateChange, routeKey]);

  const showLiveCanvas = visible && providerSurfaceState === "ready";

  return (
    <>
      <div
        ref={setCanvas}
        className="map-provider-canvas"
        role="group"
        aria-label={`Interactive Google map for ${title}`}
        style={{
          display: "block",
          visibility: showLiveCanvas ? "visible" : "hidden",
          position: showLiveCanvas ? "relative" : "absolute",
          width: "100%",
          minHeight: showLiveCanvas ? undefined : "12rem",
        }}
        data-provider-surface={
          providerSurfaceState === "ready" ? "rendered" : "loading"
        }
      />
      {showLiveCanvas ? null : children}
    </>
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
          const marker = markers.find((candidate) => candidate.id === markerId);
          return (
            <button
              key={stop.id}
              type="button"
              className={`map-stop${selectedMarker?.id === markerId ? " map-stop-selected" : ""}${
                marker?.focusCues.length ? " map-stop-focused" : ""
              }`}
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
            }${marker.focusCues.length > 0 ? " map-option-marker-focused" : ""}`}
            aria-label={markerAccessibleLabel(marker)}
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
  const focusSummary =
    marker.focusCues.length === 0
      ? ""
      : ` ${marker.focusCues.length} linked planning note${
          marker.focusCues.length === 1 ? "" : "s"
        }.`;
  return `${marker.kind} marker: ${marker.label}. ${marker.summary}${focusSummary}`;
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
