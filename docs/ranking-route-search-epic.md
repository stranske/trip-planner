# Ranking, Route Feasibility, And Explainable Search Epic Plan

This document records the implementation contract for epic `#531`.

The goal is to sequence the ranking and route-search layer so later proposal packaging, policy review, and UI comparison flows can build on explicit scoring, feasibility, and explanation boundaries instead of mixing them into one opaque planner step.

## Epic Boundary

Epic `#531` exists to define the delivery order and dependency rules for ranking, movement feasibility, and route assembly.

It is complete when:

- the child issues are shipped in dependency order
- scoring, feasibility evaluation, and route assembly remain separate concerns
- leisure and business ranking stay distinct while reusing shared lower-level infrastructure
- the resulting search layer is explainable enough for later UI, chat, and policy-review work

## Dependency Chain

This epic should follow the ingestion and candidate-generation epic from `#525`, because ranking and route assembly should consume explicit candidate sets, normalized option bundles, and itinerary objectives instead of raw provider records.

Within the epic itself, the expected order is:

1. `#532` scoring, result, and explanation contracts
2. `#533` map-aware feasibility and move-cost evaluation
3. `#534` leisure candidate ranking
4. `#535` business candidate ranking
5. `#536` route-search and multi-scenario assembly scaffolding

Issue `#533` should build directly on the contract surfaces from `#532`, while `#534` and `#535` can proceed in parallel once the shared explanation and feasibility vocabulary is stable. Issue `#536` should not invent its own ranking or movement semantics; it should assemble scenarios from the scored and feasibility-checked outputs produced by the earlier issues.

## Shared Design Rules

Every child issue in this epic should preserve these rules:

- ranking consumes itinerary objectives, normalized bundles, and candidate sets; it does not normalize raw source payloads
- hard feasibility and move-cost logic stay explicit and inspectable instead of being buried inside one blended score
- leisure and business ranking remain separate engines with distinct objective shaping and explanation output
- route assembly composes ranked and feasibility-checked alternatives into scenario proposals without replacing explainable scoring with opaque end-to-end decisions
- explanation artifacts should preserve why options were promoted, filtered, penalized, or assembled into a route

## Child Issue Map

| Issue | Role | Must Consume | Must Produce |
|---:|---|---|---|
| `#532` | Scoring and explanation boundary | itinerary objectives from `#512` and `#518`, option-set contracts from `#514`, inventory bundles from `#524`, candidate sets from `#530` | canonical ranking inputs, score breakdowns, explanation records, and result contracts |
| `#533` | Feasibility and move-cost evaluation | destination and option feasibility surfaces from `#520` to `#524`, candidate sets from `#530`, scoring vocabulary from `#532` | reusable movement-feasibility, transfer, and move-cost evaluation outputs |
| `#534` | Leisure ranking engine | leisure objectives from `#512`, scoring contracts from `#532`, move-cost outputs from `#533`, candidate sets from `#530` | explainable leisure ranking results and promotion/penalty reasons |
| `#535` | Business ranking engine | business objectives from `#518`, policy-facing boundaries from `#516`, scoring contracts from `#532`, move-cost outputs from `#533`, candidate sets from `#530` | explainable business ranking results and policy-aware tradeoff reasons |
| `#536` | Route-search and multi-scenario assembly | ranked leisure/business outputs from `#534` and `#535`, feasibility outputs from `#533`, bundle contracts from `#524` | route-level proposals, scenario assembly scaffolding, and route explanation surfaces |

## Contract Surface

The first pass of this epic should stabilize the following surfaces before later proposal packaging and UI work expands:

- `trip_planner/contracts/` for score-breakdown, explanation, and route-result contracts shared across planning modes
- `trip_planner/itinerary/` for route assembly and scenario-search scaffolding that sits above option bundles and candidate sets
- `trip_planner/business/` for business-mode ranking inputs that remain distinct from leisure ranking behavior
- `tests/fixtures/` and adjacent contract tests for ranked-result, feasibility, move-cost, and route-assembly regression coverage

This keeps downstream work additive instead of forcing later PRs to retrofit clear ranking and route boundaries into already coupled planner behavior.

## Acceptance Mapping

The epic acceptance criteria from `#531` map to child issue outcomes as follows:

| Epic requirement | Owning issues |
|---|---|
| All child issues needed for ranking, route feasibility, and explainable search are complete | `#532` to `#536` |
| Feasibility, scoring, ranking, and route assembly remain separate concerns in the backlog | `#532`, `#533`, `#534`, `#535`, `#536` |
| Leisure and business ranking stay distinct while sharing reusable lower-level infrastructure | `#532`, `#533`, `#534`, `#535` |
| The resulting layer is explainable enough for later UI, chat, and policy-review work | `#532`, `#533`, `#534`, `#535`, `#536` |

## Design References

Use these documents together when implementing the child issues:

- [Product and architecture brief](product-architecture-brief.md)
- [Core domain contracts](domain-contracts.md)
- [Implementation plan](implementation-plan.md)
- [Shared planning contracts](shared-planning-contracts.md)
- [Leisure itinerary-objective derivation boundary](itinerary-objective-derivation-boundary.md)
- [Business objective derivation boundary](business-objective-derivation-boundary.md)
- [Normalized inventory contracts epic](normalized-inventory-contracts-epic.md)
- [Source ingestion epic](source-ingestion-epic.md)

## Working Rule

If a child issue needs to collapse scoring, feasibility, ranking, route assembly, and proposal packaging into one contract or one engine, the epic is being violated and the design should be corrected before the PR lands.
