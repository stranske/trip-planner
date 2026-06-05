import type { ReactNode } from "react";

type BudgetPanelProps = {
  children: ReactNode;
  labelledBy: string;
};

export function BudgetPanel({ children, labelledBy }: BudgetPanelProps) {
  return (
    <section
      id="workspace-panel-budget"
      role="tabpanel"
      aria-labelledby={labelledBy}
      data-testid="workspace-panel-budget"
    >
      {children}
    </section>
  );
}
