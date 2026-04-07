import { fetchJson } from "../lib/api/client";

export type TripFrame = {
  start_date: string;
  end_date: string;
  duration_days: number;
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
};

export async function fetchWorkspace(tripId: string): Promise<WorkspaceData> {
  return fetchJson<WorkspaceData>({ path: `/api/workspace/${tripId}` });
}
