import type { RuntimeScenarioComparison, WorkspaceData } from "../api/workspace";

export const PROPOSAL_VERSION = "proposal-v3";

type PolicyContext = {
  organizationId: string;
  constraintSetId: string;
};

type ScenarioOption = RuntimeScenarioComparison["scenarios"][number];

export type ProposalSubmissionPayload = {
  proposal: Record<string, unknown>;
  request: Record<string, unknown>;
  proposal_version: string;
  scenario_id: string | null;
};

export type ProposalEvaluationPayload = {
  request: Record<string, unknown>;
  proposal_version: string;
  scenario_id: string | null;
};

function routeComparison(workspace: WorkspaceData): RuntimeScenarioComparison {
  return workspace.route_comparison ?? workspace.runtime_scenario_comparison;
}

export function resolveSubmissionScenarioId(
  workspace: WorkspaceData,
  scenarioId?: string | null
): string | null {
  if (scenarioId) {
    return scenarioId;
  }

  const savedScenario =
    workspace.saved_scenarios.find(
      (record) => record.saved_scenario_id === workspace.session.current_saved_scenario_id
    ) ?? workspace.saved_scenarios[0];
  const activeVersion = savedScenario?.versions.find(
    (version) => version.version_id === savedScenario.current_version_id
  );
  const itineraryScenarioId = activeVersion?.snapshot_refs.itinerary_scenario_id;
  if (itineraryScenarioId) {
    return itineraryScenarioId;
  }

  const comparison = routeComparison(workspace);
  return comparison.lead_scenario_id ?? comparison.scenarios[0]?.scenario_id ?? null;
}

function selectedScenario(
  workspace: WorkspaceData,
  scenarioId?: string | null
): ScenarioOption | null {
  const comparison = routeComparison(workspace);
  const resolvedId = resolveSubmissionScenarioId(workspace, scenarioId);
  if (!resolvedId) {
    return comparison.scenarios[0] ?? null;
  }
  return comparison.scenarios.find((scenario) => scenario.scenario_id === resolvedId) ?? null;
}

function readPolicyContext(workspace: WorkspaceData): PolicyContext | null {
  const policyPayload = workspace.view_model?.debug_state?.sections?.policy_state?.payload;
  if (policyPayload != null && typeof policyPayload === "object") {
    const policy = policyPayload as Record<string, unknown>;
    const organizationId =
      typeof policy.organization_id === "string" ? policy.organization_id : null;
    const constraintSet =
      policy.constraint_set != null && typeof policy.constraint_set === "object"
        ? (policy.constraint_set as Record<string, unknown>)
        : null;
    const constraintSetId =
      constraintSet != null && typeof constraintSet.policy_id === "string"
        ? constraintSet.policy_id
        : null;
    if (organizationId && constraintSetId) {
      return { organizationId, constraintSetId };
    }
  }

  return null;
}

function moneyRange(
  amount: number,
  currency: string
): { currency: string; typical_amount: number; min_amount: number; max_amount: number } {
  return {
    currency,
    typical_amount: amount,
    min_amount: amount,
    max_amount: amount,
  };
}

export function buildProposalSubmissionPayload(
  workspace: WorkspaceData,
  scenarioId?: string | null
): ProposalSubmissionPayload {
  const trip = workspace.trip_record.trip;
  const tripId = trip.trip_id;
  const proposalId = `proposal:${tripId}`;
  const scenario = selectedScenario(workspace, scenarioId);
  const resolvedScenarioId = scenario?.scenario_id ?? resolveSubmissionScenarioId(workspace, scenarioId);
  const policyContext = readPolicyContext(workspace);
  if (policyContext == null) {
    throw new Error("Policy context is not available for this workspace.");
  }
  const { constraintSetId, organizationId } = policyContext;
  const estimatedTotal = scenario?.metrics.estimated_total;
  const currency =
    estimatedTotal?.currency ?? workspace.budget_state.summary.currency ?? "USD";
  const typicalAmount =
    estimatedTotal?.typical_amount ?? workspace.budget_state.summary.planned_total ?? 0;
  const scenarioLabel = scenario?.title ?? trip.title;

  const selectedOption: Record<string, unknown> = {
    category: "itinerary",
    option_id: resolvedScenarioId ?? `option:${tripId}`,
    label: scenarioLabel,
    estimated_cost: moneyRange(typicalAmount, currency),
    justification_refs: scenario?.highlights?.length
      ? scenario.highlights
      : ["workspace-scenario"],
  };

  const proposal = {
    proposal_id: proposalId,
    trip_id: tripId,
    mode: "business",
    traveler_context: {
      employee_type: "employee",
      traveler_experience: "occasional",
      loyalty_programs: [],
      mobility_or_access_needs: [],
    },
    selected_options: [selectedOption],
    cost_summary: {
      currency,
      total_estimated_cost: typicalAmount,
      category_estimates: typicalAmount > 0 ? { itinerary: typicalAmount } : {},
      notes: scenario?.summary ? [scenario.summary] : ["Built from the selected workspace scenario."],
    },
    comparables: [
      {
        category: "itinerary",
        label: scenarioLabel,
        estimated_cost: moneyRange(typicalAmount, currency),
        notes: scenario?.highlights?.length ? scenario.highlights.slice(0, 2) : ["Selected scenario"],
      },
    ],
    approval_notes: ["Submitted from the workspace Policy tab."],
    constraint_set_id: constraintSetId,
  };

  const requestId = `req-submit-${tripId}`;
  const request = {
    operation: "submit_proposal",
    request_id: requestId,
    correlation_id: {
      value: `corr-submit-${tripId}`,
      issued_by: "trip-planner",
    },
    payload: {
      proposal_ref: proposalId,
      submission_mode: "queue",
    },
    transport_pattern: "deferred",
    organization_id: organizationId,
    trip_id: tripId,
    proposal_id: proposalId,
    submitted_at: new Date().toISOString(),
  };

  return {
    proposal,
    request,
    proposal_version: PROPOSAL_VERSION,
    scenario_id: resolvedScenarioId,
  };
}

export function buildProposalEvaluationPayload(
  workspace: WorkspaceData,
  executionId: string,
  scenarioId?: string | null
): ProposalEvaluationPayload {
  const tripId = workspace.trip_record.trip.trip_id;
  const proposalId = `proposal:${tripId}`;
  const resolvedScenarioId = resolveSubmissionScenarioId(workspace, scenarioId);
  const policyContext = readPolicyContext(workspace);
  if (policyContext == null) {
    throw new Error("Policy context is not available for this workspace.");
  }
  const { organizationId } = policyContext;
  const requestId = `req-eval-${tripId}`;

  return {
    request: {
      operation: "fetch_evaluation_result",
      request_id: requestId,
      correlation_id: {
        value: `corr-eval-${tripId}`,
        issued_by: "trip-planner",
      },
      payload: {
        execution_id: executionId,
      },
      transport_pattern: "async",
      organization_id: organizationId,
      trip_id: tripId,
      proposal_id: proposalId,
      submitted_at: new Date().toISOString(),
    },
    proposal_version: PROPOSAL_VERSION,
    scenario_id: resolvedScenarioId,
  };
}
