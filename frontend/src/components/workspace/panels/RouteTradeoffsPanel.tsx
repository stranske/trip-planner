import type { ReactNode } from "react";

type RouteTradeoffsPanelProps = {
  compactLayout: boolean;
  showPolicyPosture: boolean;
  hasScenarios: boolean;
  emptyMessage: string;
  children: ReactNode;
};

export function RouteTradeoffsPanel({
  compactLayout,
  showPolicyPosture,
  hasScenarios,
  emptyMessage,
  children,
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
      {hasScenarios ? children : <p className="muted-copy">{emptyMessage}</p>}
    </section>
  );
}
