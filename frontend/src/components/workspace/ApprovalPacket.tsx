import type { WorkspaceData } from "../../api/workspace";

type ApprovalPacketProps = {
  workspace: WorkspaceData;
  onPrint: () => void;
};

function formatCurrency(amount: number, currency: string): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);
}

export function ApprovalPacket({ workspace, onPrint }: ApprovalPacketProps) {
  const trip = workspace.trip_record.trip;
  const proposal = workspace.proposal_state;
  const scenarioId = workspace.session.current_saved_scenario_id;
  const selectedScenario = workspace.route_comparison.scenarios.find(
    (scenario) => scenario.scenario_id === scenarioId
  ) ?? workspace.route_comparison.scenarios[0];
  const verdict = proposal?.evaluation.evaluation_result;
  const currency = selectedScenario?.metrics.estimated_total?.currency ?? workspace.budget_state.summary.currency;
  const total = selectedScenario?.metrics.estimated_total?.typical_amount ?? workspace.budget_state.summary.planned_total;

  return (
    <section className="approval-packet" aria-label="Approval packet" data-testid="approval-packet-document">
      <div className="approval-packet-actions no-print">
        <button type="button" onClick={onPrint}>Print / Export</button>
      </div>
      <p className="status-label">Approval packet</p>
      <h2>{trip.title}</h2>
      <p>{trip.summary}</p>
      <dl className="workspace-meta approval-packet-meta">
        <div><dt>Dates</dt><dd>{trip.trip_frame.start_date ?? "Not set"} to {trip.trip_frame.end_date ?? "Not set"}</dd></div>
        <div><dt>Destinations</dt><dd>{trip.trip_frame.primary_regions.join(", ") || "Not set"}</dd></div>
        <div><dt>Selected scenario</dt><dd>{selectedScenario?.title ?? "Not selected"}</dd></div>
        <div><dt>Estimated total</dt><dd>{formatCurrency(total, currency)}</dd></div>
        <div><dt>Policy verdict</dt><dd>{verdict?.status ?? proposal?.summary.evaluation_result_status ?? "Not evaluated"}</dd></div>
        <div><dt>Compliance score</dt><dd>{verdict ? `${Math.round(verdict.compliance_score * 100)}%` : "Not available"}</dd></div>
      </dl>
      <section>
        <h3>Budget</h3>
        <ul>
          {workspace.budget_state.summary.category_summaries.map((category) => (
            <li key={category.category_key}>{category.label}: {formatCurrency(category.planned_amount, category.currency)}</li>
          ))}
        </ul>
      </section>
      <section>
        <h3>Policy reasons</h3>
        {verdict?.failure_reasons.length ? (
          <ul>{verdict.failure_reasons.map((reason) => <li key={reason.code}><strong>{reason.code}</strong>: {reason.message}</li>)}</ul>
        ) : (
          <p>{proposal?.summary.highlights?.join(" · ") || "No blocking policy reasons were returned."}</p>
        )}
      </section>
    </section>
  );
}
