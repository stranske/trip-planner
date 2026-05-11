import type {
  RouteOptionAction,
  RouteOptionActionType,
  RouteOptionState,
  RuntimeScenarioComparison,
} from "../../api/workspace";

type RouteOptionScenario = RuntimeScenarioComparison["scenarios"][number];

const STATE_LABELS: Record<RouteOptionState, string> = {
  active: "Active option",
  baseline: "Baseline",
  fallback: "Kept for later",
  rejected: "Rejected",
  needs_research: "Needs revision",
};

const FALLBACK_ACTIONS: Record<RouteOptionState, RouteOptionAction[]> = {
  active: [
    {
      action_type: "make_baseline",
      label: "Make baseline",
      description: "Use this route as the main plan while keeping alternatives visible.",
    },
    {
      action_type: "keep",
      label: "Keep for later",
      description: "Preserve this route as a backup option without making it the main plan.",
    },
    {
      action_type: "reject",
      label: "Reject",
      description: "Move this route to history so it stops competing with active options.",
    },
    {
      action_type: "revise",
      label: "Revise",
      description: "Ask the planner to improve this route before the next checkpoint.",
    },
  ],
  baseline: [
    {
      action_type: "keep",
      label: "Keep for later",
      description: "Preserve this route as a backup option without making it the main plan.",
    },
    {
      action_type: "reject",
      label: "Reject",
      description: "Move this route to history so it stops competing with active options.",
    },
    {
      action_type: "revise",
      label: "Revise",
      description: "Ask the planner to improve this route before the next checkpoint.",
    },
  ],
  fallback: [
    {
      action_type: "make_baseline",
      label: "Make baseline",
      description: "Use this route as the main plan while keeping alternatives visible.",
    },
    {
      action_type: "reject",
      label: "Reject",
      description: "Move this route to history so it stops competing with active options.",
    },
    {
      action_type: "revise",
      label: "Revise",
      description: "Ask the planner to improve this route before the next checkpoint.",
    },
  ],
  rejected: [
    {
      action_type: "reopen",
      label: "Reopen",
      description: "Move this route back into the active comparison set.",
    },
  ],
  needs_research: [
    {
      action_type: "make_baseline",
      label: "Make baseline",
      description: "Use this route as the main plan while keeping alternatives visible.",
    },
    {
      action_type: "keep",
      label: "Keep for later",
      description: "Preserve this route as a backup option without making it the main plan.",
    },
    {
      action_type: "reject",
      label: "Reject",
      description: "Move this route to history so it stops competing with active options.",
    },
    {
      action_type: "revise",
      label: "Revise",
      description: "Ask the planner to improve this route before the next checkpoint.",
    },
  ],
};

function routeOptionId(scenario: RouteOptionScenario): string {
  return scenario.route_option_id ?? scenario.scenario_id;
}

function routeOptionState(
  scenario: RouteOptionScenario,
  leadScenarioId: string | null
): RouteOptionState {
  if (scenario.state) {
    return scenario.state;
  }
  if (scenario.scenario_id === leadScenarioId) {
    return "baseline";
  }
  if (scenario.status === "fallback") {
    return "fallback";
  }
  if (scenario.status === "blocked") {
    return "needs_research";
  }
  return "active";
}

function formatConfidence(confidence: number | undefined): string {
  if (confidence == null) {
    return "Confidence pending";
  }
  return `${Math.round(confidence * 100)}% confidence`;
}

function formatMetric(scenario: RouteOptionScenario): string {
  const estimatedTotal = scenario.metrics.estimated_total;
  const cost =
    estimatedTotal == null
      ? "cost pending"
      : new Intl.NumberFormat("en-US", {
          style: "currency",
          currency: estimatedTotal.currency,
          maximumFractionDigits: 0,
        }).format(estimatedTotal.typical_amount);
  return `${scenario.metrics.travel_minutes} min, ${scenario.metrics.transfers} transfer${
    scenario.metrics.transfers === 1 ? "" : "s"
  }, ${cost}`;
}

function routeTradeoffSummaries(scenario: RouteOptionScenario): string[] {
  return [
    scenario.comparison_note,
    ...(scenario.highlights ?? []),
    ...(scenario.unresolved_questions ?? []).map((question) => `Open question: ${question}`),
  ]
    .map((summary) => summary.trim())
    .filter(Boolean)
    .slice(0, 3);
}

export function RouteOptionWorkbench({
  comparison,
  selectedScenarioId,
  busyLabel,
  errorMessage,
  onSelectScenario,
  onRouteOptionAction,
}: {
  comparison: RuntimeScenarioComparison;
  selectedScenarioId: string | null;
  busyLabel: string | null;
  errorMessage: string | null;
  onSelectScenario: (scenarioId: string) => void;
  onRouteOptionAction: (optionId: string, actionType: RouteOptionActionType) => void;
}) {
  const scenarios = comparison.scenarios.slice(0, 4);

  if (scenarios.length === 0) {
    return (
      <section className="status-card route-workbench-card">
        <p className="status-label">Route options</p>
        <h2>Route comparison is not ready</h2>
        <p className="muted-copy">
          The workspace needs route options before it can compare alternatives.
        </p>
      </section>
    );
  }

  return (
    <section className="status-card route-workbench-card">
      <div className="route-workbench-header">
        <div>
          <p className="status-label">Route options</p>
          <h2>Compare possible route plans</h2>
          <p>
            Keep three or four route ideas visible while deciding what should become the
            working baseline.
          </p>
        </div>
        <span className="planner-conversation-pill">
          {scenarios.length} option{scenarios.length === 1 ? "" : "s"}
        </span>
      </div>
      {busyLabel ? <p className="muted-copy">{busyLabel}</p> : null}
      {errorMessage ? <p className="planner-inline-error">{errorMessage}</p> : null}
      <div className="route-option-grid" aria-label="Route option comparison workbench">
        {scenarios.map((scenario) => {
          const state = routeOptionState(scenario, comparison.lead_scenario_id);
          const optionId = routeOptionId(scenario);
          const actions = scenario.available_actions ?? FALLBACK_ACTIONS[state];
          const isSelected = scenario.scenario_id === selectedScenarioId;
          const tradeoffSummaries = routeTradeoffSummaries(scenario);

          return (
            <article
              key={scenario.scenario_id}
              className={`route-option-card route-option-card--${state}${
                isSelected ? " route-option-card-selected" : ""
              }`}
              aria-label={`${scenario.title} route option`}
            >
              <div className="route-option-card-header">
                <p className="scenario-kicker">{STATE_LABELS[state]}</p>
                <button
                  type="button"
                  className="map-toggle-chip"
                  title={`Show ${scenario.title} on the map and day plan.`}
                  aria-pressed={isSelected}
                  onClick={() => onSelectScenario(scenario.scenario_id)}
                >
                  View route
                </button>
              </div>
              <h3>{scenario.title}</h3>
              <p>{scenario.purpose ?? scenario.summary}</p>
              <dl className="workspace-meta route-option-metrics">
                <div>
                  <dt>Shape</dt>
                  <dd>{scenario.route_summary}</dd>
                </div>
                <div>
                  <dt>Friction</dt>
                  <dd>{formatMetric(scenario)}</dd>
                </div>
                <div>
                  <dt>Confidence</dt>
                  <dd>{formatConfidence(scenario.confidence)}</dd>
                </div>
              </dl>
              {tradeoffSummaries.length > 0 ? (
                <div className="route-option-tradeoffs">
                  <p className="scenario-kicker">Tradeoff summary</p>
                  <ul>
                    {tradeoffSummaries.map((summary) => (
                      <li key={summary}>{summary}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {(scenario.unresolved_questions ?? []).length > 0 ? (
                <div className="route-option-questions">
                  <p className="scenario-kicker">Open questions</p>
                  <ul>
                    {(scenario.unresolved_questions ?? []).map((question) => (
                      <li key={question}>{question}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <div className="route-option-actions" aria-label={`${scenario.title} route actions`}>
                {actions.map((action) => (
                  <button
                    key={`${optionId}-${action.action_type}`}
                    type="button"
                    title={action.description}
                    disabled={Boolean(busyLabel)}
                    onClick={() => onRouteOptionAction(optionId, action.action_type)}
                  >
                    {action.label}
                  </button>
                ))}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
