# Orchestration, Interactive Planning, And In-Trip Adjustment Epic Plan

This document records the implementation contract for epic `#543`.

The goal is to sequence the shared orchestration layer so planner turns, leisure workflows, structured feedback handling, in-trip replanning, and business-policy-prep flows build on one explicit state machine instead of splintering into mode-specific chat logic.

## Epic Boundary

Epic `#543` exists to define the delivery order and dependency rules for the orchestration, interactive planning, and in-trip-adjustment layer.

It is complete when:

- the child issues are shipped in dependency order
- planner actions, workflow state, and user-visible outputs remain explicit instead of being hidden in one opaque loop
- leisure planning, feedback learning, in-trip adjustment, and business-policy-prep stay distinct but interoperable concerns
- later UI and LLM integration can consume stable workflow contracts without redesigning the orchestration model

## Dependency Chain

This epic should follow the persistence and ranking layers from epics `#537` and `#531`, because the orchestration layer depends on stable saved-state, scenario, and ranking outputs before it can manage interactive planning flow.

Within the epic itself, the expected order is:

1. `#544` planner-turn, action, and workflow-state contracts
2. `#545` leisure planning workflow scaffold
3. `#546` option-presentation and revealed-preference feedback loops
4. `#547` in-trip monitoring, trigger, and replanning scaffolding
5. `#548` business-planning and policy-prep workflow scaffold

Issue `#546` can mature alongside `#545` once the contract surface from `#544` is stable, but `#547` and `#548` should reuse the canonical planner-turn vocabulary rather than introducing separate transition containers or ad hoc state payloads.

## Shared Design Rules

Every child issue in this epic should preserve these rules:

- `PlannerTurn` is the canonical orchestration checkpoint across leisure, business, and in-trip flows.
- Workflow state, planner actions, pending decisions, and planner outputs remain separate inspectable surfaces.
- Revealed-preference updates happen through explicit feedback events and state transitions, not implicit mutation of saved trip or scenario records.
- In-trip monitoring and replanning stay downstream from persisted state, ranking, and scenario history instead of bypassing those layers.
- Business-policy-prep remains distinct from external approval or policy-enforcement systems.

## Child Issue Map

| Issue | Role | Must Consume | Must Produce |
|---:|---|---|---|
| `#544` | Canonical orchestration contracts | persisted trip/session/scenario layers, ranking outputs, planning-autonomy guidance | `PlannerTurn` vocabulary, workflow-state models, action/output kinds, transition metadata |
| `#545` | Leisure workflow scaffold | contracts from `#544`, ranked scenarios, persisted state, autonomy/revision guidance | explainable leisure workflow turns, checkpoints, and next-step summaries |
| `#546` | Feedback-loop routing | contracts from `#544`, leisure workflow turns from `#545`, option feedback and autonomy signals | structured feedback events, session-state deltas, fallback-save requests, rerank/revision pathways |
| `#547` | In-trip monitoring and replanning | contracts from `#544`, saved scenarios/history, session state, ranking outputs | trigger events, replanning requests, revision outputs, in-trip adjustment turns |
| `#548` | Business workflow scaffold | contracts from `#544`, persisted trip state, business objectives, policy-ready proposal inputs | staged business planner turns, policy-input checkpoints, proposal-prep outputs, fallback/exception pathways |

## Contract Surface

The first pass of this epic should stabilize the following surfaces before frontend chat, map UI, or LLM-driven orchestration expands:

- `trip_planner/orchestration/` for canonical workflow contracts and mode-specific orchestration scaffolds
- `docs/contracts/orchestration-workflow.md` for the shared orchestration vocabulary and representative fixtures
- `tests/orchestration/` plus `tests/fixtures/orchestration/` for mode-specific regression coverage and workflow examples
- `docs/business-orchestration-boundary.md` and later planner-integration docs for downstream consumer guidance

This keeps later UI and agent layers additive instead of forcing them to reverse-engineer planner state from scattered output payloads.

## Acceptance Mapping

The epic acceptance criteria from `#543` map to child issue outcomes as follows:

| Epic requirement | Owning issues |
|---|---|
| All child issues needed for orchestration, interactive planning flow, and in-trip adjustment are complete | `#544` to `#548` |
| Orchestration, feedback learning, in-trip adjustment, and business-policy-prep remain distinct concerns in the backlog | `#544`, `#545`, `#546`, `#547`, `#548` |
| Planner actions and state transitions are explicit rather than hidden in chat logic | `#544`, `#545`, `#546`, `#547`, `#548` |
| The resulting layer is strong enough to support later UI and LLM integration without redefining planner workflow contracts | `#544`, `#545`, `#546`, `#547`, `#548` |

## Design References

Use these documents together when implementing the child issues:

- [Orchestration workflow contracts](contracts/orchestration-workflow.md)
- [Business orchestration boundary](business-orchestration-boundary.md)
- [Planner UI integration](planner-ui-integration.md)
- [Planning autonomy contracts](contracts/planning-autonomy.md)
- [State session persistence](state-session-persistence.md)
- [State scenario history](state-scenario-history.md)
- [Product architecture brief](product-architecture-brief.md)

## Working Rule

If a child issue needs to collapse planner state, user feedback, in-trip triggers, and business-policy-prep into one generic loop or one untyped payload, the epic is being violated and the design should be corrected before the PR lands.
