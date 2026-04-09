import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
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
          estimated_total: 3400,
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
          estimated_total: 3250,
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
        bundle_context: "route_level",
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
    expect(screen.getByRole("heading", { name: "Map preview for Kyoto base with Uji day trip" })).toBeInTheDocument();
    expect(within(screen.getByLabelText("Route context map")).getAllByText("Kyoto")).toHaveLength(2);
    expect(screen.getByText("Uji")).toBeInTheDocument();
    expect(screen.getByText("Save baseline scenario")).toBeInTheDocument();
    expect(screen.getByText("Trip-scoped planner surface")).toBeInTheDocument();
    expect(screen.getByLabelText("Route context map")).toBeInTheDocument();
    expect(screen.getByText("Destination anchors")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Assembled inventory layer" })).toBeInTheDocument();
    expect(screen.getByText("Osaka arrival buffer")).toBeInTheDocument();
    expect(screen.getByText("Kyoto cultural anchor")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Approval packet is ready" })).toBeInTheDocument();
    expect(screen.getByText("Approval-ready proposal")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Comparables and readiness signals" })).toBeInTheDocument();
    expect(screen.getByText("Conference Hotel")).toBeInTheDocument();
    await waitFor(() => {
      const plannerPanel = getPlannerHost().shadowRoot?.querySelector(
        '[aria-label="Planner side panel"]'
      );
      expect(plannerPanel).toBeTruthy();
    });
  });

  it("updates the map surface when a different scenario preview is selected", async () => {
    const user = userEvent.setup();
    mockedUseLoaderData.mockReturnValue({
      workspace: Promise.resolve(workspacePayload),
    });

    renderWorkspacePage();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "2. Kyoto plus Osaka fallback" })).toBeInTheDocument();
    });

    expect(
      screen.getByRole("heading", { name: "Map preview for Kyoto base with Uji day trip" })
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "2. Kyoto plus Osaka fallback" }));

    expect(
      screen.getByRole("heading", { name: "Map preview for Kyoto plus Osaka fallback" })
    ).toBeInTheDocument();
    expect(screen.getByText("Osaka")).toBeInTheDocument();
    expect(screen.getByText("Higher transfer load to preserve nightlife breadth.")).toBeInTheDocument();
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
      expect(screen.getByText("Reoptimization path required")).toBeInTheDocument();
    });
    expect(screen.getByText("Reoptimize plan")).toBeInTheDocument();
    expect(screen.getByText("Use a compliant downtown property")).toBeInTheDocument();
    expect(screen.getByText("Nightly lodging exceeds the allowed cap.")).toBeInTheDocument();
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
