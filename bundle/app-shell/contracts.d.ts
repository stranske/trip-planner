/**
 * Frontend declarations for the application shell layer.
 *
 * The shell composes persisted trip state, orchestration planner state,
 * and approval-readiness signals without redefining the underlying
 * domain contracts in UI-only shapes.
 */

import type { PlannerPanelState, TripRecord } from "../planner/orchestration-contracts";

export type AppRouteId =
  | "dashboard"
  | "trip_workspace"
  | "planner_workspace"
  | "approval_center";

export type TripMode = "leisure" | "business";

export type LaunchFlowId =
  | "new_leisure_trip"
  | "new_business_trip"
  | "resume_existing_trip";

export type WorkspaceStatus = "ready" | "loading" | "empty" | "error";

export interface SessionUserRecord {
  user_id: string;
  display_name: string;
  organization?: string | null;
  default_trip_mode: TripMode;
}

export interface FrontendTripSummaryRecord {
  trip_id: TripRecord["trip_id"];
  title: TripRecord["title"];
  summary: TripRecord["summary"];
  mode: TripRecord["mode"];
  status: TripRecord["status"];
  start_date: TripRecord["trip_frame"]["start_date"];
  end_date: TripRecord["trip_frame"]["end_date"];
  primary_regions: TripRecord["trip_frame"]["primary_regions"];
  scenario_count: number;
  pending_checkpoint_count: number;
  policy_state: PlannerPanelState["policy_evaluation"]["status"] | null;
}

export interface FrontendWorkspaceScenarioRecord {
  scenario_id: string;
  title: string;
  summary: string;
  status: "active" | "fallback" | "revised";
  comparison_note: string;
  option_count: number;
  checkpoint_id: string | null;
  budget_variant_id: string | null;
}

export interface FrontendWorkspaceCheckpointRecord {
  checkpoint_id: string;
  label: string;
  summary: string;
  status: "current" | "saved" | "revisit";
  scenario_id: string;
  updated_label: string;
}

export interface FrontendWorkspaceBudgetVariantRecord {
  variant_id: string;
  scenario_id: string;
  label: string;
  total_amount: number;
  variance_label: string;
}

export interface FrontendWorkspaceBudgetRecord {
  budget_state_id: string;
  currency: string;
  baseline_total: number;
  selected_total: number;
  actual_total: number;
  status: "healthy" | "watch" | "over";
  variance_label: string;
  categories: string[];
  variants: FrontendWorkspaceBudgetVariantRecord[];
}

export interface FrontendTravelerProfileRecord {
  profile_id: string;
  mode: TripMode;
  label: string;
  summary: string;
  readiness: string;
}

export interface FrontendRecentSessionRecord {
  session_id: string;
  trip_id: TripRecord["trip_id"] | null;
  mode: TripMode;
  label: string;
  summary: string;
  last_active_label: string;
  resume_route: AppRouteId;
}

export interface FrontendLaunchFlowRecord {
  launch_id: LaunchFlowId;
  mode: TripMode;
  title: string;
  summary: string;
  cta_label: string;
  starting_needs: string[];
  profile_id: string | null;
  trip_id: TripRecord["trip_id"] | null;
  recent_session_id: string | null;
  policy_context: string | null;
}

export interface FrontendAccountEntryRecord {
  traveler_profiles: FrontendTravelerProfileRecord[];
  recent_sessions: FrontendRecentSessionRecord[];
  launch_flows: FrontendLaunchFlowRecord[];
  selected_launch_id: LaunchFlowId | null;
  empty_state_message: string | null;
}

export interface FrontendAppRouteRecord {
  route_id: AppRouteId;
  label: string;
  path: string;
  description: string;
  requires_active_trip: boolean;
  modes: Array<"leisure" | "business">;
}

export interface FrontendVisualizationAnchorRecord {
  anchor_id: string;
  label: string;
  kind: "destination" | "lodging" | "activity" | "meeting" | "transfer";
  summary: string;
}

export interface FrontendVisualizationRouteSegmentRecord {
  segment_id: string;
  label: string;
  mode: "walk" | "rail" | "car" | "flight" | "ferry" | "tram" | "rideshare";
  from_label: string;
  to_label: string;
  duration_label: string;
  burden_label: string;
  warning: string | null;
}

export interface FrontendVisualizationTimelineBlockRecord {
  block_id: string;
  label: string;
  kind: "arrival" | "recovery" | "transit" | "stay" | "meeting" | "buffer" | "activity";
  time_label: string;
  summary: string;
}

export interface FrontendVisualizationTimelineDayRecord {
  day_id: string;
  label: string;
  posture: string;
  movement_summary: string;
  blocks: FrontendVisualizationTimelineBlockRecord[];
}

export interface FrontendScenarioVisualizationRecord {
  scenario_id: string;
  mode: TripMode;
  title: string;
  variant_label: string;
  summary: string;
  route_shape: string;
  movement_burden: string;
  tradeoff_summary: string;
  map_status: "ready" | "fallback";
  map_summary: string;
  route_warnings: string[];
  anchors: FrontendVisualizationAnchorRecord[];
  route_segments: FrontendVisualizationRouteSegmentRecord[];
  timeline_days: FrontendVisualizationTimelineDayRecord[];
}

export interface FrontendRuntimeScenarioComparisonRecord {
  scenario_id: string;
  title: string;
  rank: number;
  status: string;
  summary: string;
  comparison_note: string;
  option_count: number;
  checkpoint_id: string | null;
  budget_variant_id: string | null;
  route_sequence: string[];
  route_summary: string;
  recommended_for_selection: boolean;
  feasible: boolean;
  metrics: {
    score: number;
    travel_minutes: number;
    transfers: number;
    estimated_total: { currency: string; typical_amount: number } | null;
  };
  delta: {
    score_delta: number;
    travel_minutes_delta: number;
    transfers_delta: number;
    estimated_total_delta: number | null;
  };
  highlights: string[];
}

export interface FrontendRuntimeScenarioComparisonSurface {
  trip_id: string;
  title: string;
  summary: string;
  comparison_axes: Array<{
    key: string;
    label: string;
    direction: "higher_better" | "lower_better";
  }>;
  lead_scenario_id: string | null;
  scenarios: FrontendRuntimeScenarioComparisonRecord[];
  source_refs: string[];
}

export interface FrontendWorkspaceRecord {
  trip_id: string | null;
  status: WorkspaceStatus;
  planner_panel_state: PlannerPanelState | null;
  scenario_summaries: FrontendWorkspaceScenarioRecord[];
  runtime_scenario_comparison: FrontendRuntimeScenarioComparisonSurface | null;
  checkpoint_history: FrontendWorkspaceCheckpointRecord[];
  budget_summary: FrontendWorkspaceBudgetRecord | null;
  loading_message: string | null;
  error_message: string | null;
  persistence_summary: string[];
  visualization_scenarios: FrontendScenarioVisualizationRecord[];
  active_visualization_scenario_id: string | null;
}

export interface FrontendShellState {
  session: SessionUserRecord;
  routes: FrontendAppRouteRecord[];
  active_route: AppRouteId;
  trips: FrontendTripSummaryRecord[];
  active_trip_id: string | null;
  account_entry: FrontendAccountEntryRecord;
  workspace: FrontendWorkspaceRecord;
}
