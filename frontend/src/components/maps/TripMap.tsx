import type {
  FeasibilitySummary,
  RuntimeScenarioComparison,
  WorkspaceData,
} from "../../api/workspace";
import {
  buildGoogleMapsEmbedUrl,
  buildTripMapViewModel,
  resolveTripMapProvider,
} from "./tripMapModel";

type TripMapScenario = RuntimeScenarioComparison["scenarios"][number];
type InventoryBundle = WorkspaceData["inventory_summary"]["bundles"][number];

function formatEstimatedTotal(
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

export function TripMap({
  comparison,
  activeScenarioId,
  onSelectScenario,
  bundles,
  feasibilitySummary,
  providerOverride,
  googleMapsApiKeyOverride,
}: {
  comparison: RuntimeScenarioComparison;
  activeScenarioId: string | null;
  onSelectScenario: (scenarioId: string) => void;
  bundles: InventoryBundle[];
  feasibilitySummary: FeasibilitySummary;
  providerOverride?: "google-maps" | "fallback";
  googleMapsApiKeyOverride?: string;
}) {
  const model = buildTripMapViewModel({
    comparison,
    activeScenarioId,
    bundles,
    feasibilitySummary,
  });

  if (model == null) {
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

  const googleMapsApiKey =
    googleMapsApiKeyOverride ?? import.meta.env.VITE_GOOGLE_MAPS_EMBED_API_KEY ?? "";
  const provider =
    providerOverride ??
    resolveTripMapProvider({
      googleMapsApiKey,
      preferredProvider: import.meta.env.VITE_MAP_PROVIDER,
    });
  const googleMapsEmbedUrl =
    provider === "google-maps" && googleMapsApiKey
      ? buildGoogleMapsEmbedUrl({ apiKey: googleMapsApiKey, model })
      : null;
  const activeScenario = model.activeScenario;

  return (
    <section className="status-card map-card">
      <p className="status-label">Map surface</p>
      <h2>Map preview for {activeScenario.title}</h2>
      <p>{activeScenario.summary}</p>
      <div className="map-provider-row">
        <span className="map-provider-pill">
          {provider === "google-maps" ? "Google Maps provider" : "Fallback provider preview"}
        </span>
        <span className="muted-copy">
          {provider === "google-maps"
            ? "Route overlays are rendered through the Google Maps embed path while preserving a fallback seam."
            : "Fallback route rendering stays available for local development and provider outages."}
        </span>
      </div>
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
      <div className="map-surface">
        <div className="map-visual-shell" aria-label="Route context map">
          {googleMapsEmbedUrl ? (
            <iframe
              className="map-embed-frame"
              title={`Google Maps route for ${activeScenario.title}`}
              src={googleMapsEmbedUrl}
              loading="lazy"
              referrerPolicy="no-referrer-when-downgrade"
            />
          ) : (
            <div className="map-route">
              {model.stops.map((stop, index) => (
                <div key={`${activeScenario.scenario_id}-${stop.query}-${index}`} className="map-stop">
                  <div className="map-stop-marker">
                    <span>{index + 1}</span>
                  </div>
                  <div className="map-stop-copy">
                    <h3>{stop.label}</h3>
                    <p>{stop.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="map-sidebar">
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
            <p>{model.feasibilityNote}</p>
            <div className="map-anchor-list">
              {model.destinationAnchors.length === 0 ? (
                <span className="map-anchor-chip map-anchor-chip-muted">Awaiting option anchors</span>
              ) : (
                model.destinationAnchors.map((destination) => (
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
        </div>
      </div>
    </section>
  );
}
