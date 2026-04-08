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
  inventory_summary: {
    bundle_count: 2,
    bundles: [
      {
        bundle_id: "bundle-osaka-gateway",
        title: "Osaka arrival buffer",
        bundle_context: "transport_lodging",
        summary: "Front-load the airport arrival and first-night stay into one inspectable bundle.",
        destination_names: ["KIX Airport", "Osaka"],
        option_count: 2,
        strengths: ["Low-friction arrival handoff"],
        tradeoffs: ["Station-area stay is functional rather than atmospheric."],
      },
      {
        bundle_id: "bundle-kyoto-culture-day",
        title: "Kyoto cultural anchor",
        bundle_context: "route_level",
        summary: "Expose the Kyoto cultural day as a normalized mixed inventory bundle.",
        destination_names: ["Osaka", "Kyoto"],
        option_count: 3,
        strengths: ["Preserves activity detail"],
        tradeoffs: ["Requires a base change."],
      },
    ],
    notes: [
      "Bundle summaries are assembled from normalized destination, lodging, transport, and activity records.",
    ],
  },
  planner_panel_state: {
    trip: {
      trip_id: "trip-leisure-kyoto-draft",
      user_id: "user:test",
      mode: "leisure",
      status: "draft",
      trip_frame: {
        start_date: "2026-04-10",
        end_date: "2026-04-24",
        duration_days: 14,
        primary_regions: ["JP-26", "JP-27"],
        traveler_party: {
          kind: "pair",
          traveler_count: 2,
          notes: "Anniversary planning",
        },
      },
      profile_refs: {
        leisure_profile_id: "profile:kyoto",
      },
      title: "Spring Kyoto anniversary draft",
      summary: "Initial leisure trip shell with routing and lodging options.",
    },
    option_set: {
      option_set_id: "option-set:workspace-panel",
      trip_id: "trip-leisure-kyoto-draft",
      purpose: "workspace_review",
      scope: "scenario_selection",
      title: "Kyoto leisure scenario comparison",
      comparison_axes: [
        { key: "score", label: "Planner score", direction: "higher_better" },
        { key: "travel_minutes", label: "Travel minutes", direction: "lower_better" },
      ],
      explanation: ["Workspace panel mirrors the current scenario feed."],
      options: [
        {
          option_id: "scenario:trip-leisure-kyoto-draft:1",
          kind: "scenario",
          label: "Kyoto base with Uji day trip",
          summary: "Balanced Kyoto culture baseline",
          drawbacks: ["Evening variety is lower than the Osaka-heavy fallback."],
          explanation: ["Rank #1 with score 0.93."],
        },
      ],
    },
    proposal: null,
    policy_evaluation: null,
    pending_decisions: [
      {
        decision_id: "decision:save-baseline",
        title: "Save baseline scenario",
        prompt: "Should the current Kyoto route become the saved baseline?",
        choices: ["Keep the current direction.", "Compare another planner-backed option first."],
      },
    ],
    outputs: [
      {
        output_id: "output:workspace-summary",
        title: "Workspace scenario feed",
        body: "Planner-side-panel content is now mounted inside the workspace route.",
        tags: ["workspace", "planner-panel"],
      },
    ],
    planner_behavior: {
      trip_stage: "compare",
      ask_before_next_major_change: true,
      target_research_passes: 3,
      target_options_before_checkpoint: 2,
      surface_options_early: true,
      explanation_density: "standard",
    },
    next_step_actions: [
      {
        action_id: "action:answer-decision",
        action_kind: "answer_decision",
        label: "Answer the current planner decision",
        description: "Resolve the active planner question before the next planning checkpoint.",
        emphasis: "primary",
        target_section: "decisions",
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
    expect(screen.getByText("Trip-scoped planner surface")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Assembled inventory layer" })).toBeInTheDocument();
    expect(screen.getByText("Osaka arrival buffer")).toBeInTheDocument();
    expect(screen.getByText("Kyoto cultural anchor")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByLabelText("Planner side panel")).toBeInTheDocument();
    });
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
        planner_panel_state: {
          ...workspacePayload.planner_panel_state,
          option_set: {
            ...workspacePayload.planner_panel_state.option_set,
            title: "Planner workspace bootstrap",
            purpose: "workspace_bootstrap",
            options: [
              {
                option_id: "bootstrap:keep-frame",
                kind: "trip_setup",
                label: "Keep the current trip frame narrow",
                summary: "Use the current trip shell as the first planner boundary.",
                drawbacks: ["You may need another pass if the trip should span more regions."],
                explanation: ["Best when the user wants to iterate later."],
              },
            ],
          },
          pending_decisions: [],
          outputs: [
            {
              output_id: "output:bootstrap-ready",
              title: "Workspace bootstrap is ready",
              body: "The workspace has enough persisted trip context to mount the planner surface.",
              tags: ["bootstrap"],
            },
          ],
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
    expect(screen.getByText("Workspace bootstrap is ready")).toBeInTheDocument();
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
        inventory_summary: {
          bundle_count: 0,
          bundles: [],
          notes: ["Bundle assembly will appear here once normalized option inputs are available for the trip."],
        },
        planner_panel_state: {
          ...workspacePayload.planner_panel_state,
          trip: {
            ...workspacePayload.planner_panel_state.trip,
            trip_id: "trip-chicago-kickoff",
            title: "Chicago kickoff",
            summary: "Get into the workspace quickly.",
            mode: "business",
            trip_frame: {
              start_date: null,
              end_date: null,
              duration_days: null,
              primary_regions: ["Chicago"],
              traveler_party: {
                kind: "team",
                traveler_count: 3,
                notes: "Customer kickoff",
              },
            },
          },
          option_set: {
            ...workspacePayload.planner_panel_state.option_set,
            purpose: "workspace_bootstrap",
            title: "Planner workspace bootstrap",
          },
          pending_decisions: [],
        },
      }),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Chicago kickoff" })).toBeInTheDocument();
    });

    expect(screen.getByText("Dates not set yet")).toBeInTheDocument();
    expect(screen.getByText("Duration not set yet")).toBeInTheDocument();
    expect(screen.getAllByText("Planner workspace bootstrap").length).toBeGreaterThan(0);
    expect(screen.getByText("Bundle assembly has not started yet for this trip.")).toBeInTheDocument();
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
