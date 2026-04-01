# Candidate Generation Contracts

`trip_planner/candidates` is the deterministic bridge between ingestion and later ranking.

## Boundary

- Inputs are already-normalized `Destination`, `LodgingOption`, `TransportOption`, and `ActivityOption` objects.
- Outputs are early candidate seeds, explicit exclusion records, and a comparison-ready `OptionSet` projection.
- This layer may assemble `InventoryBundle` seeds, but it does not perform final ranking, route search, or policy optimization.

## What The Layer Adds

- deterministic bundle seeding for profile learning, inventory narrowing, and initial policy comparison
- explicit exclusion records for freshness, availability, destination coverage, and first-pass policy violations
- preserved explanation metadata, source references, booking links, and unresolved-risk notes
- a stable `OptionSet` projection so later ranking can consume candidate seeds without reinterpreting raw normalized objects

## What The Layer Does Not Add

- combinatorial search over all itinerary permutations
- final scoring or recommendation policy
- UI-specific presentation state

Candidate generation should stay inspectable. If a future change needs hidden heuristics or provider-specific shortcuts here, it belongs in a later ranking/search layer instead.
