/**
 * Documentation example helpers for consuming planner orchestration outputs.
 *
 * @import {
 *   PlannerPanelState,
 *   PolicyEvaluationRecord,
 * } from "../../bundle/planner/orchestration-contracts"
 */

export const POLICY_STATUS_COMPONENT_MAP = {
  compliant: {
    posture_tone: "positive",
    readiness_label: "ready to submit",
    components: [
      "renderPolicyPostureDisplayComponent",
      "renderComparablesDisplayComponent",
      "renderJustificationBurdenComponent",
      "renderProposalReadinessIndicatorComponent",
    ],
  },
  exception_required: {
    posture_tone: "caution",
    readiness_label: "exception packet ready",
    components: [
      "renderPolicyPostureDisplayComponent",
      "renderComparablesDisplayComponent",
      "renderJustificationBurdenComponent",
      "renderProposalReadinessIndicatorComponent",
    ],
  },
  non_compliant: {
    posture_tone: "critical",
    readiness_label: "blocked",
    components: [
      "renderPolicyPostureDisplayComponent",
      "renderComparablesDisplayComponent",
      "renderJustificationBurdenComponent",
      "renderProposalReadinessIndicatorComponent",
    ],
  },
};

/**
 * @param {PlannerPanelState} panelState
 * @returns {{
 *   summary: {
 *     trip_id: string,
 *     mode: string,
 *     active_signals: string[],
 *   },
 *   sections: {
 *     outputs: number,
 *     decisions: number,
 *     options: number,
 *     approval: boolean,
 *   },
 *   approval: {
 *     status: string | null,
 *     mapped_components: string[],
 *   },
 * }}
 */
export function buildPlannerUiConsumptionExample(panelState) {
  const policyStatus = panelState.policy_evaluation?.status ?? null;

  return {
    summary: {
      trip_id: panelState.trip.trip_id,
      mode: panelState.trip.mode,
      active_signals: [
        `${panelState.outputs.length} outputs`,
        `${panelState.pending_decisions.length} pending decisions`,
        `${panelState.option_set.options.length} options`,
      ],
    },
    sections: {
      outputs: panelState.outputs.length,
      decisions: panelState.pending_decisions.length,
      options: panelState.option_set.options.length,
      approval: Boolean(panelState.policy_evaluation && panelState.proposal),
    },
    approval: {
      status: policyStatus,
      mapped_components: policyStatus ? POLICY_STATUS_COMPONENT_MAP[policyStatus].components : [],
    },
  };
}

/**
 * @param {PolicyEvaluationRecord | null} policyEvaluation
 * @returns {{
 *   status: string,
 *   posture_tone: string,
 *   readiness_label: string,
 *   blocking_failure_count: number,
 *   approval_requirement_count: number,
 *   mapped_components: string[],
 * }}
 */
export function mapPolicyStateToUiComponents(policyEvaluation) {
  if (!policyEvaluation) {
    return {
      status: "inactive",
      posture_tone: "neutral",
      readiness_label: "not rendered",
      blocking_failure_count: 0,
      approval_requirement_count: 0,
      mapped_components: [],
    };
  }

  const componentMap = POLICY_STATUS_COMPONENT_MAP[policyEvaluation.status];

  return {
    status: policyEvaluation.status,
    posture_tone: componentMap.posture_tone,
    readiness_label: componentMap.readiness_label,
    blocking_failure_count: policyEvaluation.failure_reasons.filter(
      (failure) => failure.severity === "blocking"
    ).length,
    approval_requirement_count: policyEvaluation.approval_requirements.length,
    mapped_components: componentMap.components,
  };
}
