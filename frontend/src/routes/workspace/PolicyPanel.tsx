import type { ReactNode } from "react";

type PolicyPanelProps = {
  children: ReactNode;
  labelledBy: string;
};

export function PolicyPanel({ children, labelledBy }: PolicyPanelProps) {
  return (
    <section
      id="workspace-panel-policy"
      role="tabpanel"
      aria-labelledby={labelledBy}
      data-testid="workspace-panel-policy"
    >
      {children}
    </section>
  );
}
