import type { FeasibilitySummary, RuntimeScenarioComparison, WorkspaceData } from "../../api/workspace";
import {
  buildTripMapSurfaceModel,
  formatEstimatedTotal,
} from "./mapSurface";

type InventoryBundle = WorkspaceData["inventory_summary"]["bundles"][number];

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

  const mapSurface = buildTripMapSurfaceModel({
    activeScenario,
    bundles,
    feasibilitySummary,
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_EMBED_API_KEY,
  });

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
      <p className="muted-copy">
        {mapSurface.provider.label} is the current map path. {mapSurface.provider.summary}
      </p>
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
        {mapSurface.provider.kind === "google-maps" ? (
          <div className="map-route">
            <iframe
              title={`Google Maps route preview for ${activeScenario.title}`}
              src={mapSurface.provider.iframeSrc}
              className="map-provider-frame"
              loading="lazy"
              referrerPolicy="no-referrer-when-downgrade"
            />
          </div>
        ) : (
          <div className="map-route">
            {mapSurface.routeStops.map((stop, index) => (
              <div key={stop.id} className="map-stop">
                <div className="map-stop-marker">
                  <span>{index + 1}</span>
                </div>
                <div className="map-stop-copy">
                  <h3>{stop.label}</h3>
                  <p>{stop.description}</p>
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="map-sidebar">
          <article className="decision-card">
            <h3>{mapSurface.provider.kind === "google-maps" ? "Live provider path" : "Fallback route path"}</h3>
            <p>{mapSurface.provider.summary}</p>
          </article>
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
