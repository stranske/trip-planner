# Budget And Business Policy Execution Epic Plan

This document records the implementation contract for epic `#678`.

The goal is to sequence the budget and business-policy execution layer so budget editing, actual-spend capture, policy import, proposal submission, approval-readiness display, and post-policy reoptimization land as separate inspectable surfaces instead of one opaque business workflow.

## Epic Boundary

Epic `#678` exists to define the delivery order and dependency rules for the first runtime-backed budget and business-policy execution layer consumed by the app workspace.

It is complete when:

- the child issues are shipped in dependency order
- budget editing, spend capture, policy sync, proposal handling, and reoptimization remain separate inspectable concerns
- the app can move from planning into a small-business policy workflow without collapsing planner, policy, and approval responsibilities together
- later organization-specific integrations can build on stable business workflow surfaces instead of replacing them

## Dependency Chain

This epic depends on the persistence and workflow-state surfaces from `#675`, the planner workspace slice from `#676`, the runtime planning-service lane from `#677`, and the policy-facing execution contracts from `#549`, because budget and policy workflows need durable trip state, workspace-visible planner outputs, explicit service-layer results, and a stable cross-repo policy boundary before they can become usable application behavior.

Within the epic itself, the expected order is:

1. `#694` budget editing and actual-spend capture with workspace-visible totals
2. `#695` policy constraint sync/import and approval-readiness display
3. `#696` proposal submission, result ingestion, and approval-packet UI
4. `#697` reoptimization and exception-handling flows after policy results

Issue `#695` should build on the persisted budget and trip state from `#694` instead of inventing a separate business-session model. Issue `#696` should submit and render policy decisions through the synced policy and approval-readiness surfaces from `#695` instead of bypassing them with one-off export helpers. Issue `#697` should reuse the proposal and result surfaces from `#696` so reoptimization remains an explicit follow-up workflow rather than a hidden side effect.

## Shared Design Rules

Every child issue in this epic should preserve these rules:

- Keep `trip_planner/budget/` as the canonical home for budget editing, spend capture, and budget-state helpers.
- Keep `trip_planner/business_policy_export/` and the existing policy-facing business contracts as the canonical home for business-policy workflow orchestration above lower-level planner outputs.
- Keep `trip_planner/app/routes/` and `frontend/src/components/budget/` plus `frontend/src/components/policy/` as the user-visible seam for budget and policy behavior instead of letting the frontend invent its own business workflow state.
- Treat `Travel-Plan-Permission` as authoritative for policy evaluation and approval posture while this repo remains responsible for planning, packaging, and planner-side reaction.
- Keep budget editing, policy readiness, proposal submission, and reoptimization as distinct service and UI handoffs even when a single workspace screen renders the combined business workflow.
- Favor inspectable, testable intermediate outputs over opaque approval helpers so later organization-specific integrations can reuse the same surfaces.

## Child Issue Map

| Issue | Role | Must Consume | Must Produce |
|---:|---|---|---|
| `#694` | Budget editing and actual-spend capture | persisted trip/workflow state from `#675`, planner workspace seams from `#676`, runtime inventory and ranking outputs from `#677` | editable budget model, actual-spend capture surfaces, workspace-visible totals and variance signals |
| `#695` | Policy sync and approval-readiness display | budget state from `#694`, policy execution contracts from `#549`, workspace planner outputs from `#676` and `#677` | synced policy constraints, readiness indicators, approval-facing business status rendered in the workspace |
| `#696` | Proposal submission and result-ingestion UI | synced policy and readiness state from `#695`, policy-facing proposal contracts, budget and planner outputs from `#694` through `#677` | proposal submission flow, result-ingestion surfaces, approval-packet UI, explicit submission/result linkage |
| `#697` | Reoptimization and exception handling after policy results | proposal/result surfaces from `#696`, execution and exception vocabulary from `#549`, planner service outputs from `#677` | reoptimization flows, exception-ready alternatives, disposition state, workspace-visible follow-up actions |

## Contract Surface

The first pass of this epic should stabilize the following surfaces before deeper organization or approval automation expands:

- `trip_planner/budget/` for budget state, spend tracking, and workspace-visible budget calculations
- `trip_planner/business_policy_export/` for approval-readiness, proposal packaging, and planner-side reaction orchestration
- `trip_planner/app/routes/` plus the budget/policy frontend components for workspace-consumed business workflow behavior
- runtime, frontend, and fixture-backed tests that prove the app can move from planner output to budgeted policy workflow without losing inspectable boundaries

This keeps later enterprise-specific policy handling additive instead of forcing those integrations to bootstrap the first usable business workflow surface at the same time.

## Acceptance Mapping

The epic acceptance criteria from `#678` map to child issue outcomes as follows:

| Epic requirement | Owning issues |
|---|---|
| All child issues needed for the budget and business-policy execution layer are complete | `#694`, `#695`, `#696`, `#697` |
| The epic preserves clear boundaries between budget capture, policy sync, proposal handling, and reoptimization | `#694`, `#695`, `#696`, `#697` |
| The resulting work leaves a coherent next-stage surface for the remaining product backlog | `#694`, `#695`, `#696`, `#697` |

## Relationship To Earlier Planning Docs

The repo already contains broader policy-integration and business-planning documents such as [policy-integration-execution-epic.md](policy-integration-execution-epic.md), [contracts/trip-plan-proposal.md](contracts/trip-plan-proposal.md), and [planner-ui-integration.md](planner-ui-integration.md). Those remain useful design references, but epic `#678` is the runtime-backed sequencing contract for the current budget and business-policy workflow consumed by the application workspace and should be treated as the active parent lane for issues `#694` through `#697`.

## Design References

Use these documents together when implementing the child issues:

- [Product and architecture brief](product-architecture-brief.md)
- [Implementation plan](implementation-plan.md)
- [Accounts, persistence, and workflow state epic plan](accounts-persistence-workflow-state-epic.md)
- [Planner workspace vertical slice epic plan](planner-workspace-vertical-slice-epic.md)
- [Runtime planning services epic plan](runtime-planning-services-epic.md)
- [Policy integration execution epic plan](policy-integration-execution-epic.md)
- [Policy-facing proposal contracts](contracts/trip-plan-proposal.md)
- [Planner UI integration](planner-ui-integration.md)
- [Business travel profile](business-travel-profile.md)

## Working Rule

If a child issue needs to hide budget editing, policy sync, proposal handling, approval readiness, and reoptimization inside one generic business-flow helper or one oversized workspace patch, the epic is being violated and the design should be corrected before the PR lands.
