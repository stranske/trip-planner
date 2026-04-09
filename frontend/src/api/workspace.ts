import { fetchJson } from "../lib/api/client";
import type { PlannerPanelState } from "../../../bundle/planner/orchestration-contracts";

export type TripFrame = {
  start_date: string | null;
  end_date: string | null;
  duration_days: number | null;
  primary_regions: string[];
};

export type TripRecord = {
  trip: {
    trip_id: string;
    title: string;
    summary: string;
    status: string;
    mode: string;
    trip_frame: TripFrame;
  };
  artifact_refs: {
    saved_scenario_ids: string[];
    scenario_search_id: string | null;
    session_state_id: string | null;
    budget_state_id: string | null;
  };
};

export type SessionState = {
  current_saved_scenario_id: string | null;
  active_budget_plan_id: string | null;
  pending_decisions: Array<{
    decision_id: string;
    title: string;
    prompt: string;
    blocking: boolean;
  }>;
  interaction_state: {
    interaction_style: string;
    initiative_level: string;
    checkpoint_frequency: string;
  };
  recent_option_presentations: Array<{
    presentation_id: string;
    summary: string;
    surfaced_option_ids: string[];
  }>;
};

export type BudgetCategorySummary = {
  category_key: string;
  label: string;
  currency: string;
  planned_amount: number;
  actual_amount: number;
  remaining_amount: number;
  flexibility: string;
};

export type BudgetCategoryAllocation = {
  category_key: string;
  label: string;
  planned_amount: number;
  currency: string;
  flexibility: string;
  notes: string[];
};

export type BudgetScenario = {
  scenario_budget_id: string;
  saved_scenario_id: string | null;
  title: string;
  summary: string;
  tags: string[];
  notes: string[];
  allocations: BudgetCategoryAllocation[];
};

export type BudgetPlan = {
  budget_plan_id: string;
  trip_id: string;
  owner_profile_id: string;
  title: string;
  mode: string;
  created_at: string;
  updated_at: string;
  scenario_budgets: BudgetScenario[];
  current_scenario_budget_id: string | null;
  currency: string;
  schema_version: string;
  tags: string[];
  notes: string[];
};

export type BudgetVersion = {
  version_id: string;
  budget_plan_id: string;
  recorded_at: string;
  summary: string;
};

export type ActualSpendEvent = {
  spend_event_id: string;
  trip_id: string;
  budget_plan_id: string;
  category_key: string;
  amount: number;
  currency: string;
  occurred_at: string;
  source_kind: string;
  source_context: string;
  scenario_budget_id: string | null;
  saved_scenario_id: string | null;
  merchant_name: string;
  source_ref: string | null;
  notes: string[];
};

export type BudgetSummary = {
  currency: string;
  has_budget_plan: boolean;
  current_scenario_budget_id: string | null;
  current_scenario_title: string | null;
  planned_total: number;
  actual_total: number;
  remaining_total: number;
  spend_event_count: number;
  version_count: number;
  suggested_categories: string[];
  category_summaries: BudgetCategorySummary[];
};

export type BudgetWorkspaceState = {
  budget_plan: BudgetPlan | null;
  versions: BudgetVersion[];
  spend_events: ActualSpendEvent[];
  summary: BudgetSummary;
};

export type SavedScenarioRecord = {
  saved_scenario_id: string;
  current_version_id: string;
  versions: Array<{
    version_id: string;
    title: string;
    label: string;
    summary: string;
    snapshot_refs: {
      itinerary_scenario_id?: string;
    };
  }>;
};

export type ScenarioSearchResult = {
  title: string;
  scenarios: Array<{
    scenario_id: string;
    title: string;
    rank: number;
    score: number;
    scenario_summary: {
      headline: string;
      scenario_kind: string;
      recommended_for_selection: boolean;
      total_travel_minutes: number;
      total_transfer_count: number;
      route_sequence: string[];
    };
    unresolved_tradeoffs: Array<{
      tradeoff_id: string;
      summary: string;
      severity: string;
    }>;
  }>;
};

export type WorkspaceData = {
  trip_record: TripRecord;
  session: SessionState;
  saved_scenarios: SavedScenarioRecord[];
  scenario_comparison: {
    summary: string;
    outcome: string;
    focus_areas: string[];
  } | null;
  scenario_search: ScenarioSearchResult;
  activity_log: Array<{
    activity_event_id: string;
    occurred_at: string;
    event_kind: string;
    summary: string;
  }>;
  planner_panel_state: PlannerPanelState;
  inventory_summary: {
    bundle_count: number;
    bundles: Array<{
      bundle_id: string;
      title: string;
      bundle_context: string;
      summary: string;
      destination_names: string[];
      option_count: number;
      strengths: string[];
      tradeoffs: string[];
    }>;
    notes: string[];
  };
  budget_state: BudgetWorkspaceState;
  proposal_state: {
    proposal_state_id: string;
    trip_id: string;
    proposal_id: string;
    proposal_version: string;
    scenario_id: string | null;
    execution_id: string | null;
    submission_status: string;
    evaluation_status: string | null;
    proposal: {
      proposal_id: string;
      approval_notes?: string[];
      comparables?: Array<{
        category: string;
        label: string;
        vendor: string;
        booking_channel: string;
        estimated_cost: {
          currency: string;
          typical_amount: number;
        };
        notes: string[];
      }>;
    };
    evaluation: {
      evaluation_result?: {
        evaluation_id: string;
        status: string;
        approval_requirements: Array<{
          role: string;
          reason: string;
          mandatory: boolean;
        }>;
        failure_reasons: Array<{
          code: string;
          message: string;
          severity: string;
          related_category: string;
        }>;
        notes: string[];
        compliance_score: number;
      };
    };
    follow_up: {
      status: string;
      path: string;
      title: string;
      summary: string;
      recommended_action?: string;
      recommended_label?: string;
      alternatives?: Array<{
        category: string;
        summary: string;
        rationale: string;
        comparable_ref?: string | null;
      }>;
      guidance?: string[];
      notes?: string[];
      selected_alternative?: {
        category?: string;
        summary?: string;
        rationale?: string;
        comparable_ref?: string | null;
      } | null;
      requested_exception?: {
        exception_type: string;
        reason: string;
        requested_approval_roles: string[];
        notes: string[];
      } | null;
    };
    summary: {
      submission_status?: string;
      submission_summary?: string;
      evaluation_result_status?: string;
      approval_ready?: boolean;
      comparable_count?: number;
      highlights?: string[];
      follow_up_status?: string;
      follow_up_title?: string;
      follow_up_summary?: string;
    };
  } | null;
};

export type BudgetPlanUpsertPayload = {
  title: string;
  currency: string;
  current_scenario_budget_id?: string | null;
  tags?: string[];
  notes?: string[];
  scenario_budgets: Array<{
    scenario_budget_id?: string | null;
    saved_scenario_id?: string | null;
    title: string;
    summary?: string;
    tags?: string[];
    notes?: string[];
    allocations: Array<{
      category_key: string;
      label: string;
      planned_amount: number;
      currency?: string;
      flexibility?: string;
      notes?: string[];
    }>;
  }>;
  summary?: string;
};

export type ActualSpendEventUpsertPayload = {
  category_key: string;
  amount: number;
  currency?: string | null;
  occurred_at?: string | null;
  source_kind: string;
  source_context: string;
  scenario_budget_id?: string | null;
  saved_scenario_id?: string | null;
  merchant_name?: string;
  source_ref?: string | null;
  notes?: string[];
};

export async function fetchWorkspace(tripId: string): Promise<WorkspaceData> {
  return fetchJson<WorkspaceData>({
    path: `/api/workspace/${tripId}`,
    credentials: "include",
  });
}

export async function answerPlannerDecision(
  tripId: string,
  decisionId: string,
  choice: string
): Promise<WorkspaceData> {
  return fetchJson<WorkspaceData>({
    path: `/api/workspace/${tripId}/planner/decisions/${decisionId}/answer`,
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ choice }),
  });
}

export async function submitPlannerOptionFeedback(
  tripId: string,
  optionId: string,
  actionType: "accept" | "reject" | "revise" | "save_as_fallback" | "do_more_before_asking_again",
  decisionId: string | null
): Promise<WorkspaceData> {
  return fetchJson<WorkspaceData>({
    path: `/api/workspace/${tripId}/planner/options/${optionId}/feedback`,
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      action_type: actionType,
      decision_id: decisionId,
    }),
  });
}

export async function saveWorkspaceBudget(
  tripId: string,
  payload: BudgetPlanUpsertPayload
): Promise<BudgetWorkspaceState> {
  return fetchJson<BudgetWorkspaceState>({
    path: `/api/workspace/${tripId}/budget`,
    method: "PUT",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function recordWorkspaceSpendEvent(
  tripId: string,
  payload: ActualSpendEventUpsertPayload
): Promise<BudgetWorkspaceState> {
  return fetchJson<BudgetWorkspaceState>({
    path: `/api/workspace/${tripId}/budget/spend-events`,
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}
