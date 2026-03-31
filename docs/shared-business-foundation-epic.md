# Shared Planning And Business Foundation Epic Plan

This document records the implementation contract for epic `#513`.

The goal is to sequence the shared planning contracts and business-trip foundation so later inventory, policy, ranking, and orchestration work can build on stable boundaries instead of reworking the model again.

## Epic Boundary

Epic `#513` exists to define the delivery order and dependency rules for the shared planning and business-foundation layer.

It is complete when:

- the child issues are shipped in dependency order
- shared trip and option contracts remain separate from business-specific policy logic
- the business-planning layer reuses shared planning infrastructure without leaking leisure-specific assumptions
- later inventory, policy, and ranking work can build on these contracts without redesigning the core model

## Dependency Chain

This epic should follow the leisure preference foundation from epic `#506`, because later business-planning work needs the same shared trip, option, and itinerary-objective vocabulary to stay consistent across modes.

Within the epic itself, the expected order is:

1. `#514` shared trip, option-set, and itinerary-objective contracts
2. `#515` canonical `BusinessTravelProfile` contract
3. `#516` policy-facing proposal and evaluation contracts
4. `#517` source, provenance, and quality/value/fit contracts
5. `#518` policy-aware business planning objectives

Issue `#517` can mature alongside `#516` once the shared contract surfaces from `#514` and `#515` are stable, but `#518` should not infer business objectives from ad hoc request fields or provider payloads. It should consume the canonical contracts introduced by the earlier issues.

## Shared Design Rules

Every child issue in this epic should preserve these rules:

- `Trip`, `OptionSet`, and `ItineraryObjectives` remain the shared planning vocabulary across leisure and business modes.
- `BusinessTravelProfile` is the canonical business-specific profile contract, not a grab bag of policy-export fields.
- This repo plans and packages policy-ready proposals; it does not absorb policy enforcement logic from `Travel-Plan-Permission`.
- Source provenance, quality, value, and fit signals remain explicit and inspectable rather than being flattened into one score.
- Business objective derivation consumes shared contracts and business profile inputs before later ranking or workflow code adds execution behavior.

## Child Issue Map

| Issue | Role | Must Consume | Must Produce |
|---:|---|---|---|
| `#514` | Shared planning contracts | design docs, leisure-foundation lessons, current contract package boundaries | canonical `Trip`, `OptionSet`, and `ItineraryObjectives` contracts plus package layout |
| `#515` | Business traveler profile | shared contracts from `#514`, business travel design docs | canonical `BusinessTravelProfile`, traveler constraints, and planning-context fields |
| `#516` | Policy-facing proposal and evaluation boundary | shared contracts from `#514`, business profile from `#515`, repo boundary with `Travel-Plan-Permission` | proposal/export contracts, evaluation-result contracts, policy-facing handoff rules |
| `#517` | Source, provenance, and quality/value/fit contracts | shared contracts from `#514`, business profile from `#515`, source-quality design docs | provenance records, quality/value/fit signals, reusable source metadata contracts |
| `#518` | Business objective derivation | shared contracts from `#514`, business profile from `#515`, policy-facing contracts from `#516`, provenance/value inputs from `#517` | explainable policy-aware business itinerary objectives for later ranking and orchestration |

## Contract Surface

The first pass of this epic should stabilize the following surfaces before later policy integration, ranking, and UI work expands:

- `trip_planner/contracts/` for shared trip, option, destination, and itinerary-objective contracts
- `trip_planner/business/` for canonical business-profile and business-objective derivation contracts
- `trip_planner/sources/` for provenance and quality/value/fit metadata shared by later ingestion work
- `tests/contracts/` and adjacent fixtures for shared-contract, business-profile, and policy-handoff regression coverage

This keeps downstream work additive instead of forcing later PRs to retrofit stable structure into loosely defined planning state.

## Acceptance Mapping

The epic acceptance criteria from `#513` map to child issue outcomes as follows:

| Epic requirement | Owning issues |
|---|---|
| All child issues needed for the shared-contract and business-foundation layer are complete | `#514` to `#518` |
| Shared planning contracts remain distinct from business-specific policy logic | `#514`, `#515`, `#516`, `#518` |
| The business side remains separate from the leisure preference engine while reusing shared infrastructure appropriately | `#514`, `#515`, `#518` |
| The resulting contracts are strong enough to support later inventory, policy, and ranking work without redesigning the data model again | `#514`, `#515`, `#516`, `#517`, `#518` |

## Design References

Use these documents together when implementing the child issues:

- [Product and architecture brief](product-architecture-brief.md)
- [Core domain contracts](domain-contracts.md)
- [Shared planning contracts](shared-planning-contracts.md)
- [Business travel profile contract](business-travel-profile-contract.md)
- [Business travel profile](business-travel-profile.md)
- [Source and quality model](source-quality-model.md)
- [Business objective derivation boundary](business-objective-derivation-boundary.md)
- [Policy-facing proposal contracts](contracts/trip-plan-proposal.md)
- [Source and provenance contracts](contracts/source-provenance.md)

## Working Rule

If a child issue needs to collapse shared planning state, business traveler context, policy-facing exports, and objective derivation into one schema or one workflow step, the epic is being violated and the design should be corrected before the PR lands.
