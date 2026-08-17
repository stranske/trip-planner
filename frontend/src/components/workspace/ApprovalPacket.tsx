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
  const savedScenario = workspace.saved_scenarios.find(
    (scenario) => scenario.saved_scenario_id === workspace.session.current_saved_scenario_id
  );
  const activeVersion = savedScenario?.versions.find(
    (version) => version.version_id === savedScenario.current_version_id
  );
  const scenarioId = proposal?.scenario_id ?? activeVersion?.snapshot_refs.itinerary_scenario_id;
  const routeComparison = workspace.route_comparison ?? workspace.runtime_scenario_comparison;
  const selectedScenario = routeComparison.scenarios.find(
    (scenario) => scenario.scenario_id === scenarioId
  ) ?? routeComparison.scenarios[0];
  const verdict = proposal?.evaluation.evaluation_result;
  const scenarioTotal = selectedScenario?.metrics.estimated_total;
  const budgetCurrency = workspace.budget_state.summary.currency;
  const budgetTotalsUseScenarioCurrency = scenarioTotal?.currency === budgetCurrency;
  const budgetDelta = scenarioTotal
    ? workspace.budget_state.summary.planned_total - scenarioTotal.typical_amount
    : null;
  const travelerParty = trip.trip_frame.traveler_party;

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
        <div><dt>Travelers</dt><dd>{travelerParty ? `${travelerParty.traveler_count} ${travelerParty.kind}` : "Not set"}</dd></div>
        {travelerParty?.notes ? <div><dt>Traveler notes</dt><dd>{travelerParty.notes}</dd></div> : null}
        <div><dt>Selected scenario</dt><dd>{selectedScenario?.title ?? "Not selected"}</dd></div>
        <div><dt>Estimated total</dt><dd>{scenarioTotal ? formatCurrency(scenarioTotal.typical_amount, scenarioTotal.currency) : "Not available"}</dd></div>
        <div><dt>Policy verdict</dt><dd>{verdict?.status ?? proposal?.summary.evaluation_result_status ?? "Not evaluated"}</dd></div>
        <div><dt>Compliance score</dt><dd>{verdict ? `${Math.round(verdict.compliance_score * 100)}%` : "Not available"}</dd></div>
      </dl>
      <section>
        <h3>Budget</h3>
        <p>
          Selected scenario total: {scenarioTotal ? formatCurrency(scenarioTotal.typical_amount, scenarioTotal.currency) : "Not available"}. Budget cap: {formatCurrency(workspace.budget_state.summary.planned_total, budgetCurrency)}. Remaining budget: {formatCurrency(workspace.budget_state.summary.remaining_total, budgetCurrency)}.
        </p>
        {scenarioTotal && budgetTotalsUseScenarioCurrency && budgetDelta !== null ? (
          <p>
            Scenario total is {formatCurrency(Math.abs(budgetDelta), budgetCurrency)} {budgetDelta >= 0 ? "below" : "above"} the budget cap.
          </p>
        ) : scenarioTotal ? (
          <p>Scenario and budget totals use different currencies, so the packet does not compare them.</p>
        ) : null}
        <ul>
          {workspace.budget_state.summary.category_summaries.map((category) => (
            <li key={category.category_key}>
              {category.label}: cap {formatCurrency(category.planned_amount, category.currency)}; remaining {formatCurrency(category.remaining_amount, category.currency)}
            </li>
          ))}
        </ul>
        {proposal?.proposal.comparables?.length ? (
          <>
            <h4>Itemized costs</h4>
            <ul>
              {proposal.proposal.comparables.map((comparable) => (
                <li key={`${comparable.category}:${comparable.vendor}:${comparable.label}`}>
                  {comparable.category}: {comparable.label} from {comparable.vendor} — {formatCurrency(comparable.estimated_cost.typical_amount, comparable.estimated_cost.currency)}
                </li>
              ))}
            </ul>
          </>
        ) : null}
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
