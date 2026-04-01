# Source And Provenance Contracts

The source layer exists so later planners and option models do not collapse every signal into one opaque score.

## Core Contracts

- `SourceRecord`: a normalized description of a source channel or provider
- `SourceTrustSignals`: reusable trust metadata for freshness, commerciality, editorial independence, operational reliability, and review consistency
- `QualityValueFitSummary`: reusable summary that keeps quality, value, and traveler fit distinct
- `ProvenanceReference`: a reusable attribution object that can attach a source contribution to a destination, option, option set, proposal, or policy evaluation

## Source Categories

The canonical categories are:

- `commercial_inventory`
- `ratings_reviews`
- `editorial`
- `specialist_non_commercial`
- `official_operational`
- `managed_travel_policy`

These categories are broad enough for both leisure and business planning while still distinguishing the main trust and usage differences between booking, review, editorial, operational, and policy sources.

## Quality, Value, And Fit

These should not be collapsed into one signal:

- `quality`: the intrinsic or observed standard of the thing being evaluated
- `value`: what the traveler gets relative to cost, effort, or restrictions
- `fit`: how well the option matches the traveler profile, trip context, or business policy

Example:

- a hotel can have strong `quality`
- weak `value` for a budget-sensitive traveler
- and strong `fit` for a business traveler who needs walkable access and reliable Wi-Fi

## Provenance Flow

Later contracts should treat source provenance as a first-class dependency:

1. `SourceRecord` defines the normalized source and its trust signals.
2. Candidate-generation or normalization code creates `ProvenanceReference` records for specific destination, option, or policy contributions.
3. Option and destination contracts store provenance reference ids in `source_refs`.
4. Proposal and evaluation layers use those references to justify selected channels, comparables, and exception narratives.

This keeps explanations auditable without forcing every downstream object to duplicate source metadata inline.

## Relationship To Source Strategy

Use [Source channel strategy](../source-channel-strategy.md) for the initial operating shortlist and market rationale.

Use these contracts for the code-level representation of those sources once the planner begins ingesting or normalizing them.

Issue `#526` extends this layer with raw source adapter and snapshot boundaries. See
[Source Adapter And Raw Snapshot Contracts](source-adapters.md) for the canonical
fetch, degradation, and normalization-handoff contracts that sit in front of
`ProvenanceReference`.
