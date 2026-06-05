import type { ReactNode } from "react";

type PlanPanelProps = {
  children: ReactNode;
  labelledBy: string;
};

export function PlanPanel({ children, labelledBy }: PlanPanelProps) {
  return (
    <div
      id="workspace-panel-plan"
      role="tabpanel"
      aria-labelledby={labelledBy}
      data-testid="workspace-panel-plan"
    >
      {children}
    </div>
  );
}
