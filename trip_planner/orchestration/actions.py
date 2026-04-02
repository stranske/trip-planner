"""Canonical action and workflow vocabularies for orchestration contracts."""

TURN_KINDS: tuple[str, ...] = (
    "planning_pass",
    "decision_checkpoint",
    "adjustment_pass",
)
WORKFLOW_KINDS: tuple[str, ...] = (
    "leisure_planning",
    "business_planning",
    "in_trip_adjustment",
)
WORKFLOW_STAGES: tuple[str, ...] = (
    "intake",
    "objective_derivation",
    "candidate_generation",
    "ranking",
    "decision_checkpoint",
    "policy_alignment",
    "booking_prep",
    "monitoring",
    "replanning",
    "completed",
)
WORKFLOW_STATUSES: tuple[str, ...] = (
    "active",
    "waiting_on_user",
    "blocked",
    "completed",
)
ACTION_KINDS: tuple[str, ...] = (
    "collect_context",
    "refresh_preferences",
    "derive_objectives",
    "assemble_candidates",
    "rank_options",
    "prepare_policy_summary",
    "request_decision",
    "persist_state",
    "record_warning",
    "replan_itinerary",
)
ACTION_STATUSES: tuple[str, ...] = (
    "pending",
    "in_progress",
    "completed",
    "skipped",
)
OUTPUT_KINDS: tuple[str, ...] = (
    "question",
    "option_set",
    "ranked_scenarios",
    "decision_request",
    "warning",
    "status_update",
    "policy_summary",
)
OUTPUT_SURFACES: tuple[str, ...] = (
    "planner_chat",
    "side_panel",
    "notification",
    "policy_packet",
    "timeline",
)
TRANSITION_TRIGGERS: tuple[str, ...] = (
    "user_request",
    "planner_recommendation",
    "decision_response",
    "policy_constraint",
    "budget_change",
    "trip_disruption",
    "checkpoint_due",
)
