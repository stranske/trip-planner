import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { useLoaderData } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TripDetailPage } from "./TripDetailPage";
import { TestMemoryRouter } from "../test/router";

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
    cleanup();
    mockedUseLoaderData.mockReset();
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
          planning_sessions: [
            {
              session_state_id: "session-state:kyoto-spring-abc123",
              owner_profile_id: "profile:trip-kyoto-123abc:leisure",
              mode: "leisure",
              started_at: "2026-04-10T15:00:00Z",
              updated_at: "2026-04-10T15:35:00Z",
              status: "active",
              current_saved_scenario_id: "saved-scenario:kyoto-baseline",
              activity_log_id: "activity-log:kyoto-spring",
              interaction_state: {
                initiative_level: "balanced",
                summary_granularity: "balanced",
                checkpoint_frequency: "milestone",
              },
              pending_decisions: [
                {
                  decision_id: "decision:lodging",
                  prompt: "Choose the Kyoto base neighborhood.",
                },
              ],
              recent_option_presentations: [
                {
                  presentation_id: "presentation:kyoto-1",
                  option_set_id: "option-set:kyoto-1",
                },
              ],
            },
          ],
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
              session_state_id: "session-state:kyoto-spring-abc123",
              saved_scenario_id: "saved-scenario:kyoto-baseline",
            },
          ],
        },
      }),
    });

    render(
      <TestMemoryRouter>
        <TripDetailPage />
      </TestMemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Kyoto Spring" })).toBeInTheDocument();
    });

    expect(screen.getByText("trip-kyoto-123abc")).toBeInTheDocument();
    expect(screen.getByText("Window seat preferred")).toBeInTheDocument();
    expect(screen.getByText("Kyoto baseline")).toBeInTheDocument();
    expect(screen.getByText("session-state:kyoto-spring-abc123")).toBeInTheDocument();
    expect(screen.getByText("activity-log:kyoto-spring")).toBeInTheDocument();
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
          planning_sessions: [],
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
      <TestMemoryRouter>
        <TripDetailPage />
      </TestMemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Kyoto Spring" })).toBeInTheDocument();
    });

    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(
      screen.getByText("This saved scenario is missing version details.")
    ).toBeInTheDocument();
    expect(
      screen.getByText("No planning session has been persisted for this trip yet.")
    ).toBeInTheDocument();
  });
});
