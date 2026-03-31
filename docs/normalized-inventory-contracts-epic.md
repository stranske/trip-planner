# Normalized Inventory Contracts And Option Modeling Epic Plan

This document records the implementation contract for epic `#519`.

The goal is to sequence the normalized inventory and option-modeling layer so later ingestion, candidate generation, ranking, and route assembly can build on stable planning objects instead of redefining option boundaries per source or workflow.

## Epic Boundary

Epic `#519` exists to define the delivery order and dependency rules for normalized destinations, place context, and option objects.

It is complete when:

- the child issues are shipped in dependency order
- destination, lodging, transport, and activity contracts remain distinct but interoperable
- provenance, quality, value, fit, and feasibility stay explicit on normalized option objects
- later ingestion and ranking work can consume option bundles without redefining the underlying inventory model

## Dependency Chain

This epic should follow the shared-planning and business-foundation epic from `#513`, because normalized inventory objects need the shared trip, option-set, itinerary-objective, business-profile, and provenance boundaries to already exist.

Within the epic itself, the expected order is:

1. `#520` normalized destination and place-context contracts
2. `#521` canonical `LodgingOption` contract
3. `#522` canonical `TransportOption` contract
4. `#523` canonical `ActivityOption` contract
5. `#524` inventory-bundle and mixed option-assembly contracts

Issue `#524` should not invent its own place or option schema. It should assemble the normalized contracts from `#520` to `#523` into reusable bundles and selection surfaces for later ingestion and ranking layers.

## Shared Design Rules

Every child issue in this epic should preserve these rules:

- destinations and place context stay separate from concrete option records so later source ingestion can normalize many supply channels into the same planning geography
- lodging, transport, and activity options stay distinct instead of collapsing into one generic inventory record
- provenance, quality, value, fit, and feasibility remain inspectable summaries rather than being flattened into one score
- normalized option contracts describe planning objects, not source-specific API payloads or booking-execution workflows
- option bundles assemble explicit normalized objects for later ranking and proposal packaging without swallowing source or policy logic

## Child Issue Map

| Issue | Role | Must Consume | Must Produce |
|---:|---|---|---|
| `#520` | Place and destination foundation | shared planning contracts, current domain model docs, source-quality design notes | canonical destination, place-context, and location-boundary contracts |
| `#521` | Lodging option boundary | place-context contracts from `#520`, source/provenance rules, existing lodging contract notes | canonical `LodgingOption`, stay cost/quality/value/fit summaries, lodging feasibility surface |
| `#522` | Transport option boundary | place-context contracts from `#520`, trip and itinerary-objective vocabulary, source/provenance rules | canonical `TransportOption`, segment timing/cost/feasibility summaries, movement-specific constraints |
| `#523` | Activity option boundary | place-context contracts from `#520`, trip and itinerary-objective vocabulary, source/provenance rules | canonical `ActivityOption`, activity suitability/value/fit summaries, scheduling and participation constraints |
| `#524` | Option bundle assembly | destination and option contracts from `#520` to `#523`, shared `OptionSet` boundary from `#514` | inventory bundles, mixed option assemblies, and bundle-level provenance/feasibility composition rules |

## Contract Surface

The first pass of this epic should stabilize the following surfaces before later ingestion and ranking work expands:

- `trip_planner/contracts/` for destination, place-context, and option-shape contracts shared across planning modes
- `trip_planner/sources/` for source provenance and option-normalization metadata that should stay attached to inventory objects
- `tests/contracts/` and adjacent fixtures for destination, lodging, transport, activity, and bundle contract regressions
- docs and fixtures that show how mixed option bundles compose distinct normalized option types into reusable planning candidates

This keeps downstream work additive instead of forcing later ingestion or ranking PRs to backfill stable option boundaries after the fact.

## Acceptance Mapping

The epic acceptance criteria from `#519` map to child issue outcomes as follows:

| Epic requirement | Owning issues |
|---|---|
| All child issues needed for normalized inventory contracts and early option modeling are complete | `#520` to `#524` |
| Destination, lodging, transport, and activity contracts remain distinct but compatible | `#520`, `#521`, `#522`, `#523`, `#524` |
| The resulting option model is explicit about provenance, feasibility, quality/value/fit summaries, and option-bundle assembly | `#521`, `#522`, `#523`, `#524` |
| Later ingestion and ranking issues can build on this layer without redefining the underlying option objects | `#520`, `#521`, `#522`, `#523`, `#524` |

## Design References

Use these documents together when implementing the child issues:

- [Product and architecture brief](product-architecture-brief.md)
- [Core domain contracts](domain-contracts.md)
- [Shared planning contracts](shared-planning-contracts.md)
- [Shared planning and business foundation epic](shared-business-foundation-epic.md)
- [Source and quality model](source-quality-model.md)
- [Lodging option contract](contracts/lodging-option.md)
- [Source and provenance contracts](contracts/source-provenance.md)

## Working Rule

If a child issue needs to flatten destinations, place context, lodging, transport, activities, and mixed option bundles into one generic schema, the epic is being violated and the design should be corrected before the PR lands.
