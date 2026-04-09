import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLoaderData } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClientError } from "../lib/api/errors";
import {
  answerPlannerDecision,
  recordWorkspaceSpendEvent,
  saveWorkspaceBudget,
  submitPlannerOptionFeedback,
} from "../api/workspace";
import { WorkspacePage } from "./WorkspacePage";

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useLoaderData: vi.fn(),
  };
});

vi.mock("../api/workspace", async () => {
  const actual = await vi.importActual<typeof import("../api/workspace")>("../api/workspace");
  return {
    ...actual,
    answerPlannerDecision: vi.fn(),
    submitPlannerOptionFeedback: vi.fn(),
    saveWorkspaceBudget: vi.fn(),
    recordWorkspaceSpendEvent: vi.fn(),
  };
});

const mockedUseLoaderData = vi.mocked(useLoaderData);
const mockedAnswerPlannerDecision = vi.mocked(answerPlannerDecision);
const mockedSubmitPlannerOptionFeedback = vi.mocked(submitPlannerOptionFeedback);
const mockedSaveWorkspaceBudget = vi.mocked(saveWorkspaceBudget);
const mockedRecordWorkspaceSpendEvent = vi.mocked(recordWorkspaceSpendEvent);

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
      budget_state_id: null,
    },
  },
  session: {
    current_saved_scenario_id: "saved-scenario:kyoto-baseline",
    active_budget_plan_id: null,
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
  activity_log: [],
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
  budget_state: {
    budget_plan: null,
    versions: [],
    spend_events: [],
    summary: {
      currency: "USD",
      has_budget_plan: false,
      current_scenario_budget_id: null,
      current_scenario_title: null,
      planned_total: 0,
      actual_total: 0,
      remaining_total: 0,
      spend_event_count: 0,
      version_count: 0,
      suggested_categories: ["lodging", "food", "activities", "local_mobility"],
      category_summaries: [
        {
          category_key: "lodging",
          label: "Lodging",
          currency: "USD",
          planned_amount: 0,
          actual_amount: 0,
          remaining_amount: 0,
          flexibility: "guardrail",
        },
        {
          category_key: "food",
          label: "Food",
          currency: "USD",
          planned_amount: 0,
          actual_amount: 0,
          remaining_amount: 0,
          flexibility: "flexible",
        },
      ],
    },
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

function getPlannerHost() {
  const plannerHost = document.querySelector(".planner-panel-host");
  expect(plannerHost).toBeTruthy();
  return plannerHost as HTMLDivElement;
}

describe("WorkspacePage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    mockedAnswerPlannerDecision.mockReset();
    mockedSubmitPlannerOptionFeedback.mockReset();
    mockedSaveWorkspaceBudget.mockReset();
    mockedRecordWorkspaceSpendEvent.mockReset();
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
      const plannerPanel = getPlannerHost().shadowRoot?.querySelector(
        '[aria-label="Planner side panel"]'
      );
      expect(plannerPanel).toBeTruthy();
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
    await waitFor(() => {
      expect(getPlannerHost().shadowRoot?.querySelector('[aria-label="Planner side panel"]')).toBeTruthy();
    });
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
            budget_state_id: null,
          },
        },
        session: {
          ...workspacePayload.session,
          current_saved_scenario_id: null,
          active_budget_plan_id: null,
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
    expect(screen.getByText("Bundle assembly has not started yet for this trip.")).toBeInTheDocument();
    await waitFor(() => {
      expect(getPlannerHost().shadowRoot?.querySelector('[aria-label="Planner side panel"]')).toBeTruthy();
    });
  });

  it("formats single persisted trip dates without shifting date-only values across time zones", async () => {
    expect(new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(new Date("2026-05-04"))).toBe(
      "May 3",
    );

    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve({
        ...workspacePayload,
        trip_record: {
          ...workspacePayload.trip_record,
          trip: {
            ...workspacePayload.trip_record.trip,
            trip_id: "trip-chicago-arrival",
            title: "Chicago arrival",
            trip_frame: {
              ...workspacePayload.trip_record.trip.trip_frame,
              start_date: "2026-05-04",
              end_date: null,
            },
          },
        },
      }),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Chicago arrival" })).toBeInTheDocument();
    });

    expect(screen.getByText("May 4")).toBeInTheDocument();
    expect(screen.queryByText("2026-05-04")).not.toBeInTheDocument();
  });

  it("saves a budget plan and refreshes the workspace totals", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve(workspacePayload),
    });
    mockedSaveWorkspaceBudget.mockResolvedValue({
      budget_plan: {
        budget_plan_id: "budget-plan:trip-leisure-kyoto-draft",
        trip_id: "trip-leisure-kyoto-draft",
        owner_profile_id: "profile:kyoto",
        title: "Kyoto spring guardrails",
        mode: "leisure",
        created_at: "2026-04-10T15:00:00Z",
        updated_at: "2026-04-10T15:10:00Z",
        scenario_budgets: [
          {
            scenario_budget_id: "budget-scenario:kyoto-baseline",
            saved_scenario_id: null,
            title: "Baseline budget",
            summary: "",
            tags: [],
            notes: [],
            allocations: [
              {
                category_key: "lodging",
                label: "Lodging",
                planned_amount: 600,
                currency: "USD",
                flexibility: "guardrail",
                notes: [],
              },
              {
                category_key: "food",
                label: "Food",
                planned_amount: 180,
                currency: "USD",
                flexibility: "flexible",
                notes: [],
              },
            ],
          },
        ],
        current_scenario_budget_id: "budget-scenario:kyoto-baseline",
        currency: "USD",
        schema_version: "v1",
        tags: [],
        notes: [],
      },
      versions: [
        {
          version_id: "budget-plan:trip-leisure-kyoto-draft-v1",
          budget_plan_id: "budget-plan:trip-leisure-kyoto-draft",
          recorded_at: "2026-04-10T15:10:00Z",
          summary: "Initial workspace budget",
        },
      ],
      spend_events: [],
      summary: {
        currency: "USD",
        has_budget_plan: true,
        current_scenario_budget_id: "budget-scenario:kyoto-baseline",
        current_scenario_title: "Baseline budget",
        planned_total: 780,
        actual_total: 0,
        remaining_total: 780,
        spend_event_count: 0,
        version_count: 1,
        suggested_categories: ["lodging", "food", "activities", "local_mobility"],
        category_summaries: [
          {
            category_key: "lodging",
            label: "Lodging",
            currency: "USD",
            planned_amount: 600,
            actual_amount: 0,
            remaining_amount: 600,
            flexibility: "guardrail",
          },
          {
            category_key: "food",
            label: "Food",
            currency: "USD",
            planned_amount: 180,
            actual_amount: 0,
            remaining_amount: 180,
            flexibility: "flexible",
          },
        ],
      },
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Budget vs actual" })).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.clear(screen.getByLabelText("Budget title"));
    await user.type(screen.getByLabelText("Budget title"), "Kyoto spring guardrails");
    await user.clear(screen.getByLabelText("Lodging cap"));
    await user.type(screen.getByLabelText("Lodging cap"), "600");
    await user.clear(screen.getByLabelText("Food cap"));
    await user.type(screen.getByLabelText("Food cap"), "180");
    await user.click(screen.getByRole("button", { name: "Save budget plan" }));

    await waitFor(() => {
      expect(mockedSaveWorkspaceBudget).toHaveBeenCalledWith(
        "trip-leisure-kyoto-draft",
        expect.objectContaining({
          title: "Kyoto spring guardrails",
        })
      );
    });

    expect(screen.getAllByText("$780.00").length).toBeGreaterThan(0);
    expect(screen.getByDisplayValue("Baseline budget")).toBeInTheDocument();
  });

  it("records a spend event and surfaces the updated merchant entry", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve({
        ...workspacePayload,
        budget_state: {
          budget_plan: {
            budget_plan_id: "budget-plan:trip-leisure-kyoto-draft",
            trip_id: "trip-leisure-kyoto-draft",
            owner_profile_id: "profile:kyoto",
            title: "Kyoto spring guardrails",
            mode: "leisure",
            created_at: "2026-04-10T15:00:00Z",
            updated_at: "2026-04-10T15:10:00Z",
            scenario_budgets: [
              {
                scenario_budget_id: "budget-scenario:kyoto-baseline",
                saved_scenario_id: null,
                title: "Baseline budget",
                summary: "",
                tags: [],
                notes: [],
                allocations: [
                  {
                    category_key: "food",
                    label: "Food",
                    planned_amount: 180,
                    currency: "USD",
                    flexibility: "flexible",
                    notes: [],
                  },
                ],
              },
            ],
            current_scenario_budget_id: "budget-scenario:kyoto-baseline",
            currency: "USD",
            schema_version: "v1",
            tags: [],
            notes: [],
          },
          versions: [],
          spend_events: [],
          summary: {
            currency: "USD",
            has_budget_plan: true,
            current_scenario_budget_id: "budget-scenario:kyoto-baseline",
            current_scenario_title: "Baseline budget",
            planned_total: 180,
            actual_total: 0,
            remaining_total: 180,
            spend_event_count: 0,
            version_count: 1,
            suggested_categories: ["food"],
            category_summaries: [
              {
                category_key: "food",
                label: "Food",
                currency: "USD",
                planned_amount: 180,
                actual_amount: 0,
                remaining_amount: 180,
                flexibility: "flexible",
              },
            ],
          },
        },
      }),
    });
    mockedRecordWorkspaceSpendEvent.mockResolvedValue({
      budget_plan: {
        budget_plan_id: "budget-plan:trip-leisure-kyoto-draft",
        trip_id: "trip-leisure-kyoto-draft",
        owner_profile_id: "profile:kyoto",
        title: "Kyoto spring guardrails",
        mode: "leisure",
        created_at: "2026-04-10T15:00:00Z",
        updated_at: "2026-04-10T15:10:00Z",
        scenario_budgets: [
          {
            scenario_budget_id: "budget-scenario:kyoto-baseline",
            saved_scenario_id: null,
            title: "Baseline budget",
            summary: "",
            tags: [],
            notes: [],
            allocations: [
              {
                category_key: "food",
                label: "Food",
                planned_amount: 180,
                currency: "USD",
                flexibility: "flexible",
                notes: [],
              },
            ],
          },
        ],
        current_scenario_budget_id: "budget-scenario:kyoto-baseline",
        currency: "USD",
        schema_version: "v1",
        tags: [],
        notes: [],
      },
      versions: [],
      spend_events: [
        {
          spend_event_id: "spend:trip-leisure-kyoto-draft:1",
          trip_id: "trip-leisure-kyoto-draft",
          budget_plan_id: "budget-plan:trip-leisure-kyoto-draft",
          category_key: "food",
          amount: 42.5,
          currency: "USD",
          occurred_at: "2026-04-10T16:00:00Z",
          source_kind: "manual",
          source_context: "Dinner near Gion",
          scenario_budget_id: "budget-scenario:kyoto-baseline",
          saved_scenario_id: null,
          merchant_name: "Kyoto Kitchen",
          source_ref: null,
          notes: [],
        },
      ],
      summary: {
        currency: "USD",
        has_budget_plan: true,
        current_scenario_budget_id: "budget-scenario:kyoto-baseline",
        current_scenario_title: "Baseline budget",
        planned_total: 180,
        actual_total: 42.5,
        remaining_total: 137.5,
        spend_event_count: 1,
        version_count: 1,
        suggested_categories: ["food"],
        category_summaries: [
          {
            category_key: "food",
            label: "Food",
            currency: "USD",
            planned_amount: 180,
            actual_amount: 42.5,
            remaining_amount: 137.5,
            flexibility: "flexible",
          },
        ],
      },
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Record spend event" })).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Amount"), "42.5");
    await user.type(screen.getByLabelText("Spend context"), "Dinner near Gion");
    await user.type(screen.getByLabelText("Merchant"), "Kyoto Kitchen");
    await user.click(screen.getByRole("button", { name: "Record spend event" }));

    await waitFor(() => {
      expect(mockedRecordWorkspaceSpendEvent).toHaveBeenCalledWith(
        "trip-leisure-kyoto-draft",
        expect.objectContaining({
          amount: 42.5,
          source_context: "Dinner near Gion",
          merchant_name: "Kyoto Kitchen",
        })
      );
    });

    expect(screen.getByText("Kyoto Kitchen")).toBeInTheDocument();
    expect(screen.getAllByText("$137.50").length).toBeGreaterThan(0);
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
