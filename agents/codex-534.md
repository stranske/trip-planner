# Issue #534 Workloop Bootstrap

This branch advances issue #534 (`[Agent] [Ranking] Build the leisure candidate ranking engine`) beyond placeholder setup by defining the concrete implementation slice for the first-pass leisure ranking engine.

## Scope For This PR Iteration

- Establish an implementation-ready plan for `trip_planner/ranking/leisure.py` that stays downstream from preference resolution and objective derivation.
- Keep follow-up commits narrowly focused on deterministic leisure ranking behavior, canonical ranking output contracts, and representative tests.
- Capture validation targets so future pushes remain reviewable and traceable to the issue acceptance criteria.

## Implementation Targets

1. Ranking engine skeleton
- Add `trip_planner/ranking/leisure.py` with a `LeisureRankingEngine` entry point.
- Consume `LeisurePreferenceProfile`, `ItineraryObjectives`, feasibility outputs, and candidate sets or bundles without bypassing upstream planning contracts.

2. Deterministic leisure scoring
- Score anchors, quality floors, budget posture, route coherence, discovery fit, movement or friction fit, and recovery protection.
- Encode tension flags and low-confidence profile areas as explicit confidence and penalty signals instead of opaque heuristics.

3. Ranking outputs + fixtures
- Emit canonical ranked-result and explanation payloads aligned with the issue #532 contracts.
- Add representative fixture-backed cases for materially different leisure traveler profiles and edge cases.

## Validation Targets

- `tests/ranking/test_leisure_ranking.py`
- `tests/fixtures/ranking/leisure/*.json`
- Assertions showing the same candidate set reorders across different leisure profiles, including at least one low-confidence or tension-heavy case.

## Notes

- Keep this iteration deterministic and inspectable; do not introduce business-mode ranking or route-search optimization work here.
- Documentation follow-up remains deferred until the exact target doc path is specified on the source issue.
