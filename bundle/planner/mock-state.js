/**
 * Planner UI mock state aligned to canonical repo contracts.
 *
 * @import {
 *   PlannerPanelState,
 *   PlannerUiScenarioRecord,
 * } from "./orchestration-contracts"
 */

/** @type {PlannerPanelState} */
export const leisureFeedbackLoopState = {
  trip: {
    trip_id: "trip-leisure-lisbon-oct",
    user_id: "traveler-88",
    mode: "leisure",
    status: "active",
    trip_frame: {
      start_date: "2025-10-03",
      end_date: "2025-10-09",
      duration_days: 7,
      primary_regions: ["Lisbon", "Sintra Coast"],
      traveler_party: {
        kind: "pair",
        traveler_count: 2,
        notes: "Keep one light day after the transatlantic arrival.",
      },
    },
    profile_refs: {
      leisure_profile_id: "profile-leisure-17",
    },
    title: "Lisbon reset with room to wander",
    summary:
      "The planner is balancing walkable neighborhoods, strong food-value picks, and fewer hard commitments.",
  },
  option_set: {
    option_set_id: "option-set-lodging-01",
    trip_id: "trip-leisure-lisbon-oct",
    purpose: "profile_learning",
    scope: "lodging",
    title: "Stay shape for the first half of the trip",
    explanation: [
      "These picks test whether the traveler values central walkability over larger rooms.",
      "Each option keeps a calmer Day 2 recovery window intact.",
    ],
    comparison_axes: [
      { key: "walkability", label: "Walkability", direction: "higher_better" },
      { key: "quiet", label: "Night Quiet", direction: "higher_better" },
      { key: "price", label: "Nightly Cost", direction: "lower_better" },
    ],
    options: [
      {
        option_id: "option-bairro-alto",
        kind: "lodging",
        label: "Design hotel near Principe Real",
        summary: "Fast access to dinners and tram routes, but some street noise risk.",
        drawbacks: ["Rooms are compact.", "Higher weekend pricing."],
        explanation: ["Best if evening spontaneity matters more than recovery quiet."],
      },
      {
        option_id: "option-alcantara",
        kind: "lodging",
        label: "Riverside guesthouse in Alcantara",
        summary: "Calmer nights and larger rooms, with slightly longer transit legs.",
        drawbacks: ["Less immediate old-city access."],
        explanation: ["Best if comfort floor and decompression time are the priority."],
      },
    ],
  },
  proposal: null,
  policy_evaluation: null,
  pending_decisions: [
    {
      decision_id: "lodging-signal",
      title: "Choose the better base camp",
      prompt: "Which tradeoff feels more like the trip you want?",
      choices: [
        "Stay central and accept tighter rooms.",
        "Prioritize recovery quiet and a little extra transit.",
      ],
    },
  ],
  outputs: [
    {
      output_id: "summary-01",
      title: "Planner read",
      body: "Your evidence points to quality where it changes the day, not blanket upgrades everywhere.",
      tags: ["leisure", "feedback-loop"],
    },
    {
      output_id: "summary-02",
      title: "What changed",
      body: "The panel now surfaces one concrete lodging decision instead of asking for more broad preference text.",
      tags: ["interactive", "decision-ready"],
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
      action_id: "answer-lodging-signal",
      action_kind: "answer_decision",
      label: "Answer the lodging decision",
      description: "Tell the planner whether central access or recovery quiet should win this round.",
      emphasis: "primary",
      target_section: "decisions",
    },
    {
      action_id: "compare-lodging-options",
      action_kind: "compare_options",
      label: "Compare the lodging options again",
      description: "Re-open the option set with the current walkability, quiet, and cost tradeoffs.",
      emphasis: "secondary",
      target_section: "options",
    },
    {
      action_id: "review-planner-read",
      action_kind: "review_outputs",
      label: "Review what changed",
      description: "Scan the latest planner outputs before confirming the next checkpoint.",
      emphasis: "quiet",
      target_section: "outputs",
    },
  ],
};

/** @type {PlannerUiScenarioRecord} */
export const leisureFeedbackLoopScenario = {
  scenario_id: "leisure-feedback-loop",
  label: "Leisure feedback loop",
  workflow: "Traveler compares lodging tradeoffs, gives feedback, and answers a single focused decision.",
  persona_summary: "Pair trip that values walkability, food value, and a softer recovery day after arrival.",
  panel_state: leisureFeedbackLoopState,
};

/** @type {PlannerPanelState} */
export const inTripRevisionPromptState = {
  trip: {
    trip_id: "trip-kyoto-intrip-replan",
    user_id: "traveler-12",
    mode: "leisure",
    status: "in_trip",
    trip_frame: {
      start_date: "2025-04-14",
      end_date: "2025-04-20",
      duration_days: 7,
      primary_regions: ["Kyoto", "Uji"],
      traveler_party: {
        kind: "solo",
        traveler_count: 1,
        notes: "Rain shifted two outdoor blocks into the middle of the trip.",
      },
    },
    profile_refs: {
      leisure_profile_id: "profile-leisure-33",
    },
    title: "Kyoto mid-trip reset after weather shift",
    summary:
      "The planner is revising the next two days around heavy rain while preserving one tea-focused neighborhood stop.",
  },
  option_set: {
    option_set_id: "option-set-rain-replan-01",
    trip_id: "trip-kyoto-intrip-replan",
    purpose: "in_trip_revision",
    scope: "daily_plan",
    title: "Reshape tomorrow around the rain window",
    explanation: [
      "Both options protect the booked tea workshop while reducing time spent crossing the city in peak rain.",
      "The revision prompt is narrowed to pace and neighborhood clustering rather than reopening the full itinerary.",
    ],
    comparison_axes: [
      { key: "weather_resilience", label: "Rain Resilience", direction: "higher_better" },
      { key: "walking_load", label: "Walking Load", direction: "lower_better" },
      { key: "reservation_risk", label: "Reservation Risk", direction: "lower_better" },
    ],
    options: [
      {
        option_id: "option-gion-indoor-cluster",
        kind: "daily_plan",
        label: "Cluster indoor stops around Gion",
        summary: "Keep the tea workshop, add a covered market lunch, and hold the evening flexible.",
        drawbacks: ["Shrinks time for temple gardens until the weather clears."],
        explanation: ["Best if minimizing wet transit matters more than covering more neighborhoods tomorrow."],
      },
      {
        option_id: "option-uji-half-day-shift",
        kind: "daily_plan",
        label: "Move Uji to a shorter half-day outing",
        summary: "Use the drier early window for Uji, then return for museum time near the hotel.",
        drawbacks: ["Creates a tighter connection back into central Kyoto."],
        explanation: ["Best if keeping one scenic rail segment still feels worth the extra coordination."],
      },
    ],
  },
  proposal: null,
  policy_evaluation: null,
  pending_decisions: [
    {
      decision_id: "rain-replan-signal",
      title: "Choose the revision style",
      prompt: "When a day goes sideways mid-trip, what should the planner protect first?",
      choices: [
        "Protect the booked anchor and make the rest easier.",
        "Keep the broader geography even if transfers stay tighter.",
      ],
    },
  ],
  outputs: [
    {
      output_id: "revision-summary-01",
      title: "Why the planner is asking now",
      body: "Tomorrow's rain band conflicts with your original east-side walking block, so the panel is asking for a revision preference before it rebooks the day.",
      tags: ["in-trip", "revision-prompt"],
    },
    {
      output_id: "revision-summary-02",
      title: "What stays fixed",
      body: "The booked tea workshop remains the anchor; the revision only changes the surrounding neighborhood flow.",
      tags: ["anchored-booking", "weather"],
    },
  ],
  planner_behavior: {
    trip_stage: "revise",
    ask_before_next_major_change: true,
    target_research_passes: 1,
    target_options_before_checkpoint: 2,
    surface_options_early: true,
    explanation_density: "lean",
  },
  next_step_actions: [
    {
      action_id: "answer-rain-revision",
      action_kind: "answer_decision",
      label: "Answer the revision prompt",
      description: "Tell the planner whether tomorrow should optimize for easier flow or broader coverage.",
      emphasis: "primary",
      target_section: "decisions",
    },
    {
      action_id: "compare-revision-options",
      action_kind: "compare_options",
      label: "Compare the revised day plans",
      description: "Review the two weather-adjusted options before the planner changes the itinerary.",
      emphasis: "secondary",
      target_section: "options",
    },
    {
      action_id: "review-revision-rationale",
      action_kind: "review_outputs",
      label: "Review the revision rationale",
      description: "Read why the planner narrowed the replan to tomorrow's weather conflict.",
      emphasis: "quiet",
      target_section: "outputs",
    },
  ],
};

/** @type {PlannerUiScenarioRecord} */
export const inTripRevisionPromptScenario = {
  scenario_id: "in-trip-revision-prompt",
  label: "In-trip revision prompt",
  workflow:
    "Traveler is already in-trip, weather disrupts the next day, and the planner asks for a focused revision preference before changing the itinerary.",
  persona_summary:
    "Solo Kyoto trip with one fixed tea booking where the traveler wants the planner to recover gracefully from weather disruption.",
  panel_state: inTripRevisionPromptState,
};

/** @type {PlannerPanelState} */
export const businessApprovalReadyReviewState = {
  trip: {
    trip_id: "trip-dallas-client-review",
    user_id: "traveler-42",
    mode: "business",
    status: "booked",
    trip_frame: {
      start_date: "2025-09-18",
      end_date: "2025-09-20",
      duration_days: 3,
      primary_regions: ["Dallas", "Irving"],
      traveler_party: {
        kind: "solo",
        traveler_count: 1,
        notes: "Traveler needs a pre-dawn arrival at the client site for an audit kickoff.",
      },
    },
    profile_refs: {
      business_profile_id: "profile-business-11",
    },
    title: "Dallas client review with policy packet",
    summary:
      "The planner is packaging a business trip for approval with comparables, policy posture, and exception notes attached.",
  },
  option_set: {
    option_set_id: "option-set-approval-review-01",
    trip_id: "trip-dallas-client-review",
    purpose: "approval_review",
    scope: "proposal_packet",
    title: "Approval-ready business travel packet",
    explanation: [
      "The selected proposal is above the lodging cap, so the planner is surfacing approval posture instead of asking for more travel discovery.",
      "Comparables remain attached so the reviewer can see the lower-cost fallback if the exception is denied.",
    ],
    comparison_axes: [
      { key: "policy_fit", label: "Policy Fit", direction: "higher_better" },
      { key: "site_access", label: "Site Access", direction: "higher_better" },
      { key: "fatigue_risk", label: "Fatigue Risk", direction: "lower_better" },
    ],
    options: [
      {
        option_id: "option-near-client-hotel",
        kind: "lodging",
        label: "Hotel beside the client campus",
        summary: "Exceeds the nightly cap but protects a 05:45 audit kickoff and reduces transfer fatigue.",
        drawbacks: ["Needs manager and finance exception approval."],
        explanation: ["Best if operational reliability matters more than strict lodging-cap compliance."],
      },
      {
        option_id: "option-airport-fallback",
        kind: "lodging",
        label: "Within-cap airport hotel fallback",
        summary: "Stays within policy but adds a pre-dawn transfer before the client review starts.",
        drawbacks: ["Adds commute risk and shortens recovery time before the audit."],
        explanation: ["Best if the approval reviewer is unlikely to grant a lodging exception."],
      },
    ],
  },
  proposal: {
    proposal_id: "proposal-approval-01",
    comparables: [
      {
        category: "lodging",
        label: "Within-cap airport hotel",
        vendor: "Courtyard",
        booking_channel: "Concur",
        estimated_cost: {
          currency: "USD",
          typical_amount: 214,
        },
        notes: [
          "Requires a pre-dawn transfer to the client site.",
          "Stays within the standard nightly lodging cap.",
        ],
      },
      {
        category: "airfare",
        label: "One-stop daytime routing",
        vendor: "American",
        booking_channel: "Concur",
        estimated_cost: {
          currency: "USD",
          typical_amount: 386,
        },
        notes: ["Extends total travel time by nearly three hours."],
      },
    ],
    justifications: [
      {
        category: "lodging",
        summary: "Higher nightly rate keeps the team near the client site for a pre-dawn audit start.",
        evidence: [
          "Audit kickoff begins at 05:45 local time.",
          "The lower-cost hotel adds a 40-minute transfer each way.",
        ],
      },
      {
        category: "schedule",
        summary: "The selected hotel reduces fatigue risk across consecutive site inspections.",
        evidence: ["Traveler arrives after a late connection on the prior evening."],
      },
    ],
    approval_notes: [
      "Attach the lower-cost comparable to the approval packet.",
      "Reference the fatigue-management rationale in the manager request.",
    ],
    requested_exception: {
      exception_type: "lodging_rate_cap",
      reason: "Request an exception to preserve site access and reduce fatigue risk.",
      requested_approval_roles: ["manager", "finance"],
      notes: ["Document why the within-cap hotel materially degrades the operating schedule."],
    },
  },
  policy_evaluation: {
    evaluation_id: "eval-approval-01",
    proposal_id: "proposal-approval-01",
    status: "exception_required",
    approval_requirements: [
      {
        role: "manager",
        reason: "Operational exception requires manager approval",
        mandatory: true,
      },
      {
        role: "finance",
        reason: "Lodging cap exception requires finance review",
        mandatory: true,
      },
    ],
    failure_reasons: [
      {
        code: "lodging_rate_cap",
        message: "Selected lodging exceeds the nightly cap but includes an operational-safety justification.",
        severity: "warning",
        related_category: "lodging",
      },
    ],
    preferred_alternatives: [
      {
        category: "lodging",
        summary: "Use the attached lower-cost comparable if the exception is denied.",
        rationale: "Preserves site access with a lower nightly cost ceiling.",
        comparable_ref: "lodging",
      },
    ],
    exception_guidance: [
      "Retain the lower-cost comparable in the approval packet.",
      "Document the operational-safety rationale in the manager approval request.",
    ],
    notes: ["Proposal is exception-eligible if the fatigue-management rationale is approved."],
    compliance_score: 0.68,
  },
  pending_decisions: [
    {
      decision_id: "approval-packet-confirmation",
      title: "Confirm the approval packet stance",
      prompt: "Should the planner package the exception request now or fall back to the within-cap option first?",
      choices: [
        "Prepare the exception packet with comparables attached.",
        "Switch to the within-cap fallback before requesting approval.",
      ],
    },
  ],
  outputs: [
    {
      output_id: "approval-summary-01",
      title: "Approval packet status",
      body: "The planner has attached policy posture, comparables, and justification evidence so the traveler can request approval without reopening trip discovery.",
      tags: ["business", "approval-ready"],
    },
    {
      output_id: "approval-summary-02",
      title: "Why the exception exists",
      body: "The selected lodging exceeds policy, but it materially reduces pre-dawn transfer risk before the client audit starts.",
      tags: ["policy", "exception"],
    },
  ],
  planner_behavior: {
    trip_stage: "approval",
    ask_before_next_major_change: true,
    target_research_passes: 0,
    target_options_before_checkpoint: 1,
    surface_options_early: false,
    explanation_density: "detailed",
  },
  next_step_actions: [
    {
      action_id: "prepare-approval-packet",
      action_kind: "prepare_approval",
      label: "Prepare the approval packet",
      description: "Open the approval review with comparables, justification evidence, and the exception request.",
      emphasis: "primary",
      target_section: "approval",
    },
    {
      action_id: "review-approval-outputs",
      action_kind: "review_outputs",
      label: "Review the approval summary",
      description: "Read the planner's latest explanation before sending the business proposal for approval.",
      emphasis: "secondary",
      target_section: "outputs",
    },
    {
      action_id: "answer-approval-decision",
      action_kind: "answer_decision",
      label: "Answer the packet confirmation",
      description: "Tell the planner whether to request the exception or pivot to the within-cap fallback first.",
      emphasis: "quiet",
      target_section: "decisions",
    },
  ],
};

/** @type {PlannerUiScenarioRecord} */
export const businessApprovalReadyReviewScenario = {
  scenario_id: "business-approval-ready-review",
  label: "Business approval-ready review",
  workflow:
    "Traveler has a business proposal that is ready for approval review, and the planner packages policy posture, comparables, and exception guidance into one interactive panel.",
  persona_summary:
    "Business traveler with a pre-dawn client audit where the planner must justify an exception-ready lodging choice before submission.",
  panel_state: businessApprovalReadyReviewState,
};

export const plannerUiStateMocks = {
  leisure_feedback_loop: leisureFeedbackLoopScenario,
  in_trip_revision_prompt: inTripRevisionPromptScenario,
  business_approval_ready_review: businessApprovalReadyReviewScenario,
};
