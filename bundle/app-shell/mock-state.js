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

const leisureWorkspaceScenarios = [
  {
    scenario_id: "scenario-lisbon-central",
    title: "Central Lisbon base",
    summary: "Keeps tram access and evening spontaneity high for the first half of the trip.",
    status: "active",
    comparison_note: "Best score for walkability and short decision loops.",
    option_count: 3,
    checkpoint_id: "checkpoint-lisbon-lodging",
    budget_variant_id: "budget-lisbon-central",
  },
  {
    scenario_id: "scenario-lisbon-riverside",
    title: "Quiet riverside fallback",
    summary: "Trades central access for quieter recovery nights and a larger room footprint.",
    status: "fallback",
    comparison_note: "Lower nightly spend with a longer first-leg transit pattern.",
    option_count: 2,
    checkpoint_id: "checkpoint-lisbon-lodging",
    budget_variant_id: "budget-lisbon-riverside",
  },
];

const leisureCheckpointHistory = [
  {
    checkpoint_id: "checkpoint-lisbon-lodging",
    label: "Lodging tradeoff checkpoint",
    summary: "Waiting on the central-versus-quiet base-camp preference.",
    status: "current",
    scenario_id: "scenario-lisbon-central",
    updated_label: "Updated 2h ago",
  },
  {
    checkpoint_id: "checkpoint-lisbon-seed",
    label: "Trip brief capture",
    summary: "Seeded walkability, fatigue, and soft-landing preferences into the workspace.",
    status: "saved",
    scenario_id: "scenario-lisbon-central",
    updated_label: "Saved yesterday",
  },
];

const leisureBudgetSummary = {
  budget_state_id: "budget-lisbon-01",
  currency: "USD",
  baseline_total: 3200,
  selected_total: 3110,
  actual_total: 0,
  status: "healthy",
  variance_label: "$90 under target",
  categories: ["lodging", "local transit", "dining"],
  variants: [
    {
      variant_id: "budget-lisbon-central",
      scenario_id: "scenario-lisbon-central",
      label: "Central base",
      total_amount: 3110,
      variance_label: "$90 under target",
    },
    {
      variant_id: "budget-lisbon-riverside",
      scenario_id: "scenario-lisbon-riverside",
      label: "Quiet fallback",
      total_amount: 2960,
      variance_label: "$240 under target",
    },
  ],
};

const businessWorkspaceScenarios = [
  {
    scenario_id: "scenario-sea-near-client",
    title: "Primary exception-ready scenario",
    summary: "Keeps the hotel close to the client site and preserves a low-risk arrival window.",
    status: "active",
    comparison_note: "Best operational fit, but requires a hotel-zone exception.",
    option_count: 1,
    checkpoint_id: "checkpoint-sea-approval",
    budget_variant_id: "budget-sea-primary",
  },
  {
    scenario_id: "scenario-sea-downtown",
    title: "Compliant downtown fallback",
    summary: "Avoids the exception packet at the cost of a 5:10am transfer and higher arrival risk.",
    status: "fallback",
    comparison_note: "Compliance-first alternative for travel-ops review.",
    option_count: 1,
    checkpoint_id: "checkpoint-sea-approval",
    budget_variant_id: "budget-sea-fallback",
  },
];

const businessCheckpointHistory = [
  {
    checkpoint_id: "checkpoint-sea-approval",
    label: "Approval packet review",
    summary: "Comparables and justification are ready for travel ops review.",
    status: "current",
    scenario_id: "scenario-sea-near-client",
    updated_label: "Updated 30m ago",
  },
  {
    checkpoint_id: "checkpoint-sea-kickoff",
    label: "Policy-aware kickoff",
    summary: "Captured traveler purpose, audit timing, and exception posture before planning.",
    status: "saved",
    scenario_id: "scenario-sea-near-client",
    updated_label: "Saved yesterday",
  },
];

const businessBudgetSummary = {
  budget_state_id: "budget-sea-01",
  currency: "USD",
  baseline_total: 1850,
  selected_total: 1810,
  actual_total: 0,
  status: "watch",
  variance_label: "$40 under target before exception review",
  categories: ["lodging", "air", "ground transport"],
  variants: [
    {
      variant_id: "budget-sea-primary",
      scenario_id: "scenario-sea-near-client",
      label: "Near-client hotel",
      total_amount: 1810,
      variance_label: "$40 under target",
    },
    {
      variant_id: "budget-sea-fallback",
      scenario_id: "scenario-sea-downtown",
      label: "Downtown fallback",
      total_amount: 1725,
      variance_label: "$125 under target",
    },
  ],
};

const inTripRevisionWorkspaceScenarios = [
  {
    scenario_id: "scenario-lisbon-rain-reset",
    title: "Rain-adjusted active plan",
    summary: "Rebalances the final two days around indoor stops and lower transfer friction.",
    status: "revised",
    comparison_note: "Current best fit after weather drift and spend pressure.",
    option_count: 3,
    checkpoint_id: "checkpoint-lisbon-replan",
    budget_variant_id: "budget-lisbon-rain-reset",
  },
  {
    scenario_id: "scenario-lisbon-central",
    title: "Original central base",
    summary: "The pre-replan scenario is still saved as a fallback if conditions improve.",
    status: "fallback",
    comparison_note: "Preserved for comparison against the revised route shape.",
    option_count: 3,
    checkpoint_id: "checkpoint-lisbon-lodging",
    budget_variant_id: "budget-lisbon-central",
  },
];

const inTripRevisionCheckpointHistory = [
  {
    checkpoint_id: "checkpoint-lisbon-replan",
    label: "In-trip replanning checkpoint",
    summary: "Weather drift and actual spend triggered a scenario refresh mid-trip.",
    status: "current",
    scenario_id: "scenario-lisbon-rain-reset",
    updated_label: "Updated 20m ago",
  },
  {
    checkpoint_id: "checkpoint-lisbon-lodging",
    label: "Original lodging decision",
    summary: "The initial stay-shape decision remains saved for comparison.",
    status: "revisit",
    scenario_id: "scenario-lisbon-central",
    updated_label: "Saved 2 days ago",
  },
];

const inTripRevisionBudgetSummary = {
  budget_state_id: "budget-lisbon-02",
  currency: "USD",
  baseline_total: 3200,
  selected_total: 3345,
  actual_total: 1860,
  status: "watch",
  variance_label: "$145 over target unless the revised scenario holds",
  categories: ["lodging", "rail", "museum swaps"],
  variants: [
    {
      variant_id: "budget-lisbon-rain-reset",
      scenario_id: "scenario-lisbon-rain-reset",
      label: "Rain-adjusted plan",
      total_amount: 3345,
      variance_label: "$145 over target",
    },
    {
      variant_id: "budget-lisbon-central",
      scenario_id: "scenario-lisbon-central",
      label: "Original plan",
      total_amount: 3480,
      variance_label: "$280 over target",
    },
  ],
};

const leisureVisualizationScenarios = [
  {
    scenario_id: "scenario-lisbon-regional-loop",
    title: "Lisbon regional loop",
    variant_label: "base route",
    summary: "Keeps Lisbon as the lodging anchor while layering one Sintra day and one riverfront recovery day.",
    route_shape: "regional cluster",
    movement_burden: "low transfer burden",
    tradeoff_summary: "Best route coherence with one medium-transfer excursion day.",
    map_status: "ready",
    map_summary: "Map surface should emphasize the Lisbon core, Sintra rail branch, and recovery-friendly riverside fallback anchors.",
    route_warnings: [
      "Sintra day can stack hill fatigue after a late arrival evening.",
    ],
    anchors: [
      {
        anchor_id: "anchor-lisbon-base",
        label: "Baixa base hotel",
        kind: "lodging",
        summary: "Central lodging anchor for walkable dinners and tram access.",
      },
      {
        anchor_id: "anchor-sintra",
        label: "Sintra day cluster",
        kind: "destination",
        summary: "Regional excursion anchor with a single rail transfer.",
      },
      {
        anchor_id: "anchor-riverside",
        label: "Belém recovery block",
        kind: "activity",
        summary: "Low-friction afternoon fallback for a lighter day.",
      },
    ],
    route_segments: [
      {
        segment_id: "segment-arrival",
        label: "Arrival to base",
        mode: "tram",
        from_label: "Airport",
        to_label: "Baixa base hotel",
        duration_label: "35 min",
        burden_label: "light arrival burden",
        warning: null,
      },
      {
        segment_id: "segment-sintra",
        label: "Regional day loop",
        mode: "rail",
        from_label: "Rossio",
        to_label: "Sintra day cluster",
        duration_label: "45 min each way",
        burden_label: "moderate day-trip burden",
        warning: "Watch hill fatigue if the prior night runs late.",
      },
    ],
    timeline_days: [
      {
        day_id: "day-1",
        label: "Day 1 arrival",
        posture: "soft landing",
        movement_summary: "Keep the first evening compact and fully walkable.",
        blocks: [
          {
            block_id: "block-1",
            label: "Hotel check-in",
            kind: "arrival",
            time_label: "15:00",
            summary: "Drop bags and keep the first neighborhood radius small.",
          },
          {
            block_id: "block-2",
            label: "Baixa dinner loop",
            kind: "activity",
            time_label: "19:00",
            summary: "Short walk loop with low commitment if arrival runs late.",
          },
        ],
      },
      {
        day_id: "day-3",
        label: "Day 3 Sintra excursion",
        posture: "regional move day",
        movement_summary: "One out-and-back rail segment plus hill-heavy exploration.",
        blocks: [
          {
            block_id: "block-3",
            label: "Rossio departure",
            kind: "transit",
            time_label: "08:15",
            summary: "Board the first rail leg before the station crowds build.",
          },
          {
            block_id: "block-4",
            label: "Castle + garden cluster",
            kind: "activity",
            time_label: "10:00",
            summary: "Keep one recovery break between hill sections.",
          },
        ],
      },
    ],
  },
  {
    scenario_id: "scenario-lisbon-scenic-transit",
    title: "Scenic transit variant",
    variant_label: "scenic route",
    summary: "Trades one extra transfer for ferry and tram segments that turn the route itself into part of the trip value.",
    route_shape: "scenic transit chain",
    movement_burden: "medium transfer burden",
    tradeoff_summary: "Higher route delight, but more transfer exposure and less slack for late starts.",
    map_status: "ready",
    map_summary: "Map should emphasize the ferry stitch, tram spine, and where scenic movement increases transfer exposure.",
    route_warnings: [
      "Ferry timing narrows the margin for a slow morning.",
      "Scenic route variant adds one extra transfer on the river crossing.",
    ],
    anchors: [
      {
        anchor_id: "anchor-ferry",
        label: "River ferry stitch",
        kind: "transfer",
        summary: "The scenic crossing is part of the route value, not just transit overhead.",
      },
      {
        anchor_id: "anchor-tram",
        label: "Historic tram spine",
        kind: "activity",
        summary: "Route keeps hillside access scenic rather than taxi-heavy.",
      },
    ],
    route_segments: [
      {
        segment_id: "segment-ferry",
        label: "River crossing",
        mode: "ferry",
        from_label: "Cais do Sodré",
        to_label: "Cacilhas",
        duration_label: "15 min",
        burden_label: "light scenic burden",
        warning: "Missing the ferry pushes the afternoon sequence off by 30 minutes.",
      },
      {
        segment_id: "segment-tram",
        label: "Hillside tram arc",
        mode: "tram",
        from_label: "Cacilhas return",
        to_label: "Alfama ridge",
        duration_label: "30 min",
        burden_label: "moderate crowding risk",
        warning: null,
      },
    ],
    timeline_days: [
      {
        day_id: "day-2",
        label: "Day 2 scenic transfer day",
        posture: "route-first day",
        movement_summary: "The movement experience is the headline, so the route needs visible slack markers.",
        blocks: [
          {
            block_id: "block-5",
            label: "Ferry boarding buffer",
            kind: "buffer",
            time_label: "09:10",
            summary: "Hold a 20-minute margin so the scenic chain stays intact.",
          },
          {
            block_id: "block-6",
            label: "Riverfront lunch",
            kind: "stay",
            time_label: "12:30",
            summary: "Pause between ferry and tram segments to cut transfer fatigue.",
          },
        ],
      },
    ],
  },
];

const businessVisualizationScenarios = [
  {
    scenario_id: "scenario-seattle-meeting-window",
    title: "Meeting-window compliant route",
    variant_label: "business base route",
    summary: "Centers the hotel near the client site so the pre-dawn audit window stays resilient.",
    route_shape: "hub and spoke",
    movement_burden: "low morning risk",
    tradeoff_summary: "Best for arrival certainty, but requires exception-ready lodging context.",
    map_status: "ready",
    map_summary: "Map should foreground the hotel-to-client corridor, Bellevue meeting window, and return buffer for the approval packet.",
    route_warnings: [
      "Hotel zone exception remains the main non-route blocker.",
      "Cross-lake traffic can erase the evening buffer if departure slips.",
    ],
    anchors: [
      {
        anchor_id: "anchor-hotel",
        label: "Client-adjacent hotel",
        kind: "lodging",
        summary: "Chosen to preserve the 5:45am arrival window.",
      },
      {
        anchor_id: "anchor-client",
        label: "Audit site",
        kind: "meeting",
        summary: "Hard arrival target with no acceptable late window.",
      },
      {
        anchor_id: "anchor-bellevue",
        label: "Bellevue follow-up",
        kind: "meeting",
        summary: "Secondary meeting block that tightens the afternoon transfer sequence.",
      },
    ],
    route_segments: [
      {
        segment_id: "segment-audit-drive",
        label: "Pre-dawn audit corridor",
        mode: "car",
        from_label: "Client-adjacent hotel",
        to_label: "Audit site",
        duration_label: "12 min",
        burden_label: "low arrival risk",
        warning: null,
      },
      {
        segment_id: "segment-bellevue",
        label: "Cross-lake meeting hop",
        mode: "rideshare",
        from_label: "Audit site",
        to_label: "Bellevue follow-up",
        duration_label: "28 min",
        burden_label: "medium traffic burden",
        warning: "Traffic spikes can consume the lunch buffer.",
      },
    ],
    timeline_days: [
      {
        day_id: "day-1",
        label: "Audit day",
        posture: "constrained meeting window",
        movement_summary: "Very little slack until the primary audit block is complete.",
        blocks: [
          {
            block_id: "block-7",
            label: "Hotel departure",
            kind: "transit",
            time_label: "05:20",
            summary: "Leave before the road network starts shifting into commuter congestion.",
          },
          {
            block_id: "block-8",
            label: "Client audit",
            kind: "meeting",
            time_label: "05:45",
            summary: "Primary hard-window work block that anchors the route choice.",
          },
          {
            block_id: "block-9",
            label: "Bellevue debrief",
            kind: "meeting",
            time_label: "14:00",
            summary: "Secondary meeting with a narrow traffic buffer.",
          },
        ],
      },
    ],
  },
];
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
    scenario_summaries: [],
    checkpoint_history: [],
    budget_summary: null,
    loading_message: null,
    error_message: null,
    persistence_summary: [
      "First-trip launch should create persisted account, trip, and session records together.",
      "Empty-state onboarding must stay deterministic until live identity and session APIs arrive.",
    ],
    visualization_scenarios: [],
    active_visualization_scenario_id: null,
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
    scenario_summaries: [],
    checkpoint_history: [],
    budget_summary: null,
    loading_message: null,
    error_message: null,
    persistence_summary: [
      "Account is signed in and can resume saved leisure or business trips.",
      "Trip launch should branch into issue #557 once account and entry flows land.",
    ],
    visualization_scenarios: [],
    active_visualization_scenario_id: null,
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
    scenario_summaries: [],
    checkpoint_history: [],
    budget_summary: null,
    loading_message: null,
    error_message: null,
    persistence_summary: [
      "Business launch should create the trip shell together with policy and approval capture.",
      "Session-entry must preserve why the traveler is starting a policy-aware trip before the planner workspace mounts.",
    ],
    visualization_scenarios: [],
    active_visualization_scenario_id: null,
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
    scenario_summaries: leisureWorkspaceScenarios,
    checkpoint_history: leisureCheckpointHistory,
    budget_summary: leisureBudgetSummary,
    loading_message: null,
    error_message: null,
    persistence_summary: [
      "Scenario history is available from saved-trip state.",
      "Planner checkpoints should reuse orchestration payloads rather than page-local copies.",
      "Budget variants should stay linked to persisted budget-state ids rather than UI-only totals.",
    ],
    visualization_scenarios: leisureVisualizationScenarios,
    active_visualization_scenario_id: "scenario-lisbon-regional-loop",
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
    scenario_summaries: businessWorkspaceScenarios,
    checkpoint_history: businessCheckpointHistory,
    budget_summary: businessBudgetSummary,
    loading_message: null,
    error_message: null,
    persistence_summary: [
      "Approval comparables and packet metadata should remain attached to the proposal contract.",
      "Business approval surfaces should sit beside planner state, not replace it.",
    ],
    visualization_scenarios: businessVisualizationScenarios,
    active_visualization_scenario_id: "scenario-seattle-meeting-window",
  },
};

/** @type {FrontendShellState} */
export const inTripRevisionShellState = {
  session: signedInSession,
  routes: [],
  active_route: "trip_workspace",
  trips: signedInDashboardShellState.trips,
  active_trip_id: leisurePlannerPanelState.trip.trip_id,
  account_entry: signedInDashboardShellState.account_entry,
  workspace: {
    trip_id: leisurePlannerPanelState.trip.trip_id,
    status: "ready",
    planner_panel_state: {
      ...leisurePlannerPanelState,
      trip: {
        ...leisurePlannerPanelState.trip,
        summary: "Mid-trip replanning is active after weather drift and a tighter spend posture.",
      },
    },
    scenario_summaries: inTripRevisionWorkspaceScenarios,
    checkpoint_history: inTripRevisionCheckpointHistory,
    budget_summary: inTripRevisionBudgetSummary,
    loading_message: null,
    error_message: null,
    persistence_summary: [
      "Revised scenarios should stay linked to the same persisted trip id while checkpoint history keeps the original branch visible.",
      "Budget drift should point to saved budget-state variants instead of mutating ranked option records.",
    ],
  },
};

export const appShellStateMocks = {
  first_time_leisure_dashboard: firstTimeLeisureDashboardShellState,
  signed_in_dashboard: signedInDashboardShellState,
  business_policy_start_dashboard: businessPolicyStartDashboardShellState,
  active_leisure_trip: activeLeisureTripShellState,
  active_business_trip: activeBusinessTripShellState,
  in_trip_revision: inTripRevisionShellState,
};
