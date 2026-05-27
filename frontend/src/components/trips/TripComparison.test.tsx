import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { TripRecord } from "../../api/trips";
import { TripComparison } from "./TripComparison";

afterEach(() => {
  cleanup();
});

const currentTrip = {
  trip_id: "trip-current",
  title: "Kyoto autumn loop",
  summary: "Two weeks across Kyoto and Osaka.",
  mode: "leisure",
  status: "active",
  trip_frame: {
    duration_days: 14,
    primary_regions: ["Kyoto", "Osaka"],
    traveler_party: { kind: "solo", traveler_count: 1, notes: "" },
  },
};

function buildTripRecord(
  tripId: string,
  title: string,
  durationDays: number,
  regions: string[]
): TripRecord {
  return {
    trip_id: tripId,
    user_id: "user-1",
    title,
    summary: `${title} summary`,
    mode: "leisure",
    status: "active",
    trip_frame: {
      start_date: null,
      end_date: null,
      duration_days: durationDays,
      primary_regions: regions,
      traveler_party: { kind: "solo", traveler_count: 1, notes: "" },
    },
    profile_refs: { leisure_profile_id: null, business_profile_id: null },
    artifacts: {
      objective_id: null,
      option_set_ids: [],
      itinerary_state_id: null,
      budget_state_id: null,
      policy_state_id: null,
    },
  };
}

describe("TripComparison", () => {
  it("renders the empty state when there are no other persisted trips", () => {
    render(
      <TripComparison
        currentTrip={currentTrip}
        trips={[buildTripRecord("trip-current", "Kyoto autumn loop", 14, ["Kyoto"])]}
        selectedTripId={null}
        onSelectTrip={vi.fn()}
      />
    );

    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
      "Trip-to-trip comparison will appear as more persisted trips land"
    );
  });

  it("renders both the current trip and a comparison candidate", () => {
    render(
      <TripComparison
        currentTrip={currentTrip}
        trips={[buildTripRecord("trip-other", "Lisbon coast week", 7, ["Lisbon"])]}
        selectedTripId={null}
        onSelectTrip={vi.fn()}
      />
    );

    expect(screen.getByText("Kyoto autumn loop")).toBeInTheDocument();
    expect(screen.getByText("Lisbon coast week")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Compare with Lisbon coast week" })
    ).toBeInTheDocument();
  });

  it("invokes onSelectTrip when a comparison chip is clicked", () => {
    const onSelectTrip = vi.fn();

    render(
      <TripComparison
        currentTrip={currentTrip}
        trips={[buildTripRecord("trip-other", "Lisbon coast week", 7, ["Lisbon"])]}
        selectedTripId={null}
        onSelectTrip={onSelectTrip}
      />
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Compare with Lisbon coast week" })
    );

    expect(onSelectTrip).toHaveBeenCalledWith("trip-other");
  });
});
