import { fetchJson } from "../lib/api/client";

export type TravelerParty = {
  kind: string;
  traveler_count: number;
  notes: string;
};

export type TripFrame = {
  start_date: string | null;
  end_date: string | null;
  duration_days: number | null;
  primary_regions: string[];
  traveler_party: TravelerParty;
};

export type TripRecord = {
  trip_id: string;
  user_id: string;
  title: string;
  summary: string;
  mode: string;
  status: string;
  trip_frame: TripFrame;
  profile_refs: {
    leisure_profile_id: string | null;
    business_profile_id: string | null;
  };
  artifacts: {
    objective_id: string | null;
    option_set_ids: string[];
    itinerary_state_id: string | null;
    budget_state_id: string | null;
    policy_state_id: string | null;
  };
};

export type SavedScenarioRecord = {
  saved_scenario_id: string;
  current_version_id: string;
  versions: Array<{
    version_id: string;
    title: string;
    label: string;
    summary: string;
  }>;
  comparisons: Array<{
    comparison_id: string;
    summary: string;
    outcome: string;
  }>;
};

export type PlanningHistoryEntry = {
  activity_event_id: string;
  occurred_at: string;
  event_kind: string;
  summary: string;
  actor: string;
  session_state_id: string;
  saved_scenario_id: string | null;
};

export type PlanningSessionRecord = {
  session_state_id: string;
  owner_profile_id: string;
  mode: string;
  started_at: string;
  updated_at: string;
  status: string;
  current_saved_scenario_id: string | null;
  activity_log_id: string | null;
  interaction_state: {
    initiative_level: string;
    summary_granularity: string;
    checkpoint_frequency: string;
  };
  pending_decisions: Array<{
    decision_id: string;
    prompt: string;
  }>;
  recent_option_presentations: Array<{
    presentation_id: string;
    option_set_id: string;
  }>;
};

export type TripScenarioHistoryData = {
  saved_scenarios: SavedScenarioRecord[];
  planning_history: PlanningHistoryEntry[];
  planning_sessions: PlanningSessionRecord[];
};

export type CreateTripPayload = {
  title: string;
  summary: string;
  mode: string;
  trip_frame: TripFrame;
};

export async function fetchTrips(): Promise<TripRecord[]> {
  const response = await fetchJson<{ trips: TripRecord[] }>({
    path: "/api/trips",
    credentials: "include",
  });
  return response.trips;
}

export async function fetchTrip(tripId: string): Promise<TripRecord> {
  const response = await fetchJson<{ trip: TripRecord }>({
    path: `/api/trips/${tripId}`,
    credentials: "include",
  });
  return response.trip;
}

export async function fetchTripScenarioHistory(
  tripId: string,
): Promise<TripScenarioHistoryData> {
  return fetchJson<TripScenarioHistoryData>({
    path: `/api/trips/${tripId}/scenario-history`,
    credentials: "include",
  });
}

export async function createTrip(payload: CreateTripPayload): Promise<TripRecord> {
  const response = await fetchJson<{ trip: TripRecord }>({
    path: "/api/trips",
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return response.trip;
}
