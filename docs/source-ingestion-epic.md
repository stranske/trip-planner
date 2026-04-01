# Source Ingestion Epic Plan

This document records the implementation contract for epic `#525`.

The goal is to sequence source adapters, ingestion scaffolding, entity resolution, and candidate generation without collapsing those concerns into one pipeline step.

## Epic Boundary

Epic `#525` exists to define the delivery order and dependency rules for the first ingestion layer.

It is complete when:

- the child issues are shipped in dependency order
- provenance and source-confidence data remain explicit across the layer
- raw snapshots, normalization, deduplication, and candidate generation stay distinct
- later ranking and route assembly can build on these contracts without redesigning them

## Dependency Chain

The ingestion epic depends on the normalized planning object layer completed in issues `#520` through `#524`.

Within the epic itself, the expected order is:

1. `#526` source adapter interfaces and raw snapshot contracts
2. `#527` entity resolution and deduplication contracts
3. `#528` lodging and transport ingestion scaffolding
4. `#529` destination and activity ingestion scaffolding, including significance- and uncertainty-preserving normalization for place and activity records
5. `#530` candidate generation and filtering contracts

Issues `#528` and `#529` can proceed in parallel once `#526` and `#527` have landed, but `#530` should not start from ad hoc provider payloads. It should consume normalized outputs produced by the ingestion layer.

## Shared Design Rules

Every child issue in this epic should preserve these rules:

- Adapters fetch or read source payloads. They do not decide ranking.
- Raw snapshots preserve provider identity, query context, freshness, and failure details.
- Resolution and deduplication produce inspectable merge decisions with provenance.
- Ingestion pipelines emit normalized planning objects plus warnings, conflicts, and provenance metadata.
- Candidate generation filters and assembles early bundle seeds, but it does not perform final scoring or route search.

## Child Issue Map

| Issue | Role | Must Consume | Must Produce |
|---:|---|---|---|
| `#526` | Source adapter and snapshot boundary | source taxonomy, provenance rules, source-quality model | adapter interfaces, raw snapshots, normalization handoff records |
| `#527` | Entity resolution and deduplication | raw snapshots from `#526`, provenance structures from `#517` | match records, merge decisions, ambiguous-case handling |
| `#528` | Lodging and transport ingestion | snapshots from `#526`, dedup contracts from `#527`, normalized options from `#521` and `#522` | canonical `LodgingOption` and `TransportOption` outputs with provenance |
| `#529` | Destination and activity ingestion | snapshots from `#526`, dedup contracts from `#527`, normalized objects from `#520` and `#523` | canonical `Destination` and `ActivityOption` outputs with provenance |
| `#530` | Candidate generation and filtering | normalized outputs from `#528` and `#529`, bundle contracts from `#524` | early candidate sets, filter explanations, bundle seeds |

## Contract Surface

The first pass of this epic should stabilize the following surfaces before any provider-rich expansion:

- `trip_planner/sources/` for adapter, snapshot, and resolution contracts
- `trip_planner/ingestion/` for category-specific normalization pipelines
- `trip_planner/candidates/` for deterministic candidate-generation contracts
- `tests/fixtures/` for representative source, resolution, ingestion, and candidate scenarios

For the first ingestion pass, see [contracts/source-ingestion.md](contracts/source-ingestion.md).
For the deterministic post-ingestion assembly boundary, see [contracts/candidate-generation.md](contracts/candidate-generation.md).

This keeps extension work additive instead of forcing later PRs to retrofit structure into already coupled code.

## Acceptance Mapping

The epic acceptance criteria from `#525` map to child issue outcomes as follows:

| Epic requirement | Owning issues |
|---|---|
| All child issues needed for adapters, ingestion, deduplication, and candidate generation are complete | `#526` to `#530` |
| Source adapters, normalization, deduplication, and candidate generation remain separate concerns | `#526`, `#527`, `#528`, `#529`, `#530` |
| Provenance and source-confidence handling are explicit throughout the layer | `#526`, `#527`, `#528`, `#529`, `#530` |
| Later ranking, search, and policy-aware option assembly can build on the layer without redesigning ingestion contracts | `#527`, `#528`, `#529`, `#530` |

## Design References

Use these documents together when implementing the child issues:

- [Product and architecture brief](product-architecture-brief.md)
- [Core domain contracts](domain-contracts.md)
- [Source and quality model](source-quality-model.md)
- [Source channel strategy](source-channel-strategy.md)
- [Source and provenance contracts](contracts/source-provenance.md)
- [Inventory bundle contract](contracts/inventory-bundle.md)

## Working Rule

If a child issue needs to invent a shortcut that bypasses snapshots, provenance, or normalized object contracts, the epic is being violated and the design should be corrected before the PR lands.
