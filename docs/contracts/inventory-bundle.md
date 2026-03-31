# InventoryBundle And MixedOption Contracts

`InventoryBundle` and `MixedOption` sit downstream from the normalized destination and option contracts and upstream from later ranking or UI comparison work.

## Boundary

- `InventoryBundle` is the local assembly unit. It groups normalized `Destination`, `LodgingOption`, `TransportOption`, and `ActivityOption` objects that belong together as one coherent slice of an alternative.
- `MixedOption` is the comparison-ready alternative. It can contain one bundle for a simple lodging-only or transport-plus-lodging comparison, or multiple bundles for a route-level alternative with distinct gateway and activity-rich phases.
- `OptionSet` remains the planner’s presentation container. `MixedOption.to_option()` exists so this assembly layer can feed the shared `OptionSet` contract rather than competing with it.

## What The Layer Adds

- bundle-level feasibility with explicit blocking reasons for infeasible but still inspectable alternatives
- route coherence and schedule-fit summaries that stay separate from raw transport or lodging detail
- budget posture summaries that roll up category totals without flattening the underlying normalized objects
- explanation metadata that keeps strengths and tradeoffs attached to the assembled alternative

## What It Does Not Add

- final ranking or scoring policy
- live inventory fetching or combinatorial search
- UI-specific rendering state

Those remain later concerns. This layer exists to make cross-category alternatives stable, inspectable, and reusable across profile-learning and inventory-narrowing flows.
