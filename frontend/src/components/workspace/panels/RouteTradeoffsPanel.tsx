type RouteTradeoffMetric = {
  label: string;
  value: string;
  testId?: string;
};

type RouteTradeoffCard = {
  id: string;
  kicker: string;
  title: string;
  summary: string;
  comparisonNote: string;
  highlights: string[];
  isSelected: boolean;
  metrics: RouteTradeoffMetric[];
};

export type RouteTradeoffsPanelProps = {
  compactLayout: boolean;
  showPolicyPosture: boolean;
  scenarios: RouteTradeoffCard[];
  emptyMessage: string;
};

export function RouteTradeoffsPanel({
  compactLayout,
  showPolicyPosture,
  scenarios,
  emptyMessage,
}: RouteTradeoffsPanelProps) {
  return (
    <section className="status-card">
      <p className="status-label">Route tradeoffs</p>
      <h2>{compactLayout ? "Compact route tradeoffs" : "Review route tradeoffs"}</h2>
      <p>
        {showPolicyPosture
          ? "Cost, route burden, feasibility, and approval posture stay scannable here without forcing you into raw planning notes."
          : "Cost, route burden, and feasibility stay scannable here without forcing you into raw planning notes."}
      </p>
      {scenarios.length > 0 ? (
        <div className="scenario-review-grid" aria-label="Scenario review board">
          {scenarios.map((scenario) => (
            <article
              key={scenario.id}
              className={`scenario-card scenario-review-card${
                scenario.isSelected ? " scenario-card-active" : ""
              }`}
              aria-label={`${scenario.title} review summary`}
            >
              <p className="scenario-kicker">{scenario.kicker}</p>
              <h3>{scenario.title}</h3>
              <p>{scenario.summary}</p>
              <dl className="workspace-meta scenario-review-metrics">
                {scenario.metrics.map((metric) => (
                  <div key={`${scenario.id}-${metric.label}`}>
                    <dt>{metric.label}</dt>
                    <dd data-testid={metric.testId}>{metric.value}</dd>
                  </div>
                ))}
              </dl>
              <p className="muted-copy">{scenario.comparisonNote}</p>
              <ul className="focus-area-list scenario-highlight-list">
                {scenario.highlights.slice(0, 2).map((highlight) => (
                  <li key={highlight}>{highlight}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      ) : (
        <p className="muted-copy">{emptyMessage}</p>
      )}
    </section>
  );
}
