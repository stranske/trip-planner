import type { ReactNode } from "react";

type NotebookPanelProps = {
  children: ReactNode;
  labelledBy: string;
};

export function NotebookPanel({ children, labelledBy }: NotebookPanelProps) {
  return (
    <section
      id="workspace-panel-notebook"
      role="tabpanel"
      aria-labelledby={labelledBy}
      data-testid="workspace-panel-notebook"
    >
      {children}
    </section>
  );
}
