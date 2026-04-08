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
