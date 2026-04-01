# Leisure Ranking

`trip_planner/ranking/leisure.py` is the first-pass leisure ranking engine for candidate bundles.

## Boundary

- Inputs should already be resolved leisure preferences, itinerary objectives, candidate bundles, and feasibility outputs.
- This layer ranks bundles; it does not replace preference resolution, objective derivation, candidate generation, or feasibility evaluation.
- Outputs must stay explainable through canonical `RankedResultSet` records, confidence summaries, penalties, and risks.

## What The Leisure Scorer Must Keep Explicit

- first-tier leisure dimension alignment such as discovery vs iconic, movement vs friction, recovery vs intensity, and route coherence vs eclectic contrast
- anchors, quality floors, budget posture, and salient hybrid factors
- tension flags and low-confidence preference areas
- feasibility blockers, route warnings, and missing-data penalties

## Working Rule

When leisure ranking changes:

1. Keep the scorer deterministic and inspectable.
2. Preserve why a bundle moved up or down through score contributions and explanation records.
3. Keep preference-resolution and objective-derivation logic upstream; extend those layers instead of duplicating them here.
