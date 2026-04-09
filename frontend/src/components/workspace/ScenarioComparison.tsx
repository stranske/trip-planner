import type { RuntimeScenarioComparison, SavedScenarioRecord } from "../../api/workspace";

type ComparisonScenario = RuntimeScenarioComparison["scenarios"][number];

function formatMetricValue(
  axisKey: string,
  scenario: ComparisonScenario
): string {
  if (axisKey === "estimated_total") {
    const estimatedTotal = scenario.metrics.estimated_total;
    if (estimatedTotal == null) {
      return "Pending";
    }
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: estimatedTotal.currency,
      maximumFractionDigits: 0,
    }).format(estimatedTotal.typical_amount);
  }

  if (axisKey === "score") {
    return scenario.metrics.score.toFixed(2);
  }

  if (axisKey === "travel_minutes") {
    return `${scenario.metrics.travel_minutes} min`;
  }

  if (axisKey === "transfers") {
    return `${scenario.metrics.transfers}`;
  }

  return "Unavailable";
}

function formatScenarioDelta(
  axisKey: string,
  scenario: ComparisonScenario
): string {
  if (axisKey === "score") {
    return `${scenario.delta.score_delta >= 0 ? "+" : ""}${scenario.delta.score_delta.toFixed(2)}`;
  }
  if (axisKey === "travel_minutes") {
    return `${scenario.delta.travel_minutes_delta >= 0 ? "+" : ""}${scenario.delta.travel_minutes_delta} min`;
  }
  if (axisKey === "transfers") {
    return `${scenario.delta.transfers_delta >= 0 ? "+" : ""}${scenario.delta.transfers_delta}`;
  }
  if (axisKey === "estimated_total") {
    if (scenario.delta.estimated_total_delta == null) {
      return "Pending";
    }
    return `${scenario.delta.estimated_total_delta >= 0 ? "+" : ""}${scenario.delta.estimated_total_delta.toFixed(0)}`;
  }
  return "0";
}

function findSavedScenarioDetails(
  savedScenarios: SavedScenarioRecord[],
  scenarioId: string
): { label: string; title: string; summary: string } | null {
  for (const savedScenario of savedScenarios) {
    const activeVersion =
      savedScenario.versions.find((version) => version.version_id === savedScenario.current_version_id) ??
      savedScenario.versions[0];
    if (activeVersion?.snapshot_refs.itinerary_scenario_id === scenarioId) {
      return {
        label: activeVersion.label,
        title: activeVersion.title,
        summary: activeVersion.summary,
      };
    }
  }
  return null;
}

export function ScenarioComparison({
  comparison,
  savedScenarios,
  selectedScenarioId,
  onSelectScenario,
}: {
  comparison: RuntimeScenarioComparison;
  savedScenarios: SavedScenarioRecord[];
  selectedScenarioId: string | null;
  onSelectScenario: (scenarioId: string) => void;
}) {
  const leadScenario =
    comparison.scenarios.find((scenario) => scenario.scenario_id === comparison.lead_scenario_id) ??
    comparison.scenarios[0] ??
    null;
  const selectedScenario =
    comparison.scenarios.find((scenario) => scenario.scenario_id === selectedScenarioId) ??
    leadScenario;
  const secondaryScenario =
    selectedScenario?.scenario_id === leadScenario?.scenario_id
      ? comparison.scenarios.find((scenario) => scenario.scenario_id !== leadScenario?.scenario_id) ?? null
      : selectedScenario;
  const comparedScenarios = [leadScenario, secondaryScenario].filter(
    (scenario, index, scenarios): scenario is ComparisonScenario =>
      scenario !== null &&
      scenarios.findIndex((candidate) => candidate?.scenario_id === scenario.scenario_id) === index
  );

  if (comparison.scenarios.length === 0) {
    return (
      <section className="status-card">
        <p className="status-label">Scenario comparison</p>
        <h2>Saved-scenario comparison is not ready</h2>
        <p className="muted-copy">
          Persisted workspace state exists, but runtime scenario rows have not been assembled yet.
        </p>
      </section>
    );
  }

  return (
    <section className="status-card">
      <p className="status-label">Scenario comparison</p>
      <h2>{comparison.title}</h2>
      <p>{comparison.summary}</p>
      <div className="map-scenario-toggle" aria-label="Saved scenario comparison choices">
        {comparison.scenarios.map((scenario) => (
          <button
            key={scenario.scenario_id}
            type="button"
            className={`map-toggle-chip${
              scenario.scenario_id === selectedScenario?.scenario_id ? " map-toggle-chip-active" : ""
            }`}
            aria-pressed={scenario.scenario_id === selectedScenario?.scenario_id}
            onClick={() => onSelectScenario(scenario.scenario_id)}
          >
            Compare {scenario.rank}. {scenario.title}
          </button>
        ))}
      </div>
      <div className="scenario-stack">
        {comparedScenarios.map((scenario) => {
          const savedScenarioDetails = findSavedScenarioDetails(savedScenarios, scenario.scenario_id);
          return (
            <article key={scenario.scenario_id} className="scenario-card">
              <p className="scenario-kicker">{savedScenarioDetails?.label ?? scenario.status}</p>
              <h3>{savedScenarioDetails?.title ?? scenario.title}</h3>
              <p>{savedScenarioDetails?.summary ?? scenario.summary}</p>
              <p className="muted-copy">{scenario.comparison_note}</p>
            </article>
          );
        })}
      </div>
      <div className="decision-stack" aria-label="Scenario comparison metrics">
        {comparison.comparison_axes.map((axis) => (
          <article key={axis.key} className="decision-card">
            <h3>{axis.label}</h3>
            {comparedScenarios.map((scenario) => (
              <p key={`${axis.key}-${scenario.scenario_id}`}>
                {scenario.title}: {formatMetricValue(axis.key, scenario)}
                {scenario.scenario_id === leadScenario?.scenario_id ? " (lead)" : ` (${formatScenarioDelta(axis.key, scenario)} vs lead)`}
              </p>
            ))}
          </article>
        ))}
        {selectedScenario ? (
          <article className="decision-card">
            <h3>Selected scenario highlights</h3>
            <ul className="focus-area-list">
              {selectedScenario.highlights.slice(0, 3).map((highlight) => (
                <li key={highlight}>{highlight}</li>
              ))}
            </ul>
          </article>
        ) : null}
      </div>
    </section>
  );
}
