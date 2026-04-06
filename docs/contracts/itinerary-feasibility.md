# Itinerary Feasibility Contracts

`trip_planner/itinerary/feasibility.py` is the first shared realism layer between candidate generation and later ranking.

## Boundary

- Inputs are normalized `InventoryBundle` values from candidate generation or later route assembly.
- Outputs are explicit move-cost summaries, timing conflicts, route-continuity warnings, missing-data flags, and a bundle-level feasibility assessment.
- This layer does not decide final ranking. It supplies hard blockers, soft friction signals, and a conservative `recommended_for_ranking` gate that ranking must consume rather than replace.

## What Must Be Explicit

- travel time and transfer burden should remain separate from subjective ranking weights
- hard infeasibility and soft friction penalties must not collapse into one opaque score
- feasible bundles with unresolved missing data or extreme friction should stay visible as feasible while still being marked not yet recommended for ranking
- late-arrival, same-day chaining, and schedule-protection problems should surface as named timing conflicts
- route continuity problems should remain inspectable as warnings instead of being silently baked into downstream scores

## Working Rule

When later ranking modules evaluate bundles or route options:

1. Call the feasibility layer first.
2. Drop or heavily down-rank outputs with blocking reasons, and treat `recommended_for_ranking = false` as a softer deprioritization signal rather than a hard reject.
3. Carry forward `friction_penalty_total`, timing warnings, and missing-data notes into ranking explanations instead of rebuilding travel realism from scratch.

If a later PR needs richer provider-backed timing logic, extend this layer instead of creating a separate hidden feasibility heuristic inside ranking.
