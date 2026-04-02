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

The first pass stays backend-neutral. The goal is to lock the persistence contract before later UI, orchestration, and notification work depends on it.
