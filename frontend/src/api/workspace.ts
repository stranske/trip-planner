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
  };
};

export type SessionState = {
  current_saved_scenario_id: string | null;
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
