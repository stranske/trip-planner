# Ranking Result Contracts

`trip_planner/ranking` defines the canonical output contract for every later ranking layer.

## Boundary

- Inputs should already be normalized options, candidate seeds, itinerary objectives, and later feasibility outputs.
- Outputs are ranked results, explicit score breakdowns, adjustment records, confidence summaries, unresolved-risk flags, and explanation records.
- This layer does not implement leisure ranking logic, business policy logic, or route search by itself.

## What Must Be Explicit

- component-level contributions instead of one opaque scalar
- penalties, bonuses, and missing-data penalties as separate records
- confidence and missing-data summaries that later UI or chat layers can surface directly
- explanation records that keep both machine-readable factor keys and human-readable summaries
- support for item-level results and bundle or route-level results in one shared result-set shape

## Result Model

Future ranking modules should emit `RankedResultSet` values built from:

- `RankedResult` for each ranked candidate, bundle, or route
- `ScoreBreakdown` with `ScoreContribution`, `ScoreAdjustment`, and missing-data penalties
- `ScoreConfidenceSummary` for uncertainty and coverage
- `RiskFlag` for unresolved risks that should survive into review or UI layers
- `ExplanationRecord` for summary, promotion, penalty, risk, and confidence narratives

## Working Rule

When a future ranking layer emits results:

1. Keep the result target explicit: item results should point to a ranked option, while bundle or route results should point to a stable bundle identifier.
2. Preserve why the score changed: every meaningful promotion, penalty, and missing-data discount should be represented in the score breakdown or explanation records.
3. Keep uncertainty inspectable: low-confidence inputs and unresolved risks should remain visible instead of being hidden inside the final score.

If a future PR needs ranking output that cannot fit these contracts, extend `trip_planner/ranking` rather than inventing a parallel result container.
