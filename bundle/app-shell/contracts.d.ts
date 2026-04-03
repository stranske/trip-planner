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

export type WorkspaceStatus = "ready" | "loading" | "empty" | "error";

export interface SessionUserRecord {
  user_id: string;
  display_name: string;
  organization?: string | null;
  default_trip_mode: "leisure" | "business";
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

export interface FrontendAppRouteRecord {
  route_id: AppRouteId;
  label: string;
  path: string;
  description: string;
  requires_active_trip: boolean;
  modes: Array<"leisure" | "business">;
}

export interface FrontendWorkspaceRecord {
  trip_id: string | null;
  status: WorkspaceStatus;
  planner_panel_state: PlannerPanelState | null;
  loading_message: string | null;
  error_message: string | null;
  persistence_summary: string[];
}

export interface FrontendShellState {
  session: SessionUserRecord;
  routes: FrontendAppRouteRecord[];
  active_route: AppRouteId;
  trips: FrontendTripSummaryRecord[];
  active_trip_id: string | null;
  workspace: FrontendWorkspaceRecord;
}
