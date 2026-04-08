import { useEffect, useRef } from "react";

import type { PlannerPanelState } from "../../../../bundle/planner/orchestration-contracts";

type PlannerSidePanelController = {
  replaceState: (nextData: PlannerPanelState) => void;
  destroy: () => void;
};

type PlannerDecisionAnswerEvent = CustomEvent<{
  trip_id: string;
  decision_id: string;
  choice: string;
}>;

type PlannerResponseEvent = CustomEvent<{
  action_type?: string;
  option_id: string;
  decision_id: string | null;
}>;

export function PlannerSidePanelSurface({
  state,
  onDecisionAnswer,
  onOptionFeedback,
}: {
  state: PlannerPanelState;
  onDecisionAnswer: (decisionId: string, choice: string) => void;
  onOptionFeedback: (optionId: string, actionType: string, decisionId: string | null) => void;
}) {
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

  useEffect(() => {
    const mountNode = mountRef.current;
    if (!mountNode) {
      return;
    }

    function handleDecisionAnswer(event: Event) {
      const detail = (event as PlannerDecisionAnswerEvent).detail;
      onDecisionAnswer(detail.decision_id, detail.choice);
    }

    function handlePlannerResponse(event: Event) {
      const detail = (event as PlannerResponseEvent).detail;
      onOptionFeedback(detail.option_id, detail.action_type ?? "accept", detail.decision_id ?? null);
    }

    mountNode.addEventListener("planner-decision-answer", handleDecisionAnswer as EventListener);
    mountNode.addEventListener("planner-response-accept", handlePlannerResponse as EventListener);
    mountNode.addEventListener("planner-response-reject", handlePlannerResponse as EventListener);
    mountNode.addEventListener("planner-response-revise", handlePlannerResponse as EventListener);
    mountNode.addEventListener(
      "planner-response-save-as-fallback",
      handlePlannerResponse as EventListener
    );
    mountNode.addEventListener(
      "planner-response-do-more-before-asking-again",
      handlePlannerResponse as EventListener
    );

    return () => {
      mountNode.removeEventListener(
        "planner-decision-answer",
        handleDecisionAnswer as EventListener
      );
      mountNode.removeEventListener("planner-response-accept", handlePlannerResponse as EventListener);
      mountNode.removeEventListener("planner-response-reject", handlePlannerResponse as EventListener);
      mountNode.removeEventListener("planner-response-revise", handlePlannerResponse as EventListener);
      mountNode.removeEventListener(
        "planner-response-save-as-fallback",
        handlePlannerResponse as EventListener
      );
      mountNode.removeEventListener(
        "planner-response-do-more-before-asking-again",
        handlePlannerResponse as EventListener
      );
    };
  }, [onDecisionAnswer, onOptionFeedback]);

  return <div ref={mountRef} className="planner-panel-host" />;
}
