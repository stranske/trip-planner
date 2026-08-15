import type { ReactNode } from "react";

import type { WorkspaceData } from "../../../api/workspace";

export type PolicyPanelBlockingPrecondition = {
  message: string;
  actionLabel: string;
  onSatisfy: () => void;
};

export type PolicyPanelView =
  | {
      kind: "not-evaluated";
      onPrepare: () => void;
      blockingPrecondition?: PolicyPanelBlockingPrecondition;
    }
  | {
      kind: "compliant";
      summary: string;
    }
  | {
      kind: "non-compliant";
      issueCodes: string[];
      summary: string;
    }
  | {
      kind: "service-unavailable";
      message: string;
      onRetry: () => void;
    };

type PolicyPanelProps = {
  view: PolicyPanelView;
  approvalDetailsContent?: ReactNode | null;
  grid?: boolean;
  statusMessage?: string | null;
};

function isFailedTransportStatus(status: string | null | undefined): boolean {
  return status != null && ["failed", "error", "errored", "rejected", "invalid"].includes(status);
}

export function derivePolicyPanelView(
  workspace: WorkspaceData,
  handlers: {
    onPrepare: () => void;
    onRetry: () => void;
    onSatisfyPrecondition: () => void;
  }
): PolicyPanelView {
  const proposal = workspace.proposal_state;
  if (proposal == null) {
    return {
      kind: "not-evaluated",
      onPrepare: handlers.onPrepare,
      blockingPrecondition:
        workspace.trip_record.trip.mode !== "business"
          ? {
              message: "Approval packets are only available for business trips.",
              actionLabel: "Open Plan to review trip mode",
              onSatisfy: handlers.onSatisfyPrecondition,
            }
          : undefined,
    };
  }

  const summary = proposal.summary;
  const submissionStatus = summary.submission_status ?? proposal.submission_status;
  const transportStatus = summary.evaluation_transport_status ?? proposal.evaluation_status;

  if (isFailedTransportStatus(submissionStatus) || isFailedTransportStatus(transportStatus)) {
    return {
      kind: "service-unavailable",
      message:
        summary.submission_summary ??
        "The travel policy service is unavailable. Retry after confirming connectivity.",
      onRetry: handlers.onRetry,
    };
  }

  if (summary.approval_ready || summary.evaluation_result_status === "compliant") {
    return {
      kind: "compliant",
      summary:
        summary.follow_up_summary ??
        summary.submission_summary ??
        "This workspace complies with the configured travel policy.",
    };
  }

  if (summary.evaluation_result_status === "non_compliant") {
    const issueCodes =
      proposal.evaluation?.evaluation_result?.failure_reasons?.map((reason) => reason.code) ??
      summary.highlights ??
      [];
    return {
      kind: "non-compliant",
      issueCodes: issueCodes.length > 0 ? issueCodes : ["policy-review-required"],
      summary:
        summary.follow_up_summary ??
        summary.submission_summary ??
        "Policy review found blocking issues that must be resolved.",
    };
  }

  return {
    kind: "not-evaluated",
    onPrepare: handlers.onPrepare,
  };
}

function renderPolicyState(view: PolicyPanelView, statusMessage?: string | null) {
  const liveRegion = (
    <div aria-live="polite" role="status" data-testid="policy-status-live-region">
      {statusMessage ? <p className="muted-copy">{statusMessage}</p> : null}
    </div>
  );

  switch (view.kind) {
    case "not-evaluated":
      return (
        <section className="status-card" data-testid="policy-state-not-evaluated">
          <p className="status-label">Approval packet</p>
          <h2>Policy not yet evaluated</h2>
          <p className="muted-copy">
            Approval packet records have not been saved for this workspace yet, or evaluation is still
            pending.
          </p>
          {view.blockingPrecondition ? (
            <p className="planner-inline-error">{view.blockingPrecondition.message}</p>
          ) : null}
          {liveRegion}
          {view.blockingPrecondition ? (
            <button type="button" onClick={view.blockingPrecondition.onSatisfy}>
              {view.blockingPrecondition.actionLabel}
            </button>
          ) : (
            <button type="button" onClick={view.onPrepare}>
              Prepare approval packet
            </button>
          )}
        </section>
      );
    case "compliant":
      return (
        <section className="status-card" data-testid="policy-state-compliant">
          <p className="status-label">Approval packet</p>
          <h2>Policy compliant</h2>
          <p className="muted-copy">{view.summary}</p>
          {liveRegion}
        </section>
      );
    case "non-compliant":
      return (
        <section className="status-card" data-testid="policy-state-non-compliant">
          <p className="status-label">Approval packet</p>
          <h2>Policy non-compliant</h2>
          <p className="muted-copy">{view.summary}</p>
          <ul data-testid="policy-issue-codes">
            {view.issueCodes.map((code) => (
              <li key={code}>{code}</li>
            ))}
          </ul>
          {liveRegion}
        </section>
      );
    case "service-unavailable":
      return (
        <section className="status-card" data-testid="policy-state-service-unavailable">
          <p className="status-label">Approval packet</p>
          <h2>Policy service unavailable</h2>
          <p className="muted-copy">{view.message}</p>
          {liveRegion}
          <button type="button" onClick={view.onRetry}>
            Retry policy check
          </button>
        </section>
      );
  }
}

export function PolicyPanel({
  view,
  approvalDetailsContent = null,
  grid = false,
  statusMessage = null,
}: PolicyPanelProps) {
  const content = (
    <>
      {renderPolicyState(view, statusMessage)}
      {approvalDetailsContent ? (
        <section className="status-card" data-testid="tpp-label">
          {approvalDetailsContent}
        </section>
      ) : null}
    </>
  );

  return grid ? <div className="workspace-grid">{content}</div> : content;
}
