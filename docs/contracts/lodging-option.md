# LodgingOption Contract

`LodgingOption` is the normalized lodging boundary for later option-bundle and ranking work.

It separates the major decision surfaces that frequently get conflated:

- `cost_summary` captures nightly, total, taxes-and-fees, and deposit ranges.
- `quality_summary` captures the inherent lodging product signal such as sleep quality, property condition, and service.
- `value_summary` captures whether the product is a good trade for the money or policy budget.
- `fit_summary` captures whether the lodging matches the trip context, especially quiet and recovery needs.
- `feasibility` captures business approval state, inventory posture, and operational constraints.

This distinction is intentional. A lodging option can be high quality but poor fit, or strong fit and value without matching a luxury-quality floor.

## Usage Boundary

Use `LodgingOption` when later issues need a stable lodging object for:

- mixed inventory bundle assembly in `#524`
- source-ingestion normalization in `#528`
- lodging ranking and explanation work in `#534` and `#535`
- proposal packaging when a selected stay needs policy-ready provenance

Do not overload this contract with final ranking logic or source-specific API fields. Source-specific details should stay in provenance records or future adapter-layer contracts, while ranking decisions should consume this normalized boundary instead of mutating it.
