import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLoaderData } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TripDetailPage } from "./TripDetailPage";

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useLoaderData: vi.fn(),
  };
});

const mockedUseLoaderData = vi.mocked(useLoaderData);

describe("TripDetailPage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders persisted trip metadata from the loader payload", async () => {
    mockedUseLoaderData.mockReturnValue({
      tripDetail: Promise.resolve({
        trip: {
          trip_id: "trip-kyoto-123abc",
          user_id: "user:test",
          title: "Kyoto Spring",
          summary: "Food and gardens",
          mode: "leisure",
          status: "draft",
          trip_frame: {
            start_date: "2026-04-20",
            end_date: "2026-04-26",
            duration_days: 7,
            primary_regions: ["Kyoto", "Osaka"],
            traveler_party: { kind: "solo", traveler_count: 1, notes: "Window seat preferred" },
          },
          profile_refs: {
            leisure_profile_id: "profile:trip-kyoto-123abc:leisure",
            business_profile_id: null,
          },
          artifacts: {
            objective_id: null,
            option_set_ids: [],
            itinerary_state_id: null,
            budget_state_id: null,
            policy_state_id: null,
          },
        },
        scenarioHistory: {
          saved_scenarios: [
            {
              saved_scenario_id: "saved-scenario:kyoto-baseline",
              current_version_id: "saved-scenario:kyoto-baseline-v1",
              versions: [
                {
                  version_id: "saved-scenario:kyoto-baseline-v1",
                  title: "Kyoto baseline",
                  label: "baseline",
                  summary: "Keeps the calm Kyoto-first route on hand for later refinement.",
                },
              ],
              comparisons: [],
            },
          ],
          planning_history: [
            {
              activity_event_id: "activity:scenario-saved-1",
              occurred_at: "2026-04-10T15:30:00Z",
              event_kind: "scenario_saved",
              summary: "Saved the Kyoto baseline after the first planning pass.",
              actor: "planner",
              saved_scenario_id: "saved-scenario:kyoto-baseline",
            },
          ],
        },
      }),
    });

    render(
      <MemoryRouter>
        <TripDetailPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Kyoto Spring" })).toBeInTheDocument();
    });

    expect(screen.getByText("trip-kyoto-123abc")).toBeInTheDocument();
    expect(screen.getByText("Window seat preferred")).toBeInTheDocument();
    expect(screen.getByText("Kyoto baseline")).toBeInTheDocument();
    expect(
      screen.getByText("Saved the Kyoto baseline after the first planning pass.")
    ).toBeInTheDocument();
  });

  it("renders a defensive fallback when a saved scenario has no versions", async () => {
    mockedUseLoaderData.mockReturnValue({
      tripDetail: Promise.resolve({
        trip: {
          trip_id: "trip-kyoto-123abc",
          user_id: "user:test",
          title: "Kyoto Spring",
          summary: "Food and gardens",
          mode: "leisure",
          status: "draft",
          trip_frame: {
            start_date: "2026-04-20",
            end_date: "2026-04-26",
            duration_days: 7,
            primary_regions: ["Kyoto"],
            traveler_party: { kind: "solo", traveler_count: 1, notes: "" },
          },
          profile_refs: {
            leisure_profile_id: "profile:trip-kyoto-123abc:leisure",
            business_profile_id: null,
          },
          artifacts: {
            objective_id: null,
            option_set_ids: [],
            itinerary_state_id: null,
            budget_state_id: null,
            policy_state_id: null,
          },
        },
        scenarioHistory: {
          saved_scenarios: [
            {
              saved_scenario_id: "saved-scenario:kyoto-empty",
              current_version_id: "saved-scenario:kyoto-empty-v1",
              versions: [],
              comparisons: [],
            },
          ],
          planning_history: [],
        },
      }),
    });

    render(
      <MemoryRouter>
        <TripDetailPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Kyoto Spring" })).toBeInTheDocument();
    });

    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(
      screen.getByText("This saved scenario is missing version details.")
    ).toBeInTheDocument();
  });
});
