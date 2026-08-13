import type { ReactNode } from "react";

type PolicyPanelProps = {
  approvalPacketContent: ReactNode | null;
  approvalDetailsContent?: ReactNode | null;
  grid?: boolean;
  noPacketAction?: {
    onPrepare: () => void;
  } | null;
};

export function PolicyPanel({
  approvalPacketContent,
  approvalDetailsContent = null,
  grid = false,
  noPacketAction = null,
}: PolicyPanelProps) {
  const content = (
    <>
      {noPacketAction ? (
        <section className="status-card" data-testid="approval-packet">
          <p className="status-label">Approval packet</p>
          <h2>No approval packet yet</h2>
          <p className="muted-copy">
            Approval packet records have not been saved for this workspace yet.
          </p>
          <p className="muted-copy">
            Start in Plan to prepare the trip details that policy review needs.
          </p>
          <button type="button" onClick={noPacketAction.onPrepare}>
            Prepare approval packet
          </button>
        </section>
      ) : approvalPacketContent ? (
        <section className="status-card" data-testid="approval-packet">
          {approvalPacketContent}
        </section>
      ) : null}
      {approvalDetailsContent ? (
        <section className="status-card" data-testid="tpp-label">
          {approvalDetailsContent}
        </section>
      ) : null}
    </>
  );

  return grid ? <div className="workspace-grid">{content}</div> : content;
}
