import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLoaderData } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClientError } from "../lib/api/errors";
import {
  answerPlannerDecision,
  createNotebookItem,
  deleteNotebookItem,
  fetchPlannerSession,
  recordWorkspaceSpendEvent,
  refreshWorkspaceProposalStatus,
  saveWorkspaceBudget,
  setNotebookFocus,
  submitPlannerTurn,
  submitPlannerOptionFeedback,
  submitRouteOptionAction,
  updateNotebookItem,
  updateWorkspacePlanningMode,
  type PlannerSessionResponse,
  type WorkspaceData,
} from "../api/workspace";
import { TestMemoryRouter } from "../test/router";
import type { TripRecord } from "../api/trips";
import { WorkspacePage } from "./WorkspacePage";

vi.mock("../api/workspace", async () => {
  const actual = await vi.importActual<typeof import("../api/workspace")>("../api/workspace");
  return {
    ...actual,
    answerPlannerDecision: vi.fn(),
    fetchPlannerSession: vi.fn(),
    submitPlannerOptionFeedback: vi.fn(),
    submitRouteOptionAction: vi.fn(),
    submitPlannerTurn: vi.fn(),
    updateWorkspacePlanningMode: vi.fn(),
    saveWorkspaceBudget: vi.fn(),
    recordWorkspaceSpendEvent: vi.fn(),
    refreshWorkspaceProposalStatus: vi.fn(),
    createNotebookItem: vi.fn(),
    updateNotebookItem: vi.fn(),
    deleteNotebookItem: vi.fn(),
    setNotebookFocus: vi.fn(),
  };
});

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useLoaderData: vi.fn(),
  };
});

const mockedUseLoaderData = vi.mocked(useLoaderData);
const mockedAnswerPlannerDecision = vi.mocked(answerPlannerDecision);
const mockedFetchPlannerSession = vi.mocked(fetchPlannerSession);
const mockedSubmitPlannerOptionFeedback = vi.mocked(submitPlannerOptionFeedback);
const mockedSubmitRouteOptionAction = vi.mocked(submitRouteOptionAction);
const mockedSubmitPlannerTurn = vi.mocked(submitPlannerTurn);
const mockedUpdateWorkspacePlanningMode = vi.mocked(updateWorkspacePlanningMode);
const mockedSaveWorkspaceBudget = vi.mocked(saveWorkspaceBudget);
const mockedRecordWorkspaceSpendEvent = vi.mocked(recordWorkspaceSpendEvent);
const mockedRefreshWorkspaceProposalStatus = vi.mocked(refreshWorkspaceProposalStatus);
const mockedCreateNotebookItem = vi.mocked(createNotebookItem);
const mockedUpdateNotebookItem = vi.mocked(updateNotebookItem);
const mockedDeleteNotebookItem = vi.mocked(deleteNotebookItem);
const mockedSetNotebookFocus = vi.mocked(setNotebookFocus);
const tripComparisonPayload: TripRecord[] = [
  {
    trip_id: "trip-leisure-kyoto-draft",
    user_id: "user:test",
    title: "Spring Kyoto anniversary draft",
    summary: "Initial leisure trip shell with routing and lodging options.",
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
  {
    trip_id: "trip-business-tokyo-summit",
    user_id: "user:test",
    title: "Tokyo client summit",
    summary: "Business trip with denser approval posture and shorter duration.",
    mode: "business",
    status: "active",
    trip_frame: {
      start_date: "2026-05-02",
      end_date: "2026-05-06",
      duration_days: 5,
      primary_regions: ["Tokyo", "Yokohama"],
      traveler_party: {
        kind: "team",
        traveler_count: 3,
        notes: "Client summit team",
      },
    },
    profile_refs: {
      leisure_profile_id: null,
      business_profile_id: "profile:tokyo-business",
    },
    artifacts: {
      objective_id: null,
      option_set_ids: [],
      itinerary_state_id: null,
      budget_state_id: null,
      policy_state_id: "policy:tokyo",
    },
  },
  {
    trip_id: "trip-leisure-seoul-weekend",
    user_id: "user:test",
    title: "Seoul gallery weekend",
    summary: "Shorter leisure trip with a tighter route envelope.",
    mode: "leisure",
    status: "draft",
    trip_frame: {
      start_date: "2026-06-12",
      end_date: "2026-06-15",
      duration_days: 4,
      primary_regions: ["Seoul"],
      traveler_party: {
        kind: "solo",
        traveler_count: 1,
        notes: "Gallery weekend",
      },
    },
    profile_refs: {
      leisure_profile_id: "profile:seoul",
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
];

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
    selected_planning_mode: "collaborative",
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
  planner_memory: {
    current_checkpoint_id: "planner-checkpoint:trip-leisure-kyoto-draft:1",
    checkpoints: [
      {
        checkpoint_id: "planner-checkpoint:trip-leisure-kyoto-draft:1",
        checkpoint_kind: "conversation_summary",
        turn_index: 1,
        message_count: 2,
        summary:
          "Turn 1 checkpoint keeps the latest traveler intent and planner guidance available for later resume.",
        source_message_ids: [
          "planner-action:trip-leisure-kyoto-draft:user-1",
          "planner-action:trip-leisure-kyoto-draft:planner-1",
        ],
        created_at: "2026-04-12T06:10:00+00:00",
        updated_at: "2026-04-12T06:10:00+00:00",
      },
    ],
    artifacts: [
      {
        memory_artifact_id: "planner-memory:trip-leisure-kyoto-draft:1",
        checkpoint_id: "planner-checkpoint:trip-leisure-kyoto-draft:1",
        artifact_kind: "conversation_summary",
        title: "Planner checkpoint 1",
        summary:
          "Turn 1 checkpoint keeps the latest traveler intent and planner guidance available for later resume.",
        detail:
          "Traveler focus: Keep the Kyoto baseline but protect recovery time. Planner summary: The planner recommends preserving the Kyoto baseline and revisiting transfers later.",
        source_message_ids: [
          "planner-action:trip-leisure-kyoto-draft:user-1",
          "planner-action:trip-leisure-kyoto-draft:planner-1",
        ],
        tags: ["planner-memory", "user-visible", "checkpoint-summary"],
        created_at: "2026-04-12T06:10:00+00:00",
        updated_at: "2026-04-12T06:10:00+00:00",
      },
    ],
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
      {
        scenario_id: "scenario:trip-leisure-kyoto-draft:2",
        title: "Kyoto plus Osaka fallback",
        rank: 2,
        score: 0.88,
        scenario_summary: {
          headline: "Higher-energy fallback with extra transfers",
          scenario_kind: "alternative",
          recommended_for_selection: false,
          total_travel_minutes: 360,
          total_transfer_count: 7,
          route_sequence: ["kyoto", "osaka", "kyoto"],
        },
        unresolved_tradeoffs: [
          {
            tradeoff_id: "tradeoff:osaka-nightlife",
            summary: "Higher transfer load to preserve nightlife breadth.",
            severity: "info",
          },
        ],
      },
    ],
  },
  ranking: {
    ranking_id: "ranking:trip-leisure-kyoto-draft:workspace",
    trip_id: "trip-leisure-kyoto-draft",
    title: "Kyoto leisure scenario comparison",
    summary: "Two ranked scenarios are available for workspace review.",
    lead_scenario_id: "scenario:trip-leisure-kyoto-draft:1",
    source_result_set_id: "ranked-results:kyoto-spring",
    source_refs: ["ranked-results:kyoto-spring"],
    rows: [
      {
        scenario_id: "scenario:trip-leisure-kyoto-draft:1",
        title: "Kyoto base with Uji day trip",
        rank: 1,
        score: 0.93,
        status: "positive",
        summary: "Balanced Kyoto culture baseline",
        scenario_kind: "primary",
        recommended_for_selection: true,
        feasible: true,
        route_sequence: ["kyoto", "uji", "kyoto"],
        total_travel_minutes: 265,
        total_transfer_count: 4,
        estimated_total: {
          currency: "JPY",
          typical_amount: 3400,
        },
        source_result_id: "ranked-result:kyoto-spring:1",
        supporting_option_ids: ["bundle-osaka-gateway"],
        objective_refs: ["objective:kyoto-culture"],
        unresolved_tradeoffs: [],
      },
      {
        scenario_id: "scenario:trip-leisure-kyoto-draft:2",
        title: "Kyoto plus Osaka fallback",
        rank: 2,
        score: 0.88,
        status: "caution",
        summary: "Higher-energy fallback with extra transfers",
        scenario_kind: "alternative",
        recommended_for_selection: false,
        feasible: true,
        route_sequence: ["kyoto", "osaka", "kyoto"],
        total_travel_minutes: 360,
        total_transfer_count: 7,
        estimated_total: {
          currency: "JPY",
          typical_amount: 3250,
        },
        source_result_id: "ranked-result:kyoto-spring:2",
        supporting_option_ids: ["bundle-kyoto-culture-day"],
        objective_refs: ["objective:kyoto-breadth"],
        unresolved_tradeoffs: [
          {
            tradeoff_id: "tradeoff:osaka-nightlife",
            summary: "Higher transfer load to preserve nightlife breadth.",
            severity: "info",
          },
        ],
      },
    ],
  },
  get route_comparison() {
    return this.runtime_scenario_comparison;
  },
  runtime_scenario_comparison: {
    title: "Kyoto leisure scenario comparison",
    summary: "Two runtime scenarios are available for map-backed comparison.",
    lead_scenario_id: "scenario:trip-leisure-kyoto-draft:1",
    comparison_axes: [
      { key: "score", label: "Planner score", direction: "higher_better" },
      { key: "travel_minutes", label: "Travel minutes", direction: "lower_better" },
      { key: "transfers", label: "Transfers", direction: "lower_better" },
    ],
    scenarios: [
      {
        scenario_id: "scenario:trip-leisure-kyoto-draft:1",
        title: "Kyoto base with Uji day trip",
        rank: 1,
        status: "lead",
        summary: "Balanced Kyoto culture baseline",
        comparison_note: "Lead route for the current workspace comparison set.",
        option_count: 2,
        route_sequence: ["kyoto", "uji", "kyoto"],
        route_summary: "kyoto -> uji -> kyoto",
        recommended_for_selection: true,
        feasible: true,
        metrics: {
          score: 0.93,
          travel_minutes: 265,
          transfers: 4,
          estimated_total: {
            currency: "JPY",
            typical_amount: 3400,
          },
        },
        delta: {
          score_delta: 0,
          travel_minutes_delta: 0,
          transfers_delta: 0,
          estimated_total_delta: 0,
        },
        highlights: ["Moderate travel friction with a clear cultural center of gravity."],
      },
      {
        scenario_id: "scenario:trip-leisure-kyoto-draft:2",
        title: "Kyoto plus Osaka fallback",
        rank: 2,
        status: "alternative",
        summary: "Higher-energy fallback with extra transfers",
        comparison_note: "Alternative route preserved for direct scenario comparison.",
        option_count: 2,
        route_sequence: ["kyoto", "osaka", "kyoto"],
        route_summary: "kyoto -> osaka -> kyoto",
        recommended_for_selection: false,
        feasible: true,
        metrics: {
          score: 0.88,
          travel_minutes: 360,
          transfers: 7,
          estimated_total: {
            currency: "JPY",
            typical_amount: 3250,
          },
        },
        delta: {
          score_delta: -0.05,
          travel_minutes_delta: 95,
          transfers_delta: 3,
          estimated_total_delta: -150,
        },
        highlights: ["Higher transfer load to preserve nightlife breadth."],
      },
    ],
    source_refs: ["ranked-results:kyoto-spring"],
  },
  runtime_state: {
    status: "ready",
    title: "Workspace runtime is ready",
    summary: "Inventory, scenario ranking, and comparison surfaces are ready for review.",
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
        bundle_context: "route_level_activity",
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
    runtime_state: {
      status: "ready",
      title: "Runtime inventory is ready",
      summary: "Persisted trip context is rich enough to assemble comparison-ready inventory bundles.",
    },
  },
  feasibility_summary: {
    assessment_count: 2,
    recommended_bundle_count: 1,
    blocking_bundle_count: 0,
    attention_bundle_count: 1,
    notes: ["Route feasibility is available for the current workspace bundle set."],
    assessments: [
      {
        bundle_id: "bundle-osaka-gateway",
        bundle_title: "Osaka arrival buffer",
        bundle_context: "transport_lodging",
        status: "positive",
        total_travel_minutes: 90,
        total_transfer_count: 1,
        friction_penalty_total: 0.4,
      },
      {
        bundle_id: "bundle-kyoto-culture-day",
        bundle_title: "Kyoto cultural anchor",
        bundle_context: "route_level_activity",
        status: "caution",
        total_travel_minutes: 175,
        total_transfer_count: 3,
        friction_penalty_total: 1.2,
      },
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
  proposal_state: {
    proposal_state_id: "proposal-state:trip-leisure-kyoto-draft",
    trip_id: "trip-leisure-kyoto-draft",
    proposal_id: "proposal:trip-leisure-kyoto-draft",
    proposal_version: "proposal-v3",
    scenario_id: "scenario:trip-leisure-kyoto-draft:1",
    execution_id: "exec-approved-001",
    submission_status: "succeeded",
    evaluation_status: "succeeded",
    proposal: {
      proposal_id: "proposal:trip-leisure-kyoto-draft",
      comparables: [
        {
          category: "lodging",
          label: "Conference Hotel",
          vendor: "Marriott",
          booking_channel: "Navan",
          estimated_cost: {
            currency: "USD",
            typical_amount: 245,
          },
          notes: ["Near the venue."],
        },
      ],
      approval_notes: ["Manager review required."],
    },
    evaluation: {
      evaluation_result: {
        evaluation_id: "eval-approved-001",
        status: "compliant",
        approval_requirements: [
          {
            role: "manager",
            reason: "International travel",
            mandatory: true,
          },
        ],
        failure_reasons: [],
        notes: ["Policy constraints satisfied."],
        compliance_score: 0.98,
      },
    },
    follow_up: {
      status: "resolved",
      path: "approval",
      title: "Approval-ready proposal",
      summary: "Policy evaluation passed. Move the workspace packet into final approval handling.",
      recommended_action: "prepare_approval",
      recommended_label: "Advance to approval",
      alternatives: [],
      guidance: [],
      notes: [],
      selected_alternative: null,
      requested_exception: null,
    },
    summary: {
      submission_status: "succeeded",
      submission_summary: "Proposal submitted to the policy engine.",
      submission_requires_polling: false,
      evaluation_transport_status: "succeeded",
      evaluation_result_status: "compliant",
      approval_ready: true,
      comparable_count: 1,
      highlights: ["Policy constraints satisfied."],
      follow_up_status: "resolved",
      follow_up_title: "Approval-ready proposal",
      follow_up_summary:
        "Policy evaluation passed. Move the workspace packet into final approval handling.",
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
  view_model: null,
} satisfies WorkspaceData;

const plannerSessionPayload = {
  trip_id: "trip-leisure-kyoto-draft",
  session_state_id: "session:trip-leisure-kyoto-draft",
  conversation_id: "planner-conversation:trip-leisure-kyoto-draft",
  resumed_at: null,
  session: workspacePayload.session,
  planner_panel_state: workspacePayload.planner_panel_state,
  planner_memory: workspacePayload.planner_memory,
  available_tools: [
    {
      tool_name: "read_workspace_state",
      description: "Read the current persisted workspace state.",
      mutates_state: false,
    },
    {
      tool_name: "update_budget_plan",
      description: "Update the persisted workspace budget.",
      mutates_state: true,
    },
  ],
  activity_log: workspacePayload.activity_log,
  messages: [
    {
      message_id: "planner-action:trip-leisure-kyoto-draft:user-1",
      role: "user",
      content: "Can you summarize what I should compare next?",
      created_at: "2026-04-12T06:09:00+00:00",
      refs: ["session:trip-leisure-kyoto-draft"],
      tool_calls: [],
      structured_blocks: [],
    },
    {
      message_id: "planner-action:trip-leisure-kyoto-draft:planner-1",
      role: "planner",
      content: "Compare the Kyoto baseline against the Osaka fallback before locking the plan.",
      created_at: "2026-04-12T06:10:00+00:00",
      refs: ["session:trip-leisure-kyoto-draft", "scenario:trip-leisure-kyoto-draft:1"],
      tool_calls: [],
      structured_blocks: [],
    },
  ],
} satisfies PlannerSessionResponse;

function renderWorkspacePage() {
  return render(
    <TestMemoryRouter>
      <WorkspacePage />
    </TestMemoryRouter>
  );
}

function getPlannerHost() {
  const plannerHost = document.querySelector(".planner-panel-host");
  expect(plannerHost).toBeTruthy();
  return plannerHost as HTMLDivElement;
}

const originalMatchMedia = window.matchMedia;

function stubMatchMedia(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

describe("WorkspacePage", () => {
  beforeEach(() => {
    mockedFetchPlannerSession.mockResolvedValue(plannerSessionPayload);
    mockedSubmitPlannerTurn.mockResolvedValue(plannerSessionPayload);
    mockedSubmitRouteOptionAction.mockResolvedValue(workspacePayload);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.unstubAllEnvs();
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: originalMatchMedia,
    });
    mockedAnswerPlannerDecision.mockReset();
    mockedFetchPlannerSession.mockReset();
    mockedSubmitPlannerOptionFeedback.mockReset();
    mockedSubmitRouteOptionAction.mockReset();
    mockedSubmitPlannerTurn.mockReset();
    mockedUpdateWorkspacePlanningMode.mockReset();
    mockedSaveWorkspaceBudget.mockReset();
    mockedRecordWorkspaceSpendEvent.mockReset();
    mockedRefreshWorkspaceProposalStatus.mockReset();
    mockedCreateNotebookItem.mockReset();
    mockedUpdateNotebookItem.mockReset();
    mockedDeleteNotebookItem.mockReset();
    mockedSetNotebookFocus.mockReset();
  });

  it("does not render raw runtime/provider/debug labels for default leisure workspaces", async () => {
    const leisureWorkspaceWithViewModel: WorkspaceData = {
      ...workspacePayload,
      view_model: {
        user_summary: {
          trip_title: workspacePayload.trip_record.trip.title,
          trip_mode: "leisure",
          mode_label: "Leisure trip",
          status: "ready",
          headline: "Your trip plan is ready to review.",
          decided: ["2 saved scenario draft(s)"],
          uncertain: [],
        },
        next_step: {
          title: "Review and pick a scenario",
          summary:
            "Compare the saved scenarios and choose one to keep planning around.",
          action_label: "Open scenario comparison",
          action_target: "scenario-comparison",
          blocked: false,
        },
        panel_visibility: {
          show_budget_panel: true,
          show_policy_posture: false,
          show_proposal_panel: false,
          show_approval_readiness_panel: false,
        },
        policy_presentation: {
          active_policy_state: false,
          posture_label: "Not applicable",
          approval_status_label: "Not applicable",
          next_step_label: "No policy action needed",
          summary: "Policy approval is not part of this workspace yet.",
        },
        business_summary: null,
        debug_state: { sections: {} },
      },
    };
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve(leisureWorkspaceWithViewModel),
      trips: Promise.resolve(tripComparisonPayload),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(
        screen.getAllByRole("heading", { name: "Spring Kyoto anniversary draft" }).length
      ).toBeGreaterThan(0);
    });
    expect(screen.getByText("Leisure trip")).toBeInTheDocument();
    expect(screen.getByText("Your trip plan is ready to review.")).toBeInTheDocument();
    expect(screen.getByText("2 saved scenario draft(s)")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Review and pick a scenario" })).toBeInTheDocument();
    expect(
      screen.getByText("Compare the saved scenarios and choose one to keep planning around.")
    ).toBeInTheDocument();
    const helpDisclosure = screen.getByText("How to use this trip workspace").closest("details");
    expect(helpDisclosure).not.toBeNull();
    expect(helpDisclosure).not.toHaveAttribute("open");

    const renderedText = document.body.textContent ?? "";
    const forbiddenRawLabels = [
      "runtime provider",
      "fallback mode",
      "trip-scoped",
      "runtime-backed",
      "api client",
      "policy_state_id",
      "proposal_state_id",
      "session_state_id",
      "scenario_search_id",
    ];
    for (const label of forbiddenRawLabels) {
      expect(renderedText.toLowerCase()).not.toContain(label.toLowerCase());
    }
  });

  it("renders timeline structure from persisted trip and scenario state", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve(workspacePayload),
      trips: Promise.resolve(tripComparisonPayload),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getAllByRole("heading", { name: "Spring Kyoto anniversary draft" }).length).toBeGreaterThan(0);
    });

    const routeContextMap = screen.getByLabelText("Route context map");

    expect(screen.getAllByRole("heading", { name: "Kyoto base with Uji day trip" }).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Map preview for Kyoto base with Uji day trip" })).toBeInTheDocument();
    expect(within(routeContextMap).getAllByText("Kyoto").length).toBeGreaterThan(0);
    expect(within(routeContextMap).getAllByText("Uji").length).toBeGreaterThan(0);
    expect(screen.getByText("Save baseline scenario")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Traveler planning workspace" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "How should the planner work?" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Collaborative/ })).toBeChecked();
    await waitFor(() => {
      expect(mockedFetchPlannerSession).toHaveBeenCalledWith("trip-leisure-kyoto-draft");
    });
    expect(screen.getByRole("heading", { name: "Message your planner" })).toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.getByText("Compare the Kyoto baseline against the Osaka fallback before locking the plan.")
      ).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Compare routes" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Planner tools available")).not.toBeInTheDocument();
    expect(routeContextMap).toBeInTheDocument();
    expect(screen.getByText("Destination context")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Trip rhythm and day sequence" })).toBeInTheDocument();
    expect(screen.getByLabelText("Timeline summary")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Review route tradeoffs" })).toBeInTheDocument();
    expect(screen.getByLabelText("Scenario review board")).toBeInTheDocument();
    expect(screen.getAllByText("Approval posture").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Places and options to review" })).toBeInTheDocument();
    expect(screen.getAllByText("Osaka arrival buffer").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Kyoto cultural anchor").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Approval packet is ready" })).toBeInTheDocument();
    expect(screen.getByText("Ready for approval")).toBeInTheDocument();
    expect(screen.getAllByText("Advance to approval").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Options and readiness signals" })).toBeInTheDocument();
    expect(screen.getByText("Conference Hotel")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Planner notes to keep" })).toBeInTheDocument();
    expect(screen.getByText("Planner checkpoint 1")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Compare this workspace with other saved trips" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Compare 2. Kyoto plus Osaka fallback" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Compare with Tokyo client summit" })).toBeInTheDocument();
    await waitFor(() => {
      const plannerPanel = getPlannerHost().shadowRoot?.querySelector(
        '[aria-label="Planner side panel"]'
      );
      expect(plannerPanel).toBeTruthy();
    });
  });

  it("hides proposal and approval panels for leisure workspaces without active policy state", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve({
        ...workspacePayload,
        proposal_state: null,
      }),
      trips: Promise.resolve(tripComparisonPayload),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getAllByRole("heading", { name: "Spring Kyoto anniversary draft" }).length).toBeGreaterThan(0);
    });

    expect(screen.queryByText("Approval packet")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Options and readiness signals" })).not.toBeInTheDocument();
    expect(screen.queryByText("Approval posture")).not.toBeInTheDocument();
    expect(screen.queryByText("Policy posture")).not.toBeInTheDocument();
  });

  it("persists planning mode selections through the workspace API", async () => {
    const user = userEvent.setup();
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve(workspacePayload),
      trips: Promise.resolve(tripComparisonPayload),
    });
    mockedUpdateWorkspacePlanningMode.mockResolvedValue({
      ...workspacePayload,
      session: {
        ...workspacePayload.session,
        selected_planning_mode: "delegated",
      },
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "How should the planner work?" })).toBeInTheDocument();
    });
    await user.click(screen.getByRole("radio", { name: /Delegated/ }));

    expect(mockedUpdateWorkspacePlanningMode).toHaveBeenCalledWith(
      "trip-leisure-kyoto-draft",
      "delegated"
    );
    await waitFor(() => {
      expect(screen.getByRole("radio", { name: /Delegated/ })).toBeChecked();
    });
  });

  it("submits planner conversation turns through the trip-scoped planner API", async () => {
    const user = userEvent.setup();
    const nextPlannerSession = {
      ...plannerSessionPayload,
      messages: [
        ...plannerSessionPayload.messages,
        {
          message_id: "planner-action:trip-leisure-kyoto-draft:user-2",
          role: "user",
          content: "Keep Uji, but reduce transfer pressure.",
          created_at: "2026-04-12T06:15:00+00:00",
          refs: ["session:trip-leisure-kyoto-draft"],
          tool_calls: [],
          structured_blocks: [
            {
              kind: "traveler_input_summary",
              title: "Traveler input summary",
              body: "Key details pulled out of the traveler message.",
              items: ["Preferences: Keep Uji, reduce transfer pressure"],
              metadata: {
                preferences: ["Keep Uji, but reduce transfer pressure"],
              },
              hidden: false,
            },
          ],
        },
        {
          message_id: "planner-action:trip-leisure-kyoto-draft:planner-2",
          role: "planner",
          content: "Keep the Uji day trip and compare fewer evening moves before the next checkpoint.",
          created_at: "2026-04-12T06:16:00+00:00",
          refs: ["session:trip-leisure-kyoto-draft", "scenario:trip-leisure-kyoto-draft:1"],
          turn_metadata: {
            plan_maturity: "coherent_plan",
            task_class: "route_comparison",
            visible_response_blocks: [
              {
                kind: "next_steps",
                title: "Next planning moves",
                items: ["Compare fewer evening moves.", "Preserve Uji as the baseline day trip."],
              },
            ],
            debug_routing_details: {
              runtime_mode: "fallback",
              runtime_provider: null,
            },
          },
          structured_blocks: [
            {
              kind: "summary",
              title: "Planner summary",
              body: "Keep the Uji day trip and reduce evening movement.",
              items: ["Preserve the preferred Kyoto baseline."],
              metadata: {},
              hidden: false,
            },
            {
              kind: "question",
              title: "Questions to settle",
              body: "",
              items: ["How much evening variety should the route preserve?"],
              metadata: {},
              hidden: false,
            },
            {
              kind: "decision",
              title: "Open decisions",
              body: "",
              items: ["Should the current Kyoto route become the saved baseline?"],
              metadata: {
                decision_ids: ["decision:save-baseline"],
              },
              hidden: false,
            },
            {
              kind: "route_option",
              title: "Route options in view",
              body: "",
              items: ["Kyoto base with Uji day trip: Balanced Kyoto culture baseline"],
              metadata: {
                option_ids: ["scenario:trip-leisure-kyoto-draft:1"],
              },
              hidden: false,
            },
            {
              kind: "comparison",
              title: "Comparison frame",
              body: "",
              items: [
                "Kyoto baseline has fewer transfers; Osaka fallback has more evening variety.",
              ],
              metadata: {},
              hidden: false,
            },
            {
              kind: "next_action",
              title: "Next actions",
              body: "",
              items: ["Compare fewer evening moves.", "Preserve Uji as the baseline day trip."],
              metadata: {},
              hidden: false,
            },
            {
              kind: "debug",
              title: "Planner diagnostics",
              body: "Routing details and tool traces are hidden from the normal traveler view.",
              items: [],
              metadata: {
                routing: {
                  runtime_mode: "fallback",
                },
              },
              hidden: true,
            },
          ],
          tool_calls: [
            {
              tool_name: "read_workspace_state",
              status: "succeeded",
              summary: "Read the current workspace state.",
              mutates_state: false,
              refs: ["session:trip-leisure-kyoto-draft"],
              output: {},
            },
          ],
        },
      ],
    } satisfies PlannerSessionResponse;
    mockedSubmitPlannerTurn.mockResolvedValue(nextPlannerSession);

    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve(workspacePayload),
      trips: Promise.resolve(tripComparisonPayload),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByText("Can you summarize what I should compare next?")).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText("Message the planner"), "Keep Uji, but reduce transfer pressure.");
    await user.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() => {
      expect(mockedSubmitPlannerTurn).toHaveBeenCalledWith(
        "trip-leisure-kyoto-draft",
        "Keep Uji, but reduce transfer pressure."
      );
    });
    await waitFor(() => {
      expect(
        screen.getByText("Keep the Uji day trip and compare fewer evening moves before the next checkpoint.")
      ).toBeInTheDocument();
    });
    expect(screen.getByText("coherent plan")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Planner summary" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Questions to settle" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Open decisions" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Route options in view" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Comparison frame" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Next actions" })).toBeInTheDocument();
    expect(screen.getByText("Traveler input summary")).toBeInTheDocument();
    expect(screen.getByText("Compare fewer evening moves.")).toBeInTheDocument();
    expect(screen.queryByText("Planner diagnostics")).not.toBeInTheDocument();
    expect(screen.queryByText("read_workspace_state: Read the current workspace state.")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Diagnostics" }));
    expect(screen.getByText("Planner diagnostics")).toBeInTheDocument();
    expect(screen.getByText("read_workspace_state: Read the current workspace state.")).toBeInTheDocument();
    expect(screen.getByLabelText("Message the planner")).toHaveValue("");
  });

  it("fills traveler-friendly prompt suggestions into the planner message box", async () => {
    const user = userEvent.setup();
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve(workspacePayload),
      trips: Promise.resolve(tripComparisonPayload),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Summarize decisions" })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Summarize decisions" }));

    expect(screen.getByLabelText("Message the planner")).toHaveValue(
      "Summarize what we have decided, what is still open, and what you recommend next."
    );
  });

  it("labels the planner panel as deterministic fallback when runtime metadata is absent", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve(workspacePayload),
      trips: Promise.resolve(tripComparisonPayload),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByLabelText("Planner availability")).toBeInTheDocument();
    });

    const runtime = screen.getByLabelText("Planner availability");
    expect(within(runtime).getByText("Guided planner")).toHaveClass(
      "planner-runtime-pill--fallback"
    );
    expect(within(runtime).getByText("Planning guide")).toBeInTheDocument();
  });

  it("merges fetched planner session state into the workspace surface", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve(workspacePayload),
      trips: Promise.resolve(tripComparisonPayload),
    });
    mockedFetchPlannerSession.mockResolvedValueOnce({
      ...plannerSessionPayload,
      planner_panel_state: {
        ...workspacePayload.planner_panel_state,
        planner_behavior: {
          ...workspacePayload.planner_panel_state.planner_behavior,
          runtime_status: "ready",
          runtime_mode: "model",
          runtime_label: "Model-backed planner",
          runtime_summary: "Planner model configuration is active for this workspace.",
        },
      },
      activity_log: [
        {
          activity_event_id: "activity:session-refresh",
          occurred_at: "2026-04-12T07:09:00+00:00",
          event_kind: "planner_session_loaded",
          summary: "Planner session loaded model-backed workspace context.",
        },
      ],
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByLabelText("Planner availability")).toBeInTheDocument();
    });

    const runtime = screen.getByLabelText("Planner availability");
    await waitFor(() => {
      expect(within(runtime).getByText("AI-assisted planner")).toHaveClass(
        "planner-runtime-pill--ready"
      );
    });
    expect(screen.getByText("Planner session loaded model-backed workspace context.")).toBeInTheDocument();
  });

  it("labels the planner panel as model-backed when runtime metadata reports a configured model", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve({
        ...workspacePayload,
        planner_panel_state: {
          ...workspacePayload.planner_panel_state,
          planner_behavior: {
            ...workspacePayload.planner_panel_state.planner_behavior,
            runtime_status: "ready",
            runtime_mode: "model",
            runtime_label: "Model-backed planner",
            runtime_summary: "Planner model configuration is active for this workspace.",
          },
        },
      }),
      trips: Promise.resolve(tripComparisonPayload),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByLabelText("Planner availability")).toBeInTheDocument();
    });

    const runtime = screen.getByLabelText("Planner availability");
    expect(within(runtime).getByText("AI-assisted planner")).toHaveClass("planner-runtime-pill--ready");
    expect(within(runtime).getByText("Live assistance")).toBeInTheDocument();
  });

  it("updates the map surface when a different scenario preview is selected", async () => {
    const user = userEvent.setup();
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve(workspacePayload),
      trips: Promise.resolve(tripComparisonPayload),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "2. Kyoto plus Osaka fallback" })).toBeInTheDocument();
    });

    expect(
      screen.getByRole("heading", { name: "Map preview for Kyoto base with Uji day trip" })
    ).toBeInTheDocument();
    expect(screen.getAllByText("kyoto -> uji -> kyoto").length).toBeGreaterThan(0);
    expect(screen.getByText("93 / 100 planner score")).toBeInTheDocument();
    expect(screen.getAllByText("Balanced Kyoto culture baseline").length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "2. Kyoto plus Osaka fallback" }));

    expect(
      screen.getByRole("heading", { name: "Map preview for Kyoto plus Osaka fallback" })
    ).toBeInTheDocument();
    expect(screen.getAllByText("kyoto -> osaka -> kyoto").length).toBeGreaterThan(0);
    expect(screen.getByText("88 / 100 planner score")).toBeInTheDocument();
    expect(screen.getAllByText("Higher-energy fallback with extra transfers").length).toBeGreaterThan(0);
    expect(within(screen.getByLabelText("Route context map")).getAllByText("Osaka").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Higher transfer load to preserve nightlife breadth.").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Selected scenario affordances" })).toBeInTheDocument();
    expect(screen.getByText("Alternative scenario")).toBeInTheDocument();
    expect(screen.getByText("7 transfer checkpoint(s)")).toBeInTheDocument();
  });

  it("renders the Google Maps JavaScript provider path when configured", async () => {
    vi.stubEnv("VITE_GOOGLE_MAPS_BROWSER_API_KEY", "test-key");
    const user = userEvent.setup();
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve(workspacePayload),
      trips: Promise.resolve(tripComparisonPayload),
    });

    const { container } = renderWorkspacePage();

    await waitFor(() => {
      expect(
        screen.getByLabelText("Interactive map for Kyoto base with Uji day trip")
      ).toBeInTheDocument();
    });

    expect(screen.getAllByText("Google Maps JavaScript adapter").length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Route geometry overlay for Kyoto base with Uji day trip")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /stop marker:/ }).length).toBeGreaterThan(0);
    expect(container.querySelector("iframe")).toBeNull();
    expect(screen.queryByTitle(/google maps/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Fallback option markers")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /lodging marker: Osaka arrival buffer/ }));
    expect(screen.getAllByRole("heading", { name: "Osaka arrival buffer" }).length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: /activity marker: Kyoto cultural anchor/ }));
    expect(screen.getAllByRole("heading", { name: "Kyoto cultural anchor" }).length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: /policy marker: Route burden warning/ }));
    expect(screen.getByRole("heading", { name: "Route burden warning" })).toBeInTheDocument();
    expect(screen.getAllByText("Approval or feasibility warning active").length).toBeGreaterThan(0);
    expect(screen.getByText("Live provider path")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "2. Kyoto plus Osaka fallback" }));

    expect(screen.getByLabelText("Interactive map for Kyoto plus Osaka fallback")).toBeInTheDocument();
    expect(screen.getAllByText("Osaka").length).toBeGreaterThan(0);
  });

  it("uses the legacy embed API key env var as a compatibility fallback", async () => {
    vi.stubEnv("VITE_GOOGLE_MAPS_EMBED_API_KEY", "legacy-test-key");
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve(workspacePayload),
      trips: Promise.resolve(tripComparisonPayload),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(
        screen.getByLabelText("Interactive map for Kyoto base with Uji day trip")
      ).toBeInTheDocument();
    });

    expect(screen.getAllByText("Google Maps JavaScript adapter").length).toBeGreaterThan(0);
    expect(screen.getByText("Live provider path")).toBeInTheDocument();
  });

  it("updates the dedicated comparison surfaces when scenario and trip selections change", async () => {
    const user = userEvent.setup();
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve(workspacePayload),
      trips: Promise.resolve(tripComparisonPayload),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Compare 2. Kyoto plus Osaka fallback" })).toBeInTheDocument();
    });

    expect(screen.getAllByText("Moderate travel friction with a clear cultural center of gravity.").length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "Compare 2. Kyoto plus Osaka fallback" }));
    expect(
      screen.getByRole("heading", { name: "Map preview for Kyoto plus Osaka fallback" })
    ).toBeInTheDocument();
    expect(screen.getAllByText("Osaka rainy-day fallback").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Higher transfer load to preserve nightlife breadth.").length).toBeGreaterThan(0);

    expect(screen.getByText("Tokyo client summit")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Compare with Seoul gallery weekend" }));
    expect(screen.getByText("Compared trip: Seoul")).toBeInTheDocument();
    expect(screen.getByText("Seoul gallery weekend is stored as a leisure trip with 1 traveler(s).")).toBeInTheDocument();
  });

  it("falls back to plain number formatting when comparable currency codes are invalid", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve({
        ...workspacePayload,
        proposal_state: {
          ...workspacePayload.proposal_state,
          proposal: {
            ...workspacePayload.proposal_state.proposal,
            comparables: [
              {
                ...workspacePayload.proposal_state.proposal.comparables[0],
                estimated_cost: {
                  ...workspacePayload.proposal_state.proposal.comparables[0].estimated_cost,
                  currency: "INVALID",
                },
              },
            ],
          },
        },
      }),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Options and readiness signals" })).toBeInTheDocument();
    });

    expect(screen.getByText(/Marriott via Navan · 245/)).toBeInTheDocument();
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
        route_comparison: {
          ...workspacePayload.route_comparison,
          lead_scenario_id: null,
          scenarios: [],
        },
        runtime_scenario_comparison: {
          ...workspacePayload.runtime_scenario_comparison,
          lead_scenario_id: null,
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
      trips: Promise.resolve([tripComparisonPayload[0]]),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByText("Day plan is not ready yet")).toBeInTheDocument();
    });
    expect(
      screen.getByText(
        "Ask the planner to compare routes or draft a first sequence of stops."
      )
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(getPlannerHost().shadowRoot?.querySelector('[aria-label="Planner side panel"]')).toBeTruthy();
    });
  });

  it("renders the fallback map state and compact review copy on small screens", async () => {
    stubMatchMedia(true);
    vi.stubEnv("VITE_GOOGLE_MAPS_BROWSER_API_KEY", "");
    vi.stubEnv("VITE_GOOGLE_MAPS_EMBED_API_KEY", "");
    vi.stubEnv("VITE_GOOGLE_MAPS_PROVIDER_STATE", "missing");
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve(workspacePayload),
      trips: Promise.resolve(tripComparisonPayload),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Compact route tradeoffs" })).toBeInTheDocument();
    });

    expect(screen.getByText("Compact review keeps route, day plan, and next choices close together.")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Textual fallback route path")).toBeInTheDocument();
    });
    expect(screen.getAllByText(/Google Maps JavaScript is not configured in this environment/).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Compact day-by-day review" })).toBeInTheDocument();
  });

  it("renders a loading fallback state while the provider adapter is initializing", async () => {
    vi.stubEnv("VITE_GOOGLE_MAPS_BROWSER_API_KEY", "test-key");
    vi.stubEnv("VITE_GOOGLE_MAPS_PROVIDER_STATE", "loading");
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve(workspacePayload),
      trips: Promise.resolve(tripComparisonPayload),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByText("Provider loading fallback path")).toBeInTheDocument();
    });

    expect(screen.getAllByText(/Google Maps JavaScript is loading/).length).toBeGreaterThan(0);
    expect(within(screen.getByLabelText("Route context map")).getAllByText("Kyoto").length).toBeGreaterThan(0);
  });

  it("renders a provider-error fallback state and keeps route context visible", async () => {
    vi.stubEnv("VITE_GOOGLE_MAPS_BROWSER_API_KEY", "test-key");
    vi.stubEnv("VITE_GOOGLE_MAPS_PROVIDER_STATE", "error");
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve(workspacePayload),
      trips: Promise.resolve(tripComparisonPayload),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByText("Provider error fallback path")).toBeInTheDocument();
    });

    expect(screen.getAllByText(/failed to load/).length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Fallback option markers")).toBeInTheDocument();
    expect(within(screen.getByLabelText("Route context map")).getAllByText("Kyoto").length).toBeGreaterThan(0);
  });

  it("renders a sparse-route fallback state and keeps map context visible", async () => {
    vi.stubEnv("VITE_GOOGLE_MAPS_BROWSER_API_KEY", "test-key");
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve({
        ...workspacePayload,
        route_comparison: {
          ...workspacePayload.route_comparison,
          scenarios: workspacePayload.route_comparison.scenarios.map((scenario) =>
            scenario.scenario_id === "scenario:trip-leisure-kyoto-draft:1"
              ? {
                  ...scenario,
                  route_sequence: ["kyoto"],
                  route_summary: "kyoto",
                }
              : scenario
          ),
        },
        runtime_scenario_comparison: {
          ...workspacePayload.runtime_scenario_comparison,
          scenarios: workspacePayload.runtime_scenario_comparison.scenarios.map((scenario) =>
            scenario.scenario_id === "scenario:trip-leisure-kyoto-draft:1"
              ? {
                  ...scenario,
                  route_sequence: ["kyoto"],
                  route_summary: "kyoto",
                }
              : scenario
          ),
        },
      }),
      trips: Promise.resolve(tripComparisonPayload),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByText("Sparse route fallback path")).toBeInTheDocument();
    });

    expect(screen.getAllByText(/needs at least an origin and destination/).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Map preview for Kyoto base with Uji day trip" })).toBeInTheDocument();
    expect(within(screen.getByLabelText("Route context map")).getAllByText("Kyoto").length).toBeGreaterThan(0);
  });

  it("renders an explicit empty state when runtime scenarios are unavailable", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve({
        ...workspacePayload,
        route_comparison: {
          ...workspacePayload.route_comparison,
          lead_scenario_id: null,
          scenarios: [],
        },
        runtime_scenario_comparison: {
          ...workspacePayload.runtime_scenario_comparison,
          lead_scenario_id: null,
          scenarios: [],
        },
      }),
      trips: Promise.resolve(tripComparisonPayload),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Review route tradeoffs" })).toBeInTheDocument();
    });

    expect(screen.queryByLabelText("Scenario review board")).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "No route ideas are available yet, so there is nothing to compare."
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
        runtime_state: {
          status: "partial",
          title: "Workspace runtime is partially assembled",
          summary: "Add trip dates or duration to replace the bounded fallback with runtime bundle assembly.",
        },
        inventory_summary: {
          bundle_count: 0,
          bundles: [],
          notes: ["Trip dates or duration are still missing, so inventory assembly stays partial."],
          runtime_state: {
            status: "partial",
            title: "Runtime inventory is partially specified",
            summary: "Add trip dates or duration to replace the bounded fallback with runtime bundle assembly.",
          },
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
      trips: Promise.resolve(tripComparisonPayload),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getAllByRole("heading", { name: "Chicago kickoff" }).length).toBeGreaterThan(0);
    });

    expect(screen.getByText("Dates not set yet")).toBeInTheDocument();
    expect(screen.getByText("Duration not set yet")).toBeInTheDocument();
    expect(screen.getByText("Options need more trip detail")).toBeInTheDocument();
    expect(screen.getByText("The planner needs a little more trip detail before it can group options.")).toBeInTheDocument();
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

  it("surfaces a pending execution state before the proposal is sent", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve({
        ...workspacePayload,
        proposal_state: {
          ...workspacePayload.proposal_state,
          submission_status: "pending",
          evaluation_status: null,
          follow_up: null,
          summary: {
            submission_status: "pending",
            submission_summary: "",
            submission_requires_polling: false,
            evaluation_transport_status: undefined,
            evaluation_result_status: undefined,
            approval_ready: false,
            comparable_count: 1,
            highlights: [],
            follow_up_status: undefined,
            follow_up_title: undefined,
            follow_up_summary: undefined,
          },
        },
      }),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(
        screen.getByText(
          "Build and submit the approval packet to start live policy execution for this workspace."
        )
      ).toBeInTheDocument();
    });
    expect(screen.getByText("Waiting for policy review")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Refresh live status" })).not.toBeInTheDocument();
  });

  it("surfaces a deferred execution state while the remote verdict is queued", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve({
        ...workspacePayload,
        proposal_state: {
          ...workspacePayload.proposal_state,
          submission_status: "deferred",
          evaluation_status: null,
          follow_up: null,
          summary: {
            ...workspacePayload.proposal_state.summary,
            submission_status: "deferred",
            submission_summary: "Proposal queued for evaluation",
            submission_requires_polling: true,
            evaluation_transport_status: undefined,
            evaluation_result_status: undefined,
            approval_ready: false,
            follow_up_status: undefined,
            follow_up_title: undefined,
            follow_up_summary: undefined,
          },
        },
      }),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Policy review is deferred" })).toBeInTheDocument();
    });
    expect(screen.getByText("Waiting for policy review")).toBeInTheDocument();
    expect(screen.getByText("Proposal queued for evaluation")).toBeInTheDocument();
    expect(screen.getByText("Keep the workspace open for remote results")).toBeInTheDocument();
  });

  it("surfaces a running execution state while live polling is still in progress", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve({
        ...workspacePayload,
        proposal_state: {
          ...workspacePayload.proposal_state,
          submission_status: "submitted",
          evaluation_status: "running",
          follow_up: null,
          summary: {
            ...workspacePayload.proposal_state.summary,
            submission_status: "submitted",
            submission_summary: "Policy engine accepted the packet and is still evaluating it.",
            submission_requires_polling: true,
            evaluation_transport_status: "running",
            evaluation_result_status: undefined,
            approval_ready: false,
            follow_up_status: undefined,
            follow_up_title: undefined,
            follow_up_summary: undefined,
          },
        },
      }),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Policy review is running" })).toBeInTheDocument();
    });
    expect(screen.getByText("Waiting for policy review")).toBeInTheDocument();
    expect(screen.getByText("Policy engine accepted the packet and is still evaluating it.")).toBeInTheDocument();
    expect(screen.getByText("Keep the workspace open for remote results")).toBeInTheDocument();
  });

  it("keeps awaiting evaluation refreshable after execution succeeds", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve({
        ...workspacePayload,
        proposal_state: {
          ...workspacePayload.proposal_state,
          submission_status: "succeeded",
          evaluation_status: "retry_scheduled",
          follow_up: {
            ...workspacePayload.proposal_state.follow_up,
            status: "awaiting_evaluation",
            title: "Awaiting policy verdict",
            summary: "Policy execution finished, but the evaluation result still needs to load.",
          },
          summary: {
            ...workspacePayload.proposal_state.summary,
            submission_status: "succeeded",
            submission_summary: "Policy execution completed and the evaluation result is ready.",
            submission_requires_polling: true,
            evaluation_transport_status: "retry_scheduled",
            evaluation_result_status: undefined,
            approval_ready: false,
            follow_up_status: "awaiting_evaluation",
            follow_up_title: "Awaiting policy verdict",
            follow_up_summary:
              "Policy execution finished, but the evaluation result still needs to load.",
          },
        },
      }),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Awaiting policy evaluation result" })).toBeInTheDocument();
    });
    expect(
      screen.getAllByText("Policy execution finished, but the evaluation result still needs to load.").length
    ).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Refresh live status" })).toBeInTheDocument();
  });

  it("keeps refresh affordances visible when execution succeeded but evaluation is still missing", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve({
        ...workspacePayload,
        proposal_state: {
          ...workspacePayload.proposal_state,
          submission_status: "succeeded",
          evaluation_status: "succeeded",
          follow_up: null,
          summary: {
            ...workspacePayload.proposal_state.summary,
            submission_status: "succeeded",
            submission_summary: "Execution finished, but the evaluation payload still needs to be persisted.",
            submission_requires_polling: false,
            evaluation_transport_status: "succeeded",
            evaluation_result_status: null,
            approval_ready: false,
            follow_up_status: null,
            follow_up_title: null,
            follow_up_summary: null,
          },
        },
      }),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Awaiting policy evaluation result" })).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Refresh live status" })).toBeInTheDocument();
    expect(
      screen.getByText("Execution finished, but the evaluation payload still needs to be persisted.")
    ).toBeInTheDocument();
  });

  it("refreshes the proposal lifecycle when the workspace requests live status", async () => {
    mockedRefreshWorkspaceProposalStatus.mockResolvedValue({
      ...workspacePayload.proposal_state,
      submission_status: "succeeded",
      evaluation_status: "succeeded",
      follow_up: {
        status: "reoptimization_required",
        path: "reoptimization",
        title: "Reoptimization path required",
        summary: "Use a compliant downtown property before resubmitting the approval packet.",
        recommended_action: "reoptimize",
        recommended_label: "Reoptimize plan",
        alternatives: [
          {
            category: "lodging",
            summary: "Use a compliant downtown property",
            rationale: "Alternative meets nightly cap and booking-channel requirements.",
            comparable_ref: "lodging-alt-2",
          },
        ],
        guidance: ["Keep the policy-safe lodging alternative attached to the next submission."],
        notes: [],
        selected_alternative: {
          category: "lodging",
          summary: "Use a compliant downtown property",
          rationale: "Alternative meets nightly cap and booking-channel requirements.",
          comparable_ref: "lodging-alt-2",
        },
        requested_exception: null,
      },
      summary: {
        ...workspacePayload.proposal_state.summary,
        submission_status: "succeeded",
        submission_summary: "Policy evaluation completed",
        submission_requires_polling: false,
        evaluation_transport_status: "succeeded",
        evaluation_result_status: "non_compliant",
        approval_ready: false,
        follow_up_status: "reoptimization_required",
        follow_up_title: "Reoptimization path required",
        follow_up_summary: "Use a compliant downtown property before resubmitting the approval packet.",
      },
    });
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve({
        ...workspacePayload,
        proposal_state: {
          ...workspacePayload.proposal_state,
          submission_status: "deferred",
          evaluation_status: null,
          follow_up: null,
          summary: {
            ...workspacePayload.proposal_state.summary,
            submission_status: "deferred",
            submission_summary: "Proposal queued for evaluation",
            submission_requires_polling: true,
            evaluation_transport_status: null,
            evaluation_result_status: null,
            approval_ready: false,
            follow_up_status: null,
            follow_up_title: null,
            follow_up_summary: null,
          },
        },
      }),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Refresh live status" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Refresh live status" }));

    await waitFor(() => {
      expect(mockedRefreshWorkspaceProposalStatus).toHaveBeenCalledWith("trip-leisure-kyoto-draft");
    });
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Policy review finished with follow-up" })).toBeInTheDocument();
    });
    expect(
      screen.getAllByText("Use a compliant downtown property before resubmitting the approval packet.").length
    ).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Refresh live status" })).not.toBeInTheDocument();
  });

  it("surfaces a failed execution state when the live transport breaks", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve({
        ...workspacePayload,
        proposal_state: {
          ...workspacePayload.proposal_state,
          submission_status: "failed",
          evaluation_status: "failed",
          follow_up: null,
          summary: {
            ...workspacePayload.proposal_state.summary,
            submission_status: "failed",
            submission_summary: "TPP gateway returned a 502 response for the proposal submission.",
            submission_requires_polling: false,
            evaluation_transport_status: "failed",
            evaluation_result_status: undefined,
            approval_ready: false,
            follow_up_status: undefined,
            follow_up_title: undefined,
            follow_up_summary: undefined,
          },
        },
      }),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Live policy execution needs attention" })).toBeInTheDocument();
    });
    expect(screen.getByText("Needs policy retry")).toBeInTheDocument();
    expect(screen.getByText("TPP gateway returned a 502 response for the proposal submission.")).toBeInTheDocument();
    expect(screen.getByText("Review the live transport failure")).toBeInTheDocument();
  });

  it("surfaces reoptimization follow-up guidance for non-compliant policy results", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve({
        ...workspacePayload,
        proposal_state: {
          ...workspacePayload.proposal_state,
          follow_up: {
            status: "reoptimization_required",
            path: "reoptimization",
            title: "Reoptimization path required",
            summary: "Use a compliant downtown property before resubmitting the approval packet.",
            recommended_action: "reoptimize",
            recommended_label: "Reoptimize plan",
            alternatives: [
              {
                category: "lodging",
                summary: "Use a compliant downtown property",
                rationale: "Alternative meets nightly cap and booking-channel requirements.",
                comparable_ref: "lodging-alt-2",
              },
            ],
            guidance: ["Keep the policy-safe lodging alternative attached to the next submission."],
            notes: [],
            selected_alternative: {
              category: "lodging",
              summary: "Use a compliant downtown property",
              rationale: "Alternative meets nightly cap and booking-channel requirements.",
              comparable_ref: "lodging-alt-2",
            },
            requested_exception: null,
          },
          evaluation: {
            evaluation_result: {
              ...workspacePayload.proposal_state.evaluation.evaluation_result,
              status: "non_compliant",
              failure_reasons: [
                {
                  code: "lodging_cap_exceeded",
                  message: "Nightly lodging exceeds the allowed cap.",
                  severity: "blocking",
                  related_category: "lodging",
                },
              ],
              notes: ["Proposal requires lodging changes before submission can pass."],
              compliance_score: 0.42,
            },
          },
          summary: {
            ...workspacePayload.proposal_state.summary,
            approval_ready: false,
            evaluation_result_status: "non_compliant",
            follow_up_status: "reoptimization_required",
            follow_up_title: "Reoptimization path required",
            follow_up_summary:
              "Use a compliant downtown property before resubmitting the approval packet.",
          },
        },
      }),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Policy review finished with follow-up" })).toBeInTheDocument();
    });
    expect(screen.getByText("Needs exception")).toBeInTheDocument();
    expect(screen.getAllByText("Reoptimize plan").length).toBeGreaterThan(0);
    expect(screen.getByText("Use a compliant downtown property")).toBeInTheDocument();
    expect(screen.getByText("Nightly lodging exceeds the allowed cap.")).toBeInTheDocument();
  });

  it("surfaces exception guidance and approval requirements from live policy results", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve({
        ...workspacePayload,
        proposal_state: {
          ...workspacePayload.proposal_state,
          follow_up: {
            status: "exception_required",
            path: "exception",
            title: "Exception review required",
            summary: "Document the schedule exception and route the packet for manager approval.",
            recommended_action: "request_exception",
            recommended_label: "Prepare exception packet",
            alternatives: [],
            guidance: [
              "Attach the compliant comparable to the exception packet.",
              "Explain why the earlier arrival is required for the client meeting.",
            ],
            notes: [],
            selected_alternative: null,
            requested_exception: {
              exception_type: "schedule_protection",
              reason: "The client workshop starts before the first compliant arrival window.",
              requested_approval_roles: ["manager"],
              notes: ["Reference the supported comparable in the packet."],
            },
          },
          evaluation: {
            evaluation_result: {
              ...workspacePayload.proposal_state.evaluation.evaluation_result,
              status: "exception_required",
              approval_requirements: [
                {
                  role: "manager",
                  reason: "Schedule exception requires manager approval.",
                  mandatory: true,
                },
              ],
              failure_reasons: [
                {
                  code: "arrival_window_conflict",
                  message: "The compliant itinerary misses the client workshop start time.",
                  severity: "blocking",
                  related_category: "flight",
                },
              ],
              notes: ["Exception review is required before approval can continue."],
              compliance_score: 0.61,
            },
          },
          summary: {
            ...workspacePayload.proposal_state.summary,
            approval_ready: false,
            evaluation_result_status: "exception_required",
            follow_up_status: "exception_required",
            follow_up_title: "Exception review required",
            follow_up_summary:
              "Document the schedule exception and route the packet for manager approval.",
          },
        },
      }),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Policy review finished with follow-up" })).toBeInTheDocument();
    });
    expect(screen.getByText("Needs exception")).toBeInTheDocument();
    expect(screen.getAllByText("Prepare exception packet").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Attach the compliant comparable to the exception packet.")).toHaveLength(2);
    expect(
      screen.getByText("Explain why the earlier arrival is required for the client meeting."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Exception rationale: The client workshop starts before the first compliant arrival window."),
    ).toBeInTheDocument();
    expect(screen.getByText("Schedule exception requires manager approval.")).toBeInTheDocument();
  });

  it("skips the follow-up card when legacy records expose an empty follow-up object", async () => {
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve({
        ...workspacePayload,
        proposal_state: {
          ...workspacePayload.proposal_state,
          follow_up: {} as typeof workspacePayload.proposal_state.follow_up,
        },
      }),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Approval packet is ready" })).toBeInTheDocument();
    });

    expect(screen.queryByRole("heading", { name: "Approval-ready proposal" })).not.toBeInTheDocument();
    expect(screen.getByText("resolved")).toBeInTheDocument();
    expect(screen.queryByText("undefined")).not.toBeInTheDocument();
    expect(screen.queryByText(/Selected alternative:/)).not.toBeInTheDocument();
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
    fireEvent.change(screen.getByLabelText("Budget title"), {
      target: { value: "Kyoto spring guardrails" },
    });
    fireEvent.change(screen.getByLabelText("Lodging cap"), {
      target: { value: "600" },
    });
    fireEvent.change(screen.getByLabelText("Food cap"), {
      target: { value: "180" },
    });
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

  it("restores persisted planner feedback after a workspace reload", async () => {
    const updatedWorkspace = {
      ...workspacePayload,
      activity_log: [
        {
          activity_event_id: "activity:trip-leisure-kyoto-draft:1",
          occurred_at: "2026-04-10T05:40:00Z",
          event_kind: "decision_recorded",
          summary:
            "Traveler saved option 'scenario:trip-leisure-kyoto-draft:1' as a fallback in the workspace planner panel.",
        },
      ],
      planner_panel_state: {
        ...workspacePayload.planner_panel_state,
        option_set: {
          ...workspacePayload.planner_panel_state.option_set,
          options: [
            {
              ...workspacePayload.planner_panel_state.option_set.options[0],
              label: "Kyoto base with Uji day trip (fallback)",
              explanation: ["This option was kept as an explicit fallback for later comparison."],
            },
          ],
        },
      },
    } satisfies WorkspaceData;
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve(workspacePayload),
    });
    mockedSubmitPlannerOptionFeedback.mockResolvedValue(updatedWorkspace);

    const view = renderWorkspacePage();

    await waitFor(() => {
      expect(getPlannerHost().shadowRoot?.querySelector('[aria-label="Planner side panel"]')).toBeTruthy();
    });

    const host = view.container.querySelector(".planner-panel-host");
    const plannerMountNode = host?.shadowRoot?.lastElementChild;
    expect(plannerMountNode).not.toBeNull();
    await waitFor(() => {
      fireEvent(
        plannerMountNode as Element,
        new CustomEvent("planner-response-save-as-fallback", {
          detail: {
            option_id: "scenario:trip-leisure-kyoto-draft:1",
            action_type: "save_as_fallback",
            decision_id: null,
          },
        })
      );
      expect(mockedSubmitPlannerOptionFeedback).toHaveBeenCalledWith(
        "trip-leisure-kyoto-draft",
        "scenario:trip-leisure-kyoto-draft:1",
        "save_as_fallback",
        null
      );
    });
    await waitFor(() => {
      expect(getPlannerHost().shadowRoot?.textContent).toContain(
        "Kyoto base with Uji day trip (fallback)"
      );
    });

    view.unmount();
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve(updatedWorkspace),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(getPlannerHost().shadowRoot?.textContent).toContain(
        "Kyoto base with Uji day trip (fallback)"
      );
    });
  });

  it("renders the planning notebook panel when planning_notebook is present in the workspace", async () => {
    const notebookWorkspace: WorkspaceData = {
      ...workspacePayload,
      planning_notebook: {
        items: [
          {
            notebook_item_id: "nb-item:1",
            trip_id: "trip-leisure-kyoto-draft",
            session_state_id: "session-state:kyoto-spring",
            title: "Check shinkansen pass options",
            note: "Compare 7-day vs 14-day pass costs",
            category: "route",
            status: "active",
            priority: "high",
            source: "user",
            linked_ledger_entry_id: null,
            source_message_ids: [],
            tags: [],
            metadata: {},
            completed_at: null,
            created_at: "2026-04-12T06:00:00Z",
            updated_at: "2026-04-12T06:00:00Z",
          },
          {
            notebook_item_id: "nb-item:2",
            trip_id: "trip-leisure-kyoto-draft",
            session_state_id: "session-state:kyoto-spring",
            title: "Confirm Nishiki Market visit",
            note: "",
            category: "activities",
            status: "completed",
            priority: "normal",
            source: "user",
            linked_ledger_entry_id: null,
            source_message_ids: [],
            tags: [],
            metadata: {},
            completed_at: "2026-04-12T07:00:00Z",
            created_at: "2026-04-12T06:00:00Z",
            updated_at: "2026-04-12T07:00:00Z",
          },
        ],
        summary: {
          total_count: 2,
          active_count: 1,
          completed_count: 1,
          active_items: [
            {
              notebook_item_id: "nb-item:1",
              trip_id: "trip-leisure-kyoto-draft",
              session_state_id: "session-state:kyoto-spring",
              title: "Check shinkansen pass options",
              note: "Compare 7-day vs 14-day pass costs",
              category: "route",
              status: "active",
              priority: "high",
              source: "user",
              linked_ledger_entry_id: null,
              source_message_ids: [],
              tags: [],
              metadata: {},
              completed_at: null,
              created_at: "2026-04-12T06:00:00Z",
              updated_at: "2026-04-12T06:00:00Z",
            },
          ],
          completed_items: [
            {
              notebook_item_id: "nb-item:2",
              trip_id: "trip-leisure-kyoto-draft",
              session_state_id: "session-state:kyoto-spring",
              title: "Confirm Nishiki Market visit",
              note: "",
              category: "activities",
              status: "completed",
              priority: "normal",
              source: "user",
              linked_ledger_entry_id: null,
              source_message_ids: [],
              tags: [],
              metadata: {},
              completed_at: "2026-04-12T07:00:00Z",
              created_at: "2026-04-12T06:00:00Z",
              updated_at: "2026-04-12T07:00:00Z",
            },
          ],
          by_category: {
            route: [],
            activities: [],
          },
        },
        focus: { category: null, notebook_item_id: null },
      },
    };
    mockedUseLoaderData.mockReturnValue({ workspace: Promise.resolve(notebookWorkspace) });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Planning notebook" })).toBeInTheDocument();
    });

    expect(screen.getByText("Check shinkansen pass options")).toBeInTheDocument();
    expect(screen.getByText("Compare 7-day vs 14-day pass costs")).toBeInTheDocument();
    expect(screen.getByLabelText("Notebook item title")).toBeInTheDocument();

    const completedToggle = screen.getByText(/Completed \(1\)/);
    expect(completedToggle).toBeInTheDocument();
  });

  it("captures a new notebook item and surfaces it in the active list", async () => {
    const emptyNotebookWorkspace: WorkspaceData = {
      ...workspacePayload,
      planning_notebook: {
        items: [],
        summary: {
          total_count: 0,
          active_count: 0,
          completed_count: 0,
          active_items: [],
          completed_items: [],
          by_category: {},
        },
        focus: { category: null, notebook_item_id: null },
      },
    };
    const newItem = {
      notebook_item_id: "nb-item:new",
      trip_id: "trip-leisure-kyoto-draft",
      session_state_id: "session-state:kyoto-spring",
      title: "Book luggage storage at Kyoto Station",
      note: "",
      category: "route" as const,
      status: "active" as const,
      priority: "normal" as const,
      source: "user" as const,
      linked_ledger_entry_id: null,
      source_message_ids: [],
      tags: [],
      metadata: {},
      completed_at: null,
      created_at: "2026-04-12T08:00:00Z",
      updated_at: "2026-04-12T08:00:00Z",
    };

    mockedUseLoaderData.mockReturnValue({ workspace: Promise.resolve(emptyNotebookWorkspace) });
    mockedCreateNotebookItem.mockResolvedValue(newItem);

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Planning notebook" })).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Notebook item title"), "Book luggage storage at Kyoto Station");
    await user.click(screen.getByRole("button", { name: "Add to notebook" }));

    await waitFor(() => {
      expect(mockedCreateNotebookItem).toHaveBeenCalledWith(
        "trip-leisure-kyoto-draft",
        expect.objectContaining({ title: "Book luggage storage at Kyoto Station", category: "other" })
      );
    });

    await waitFor(() => {
      expect(screen.getByText("Book luggage storage at Kyoto Station")).toBeInTheDocument();
    });
  });

  it("completes an active notebook item and moves it to the completed section", async () => {
    const activeItem = {
      notebook_item_id: "nb-item:active",
      trip_id: "trip-leisure-kyoto-draft",
      session_state_id: "session-state:kyoto-spring",
      title: "Research tea ceremony venues",
      note: "",
      category: "activities" as const,
      status: "active" as const,
      priority: "normal" as const,
      source: "user" as const,
      linked_ledger_entry_id: null,
      source_message_ids: [],
      tags: [],
      metadata: {},
      completed_at: null,
      created_at: "2026-04-12T06:00:00Z",
      updated_at: "2026-04-12T06:00:00Z",
    };
    const completedItem = { ...activeItem, status: "completed" as const, completed_at: "2026-04-12T09:00:00Z" };

    const notebookWorkspace: WorkspaceData = {
      ...workspacePayload,
      planning_notebook: {
        items: [activeItem],
        summary: {
          total_count: 1,
          active_count: 1,
          completed_count: 0,
          active_items: [activeItem],
          completed_items: [],
          by_category: { activities: [activeItem] },
        },
        focus: { category: null, notebook_item_id: null },
      },
    };

    mockedUseLoaderData.mockReturnValue({ workspace: Promise.resolve(notebookWorkspace) });
    mockedUpdateNotebookItem.mockResolvedValue(completedItem);

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByText("Research tea ceremony venues")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(
      within(screen.getByLabelText("Research tea ceremony venues")).getByRole("button", { name: "Complete" })
    );

    await waitFor(() => {
      expect(mockedUpdateNotebookItem).toHaveBeenCalledWith(
        "trip-leisure-kyoto-draft",
        "nb-item:active",
        { status: "completed" }
      );
    });

    await waitFor(() => {
      expect(screen.getByText(/Completed \(1\)/)).toBeInTheDocument();
    });
  });

  it("deletes a notebook item and removes it from the active list", async () => {
    const itemToDelete = {
      notebook_item_id: "nb-item:delete-me",
      trip_id: "trip-leisure-kyoto-draft",
      session_state_id: "session-state:kyoto-spring",
      title: "Draft lodging short-list",
      note: "",
      category: "lodging" as const,
      status: "active" as const,
      priority: "normal" as const,
      source: "user" as const,
      linked_ledger_entry_id: null,
      source_message_ids: [],
      tags: [],
      metadata: {},
      completed_at: null,
      created_at: "2026-04-12T06:00:00Z",
      updated_at: "2026-04-12T06:00:00Z",
    };

    const notebookWorkspace: WorkspaceData = {
      ...workspacePayload,
      planning_notebook: {
        items: [itemToDelete],
        summary: {
          total_count: 1,
          active_count: 1,
          completed_count: 0,
          active_items: [itemToDelete],
          completed_items: [],
          by_category: { lodging: [itemToDelete] },
        },
        focus: { category: null, notebook_item_id: null },
      },
    };

    mockedUseLoaderData.mockReturnValue({ workspace: Promise.resolve(notebookWorkspace) });
    mockedDeleteNotebookItem.mockResolvedValue(undefined);

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByText("Draft lodging short-list")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(
      within(screen.getByLabelText("Draft lodging short-list")).getByRole("button", { name: "Delete" })
    );

    await waitFor(() => {
      expect(mockedDeleteNotebookItem).toHaveBeenCalledWith(
        "trip-leisure-kyoto-draft",
        "nb-item:delete-me"
      );
    });

    await waitFor(() => {
      expect(screen.queryByText("Draft lodging short-list")).not.toBeInTheDocument();
    });
  });

  it("sets the active focus on a notebook item when the user clicks Focus", async () => {
    const item = {
      notebook_item_id: "nb-item:focus-target",
      trip_id: "trip-leisure-kyoto-draft",
      session_state_id: "session-state:kyoto-spring",
      title: "Map out Arashiyama day hike",
      note: "",
      category: "activities" as const,
      status: "active" as const,
      priority: "normal" as const,
      source: "user" as const,
      linked_ledger_entry_id: null,
      source_message_ids: [],
      tags: [],
      metadata: {},
      completed_at: null,
      created_at: "2026-04-12T06:00:00Z",
      updated_at: "2026-04-12T06:00:00Z",
    };

    const notebookWorkspace: WorkspaceData = {
      ...workspacePayload,
      planning_notebook: {
        items: [item],
        summary: {
          total_count: 1,
          active_count: 1,
          completed_count: 0,
          active_items: [item],
          completed_items: [],
          by_category: { activities: [item] },
        },
        focus: { category: null, notebook_item_id: null },
      },
    };

    mockedUseLoaderData.mockReturnValue({ workspace: Promise.resolve(notebookWorkspace) });
    mockedSetNotebookFocus.mockResolvedValue({ category: null, notebook_item_id: "nb-item:focus-target" });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByText("Map out Arashiyama day hike")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(
      within(screen.getByLabelText("Map out Arashiyama day hike")).getByRole("button", { name: "Focus" })
    );

    await waitFor(() => {
      expect(mockedSetNotebookFocus).toHaveBeenCalledWith(
        "trip-leisure-kyoto-draft",
        expect.objectContaining({ notebook_item_id: "nb-item:focus-target" })
      );
    });

    await waitFor(() => {
      expect(screen.getByText("Active focus:")).toBeInTheDocument();
    });
  });

  it("hides the planning notebook panel when planning_notebook is absent", async () => {
    mockedUseLoaderData.mockReturnValue({ workspace: Promise.resolve(workspacePayload) });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Planning ledger" })).toBeInTheDocument();
    });

    expect(screen.queryByRole("heading", { name: "Planning notebook" })).not.toBeInTheDocument();
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
      expect(screen.getByRole("heading", { name: "Trip workspace could not load" })).toBeInTheDocument();
    });

    expect(screen.getByText("Backend warming up")).toBeInTheDocument();
  });
});
