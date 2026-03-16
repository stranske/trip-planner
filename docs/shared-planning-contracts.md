# Shared Planning Contracts

The canonical shared planning contracts now live in `trip_planner/contracts/`.

These contracts are the first cross-mode planning layer that sits above the leisure preference package and below later ranking, orchestration, persistence, and policy integration work.

## Canonical Modules

- `trip_planner/contracts/trip.py`
  - `Trip`, `TripFrameSummary`, mode-specific profile references, and artifact references
- `trip_planner/contracts/options.py`
  - `OptionSet`, `Option`, comparison axes, and cost/quality summaries
- `trip_planner/contracts/objectives.py`
  - `ItineraryObjectives` and the deterministic objective subcontracts used by later search and ranking work

## Design Intent

- `Trip` is the shared planning container, not a bag of inlined downstream payloads.
- Leisure and business profiles stay separate; `Trip` references them rather than collapsing them into one schema.
- `OptionSet` is first-class because the planner is expected to learn from concrete choices, not only from direct statements.
- `ItineraryObjectives` is the handoff contract between profile resolution and later ranking or route assembly.

## Current Boundaries

The contracts added here are intentionally lightweight:

- they are implementation-facing Python contracts
- they are not yet frontend API schemas
- they are not final booking or inventory adapters
- they do not replace the later business-policy export objects

## Usage Guidance

- New cross-mode planning work should import from `trip_planner/contracts/`.
- Preference-specific logic should continue to use `trip_planner/preferences/`.
- Legacy script JSON should not be treated as the source of truth for new planning code.
