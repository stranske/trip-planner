import type { ReactNode } from "react";

type PolicyPanelProps = {
  approvalPacketContent: ReactNode | null;
  approvalDetailsContent?: ReactNode | null;
  grid?: boolean;
};

export function PolicyPanel({
  approvalPacketContent,
  approvalDetailsContent = null,
  grid = false,
}: PolicyPanelProps) {
  const content = (
    <>
      {approvalPacketContent ? (
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
