# Trip Persistence Boundary

Issue #539 introduces the persisted trip container that sits between account ownership and the later saved-scenario/session-state backlog.

## Intent

`PersistedTripRecord` is the durable storage contract for:

- trip identity, mode, and lifecycle status
- owner and traveler-profile references
- references to planning artifacts produced elsewhere
- repository revision metadata and status history

The record should stay reference-oriented. It is a durable container, not a giant embedded blob of every planning artifact.

## Artifact Relationship

Persisted trip records may reference:

- objectives
- option sets
- ranked result sets
- scenario-search outputs
- saved-scenario ids
- itinerary state
- budget state
- policy state
- planning-session state
- activity-log state

That boundary keeps later issues clean:

- issue `#540` can add richer saved-scenario and checkpoint contracts without redefining trip ownership
- issue `#541` can deepen budget and spend persistence without mutating trip identity rules
- issue `#542` can model durable planning sessions and logs while still hanging them off a stable trip record

## Status Model

Allowed transitions are intentionally explicit:

- `draft -> active -> booked -> in_trip -> completed -> archived`
- `draft`, `active`, `booked`, and `in_trip` may also archive early when the plan is canceled

Repository implementations should persist every transition in `status_history` so downstream UI and audit flows can explain how a trip reached its current state.
