import type { ReactNode } from "react";

type MapPanelProps = {
  children: ReactNode;
  labelledBy: string;
};

export function MapPanel({ children, labelledBy }: MapPanelProps) {
  return (
    <section
      id="workspace-panel-map"
      role="tabpanel"
      aria-labelledby={labelledBy}
      data-testid="workspace-panel-map"
    >
      {children}
    </section>
  );
}
