import type { ReactNode } from "react";

type ComparePanelProps = {
  children: ReactNode;
  labelledBy: string;
};

export function ComparePanel({ children, labelledBy }: ComparePanelProps) {
  return (
    <section
      id="workspace-panel-compare"
      role="tabpanel"
      aria-labelledby={labelledBy}
      data-testid="workspace-panel-compare"
    >
      {children}
    </section>
  );
}
