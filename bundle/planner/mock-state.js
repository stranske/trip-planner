/**
 * Planner UI mock state aligned to canonical repo contracts.
 *
 * Source contract references:
 * - trip_planner/contracts/trip.py
 * - trip_planner/contracts/options.py
 * - trip_planner/business/policy_contracts.py
 */

/**
 * @typedef {Object} TripFrameSummary
 * @property {string | null} start_date
 * @property {string | null} end_date
 * @property {number | null} duration_days
 * @property {string[]} primary_regions
 * @property {{ kind: string, traveler_count: number, notes: string }} traveler_party
 */

/**
 * @typedef {Object} TripRecord
 * @property {string} trip_id
 * @property {string} user_id
 * @property {"leisure" | "business"} mode
 * @property {"draft" | "active" | "booked" | "in_trip" | "completed" | "archived"} status
 * @property {TripFrameSummary} trip_frame
 * @property {{ leisure_profile_id?: string | null, business_profile_id?: string | null }} profile_refs
 * @property {string} title
 * @property {string} summary
 */

/**
 * @typedef {Object} OptionRecord
 * @property {string} option_id
 * @property {string} kind
 * @property {string} label
 * @property {string} summary
 * @property {string[]} drawbacks
 * @property {string[]} explanation
 */

/**
 * @typedef {Object} OptionSetRecord
 * @property {string} option_set_id
 * @property {string} trip_id
 * @property {string} purpose
 * @property {string} scope
 * @property {string} title
 * @property {OptionRecord[]} options
 * @property {{ key: string, label: string, direction: string }[]} comparison_axes
 * @property {string[]} explanation
 */

/**
 * @typedef {Object} PolicyEvaluationRecord
 * @property {string} evaluation_id
 * @property {string} proposal_id
 * @property {"compliant" | "non_compliant" | "exception_required"} status
 * @property {{ role: string, reason: string, mandatory: boolean }[]} approval_requirements
 * @property {{ code: string, message: string, severity: string, related_category: string }[]} failure_reasons
 * @property {{ category: string, summary: string, rationale: string, comparable_ref?: string | null }[]} preferred_alternatives
 * @property {string[]} exception_guidance
 * @property {string[]} notes
 * @property {number} compliance_score
 */

/**
 * @typedef {Object} PendingDecisionRecord
 * @property {string} decision_id
 * @property {string} title
 * @property {string} prompt
 * @property {string[]} choices
 */

/**
 * @typedef {Object} PlannerOutputRecord
 * @property {string} output_id
 * @property {string} title
 * @property {string} body
 * @property {string[]} tags
 */

/**
 * @typedef {Object} PlannerBehaviorRecord
 * @property {string} trip_stage
 * @property {boolean} ask_before_next_major_change
 * @property {number} target_research_passes
 * @property {number} target_options_before_checkpoint
 * @property {boolean} surface_options_early
 * @property {"lean" | "standard" | "detailed"} explanation_density
 */

/**
 * @typedef {Object} NextStepActionRecord
 * @property {string} action_id
 * @property {"review_outputs" | "answer_decision" | "compare_options" | "prepare_approval"} action_kind
 * @property {string} label
 * @property {string} description
 * @property {"primary" | "secondary" | "quiet"} emphasis
 * @property {"outputs" | "decisions" | "options" | "approval"} target_section
 */

/**
 * @typedef {Object} PlannerPanelState
 * @property {TripRecord} trip
 * @property {OptionSetRecord} option_set
 * @property {PolicyEvaluationRecord | null} policy_evaluation
 * @property {PendingDecisionRecord[]} pending_decisions
 * @property {PlannerOutputRecord[]} outputs
 * @property {PlannerBehaviorRecord} planner_behavior
 * @property {NextStepActionRecord[]} next_step_actions
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
