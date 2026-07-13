import type { ReactNode } from "react";

export function CostsPanel({ children, labelledBy }: { children: ReactNode; labelledBy: string }) {
  return (
    <section
      id="workspace-panel-costs"
      role="tabpanel"
      aria-labelledby={labelledBy}
      data-testid="workspace-panel-costs"
    >
      {children}
    </section>
  );
}
