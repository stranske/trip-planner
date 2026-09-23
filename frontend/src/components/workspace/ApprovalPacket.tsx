import type { TripPricesState, WorkspaceData } from "../../api/workspace";
import { formatMoney } from "../../lib/money";
import { explainPolicyCode } from "../../lib/policyCodes";

/**
 * The document a traveller hands to the person who approves their trip.
 *
 * Every line on it must be something the product can stand behind. Observed 2026-09-22 in a
 * printed packet: "Budget cap: $0 … $1,238 above the budget cap" when no cap had been set, a
 * "Compliance score 15%" that the policy service never produced, the cost attributed to the
 * policy engine, no traveller name, and "Policy verdict: Not evaluated" after a reload for a
 * trip that had been reviewed. So this renders only what a source said, and says plainly when
 * something is absent.
 */

type ApprovalPacketProps = {
  workspace: WorkspaceData;
  onPrint: () => void;
  /** Prices the traveller entered, with who entered them. */
  prices?: TripPricesState | null;
  /** The signed-in traveller making the request. */
  requesterName?: string | null;
  /** Injected for tests; the date the packet is prepared. */
  preparedOn?: Date;
};

type PolicyResult = {
  label: string;
  reasons: Array<{ code: string; text: string; whatToDo: string | null }>;
};

function describePolicyResult(workspace: WorkspaceData): PolicyResult {
  const proposal = workspace.proposal_state;
  if (proposal == null) {
    return { label: "Not yet submitted to the travel policy service", reasons: [] };
  }
  const summary = proposal.summary;
  const verdictStatus =
    proposal.evaluation?.evaluation_result?.status ?? summary.evaluation_result_status ?? null;

  const messages: Record<string, string> = {};
  for (const reason of summary.follow_up?.failure_reasons ?? []) {
    if (reason.code && reason.message) {
      messages[reason.code] = reason.message;
    }
  }
  for (const reason of proposal.evaluation?.evaluation_result?.failure_reasons ?? []) {
    if (reason.code && reason.message) {
      messages[reason.code] = reason.message;
    }
  }
  const codes =
    summary.submission_blocking_codes && summary.submission_blocking_codes.length > 0
      ? summary.submission_blocking_codes
      : Object.keys(messages);
  const reasons = codes.map((code) => {
    const explained = explainPolicyCode(code, messages[code]);
    return { code, text: explained.meaning, whatToDo: explained.whatToDo };
  });

  if (verdictStatus === "compliant") {
    return { label: "Passed the travel policy check", reasons: [] };
  }
  if (summary.submission_outcome === "blocked_by_policy" || verdictStatus === "non_compliant") {
    return { label: "Blocked by travel policy until the items below are resolved", reasons };
  }
  if (summary.submission_outcome === "failed") {
    return { label: "Not reviewed — the policy service could not be reached", reasons: [] };
  }
  return { label: "Submitted; the policy review has not finished", reasons: [] };
}

/** The trip limit the travel policy enforces, when the synced policy publishes one. */
function policyTripLimit(workspace: WorkspaceData): { amount: number; ruleId: string } | null {
  const budgetRules = workspace.policy_state?.constraint_set?.budget_rules;
  if (budgetRules == null || typeof budgetRules !== "object") {
    return null;
  }
  const rules = budgetRules as { max_trip_total_usd?: unknown; rule_id?: unknown };
  const amount = rules.max_trip_total_usd;
  if (typeof amount !== "number" || !Number.isFinite(amount) || amount <= 0) {
    return null;
  }
  return { amount, ruleId: typeof rules.rule_id === "string" ? rules.rule_id : "policy limit" };
}

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "Not set";
  }
  const parsed = new Date(`${value}T00:00:00`);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
}

export function ApprovalPacket({
  workspace,
  onPrint,
  prices = null,
  requesterName = null,
  preparedOn = new Date(),
}: ApprovalPacketProps) {
  const trip = workspace.trip_record.trip;
  const frame = trip.trip_frame;
  const origin = (frame as { origin?: string | null }).origin ?? null;
  const destinations = frame.primary_regions.join(", ") || "Not set";
  const travelerParty = frame.traveler_party;
  const policy = describePolicyResult(workspace);

  const pricedComponents = (prices?.components ?? []).filter(
    (component) => component.typical_amount != null
  );
  const unpricedComponents = (prices?.components ?? []).filter(
    (component) => component.typical_amount == null
  );
  const flight = (prices?.components ?? []).find((component) => component.component === "transport");
  const requester =
    requesterName?.trim() || prices?.total?.price_source.attributed_to || "Not recorded";

  const budget = workspace.budget_state.summary;
  const hasBudgetCap = budget.has_budget_plan === true && budget.planned_total > 0;
  const total = prices?.total ?? null;
  const totalAmount = total?.typical_amount ?? null;
  const headroom =
    hasBudgetCap && totalAmount != null && total?.currency === budget.currency
      ? budget.planned_total - totalAmount
      : null;

  return (
    <section className="approval-packet" aria-label="Approval packet" data-testid="approval-packet-document">
      <div className="approval-packet-actions no-print">
        <button type="button" onClick={onPrint}>Print / Export</button>
      </div>

      <p className="status-label">Travel approval request</p>
      <h2>{trip.title}</h2>
      {trip.summary ? <p data-testid="approval-packet-purpose">{trip.summary}</p> : null}

      <dl className="workspace-meta approval-packet-meta">
        <div>
          <dt>Requested by</dt>
          <dd data-testid="approval-packet-requester">{requester}</dd>
        </div>
        <div>
          <dt>Prepared</dt>
          <dd>{preparedOn.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}</dd>
        </div>
        <div>
          <dt>Journey</dt>
          <dd data-testid="approval-packet-journey">
            {origin ? `${origin} → ${destinations}` : destinations}
          </dd>
        </div>
        <div>
          <dt>Dates</dt>
          <dd>
            {formatDate(frame.start_date)} to {formatDate(frame.end_date)}
          </dd>
        </div>
        <div>
          <dt>Travellers</dt>
          <dd>
            {travelerParty
              ? `${travelerParty.traveler_count} ${travelerParty.traveler_count === 1 ? "traveller" : "travellers"}`
              : "Not set"}
          </dd>
        </div>
        {travelerParty?.notes ? (
          <div>
            <dt>Notes</dt>
            <dd>{travelerParty.notes}</dd>
          </div>
        ) : null}
      </dl>

      <section>
        <h3>Costs</h3>
        {pricedComponents.length === 0 ? (
          <p data-testid="approval-packet-unpriced-notice" role="note">
            <strong>This trip has no price.</strong> No source has quoted it, so this packet
            carries no cost figure. Enter the amounts you already hold on the Budget tab and
            they will appear here, attributed to you.
          </p>
        ) : (
          <table className="approval-packet-costs" data-testid="approval-packet-costs">
            <thead>
              <tr>
                <th scope="col">Item</th>
                <th scope="col">Amount</th>
                <th scope="col">Source</th>
              </tr>
            </thead>
            <tbody>
              {pricedComponents.map((component) => (
                <tr key={component.component}>
                  <td>{component.label}</td>
                  <td>{formatMoney({ currency: component.currency, typical_amount: component.typical_amount })}</td>
                  <td>
                    {component.note ? `${component.note}. ` : ""}
                    {component.price_source
                      ? `Entered by ${component.price_source.attributed_to} on ${component.price_source.captured_at.slice(0, 10)}`
                      : null}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th scope="row">Total</th>
                <td data-testid="approval-packet-trip-cost">{formatMoney(total)}</td>
                <td>{unpricedComponents.length > 0 ? `${unpricedComponents.length} item(s) not priced` : null}</td>
              </tr>
            </tfoot>
          </table>
        )}
        {flight && flight.typical_amount != null ? (
          <ul className="approval-packet-fare-detail" data-testid="approval-packet-fare-detail">
            <li>
              Lowest fare found for the same journey:{" "}
              {flight.lowest_amount != null
                ? formatMoney({ currency: flight.currency, typical_amount: flight.lowest_amount })
                : "not given"}
            </li>
            <li>Cabin: {flight.cabin_class ? flight.cabin_class.replace(/_/g, " ") : "not given"}</li>
            <li>
              Fare evidence:{" "}
              {flight.evidence_attested
                ? "the traveller holds a screenshot or quote and will provide it"
                : "not stated"}
            </li>
          </ul>
        ) : null}
        {(() => {
          const limit = policyTripLimit(workspace);
          if (limit == null) {
            return null;
          }
          const limitMoney = { currency: "USD", typical_amount: limit.amount };
          const under =
            totalAmount != null && total?.currency === "USD" ? limit.amount - totalAmount : null;
          return (
            <p data-testid="approval-packet-policy-limit">
              {`Travel policy limit ${formatMoney(limitMoney)} (rule ${limit.ruleId})`}
              {under != null
                ? `: this trip is ${formatMoney({ currency: "USD", typical_amount: Math.abs(under) })} ${under >= 0 ? "under" : "over"} it.`
                : "."}
            </p>
          );
        })()}
        <p data-testid="approval-packet-budget">
          {hasBudgetCap
            ? headroom != null
              ? `Budget cap ${formatMoney({ currency: budget.currency, typical_amount: budget.planned_total })}: this trip is ${formatMoney({ currency: budget.currency, typical_amount: Math.abs(headroom) })} ${headroom >= 0 ? "under" : "over"} it.`
              : `Budget cap ${formatMoney({ currency: budget.currency, typical_amount: budget.planned_total })}.`
            : "No budget cap is set for this trip in the planner."}
        </p>
      </section>

      <section>
        <h3>Travel policy</h3>
        <p data-testid="approval-packet-verdict">
          <strong>{policy.label}</strong>
        </p>
        {policy.reasons.length > 0 ? (
          <ul data-testid="approval-packet-policy-reasons">
            {policy.reasons.map((reason) => (
              <li key={reason.code}>
                {reason.text}
                {reason.whatToDo ? ` ${reason.whatToDo}` : ""} <span className="muted-copy">(rule {reason.code})</span>
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section className="approval-packet-signoff" aria-label="Approver decision">
        <h3>Approver decision</h3>
        <dl>
          <div><dt>Approver</dt><dd className="signoff-line" /></div>
          <div><dt>Decision</dt><dd className="signoff-line">Approved / Not approved</dd></div>
          <div><dt>Signature</dt><dd className="signoff-line" /></div>
          <div><dt>Date</dt><dd className="signoff-line" /></div>
        </dl>
      </section>
    </section>
  );
}

