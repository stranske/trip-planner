import type { ReactNode } from "react";

export function PlanPanel({ children }: { children: ReactNode }) {
  return <div data-testid="workspace-panel-plan">{children}</div>;
}
