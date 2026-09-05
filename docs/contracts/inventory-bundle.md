# InventoryBundle And MixedOption Contracts

`InventoryBundle` and `MixedOption` sit downstream from the normalized destination and option contracts and upstream from later ranking or UI comparison work.

## Boundary

- `InventoryBundle` is the local assembly unit. It groups normalized `Destination`, `LodgingOption`, `TransportOption`, and `ActivityOption` objects that belong together as one coherent slice of an alternative.
- `MixedOption` is the comparison-ready alternative. It can contain one bundle for a simple lodging-only or transport-plus-lodging comparison, or multiple bundles for a route-level alternative with distinct gateway and activity-rich phases.
- `OptionSet` remains the planner’s presentation container. `MixedOption.to_option()` exists so this assembly layer can feed the shared `OptionSet` contract rather than competing with it.

## What The Layer Adds

- bundle-level feasibility with explicit blocking reasons for infeasible but still inspectable alternatives
- `constraint_evaluation` envelope that records hard/policy constraint posture separately from raw feasibility signals
- composition summaries that declare bundle order, primary destination, and the exact normalized option IDs assembled into each bundle or mixed alternative
- provenance summaries that roll source references and booking links up from the included normalized objects without hiding the underlying records
- quality/value/fit rollups that make mixed alternatives rankable without flattening away category-specific summaries
- route coherence and schedule-fit summaries that stay separate from raw transport or lodging detail
- budget posture summaries that roll up category totals without flattening the underlying normalized objects
- explanation metadata that keeps strengths and tradeoffs attached to the assembled alternative

## What It Does Not Add

- final ranking or scoring policy
- live inventory fetching or combinatorial search
- UI-specific rendering state

Those remain later concerns. This layer exists to make cross-category alternatives stable, inspectable, and reusable across profile-learning and inventory-narrowing flows.

## ConstraintEvaluation Envelope

Each `InventoryBundle` carries a `constraint_evaluation` block alongside `feasibility`:

- `status`: `evaluated`, `partial`, or `unavailable`
- `overall_pass`: whether the bundle is constraint-clean for downstream ranking
- `hard_constraints_satisfied`: whether structural bundle constraints passed
- `policy_constraints_satisfied`: optional business-policy posture when known
- `blocking_constraint_ids`: blocker identifiers or inherited human-readable feasibility reasons when `overall_pass` is false
- `evaluated_constraint_ids`: which constraint checks were applied
- `summary` and `notes`: human-readable evaluation context

`trip_planner/app/services/inventory.py` must emit this block on every inventory bundle payload returned to API consumers. Feasibility remains the source signal; `constraint_evaluation` is the inspectable envelope required by B2-048.

Missing or null evaluations are derived from bundle feasibility, including when constructing a bundle directly. A provided evaluation must be a non-empty mapping. Boolean fields accept actual booleans only; `policy_constraints_satisfied` also accepts null. Explicit evaluations are preserved.
