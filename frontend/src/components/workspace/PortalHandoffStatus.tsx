import type { WorkspaceData } from "../../api/workspace";

type Handoff = NonNullable<WorkspaceData["proposal_state"]>["portal_handoff"];

const labels: Record<string, string> = {
  unknown: "Unknown",
  submitted: "Submitted",
  pending_review: "Pending review",
  decision_recorded: "Decision recorded",
  approved: "Approved",
  rejected: "Rejected",
  changes_requested: "Changes requested",
};

export function PortalHandoffStatus({
  handoff,
  busy,
  onRefresh,
}: {
  handoff: Handoff;
  busy: boolean;
  onRefresh: () => void;
}) {
  if (handoff?.status !== "prepared") return null;
  const current = handoff.receipt_status === "current";
  const historical = handoff.receipt_status !== undefined && !current;
  const submission = historical
    ? handoff.last_manager_submission_status
    : handoff.manager_submission_status;
  const decision = historical ? handoff.last_manager_decision : handoff.manager_decision;
  return (
    <div role="status" aria-label="Approver portal handoff status">
      <p className="muted-copy">Handoff prepared.</p>
      <dl className="workspace-meta">
        <div>
          <dt>{historical ? "Last recorded manager submission" : "Manager submission"}</dt>
          <dd>{labels[submission ?? "unknown"] ?? "Unknown"}</dd>
        </div>
        <div>
          <dt>{historical ? "Last recorded manager decision" : "Manager decision"}</dt>
          <dd>{labels[decision ?? "unknown"] ?? "Unknown"}</dd>
        </div>
      </dl>
      {handoff.receipt_observed_at ? (
        <p className="muted-copy">Last observed: {handoff.receipt_observed_at}</p>
      ) : null}
      <p className="muted-copy">
        {current
          ? "Travel-Plan-Permission recorded this state for the checked trip snapshot."
          : handoff.receipt_status === "stale"
            ? "This receipt is stale. Check the changed trip and prepare a new handoff."
            : historical
              ? "Current receipt unavailable. Any last recorded state is historical."
              : "No authenticated receipt has been observed. Complete and submit the request there."}
      </p>
      <button type="button" className="secondary-button" disabled={busy} onClick={onRefresh}>
        Refresh approver status
      </button>
    </div>
  );
}
