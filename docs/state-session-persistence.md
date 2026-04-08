# Planning Session And Activity-Log Persistence

Issue `#542` adds the mutable session-state layer that sits beside saved scenarios and budgets while keeping a separate append-only activity log.

## Intent

`PlanningSessionState` stores the current interactive planning surface for one trip:

- interaction-style state and initiative settings
- checkpoint cadence and option-preview timing
- recent option-presentation history
- pending decisions that still need user or planner resolution

`ActivityLogEvent` stores the durable event trail for major actions such as scenario saves, rerank requests, option rejections, budget updates, and in-trip change requests.

## Boundary

This layer is intentionally split:

- `PersistedTripRecord` keeps only stable references such as `session_state_id` and `activity_log_id`
- `SavedScenarioRecord` keeps immutable version history and checkpoints
- `PlanningSessionState` owns the latest mutable interaction state
- `ActivityLogEvent` preserves append-only evidence of what happened during planning

That separation lets later orchestration, chat, and in-trip workflow code resume a live session without confusing current planner state with immutable scenario history.

## Repository Expectations

Repository implementations should treat:

- session state as mutable and versioned
- pending decisions as replaceable current state
- option-presentation history as a bounded recent-history slice on the session record
- activity-log events as append-only records that can be filtered by trip, session, decision, or option set

## Event Writing Guidance

Later workspace, orchestration, and policy features should append `ActivityLogEvent`
records whenever they create user-visible planning state transitions. The event trail is
the durable explanation surface for why a trip changed, so later issues should reuse it
instead of creating side-channel audit notes.

The first pass expects new writers to:

- attach every event to the owning `trip_id`
- include `session_state_id` whenever the action came from an active planning session
- keep `event_kind` stable and specific enough for filtering, such as
  `scenario_saved`, `policy_review_requested`, or `budget_recomputed`
- write a concise `summary` that is suitable for direct UI rendering in the trip activity
  timeline
- populate related ids like `saved_scenario_id`, `related_decision_id`, or
  `related_option_set_id` when that context exists instead of burying it only in metadata
- treat `metadata` as optional supporting detail, not the only place the core event meaning
  lives

Future policy and workspace issues should prefer appending a new event over mutating prior
history. Session state may evolve in place, but the audit trail should remain chronological
and additive so reload, verification, and later incident review can explain what happened.

The first pass stays backend-neutral. The goal is to lock the persistence contract before later UI, orchestration, and notification work depends on it.
