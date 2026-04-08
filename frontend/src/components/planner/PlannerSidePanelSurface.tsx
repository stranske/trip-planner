import { useEffect, useRef } from "react";

import type { PlannerPanelState } from "../../../../bundle/planner/orchestration-contracts";

type PlannerSidePanelController = {
  replaceState: (nextData: PlannerPanelState) => void;
  destroy: () => void;
};

export function PlannerSidePanelSurface({ state }: { state: PlannerPanelState }) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const controllerRef = useRef<PlannerSidePanelController | null>(null);

  useEffect(() => {
    let isCancelled = false;

    async function mountPlannerPanel() {
      if (!mountRef.current) {
        return;
      }

      // @ts-expect-error The planner bundle ships as plain JS outside the frontend package.
      const plannerModule = await import("../../../../bundle/planner/side-panel.js");

      if (isCancelled || !mountRef.current) {
        return;
      }

      controllerRef.current = plannerModule.renderPlannerSidePanel(mountRef.current, state);
    }

    void mountPlannerPanel();

    return () => {
      isCancelled = true;
      controllerRef.current?.destroy();
      controllerRef.current = null;
    };
  }, []);

  useEffect(() => {
    controllerRef.current?.replaceState(state);
  }, [state]);

  return <div ref={mountRef} className="planner-panel-host" />;
}
