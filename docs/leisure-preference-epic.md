# Leisure Preference Epic Plan

This document records the implementation contract for epic `#506`.

The goal is to sequence the leisure preference foundation so that contracts, evidence, fixtures, resolution, autonomy controls, and itinerary-objective derivation land in a stable order.

## Epic Boundary

Epic `#506` exists to define the delivery order and dependency rules for the first implementation pass of the leisure preference engine.

It is complete when:

- the child issues are shipped in dependency order
- leisure preference evaluation remains explicitly upstream of itinerary ranking, candidate search, and live inventory work
- the resulting modules expose reusable contracts and engine boundaries instead of extending the old script-era request shape
- leisure and business preference logic remain separate at the contract level

## Dependency Chain

The leisure preference epic should establish the foundation in this order:

1. `#507` canonical leisure preference contracts and package layout
2. `#508` evidence model for direct statements, tradeoff choices, and scenario reactions
3. `#509` traveler archetype fixtures and evaluation corpus
4. `#510` preference resolution engine and contradiction handling
5. `#511` planning-autonomy controls and revealed-preference updates
6. `#512` itinerary-objective derivation from resolved leisure profiles

Issue `#509` can mature alongside `#508` once the contract shape from `#507` is stable, but `#510` should not invent resolver behavior against ad hoc or fixture-only fields. The resolver should consume the canonical contracts and evidence surfaces first.

## Shared Design Rules

Every child issue in this epic should preserve these rules:

- `LeisurePreferenceProfile` is the canonical leisure planning contract.
- Evidence capture, resolution, autonomy, and objective derivation remain separate concerns with inspectable handoffs.
- Legacy `request.json` fields stay a compatibility bridge, not the design center.
- Contradictions, conditional preferences, and confidence levels must remain explicit rather than being flattened into one score.
- Business-travel preference logic should reuse only truly shared infrastructure, not leisure-specific assumptions.

## Child Issue Map

| Issue | Role | Must Consume | Must Produce |
|---:|---|---|---|
| `#507` | Canonical leisure contract and package layout | existing design docs, legacy request surface | dataclass contracts, schema constants, package boundaries |
| `#508` | Evidence model | contracts from `#507`, tradeoff taxonomy, anchor rules | evidence records, evidence catalog, confidence pathways |
| `#509` | Traveler fixtures and evaluation corpus | contracts from `#507`, evidence surfaces from `#508` | archetype fixtures, tension cases, reusable regression corpus |
| `#510` | Preference resolution engine | canonical contracts from `#507`, evidence from `#508`, fixtures from `#509` | resolved profiles, contradiction handling, explanation-ready outputs |
| `#511` | Autonomy controls and revealed-preference updates | resolver outputs from `#510`, canonical contracts from `#507` | planning-autonomy controls, update rules, guarded preference revisions |
| `#512` | Itinerary-objective derivation | resolved leisure profiles from `#510`, autonomy/revision guidance from `#511`, shared itinerary-objective contracts | explainable leisure itinerary objectives for downstream ranking |

## Contract Surface

The first pass of this epic should stabilize the following surfaces before ranking and UI work expands:

- `trip_planner/preferences/` for leisure contracts, evidence, resolver logic, and autonomy controls
- `trip_planner/itinerary/` for leisure itinerary-objective derivation that consumes resolved profiles
- `tests/fixtures/preferences/` for representative traveler archetypes, contradictions, and revision scenarios
- `tests/preferences/` for regression coverage across contracts, resolution, and revealed-preference handling

This keeps downstream ranking, candidate generation, and orchestration work additive instead of forcing later PRs to retrofit structure into loosely defined preference fields.

## Acceptance Mapping

The epic acceptance criteria from `#506` map to child issue outcomes as follows:

| Epic requirement | Owning issues |
|---|---|
| All child issues needed for the leisure preference engine foundation are complete | `#507` to `#512` |
| Preference evaluation remains upstream of itinerary ranking and inventory optimization | `#507`, `#508`, `#510`, `#512` |
| The foundation is strong enough to support later ranking, option generation, and interaction design without redoing the core leisure model | `#507`, `#508`, `#509`, `#510`, `#511`, `#512` |
| Leisure and business preference logic remain separated at the contract level | `#507`, `#510`, `#512` |

## Design References

Use these documents together when implementing the child issues:

- [Leisure preference engine](leisure-preference-engine.md)
- [Leisure preference contract](leisure-preference-contract.md)
- [Leisure preference schema draft](leisure-preference-schema.md)
- [Preference learning model](preference-learning-model.md)
- [Preference roadmap](preference-roadmap.md)
- [Shared planning contracts](shared-planning-contracts.md)
- [Business travel profile contract](business-travel-profile-contract.md)

## Working Rule

If a child issue needs to shortcut directly from raw questionnaire inputs to ranking weights without explicit contracts, evidence handling, and resolver outputs, the epic is being violated and the design should be corrected before the PR lands.
