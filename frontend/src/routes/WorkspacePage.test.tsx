import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLoaderData } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClientError } from "../lib/api/errors";
import { WorkspacePage } from "./WorkspacePage";

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useLoaderData: vi.fn(),
  };
});

const mockedUseLoaderData = vi.mocked(useLoaderData);

const workspacePayload = {
  trip_record: {
    trip: {
      trip_id: "trip-leisure-kyoto-draft",
      title: "Spring Kyoto anniversary draft",
      summary: "Initial leisure trip shell with routing and lodging options.",
      status: "draft",
      mode: "leisure",
      trip_frame: {
        start_date: "2026-04-10",
        end_date: "2026-04-24",
        duration_days: 14,
        primary_regions: ["JP-26", "JP-27"],
      },
    },
    artifact_refs: {
      saved_scenario_ids: ["saved-scenario:kyoto-baseline", "saved-scenario:osaka-fallback"],
      scenario_search_id: "scenario-search:kyoto-spring",
      session_state_id: "session-state:kyoto-spring",
    },
  },
  session: {
    current_saved_scenario_id: "saved-scenario:kyoto-baseline",
    pending_decisions: [
      {
        decision_id: "decision:save-baseline",
        title: "Save baseline scenario",
        prompt: "Should the current Kyoto route become the saved baseline?",
        blocking: true,
      },
    ],
    interaction_state: {
      interaction_style: "collaborative",
      initiative_level: "balanced",
      checkpoint_frequency: "milestone",
    },
    recent_option_presentations: [],
  },
  saved_scenarios: [
    {
      saved_scenario_id: "saved-scenario:kyoto-baseline",
      current_version_id: "saved-scenario:kyoto-baseline-v2",
      versions: [
        {
          version_id: "saved-scenario:kyoto-baseline-v2",
          title: "Kyoto spring preferred refinement",
          label: "preferred",
          summary: "Promoted the Kyoto baseline to the preferred scenario after refinement.",
          snapshot_refs: {
            itinerary_scenario_id: "scenario:trip-leisure-kyoto-draft:1",
          },
        },
      ],
    },
    {
      saved_scenario_id: "saved-scenario:osaka-fallback",
      current_version_id: "saved-scenario:osaka-fallback-v1",
      versions: [
        {
          version_id: "saved-scenario:osaka-fallback-v1",
          title: "Osaka rainy-day fallback",
          label: "fallback",
          summary: "Fallback route retained to preserve lower-friction rainy-day options.",
          snapshot_refs: {
            itinerary_scenario_id: "scenario:trip-leisure-kyoto-draft:2",
          },
        },
      ],
    },
  ],
  scenario_comparison: {
    summary: "Kyoto remains the preferred baseline while Osaka stays as an explicit fallback.",
    outcome: "preferred",
    focus_areas: ["recovery", "route_coherence", "weather_resilience"],
  },
  scenario_search: {
    title: "Kyoto leisure scenario comparison",
    scenarios: [
      {
        scenario_id: "scenario:trip-leisure-kyoto-draft:1",
        title: "Kyoto base with Uji day trip",
        rank: 1,
        score: 0.93,
        scenario_summary: {
          headline: "Balanced Kyoto culture baseline",
          scenario_kind: "primary",
          recommended_for_selection: true,
          total_travel_minutes: 265,
          total_transfer_count: 4,
          route_sequence: ["kyoto", "uji", "kyoto"],
        },
        unresolved_tradeoffs: [],
      },
    ],
  },
};

function renderWorkspacePage() {
  return render(
    <MemoryRouter>
      <WorkspacePage />
    </MemoryRouter>
  );
}

describe("WorkspacePage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders timeline structure from persisted trip and scenario state", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve(workspacePayload),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Spring Kyoto anniversary draft" })).toBeInTheDocument();
    });

    expect(screen.getByRole("heading", { name: "Kyoto base with Uji day trip" })).toBeInTheDocument();
    expect(screen.getAllByText("Kyoto")).toHaveLength(2);
    expect(screen.getByText("Uji")).toBeInTheDocument();
    expect(screen.getByText("Save baseline scenario")).toBeInTheDocument();
  });

  it("shows an empty-state message when no route sequence is available", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve({
        ...workspacePayload,
        saved_scenarios: [],
        scenario_search: {
          ...workspacePayload.scenario_search,
          scenarios: [],
        },
      }),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByText("Timeline data is not ready")).toBeInTheDocument();
    });
    expect(
      screen.getByText(
        "Trip context is ready now, so the next planning pass can attach saved scenarios and timeline stops."
      )
    ).toBeInTheDocument();
  });

  it("shows created-trip metadata even when the workspace has no seeded scenario state yet", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve({
        ...workspacePayload,
        trip_record: {
          trip: {
            ...workspacePayload.trip_record.trip,
            trip_id: "trip-chicago-kickoff",
            title: "Chicago kickoff",
            summary: "Get into the workspace quickly.",
            mode: "business",
            trip_frame: {
              start_date: null,
              end_date: null,
              duration_days: null,
              primary_regions: ["Chicago"],
            },
          },
          artifact_refs: {
            saved_scenario_ids: [],
            scenario_search_id: null,
            session_state_id: "session:trip-chicago-kickoff",
          },
        },
        session: {
          ...workspacePayload.session,
          current_saved_scenario_id: null,
          pending_decisions: [],
        },
        saved_scenarios: [],
        scenario_search: {
          title: "Trip setup workspace",
          scenarios: [],
        },
      }),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Chicago kickoff" })).toBeInTheDocument();
    });

    expect(screen.getByText("Dates not set yet")).toBeInTheDocument();
    expect(screen.getByText("Duration not set yet")).toBeInTheDocument();
  });

  it("renders the shared route error card when the workspace loader rejects", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.reject(
        new ApiClientError("Backend warming up", {
          path: "/api/workspace/trip-leisure-kyoto-draft",
          status: 503,
          statusText: "Service Unavailable",
        })
      ),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Workspace request failed" })).toBeInTheDocument();
    });

    expect(screen.getByText("Backend warming up")).toBeInTheDocument();
  });
});
