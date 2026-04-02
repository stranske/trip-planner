# Saved Scenario And Checkpoint Persistence

Issue `#540` introduces the durable saved-scenario layer that sits above persisted trips and below later session orchestration.

## Intent

`SavedScenarioRecord` keeps scenario history explicit and versioned instead of collapsing route alternatives into one mutable current state.

This layer owns:

- saved scenario versions that reference the planning artifacts captured at save time
- durable comparison metadata for baseline-versus-fallback or compliant-versus-exception review
- checkpoints that mark meaningful decision moments or in-trip revisions

## Snapshot Boundary

Saved scenario versions stay reference-oriented. They can point at:

- itinerary objectives
- ranked result sets
- scenario-search outputs
- itinerary scenario ids
- option sets
- budget state
- policy state
- planning-session state
- relevant leisure or business profile ids

That keeps persisted trip records small while still making scenario history inspectable and restorable.

## Labels And History

The first-pass label vocabulary is intentionally explicit:

- `baseline`
- `preferred`
- `fallback`
- `compliant_first`
- `exception_nearest`
- `in_trip_revision`

Those labels let later UI and verifier flows explain why a scenario exists instead of treating every saved snapshot as just another unnamed revision.

## Checkpoints

`ScenarioCheckpoint` is separate from `SavedScenarioRecord` so the system can mark durable decision moments without mutating the underlying snapshot history.

Typical checkpoint uses include:

- baseline capture before major comparison
- fallback capture for a retained contingency plan
- policy review milestones
- in-trip revisions with pending follow-up decisions

## Repository Expectations

Repository implementations should support:

- saving scenario records and listing version history
- restoring a prior version as a fresh active snapshot
- listing scenarios by trip or active label
- persisting comparison metadata without coupling to a storage backend
- creating and filtering checkpoints independently of version restore
