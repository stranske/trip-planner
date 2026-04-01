# Itinerary Objective Derivation Boundary

Issue #512 introduces a deterministic handoff layer between resolved leisure preferences and later itinerary ranking.

## In Scope

- Convert `ResolvedLeisureProfile` into `ItineraryObjectives`.
- Preserve explainability by carrying dimension signals, tensions, and activated interactions into objective explanations.
- Keep objective shaping deterministic so fixture-based tests can assert material profile differences.

## Out of Scope

- Candidate generation and final itinerary ranking/scoring.
- Live inventory search or route graph traversal.
- UI-specific rendering behavior.

## Contract Position

`LeisurePreferenceProfile` + evidence -> `ResolvedLeisureProfile` -> `ItineraryObjectives` -> ranking/search layer

The derivation layer owns objective shaping only; ranking owns optimization and final option ordering.
`trip_planner/ranking/leisure.py` must stay downstream from both leisure preference resolution and
itinerary-objective derivation, consuming `LeisurePreferenceProfile` and `ItineraryObjectives`
instead of bypassing them with direct ranking heuristics.
