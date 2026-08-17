import { describe, expect, it } from "vitest";

import type { WorkspaceData } from "../api/workspace";
import { buildProposalSubmissionPayload } from "./proposalSubmission";

function businessWorkspaceWithAmount(
  typicalAmount: number
): WorkspaceData {
  return {
    trip_record: {
      trip: {
        trip_id: "trip-business-tokyo-summit",
        title: "Tokyo client summit",
        summary: "Business trip",
        status: "active",
        mode: "business",
        trip_frame: {
          start_date: "2026-05-02",
          end_date: "2026-05-06",
          duration_days: 5,
          primary_regions: ["Tokyo"],
        },
      },
      artifact_refs: {
        saved_scenario_ids: [],
        scenario_search_id: null,
        session_state_id: null,
        budget_state_id: null,
      },
    },
    session: {
      current_saved_scenario_id: null,
      active_budget_plan_id: null,
      selected_planning_mode: "collaborative",
      pending_decisions: [],
      interaction_state: {
        interaction_style: "collaborative",
        initiative_level: "balanced",
        checkpoint_frequency: "milestone",
      },
      recent_option_presentations: [],
    },
    saved_scenarios: [],
    activity_log: [],
    planner_memory: { current_checkpoint_id: null, checkpoints: [], artifacts: [] },
    budget_state: {
      summary: {
        currency: "USD",
        planned_total: typicalAmount,
      },
    },
    runtime_scenario_comparison: {
      title: "Scenario comparison",
      summary: "One scenario",
      lead_scenario_id: "scenario:tokyo:1",
      comparison_axes: [],
      scenarios: [
        {
          scenario_id: "scenario:tokyo:1",
          title: "Tokyo route",
          rank: 1,
          status: "lead",
          summary: "Primary route",
          comparison_note: "Lead",
          option_count: 1,
          route_sequence: ["tokyo"],
          route_summary: "tokyo",
          recommended_for_selection: true,
          feasible: true,
          metrics: {
            score: 0.9,
            travel_minutes: 120,
            transfers: 1,
            estimated_total: {
              currency: "USD",
              typical_amount: typicalAmount,
            },
          },
          delta: {
            score_delta: 0,
            travel_minutes_delta: 0,
            transfers_delta: 0,
            estimated_total_delta: 0,
          },
          highlights: ["Direct route"],
        },
      ],
      source_refs: [],
    },
    view_model: {
      debug_state: {
        sections: {
          policy_state: {
            title: "Policy state",
            payload: {
              organization_id: "org:test",
              constraint_set: {
                policy_id: "policy:tokyo",
              },
            },
          },
        },
      },
    },
  } as unknown as WorkspaceData;
}

describe("buildProposalSubmissionPayload", () => {
  it("rejects NaN proposal costs", () => {
    expect(() => buildProposalSubmissionPayload(businessWorkspaceWithAmount(Number.NaN))).toThrow(
      "Proposal cost must be a finite number."
    );
  });

  it("rejects infinite proposal costs", () => {
    expect(() =>
      buildProposalSubmissionPayload(businessWorkspaceWithAmount(Number.POSITIVE_INFINITY))
    ).toThrow("Proposal cost must be a finite number.");
  });
});
