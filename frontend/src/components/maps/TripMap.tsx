import type {
  FeasibilitySummary,
  RuntimeScenarioComparison,
  WorkspaceData,
} from "../../api/workspace";

type TripMapScenario = RuntimeScenarioComparison["scenarios"][number];
type InventoryBundle = WorkspaceData["inventory_summary"]["bundles"][number];

function humanizeStop(stop: string): string {
  return stop
    .replace(/^dest-city-/, "")
    .replace(/^dest-/, "")
    .replace(/^city-/, "")
    .split(/[-_]/g)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatEstimatedTotal(value: number | null): string {
  if (value == null) {
    return "Pending";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function summarizeFeasibility(
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

export function TripMap({
  comparison,
  activeScenarioId,
  onSelectScenario,
  bundles,
  feasibilitySummary,
}: {
  comparison: RuntimeScenarioComparison;
  activeScenarioId: string | null;
  onSelectScenario: (scenarioId: string) => void;
  bundles: InventoryBundle[];
  feasibilitySummary: FeasibilitySummary;
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

  const bundleDestinations = Array.from(
    new Set(
      bundles
        .flatMap((bundle) => bundle.destination_names)
        .map((destination) => destination.trim())
        .filter(Boolean)
    )
  );

  return (
    <section className="status-card map-card">
      <p className="status-label">Map surface</p>
      <h2>Map preview for {activeScenario.title}</h2>
      <p>{activeScenario.summary}</p>
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
        <div className="map-route">
          {activeScenario.route_sequence.map((stop, index) => (
            <div key={`${activeScenario.scenario_id}-${stop}-${index}`} className="map-stop">
              <div className="map-stop-marker">
                <span>{index + 1}</span>
              </div>
              <div className="map-stop-copy">
                <h3>{humanizeStop(stop)}</h3>
                <p>
                  {index === 0
                    ? "Current route origin for the workspace preview."
                    : index === activeScenario.route_sequence.length - 1
                      ? "Current route destination anchor."
                      : "Intermediate route checkpoint preserved in the active scenario."}
                </p>
              </div>
            </div>
          ))}
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
            <p>{summarizeFeasibility(feasibilitySummary, bundleDestinations)}</p>
            <div className="map-anchor-list">
              {bundleDestinations.length === 0 ? (
                <span className="map-anchor-chip map-anchor-chip-muted">Awaiting option anchors</span>
              ) : (
                bundleDestinations.map((destination) => (
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
