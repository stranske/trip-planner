# Policy Integration Execution And Approval-Ready Workflows Epic Plan

This document records the implementation contract for epic `#549`.

The goal is to sequence the execution layer that connects `trip-planner` to `Travel-Plan-Permission` so policy sync, proposal submission, evaluation-result ingestion, reoptimization, and approval-readiness packaging stay explicit instead of collapsing into one opaque integration step.

## Epic Boundary

Epic `#549` exists to define the delivery order and dependency rules for policy integration execution and approval-ready workflows.

It is complete when:

- the child issues are shipped in dependency order
- policy import, proposal submission, evaluation handling, and approval packaging remain separate inspectable concerns
- `trip-planner` stays responsible for planning, packaging, and reacting while `Travel-Plan-Permission` stays authoritative for policy evaluation and approval posture
- later business UI and operational flows can consume stable execution contracts without redefining the cross-repo boundary

## Dependency Chain

This epic should follow the business contract, ranking, orchestration, and policy-prep layers from issues `#516`, `#518`, `#535`, and `#548`, because the execution layer depends on stable proposal packets, policy-facing contracts, and planner workflow state before it can call the external approval system safely.

Within the epic itself, the expected order is:

1. `#550` integration-client and execution contracts
2. `#551` policy-constraint import and organization-context sync scaffolding
3. `#552` proposal submission and evaluation-result ingestion scaffolding
4. `#553` reoptimization and exception-handling workflows
5. `#554` approval-readiness packaging and integration harnesses

Issue `#551` can mature alongside `#550` once the client and execution-envelope surface is stable, but `#552`, `#553`, and `#554` should reuse the same execution contracts instead of inventing separate transport or retry semantics.

## Shared Design Rules

Every child issue in this epic should preserve these rules:

- Keep transport and execution status in `trip_planner/integrations/tpp/` rather than leaking them into business-domain contracts.
- Keep `PolicyConstraintSet`, `TripPlanProposal`, and `PolicyEvaluationResult` as the canonical planning and policy payloads instead of wrapping business meaning in ad hoc blobs.
- Treat imported policy state as planning input and freshness metadata, not as a local reimplementation of policy authority.
- Make retries, deferred evaluation state, exception guidance, and reoptimization triggers explicit so orchestration and UI layers can reason about them deterministically.
- Approval-readiness packaging must explain what is ready, what is blocked, and what still requires an external policy or approval decision.

## Child Issue Map

| Issue | Role | Must Consume | Must Produce |
|---:|---|---|---|
| `#550` | Execution client and transport boundary | business policy contracts, business orchestration outputs, external TPP request/response expectations | client abstraction, execution envelopes, correlation/retry metadata, transport error semantics |
| `#551` | Policy sync scaffold | execution contracts from `#550`, external policy snapshots, business planning inputs | normalized `PolicyConstraintSet`, organization context snapshot, freshness/invalidation metadata |
| `#552` | Proposal submission and result ingestion | execution contracts from `#550`, synced policy context from `#551`, `TripPlanProposal`, business orchestration outputs | submission services, evaluation-result ingestion, deferred-status handling, proposal/execution linkage |
| `#553` | Reoptimization and exception routing | execution failures or evaluation results from `#552`, planner workflow state from `#548`, ranking/objective layers | retry rules, reoptimization requests, exception-ready planner pathways, disposition records |
| `#554` | Approval-readiness packaging and harnesses | proposal/evaluation state from `#552`, reoptimization/exception outputs from `#553`, planner UI and orchestration consumers | approval-ready summaries, packaging helpers, integration fixtures, end-to-end harness coverage |

## Contract Surface

The first pass of this epic should stabilize the following surfaces before more business UI or live integration behavior expands:

- `trip_planner/integrations/tpp/` for execution clients, sync services, and external exchange semantics
- `docs/contracts/tpp-execution-contracts.md` for the shared execution-envelope vocabulary
- `docs/contracts/tpp-policy-sync.md` plus later proposal-submission and approval-packaging docs for downstream consumer guidance
- `tests/fixtures/tpp/`, `tests/business/`, and `tests/orchestration/` for deterministic execution, policy-sync, and approval-readiness examples

This keeps later approval-readiness and exception-handling flows additive instead of forcing them to infer execution state from loosely documented service calls.

## Acceptance Mapping

The epic acceptance criteria from `#549` map to child issue outcomes as follows:

| Epic requirement | Owning issues |
|---|---|
| All child issues needed for policy integration execution and approval-ready workflows are complete | `#550` to `#554` |
| Policy import, submission, result ingestion, and reoptimization remain separate concerns in the backlog | `#550`, `#551`, `#552`, `#553`, `#554` |
| Policy logic stays authoritative in the external repo while the local planner remains operationally useful | `#550`, `#551`, `#552`, `#553`, `#554` |
| The resulting integration layer is strong enough to support real business planning workflows without redefining the cross-repo contract | `#550`, `#551`, `#552`, `#553`, `#554` |

## Design References

Use these documents together when implementing the child issues:

- [TPP execution contracts](contracts/tpp-execution-contracts.md)
- [TPP policy sync scaffold](contracts/tpp-policy-sync.md)
- [Trip plan proposal contracts](contracts/trip-plan-proposal.md)
- [Business orchestration boundary](business-orchestration-boundary.md)
- [Planner UI integration](planner-ui-integration.md)
- [Business travel profile](business-travel-profile.md)
- [Product architecture brief](product-architecture-brief.md)

## Working Rule

If a child issue needs to hide policy sync freshness, execution state, evaluation results, and exception routing inside one generic integration helper or one opaque payload, the epic is being violated and the design should be corrected before the PR lands.
