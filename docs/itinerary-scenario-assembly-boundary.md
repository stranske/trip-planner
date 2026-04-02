# Itinerary Scenario Assembly Boundary

Issue #536 adds a first-pass route-search scaffold that turns ranked bundle candidates into multiple explainable itinerary scenarios.

## In Scope

- Define canonical scenario and route-search result contracts.
- Assemble multiple itinerary scenarios from ranked bundle candidates plus feasibility signals.
- Preserve explanation records, unresolved tradeoffs, and primary-vs-fallback distinctions.

## Out of Scope

- Exhaustive global route optimization.
- Final booking, approval submission, or policy adjudication.
- Interactive planner UX, map rendering, or live search orchestration.

## Contract Position

`CandidateSet` -> `RankedResultSet` + `FeasibilityAssessment` -> `ScenarioSearchResult`

Scenario assembly stays downstream from candidate generation, ranking, and feasibility evaluation.
It should package coherent alternatives for later planner orchestration, not replace component scoring
with one opaque route-level heuristic.
