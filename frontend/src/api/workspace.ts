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

export type PlanningMode = "delegated" | "collaborative" | "revealed-preference" | "in-trip";
export type RouteOptionState = "active" | "baseline" | "fallback" | "rejected" | "needs_research";
export type RouteOptionActionType = "make_baseline" | "keep" | "reject" | "reopen" | "revise";

export type RouteOptionAction = {
  action_type: RouteOptionActionType;
  label: string;
  description: string;
};

export type SessionState = {
  current_saved_scenario_id: string | null;
  active_budget_plan_id: string | null;
  selected_planning_mode: PlanningMode;
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

export type ScenarioRanking = {
  ranking_id: string;
  trip_id: string;
  title: string;
  summary: string;
  lead_scenario_id: string | null;
  source_result_set_id?: string | null;
  source_refs: string[];
  rows: Array<{
    scenario_id: string;
    title: string;
    rank: number;
    score: number;
    status: string;
    summary: string;
    scenario_kind: string;
    recommended_for_selection: boolean;
    feasible: boolean;
    route_sequence: string[];
    total_travel_minutes: number;
    total_transfer_count: number;
    estimated_total?: {
      currency: string;
      typical_amount: number;
    } | null;
    source_result_id?: string | null;
    supporting_option_ids: string[];
    objective_refs: string[];
    unresolved_tradeoffs: Array<{
      tradeoff_id: string;
      summary: string;
      severity: string;
    }>;
  }>;
};

export type RuntimeScenarioComparison = {
  title: string;
  summary: string;
  lead_scenario_id: string | null;
  comparison_axes: Array<{
    key: string;
    label: string;
    direction: "higher_better" | "lower_better";
  }>;
  scenarios: Array<{
    scenario_id: string;
    title: string;
    rank: number;
    status: string;
    state?: RouteOptionState;
    route_option_id?: string;
    purpose?: string;
    confidence?: number;
    unresolved_questions?: string[];
    open_question?: string | null;
    available_actions?: RouteOptionAction[];
    available_action?: RouteOptionAction | null;
    summary: string;
    comparison_note: string;
    option_count: number;
    route_sequence: string[];
    route_summary: string;
    recommended_for_selection: boolean;
    feasible: boolean;
    metrics: {
      score: number;
      travel_minutes: number;
      transfers: number;
      estimated_total: {
        currency: string;
        typical_amount: number;
      } | null;
    };
    delta: {
      score_delta: number;
      travel_minutes_delta: number;
      transfers_delta: number;
      estimated_total_delta: number | null;
    };
    highlights: string[];
  }>;
  source_refs: string[];
};

export type FeasibilitySummary = {
  assessment_count: number;
  recommended_bundle_count: number;
  blocking_bundle_count: number;
  attention_bundle_count: number;
  notes: string[];
  assessments: Array<{
    bundle_id: string;
    bundle_title: string;
    bundle_context: string;
    status: string;
    total_travel_minutes: number;
    total_transfer_count: number;
    friction_penalty_total: number;
  }>;
};

export type PlannerCheckpoint = {
  checkpoint_id: string;
  checkpoint_kind: string;
  turn_index: number;
  message_count: number;
  summary: string;
  source_message_ids: string[];
  created_at: string;
  updated_at: string;
};

export type PlannerMemoryArtifact = {
  memory_artifact_id: string;
  checkpoint_id: string | null;
  artifact_kind: string;
  title: string;
  summary: string;
  detail: string;
  source_message_ids: string[];
  tags: string[];
  created_at: string;
  updated_at: string;
};

export type PlannerMemoryState = {
  current_checkpoint_id: string | null;
  checkpoints: PlannerCheckpoint[];
  artifacts: PlannerMemoryArtifact[];
};

export type PlanningLedgerEntryType =
  | "option_considered"
  | "option_rejected"
  | "decision"
  | "assumption"
  | "open_question"
  | "constraint"
  | "source_reference";

export type PlanningLedgerEntryStatus =
  | "active"
  | "completed"
  | "rejected"
  | "superseded"
  | "deferred";

export type PlanningLedgerEntry = {
  ledger_entry_id: string;
  trip_id: string;
  session_state_id: string;
  item_type: PlanningLedgerEntryType;
  status: PlanningLedgerEntryStatus;
  category: string;
  summary: string;
  detail: string;
  source_message_ids: string[];
  source_refs: string[];
  related_option_id: string | null;
  related_decision_id: string | null;
  supersedes_entry_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type PlanningLedgerState = {
  entries: PlanningLedgerEntry[];
  summary: {
    active_decisions: PlanningLedgerEntry[];
    open_questions: PlanningLedgerEntry[];
    active_options: PlanningLedgerEntry[];
    rejected_options: PlanningLedgerEntry[];
    constraints: PlanningLedgerEntry[];
    assumptions: PlanningLedgerEntry[];
    source_references: PlanningLedgerEntry[];
  };
};

export type ActivityLogEntry = {
  activity_event_id: string;
  occurred_at: string;
  event_kind: string;
  summary: string;
};

export type PlannerToolCallResponse = {
  tool_name: string;
  status: string;
  summary: string;
  mutates_state: boolean;
  refs: string[];
  output: Record<string, unknown>;
};

export type PlannerTurnMetadata = {
  plan_maturity: string;
  task_class: string;
  visible_response_blocks: Array<{
    kind: string;
    title: string;
    items: string[];
  }>;
  debug_routing_details: Record<string, unknown>;
};

export type PlannerStructuredBlock = {
  kind: string;
  title: string;
  body: string;
  items: string[];
  metadata: Record<string, unknown>;
  hidden: boolean;
};

export type PlannerMessage = {
  message_id: string;
  role: "user" | "planner" | string;
  content: string;
  created_at: string;
  refs: string[];
  tool_calls: PlannerToolCallResponse[];
  structured_blocks: PlannerStructuredBlock[];
  turn_metadata?: PlannerTurnMetadata | null;
};

export type PlannerSessionResponse = {
  trip_id: string;
  session_state_id: string;
  conversation_id: string;
  resumed_at: string | null;
  session: SessionState;
  planner_panel_state: PlannerPanelState;
  planner_memory: PlannerMemoryState;
  available_tools: Array<{
    tool_name: string;
    description?: string;
    mutates_state?: boolean;
    [key: string]: unknown;
  }>;
  activity_log: ActivityLogEntry[];
  messages: PlannerMessage[];
};

export type WorkspaceUserSummary = {
  trip_title: string;
  trip_mode: "leisure" | "business";
  mode_label: string;
  status: "ready" | "partial" | "empty";
  headline: string;
  decided: string[];
  uncertain: string[];
};

export type WorkspaceNextStep = {
  title: string;
  summary: string;
  action_label: string | null;
  action_target: string | null;
  blocked: boolean;
};

export type WorkspaceBusinessSummary = {
  approval_status:
    | "not_applicable"
    | "not_ready"
    | "in_review"
    | "approved"
    | "needs_attention";
  headline: string;
  blockers: string[];
};

export type WorkspaceDebugSection = {
  title: string;
  payload: unknown;
};

export type WorkspaceDebugState = {
  sections: Record<string, WorkspaceDebugSection>;
};

export type WorkspacePanelVisibility = {
  show_budget_panel: boolean;
  show_policy_posture: boolean;
  show_proposal_panel: boolean;
  show_approval_readiness_panel: boolean;
};

export type WorkspacePolicyPresentation = {
  active_policy_state: boolean;
  posture_label: string;
  approval_status_label: string;
  next_step_label: string;
  summary: string;
};

export type WorkspaceViewModel = {
  user_summary: WorkspaceUserSummary;
  next_step: WorkspaceNextStep;
  panel_visibility: WorkspacePanelVisibility;
  policy_presentation: WorkspacePolicyPresentation;
  business_summary: WorkspaceBusinessSummary | null;
  debug_state: WorkspaceDebugState;
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
  ranking: ScenarioRanking;
  route_comparison: RuntimeScenarioComparison;
  runtime_scenario_comparison: RuntimeScenarioComparison;
  activity_log: ActivityLogEntry[];
  planner_memory: PlannerMemoryState;
  planning_ledger?: PlanningLedgerState;
  planner_panel_state: PlannerPanelState;
  runtime_state: {
    status: "ready" | "partial" | "empty";
    title: string;
    summary: string;
  };
  feasibility_summary: FeasibilitySummary;
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
    runtime_state: {
      status: "ready" | "partial" | "empty";
      title: string;
      summary: string;
    };
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
    } | null;
    summary: {
      submission_status?: string;
      submission_summary?: string;
      submission_requires_polling?: boolean;
      evaluation_transport_status?: string;
      evaluation_result_status?: string;
      approval_ready?: boolean;
      comparable_count?: number;
      highlights?: string[];
      follow_up_status?: string;
      follow_up_title?: string;
      follow_up_summary?: string;
    };
  } | null;
  view_model: WorkspaceViewModel | null;
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

export async function fetchPlannerSession(tripId: string): Promise<PlannerSessionResponse> {
  return fetchJson<PlannerSessionResponse>({
    path: `/api/planner/${tripId}/session`,
    credentials: "include",
  });
}

export async function submitPlannerTurn(
  tripId: string,
  message: string
): Promise<PlannerSessionResponse> {
  return fetchJson<PlannerSessionResponse>({
    path: `/api/planner/${tripId}/turns`,
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message }),
  });
}

export async function refreshWorkspaceProposalStatus(tripId: string): Promise<WorkspaceData["proposal_state"]> {
  const response = await fetchJson<{
    proposal_state: WorkspaceData["proposal_state"];
    summary: NonNullable<WorkspaceData["proposal_state"]>["summary"] | Record<string, never>;
  }>({
    path: `/api/workspace/${tripId}/proposal/refresh`,
    method: "POST",
    credentials: "include",
  });
  return response.proposal_state;
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

export async function updateWorkspacePlanningMode(
  tripId: string,
  planningMode: PlanningMode
): Promise<WorkspaceData> {
  return fetchJson<WorkspaceData>({
    path: `/api/workspace/${tripId}/planning-mode`,
    method: "PUT",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ planning_mode: planningMode }),
  });
}

export async function createPlanningLedgerEntry(
  tripId: string,
  payload: {
    item_type: PlanningLedgerEntryType;
    status?: PlanningLedgerEntryStatus;
    category?: string;
    summary: string;
    detail?: string;
    source_message_ids?: string[];
    source_refs?: string[];
    related_option_id?: string | null;
    related_decision_id?: string | null;
  }
): Promise<PlanningLedgerEntry> {
  return fetchJson<PlanningLedgerEntry>({
    path: `/api/workspace/${tripId}/planning-ledger`,
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function updatePlanningLedgerEntry(
  tripId: string,
  ledgerEntryId: string,
  payload: Partial<Pick<
    PlanningLedgerEntry,
    "status" | "category" | "summary" | "detail" | "source_message_ids" | "source_refs" | "supersedes_entry_id"
  >>
): Promise<PlanningLedgerEntry> {
  return fetchJson<PlanningLedgerEntry>({
    path: `/api/workspace/${tripId}/planning-ledger/${ledgerEntryId}`,
    method: "PATCH",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
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

export async function submitRouteOptionAction(
  tripId: string,
  optionId: string,
  actionType: RouteOptionActionType
): Promise<WorkspaceData> {
  return fetchJson<WorkspaceData>({
    path: `/api/workspace/${tripId}/route-options/${optionId}/action`,
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      action_type: actionType,
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
