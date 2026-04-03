/**
 * Representative application-shell fixtures for issue #556.
 *
 * @import {
 *   FrontendShellState,
 * } from "./contracts"
 */

const signedInSession = {
  user_id: "user-17",
  display_name: "Avery Stone",
  organization: "Northwind Advisory",
  default_trip_mode: "leisure",
};

const firstTimeLeisureSession = {
  user_id: "user-26",
  display_name: "Mina Patel",
  organization: null,
  default_trip_mode: "leisure",
};

const businessEntrySession = {
  user_id: "user-44",
  display_name: "Jordan Lee",
  organization: "Northwind Advisory",
  default_trip_mode: "business",
};

const travelerProfiles = {
  leisure_primary: {
    profile_id: "profile-leisure-17",
    mode: "leisure",
    label: "Leisure profile",
    summary: "Prefers walkable neighborhoods, low-friction transit days, and one soft landing day.",
    readiness: "Ready to seed a new leisure trip from learned pace and comfort preferences.",
  },
  leisure_new_user: {
    profile_id: "profile-leisure-26",
    mode: "leisure",
    label: "Starter leisure profile",
    summary: "No saved trips yet, but the account already captured destination style and pace preferences.",
    readiness: "Needs a first trip brief to turn starter preferences into reusable trip state.",
  },
  business_primary: {
    profile_id: "profile-business-4",
    mode: "business",
    label: "Business travel profile",
    summary: "Carries traveler role, approval path, and hotel policy context for client-facing travel.",
    readiness: "Ready to start a policy-aware trip with approval routing and purpose capture.",
  },
};

const launchFlows = {
  new_leisure_trip: {
    launch_id: "new_leisure_trip",
    mode: "leisure",
    title: "Start a new leisure trip",
    summary: "Translate traveler preferences into destination framing, pace, and budget-aware setup.",
    cta_label: "Start leisure trip",
    starting_needs: [
      "Trip brief with dates, destination ideas, and traveler party context.",
      "Preference cues for pace, walkability, comfort, and budget.",
      "A seed itinerary question that tells the planner what to optimize first.",
    ],
    profile_id: travelerProfiles.leisure_primary.profile_id,
    trip_id: null,
    recent_session_id: null,
    policy_context: null,
  },
  new_business_trip: {
    launch_id: "new_business_trip",
    mode: "business",
    title: "Start a new business trip",
    summary: "Capture travel purpose, employer policy context, and approval posture before workspace planning.",
    cta_label: "Start business trip",
    starting_needs: [
      "Business purpose, traveler role, and client or event context.",
      "Policy-linked lodging, airfare, or approval constraints from the business profile.",
      "A routing decision for whether the planner should prepare approval evidence immediately.",
    ],
    profile_id: travelerProfiles.business_primary.profile_id,
    trip_id: null,
    recent_session_id: null,
    policy_context: "Hotel zone, approval roles, and spend posture should be seeded from the business profile.",
  },
  resume_existing_trip: {
    launch_id: "resume_existing_trip",
    mode: "leisure",
    title: "Resume an existing trip",
    summary: "Re-enter the most recent session and rehydrate trip context without rebuilding the shell.",
    cta_label: "Resume latest session",
    starting_needs: [
      "Most recent session id and the route it should reopen.",
      "Saved trip summary and the last persisted workspace checkpoint.",
      "A deterministic fallback if the session payload is no longer available.",
    ],
    profile_id: travelerProfiles.leisure_primary.profile_id,
    trip_id: "trip-leisure-lisbon-oct",
    recent_session_id: "session-leisure-lisbon-planner",
    policy_context: null,
  },
};

const leisurePlannerPanelState = {
  trip: {
    trip_id: "trip-leisure-lisbon-oct",
    user_id: "user-17",
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
        notes: "Keep one soft landing day after arrival.",
      },
    },
    profile_refs: {
      leisure_profile_id: "profile-leisure-17",
    },
    title: "Lisbon reset with room to wander",
    summary: "Walkability, food value, and a lighter first two days are driving the plan.",
  },
  option_set: {
    option_set_id: "option-set-lodging-01",
    trip_id: "trip-leisure-lisbon-oct",
    purpose: "profile_learning",
    scope: "lodging",
    title: "Stay shape for the first half of the trip",
    options: [
      {
        option_id: "option-central",
        kind: "lodging",
        label: "Central walkable hotel",
        summary: "Smaller room, faster access to dinners and tram routes.",
        drawbacks: ["More noise risk."],
        explanation: ["Best when evening spontaneity matters most."],
      },
      {
        option_id: "option-quiet",
        kind: "lodging",
        label: "Calmer riverside guesthouse",
        summary: "Larger room and quieter nights with longer transit legs.",
        drawbacks: ["Less immediate old-city access."],
        explanation: ["Best when recovery time matters more than being central."],
      },
    ],
    comparison_axes: [
      { key: "walkability", label: "Walkability", direction: "higher_better" },
      { key: "quiet", label: "Night Quiet", direction: "higher_better" },
      { key: "price", label: "Nightly Cost", direction: "lower_better" },
    ],
    explanation: [
      "The shell should carry canonical option-set meaning forward into later workspace views.",
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
      body: "The planner is asking for one specific lodging signal instead of another abstract preference dump.",
      tags: ["leisure", "decision-ready"],
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
      description: "Tell the planner whether central access or recovery quiet should win.",
      emphasis: "primary",
      target_section: "decisions",
    },
  ],
};

const businessPlannerPanelState = {
  trip: {
    trip_id: "trip-client-audit-sea",
    user_id: "user-17",
    mode: "business",
    status: "active",
    trip_frame: {
      start_date: "2025-06-17",
      end_date: "2025-06-20",
      duration_days: 4,
      primary_regions: ["Seattle", "Bellevue"],
      traveler_party: {
        kind: "solo",
        traveler_count: 1,
        notes: "Pre-dawn client audit and a policy exception for the hotel zone.",
      },
    },
    profile_refs: {
      business_profile_id: "profile-business-4",
    },
    title: "Seattle audit trip with approval packet",
    summary: "The plan is close to submission, but the hotel zone still needs an exception path.",
  },
  option_set: {
    option_set_id: "option-set-policy-01",
    trip_id: "trip-client-audit-sea",
    purpose: "approval_review",
    scope: "lodging",
    title: "Approval-ready lodging set",
    options: [
      {
        option_id: "option-hotel-near-client",
        kind: "lodging",
        label: "Hotel near client site",
        summary: "Reduces early-morning transit risk but requires an exception packet.",
        drawbacks: ["Outside standard hotel zone."],
        explanation: ["Best fit for the audit window and pre-dawn departure timing."],
      },
    ],
    comparison_axes: [
      { key: "policy_fit", label: "Policy Fit", direction: "higher_better" },
      { key: "arrival_risk", label: "Arrival Risk", direction: "lower_better" },
    ],
    explanation: ["Approval comparables and justifications should stay attached to canonical proposal data."],
  },
  proposal: {
    proposal_id: "proposal-client-audit-01",
    comparables: [
      {
        category: "lodging",
        label: "Standard downtown policy hotel",
        vendor: "Harbor Suites",
        booking_channel: "corp-portal",
        estimated_cost: {
          currency: "USD",
          typical_amount: 289,
        },
        notes: ["Compliant but adds a 5:10am transfer for the client audit."],
      },
    ],
    justifications: [
      {
        category: "lodging",
        summary: "Closer lodging materially lowers missed-audit risk.",
        evidence: ["5:45am client-site arrival requirement", "No later compliant shuttle option"],
      },
    ],
    approval_notes: ["Exception packet draft is ready for travel ops review."],
    requested_exception: {
      exception_type: "preferred_hotel_zone",
      reason: "Lower arrival risk for pre-dawn audit window.",
      requested_approval_roles: ["travel_ops", "engagement_partner"],
      notes: ["Hotel remains within negotiated budget ceiling."],
    },
  },
  policy_evaluation: {
    evaluation_id: "policy-eval-77",
    proposal_id: "proposal-client-audit-01",
    status: "exception_required",
    approval_requirements: [
      { role: "travel_ops", reason: "Hotel zone exception", mandatory: true },
      { role: "engagement_partner", reason: "Client-site timing risk", mandatory: true },
    ],
    failure_reasons: [],
    preferred_alternatives: [
      {
        category: "lodging",
        summary: "Downtown compliant hotel with longer morning transfer.",
        rationale: "Compliant baseline for exception comparison.",
        comparable_ref: "comp-1",
      },
    ],
    exception_guidance: ["Attach the pre-dawn timing evidence to the submission."],
    notes: ["Policy system found no blocking spend variance."],
    compliance_score: 0.82,
  },
  pending_decisions: [
    {
      decision_id: "approval-confirmation",
      title: "Confirm the exception posture",
      prompt: "Should the planner prepare the exception packet now?",
      choices: ["Prepare approval packet", "Re-open compliant alternative"],
    },
  ],
  outputs: [
    {
      output_id: "approval-summary-01",
      title: "Approval summary",
      body: "The route is ready for travel-ops review once the exception packet is attached.",
      tags: ["business", "approval-ready"],
    },
  ],
  planner_behavior: {
    trip_stage: "approval",
    ask_before_next_major_change: true,
    target_research_passes: 1,
    target_options_before_checkpoint: 1,
    surface_options_early: true,
    explanation_density: "lean",
  },
  next_step_actions: [
    {
      action_id: "prepare-approval-packet",
      action_kind: "prepare_approval",
      label: "Prepare approval packet",
      description: "Bundle comparables, justification, and approver list for review.",
      emphasis: "primary",
      target_section: "approval",
    },
  ],
};

/** @type {FrontendShellState} */
export const firstTimeLeisureDashboardShellState = {
  session: firstTimeLeisureSession,
  routes: [],
  active_route: "dashboard",
  trips: [],
  active_trip_id: null,
  account_entry: {
    traveler_profiles: [travelerProfiles.leisure_new_user],
    recent_sessions: [],
    launch_flows: [launchFlows.new_leisure_trip, launchFlows.new_business_trip],
    selected_launch_id: "new_leisure_trip",
    empty_state_message: "No saved trips yet. Start with a leisure brief or open a policy-aware business launch.",
  },
  workspace: {
    trip_id: null,
    status: "empty",
    planner_panel_state: null,
    loading_message: null,
    error_message: null,
    persistence_summary: [
      "First-trip launch should create persisted account, trip, and session records together.",
      "Empty-state onboarding must stay deterministic until live identity and session APIs arrive.",
    ],
  },
};

/** @type {FrontendShellState} */
export const signedInDashboardShellState = {
  session: signedInSession,
  routes: [],
  active_route: "dashboard",
  trips: [
    {
      trip_id: leisurePlannerPanelState.trip.trip_id,
      title: leisurePlannerPanelState.trip.title,
      summary: leisurePlannerPanelState.trip.summary,
      mode: leisurePlannerPanelState.trip.mode,
      status: leisurePlannerPanelState.trip.status,
      start_date: leisurePlannerPanelState.trip.trip_frame.start_date,
      end_date: leisurePlannerPanelState.trip.trip_frame.end_date,
      primary_regions: leisurePlannerPanelState.trip.trip_frame.primary_regions,
      scenario_count: 3,
      pending_checkpoint_count: 1,
      policy_state: null,
    },
    {
      trip_id: businessPlannerPanelState.trip.trip_id,
      title: businessPlannerPanelState.trip.title,
      summary: businessPlannerPanelState.trip.summary,
      mode: businessPlannerPanelState.trip.mode,
      status: businessPlannerPanelState.trip.status,
      start_date: businessPlannerPanelState.trip.trip_frame.start_date,
      end_date: businessPlannerPanelState.trip.trip_frame.end_date,
      primary_regions: businessPlannerPanelState.trip.trip_frame.primary_regions,
      scenario_count: 2,
      pending_checkpoint_count: 1,
      policy_state: businessPlannerPanelState.policy_evaluation.status,
    },
  ],
  active_trip_id: null,
  account_entry: {
    traveler_profiles: [travelerProfiles.leisure_primary, travelerProfiles.business_primary],
    recent_sessions: [
      {
        session_id: "session-leisure-lisbon-planner",
        trip_id: leisurePlannerPanelState.trip.trip_id,
        mode: "leisure",
        label: "Resume Lisbon comparison",
        summary: "Return to the lodging checkpoint with one open decision and three saved scenarios.",
        last_active_label: "Worked 2h ago",
        resume_route: "planner_workspace",
      },
      {
        session_id: "session-business-audit-approval",
        trip_id: businessPlannerPanelState.trip.trip_id,
        mode: "business",
        label: "Resume Seattle approval packet",
        summary: "Reopen the exception packet and approval-ready comparables for travel ops review.",
        last_active_label: "Worked yesterday",
        resume_route: "approval_center",
      },
    ],
    launch_flows: [
      launchFlows.new_leisure_trip,
      launchFlows.new_business_trip,
      launchFlows.resume_existing_trip,
    ],
    selected_launch_id: "resume_existing_trip",
    empty_state_message: null,
  },
  workspace: {
    trip_id: null,
    status: "empty",
    planner_panel_state: null,
    loading_message: null,
    error_message: null,
    persistence_summary: [
      "Account is signed in and can resume saved leisure or business trips.",
      "Trip launch should branch into issue #557 once account and entry flows land.",
    ],
  },
};

/** @type {FrontendShellState} */
export const businessPolicyStartDashboardShellState = {
  session: businessEntrySession,
  routes: [],
  active_route: "dashboard",
  trips: [signedInDashboardShellState.trips[1]],
  active_trip_id: null,
  account_entry: {
    traveler_profiles: [travelerProfiles.business_primary, travelerProfiles.leisure_primary],
    recent_sessions: [
      {
        session_id: "session-business-policy-start",
        trip_id: businessPlannerPanelState.trip.trip_id,
        mode: "business",
        label: "Resume policy-linked kickoff",
        summary: "Continue the trip-start flow with traveler purpose, policy posture, and approver context already loaded.",
        last_active_label: "Worked 30m ago",
        resume_route: "trip_workspace",
      },
    ],
    launch_flows: [
      launchFlows.new_business_trip,
      {
        ...launchFlows.resume_existing_trip,
        mode: "business",
        trip_id: businessPlannerPanelState.trip.trip_id,
        recent_session_id: "session-business-policy-start",
        summary: "Resume the latest business kickoff and keep policy-linked trip start intact.",
      },
      launchFlows.new_leisure_trip,
    ],
    selected_launch_id: "new_business_trip",
    empty_state_message: null,
  },
  workspace: {
    trip_id: null,
    status: "empty",
    planner_panel_state: null,
    loading_message: null,
    error_message: null,
    persistence_summary: [
      "Business launch should create the trip shell together with policy and approval capture.",
      "Session-entry must preserve why the traveler is starting a policy-aware trip before the planner workspace mounts.",
    ],
  },
};

/** @type {FrontendShellState} */
export const activeLeisureTripShellState = {
  session: signedInSession,
  routes: [],
  active_route: "trip_workspace",
  trips: signedInDashboardShellState.trips,
  active_trip_id: leisurePlannerPanelState.trip.trip_id,
  account_entry: signedInDashboardShellState.account_entry,
  workspace: {
    trip_id: leisurePlannerPanelState.trip.trip_id,
    status: "ready",
    planner_panel_state: leisurePlannerPanelState,
    loading_message: null,
    error_message: null,
    persistence_summary: [
      "Scenario history is available from saved-trip state.",
      "Planner checkpoints should reuse orchestration payloads rather than page-local copies.",
    ],
  },
};

/** @type {FrontendShellState} */
export const activeBusinessTripShellState = {
  session: signedInSession,
  routes: [],
  active_route: "approval_center",
  trips: signedInDashboardShellState.trips,
  active_trip_id: businessPlannerPanelState.trip.trip_id,
  account_entry: signedInDashboardShellState.account_entry,
  workspace: {
    trip_id: businessPlannerPanelState.trip.trip_id,
    status: "ready",
    planner_panel_state: businessPlannerPanelState,
    loading_message: null,
    error_message: null,
    persistence_summary: [
      "Approval comparables and packet metadata should remain attached to the proposal contract.",
      "Business approval surfaces should sit beside planner state, not replace it.",
    ],
  },
};

export const appShellStateMocks = {
  first_time_leisure_dashboard: firstTimeLeisureDashboardShellState,
  signed_in_dashboard: signedInDashboardShellState,
  business_policy_start_dashboard: businessPolicyStartDashboardShellState,
  active_leisure_trip: activeLeisureTripShellState,
  active_business_trip: activeBusinessTripShellState,
};
