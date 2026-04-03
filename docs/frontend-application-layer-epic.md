# Frontend Application Shell And Planning Surfaces Epic Plan

This document records the implementation contract for epic `#555`.

The goal is to sequence the frontend application layer so app shell, account and trip entry, trip workspace views, visualization surfaces, and planner interaction remain explicit instead of collapsing into one generic UI backlog item.

## Epic Boundary

Epic `#555` exists to define the delivery order and dependency rules for the user-facing application shell and primary planning surfaces.

It is complete when:

- the child issues are shipped in dependency order
- app shell, entry flows, workspace views, visualization surfaces, and planner interaction remain separate inspectable concerns
- the frontend consumes the canonical planning, orchestration, and policy contracts instead of redefining them in UI-specific shapes
- the resulting application layer is strong enough to support an end-to-end user-facing planning experience once the underlying engines are present

## Dependency Chain

This epic should follow the persistence, orchestration, ranking, and policy-integration layers from issues `#537`, `#543`, `#549`, and `#531`, because the frontend needs stable saved-trip state, planner workflow contracts, ranking outputs, and approval-readiness signals before it can present a coherent application experience.

Within the epic itself, the expected order is:

1. `#556` frontend app shell and state integration foundation
2. `#557` account, session-entry, and trip-launch flows
3. `#558` trip workspace with scenarios, rankings, and budget views
4. `#559` maps, route, and timeline visualization surfaces
5. `#560` planner interaction and business approval-readiness surfaces

Issue `#557` can mature alongside `#556` once the shell, navigation, and state boundaries are stable, but `#558`, `#559`, and `#560` should reuse the same app shell, workspace state, and orchestration vocabulary instead of inventing separate page-local models.

## Shared Design Rules

Every child issue in this epic should preserve these rules:

- Keep canonical planning and policy meaning in the existing Python and planner contracts rather than introducing frontend-only domain models.
- Treat `bundle/planner/orchestration-contracts.d.ts` as the mirror boundary for orchestration payloads until a dedicated frontend package exists.
- Keep app shell, workspace layout, visualization, and interaction surfaces modular so later React or web-app moves can lift them without re-splitting one monolith.
- Reuse existing planner-side-panel and contract docs where possible instead of forking business approval-readiness semantics in the UI layer.
- Favor bold, product-oriented travel-planning surfaces over generic dashboard framing, while keeping contract-driven empty states and validation deterministic.

## Child Issue Map

| Issue | Role | Must Consume | Must Produce |
|---:|---|---|---|
| `#556` | App shell and state foundation | persistence contracts from `#537`, orchestration state from `#543`, existing bundle/planner assets | navigation shell, shared state boundary, route/page scaffolding, frontend integration conventions |
| `#557` | Account and trip-entry flows | app shell from `#556`, persistence contracts from `#537`, trip-launch requirements from product docs | account/session entry surfaces, trip creation flow, launch-state capture, empty-state onboarding |
| `#558` | Workspace and scenario views | app shell from `#556`, saved-trip and scenario state from `#537`, ranking outputs from `#531`, orchestration payloads from `#543` | trip workspace layout, scenario/ranking panes, budget-aware summaries, workspace state composition |
| `#559` | Maps, route, and timeline surfaces | workspace state from `#558`, route and feasibility outputs from `#531`, trip structure contracts from earlier layers | visual map panes, route/timeline components, scenario visualization hooks, deterministic display states |
| `#560` | Planner interaction and approval-readiness UI | workspace shell from `#558`, planner interaction contracts from `#543`, approval-ready and policy outputs from `#549` | planner side-panel polish, interaction capture surfaces, approval-readiness displays, type and docs guardrails |

## Contract Surface

The first pass of this epic should stabilize the following surfaces before a larger frontend framework migration or live backend connectivity expands:

- `bundle/planner/` for planner-side interaction rendering, UI state helpers, and contract mirrors
- `docs/planner-ui-integration.md` and this epic plan for application-layer sequencing and contract guidance
- `tests/planner/` for deterministic state, docs-example, and type-shape checks
- future frontend application packages introduced by `#556` through `#560`, provided they continue to consume the canonical planner and policy vocabulary

This keeps later UI expansion additive instead of forcing maps, workspace state, and approval-readiness behavior to infer meaning from loosely coupled mock data.

## Acceptance Mapping

The epic acceptance criteria from `#555` map to child issue outcomes as follows:

| Epic requirement | Owning issues |
|---|---|
| All child issues needed for the frontend application shell and planning surfaces are complete | `#556` to `#560` |
| App shell, trip workspace, visualization, and planner interaction remain distinct concerns in the backlog | `#556`, `#557`, `#558`, `#559`, `#560` |
| The issue set assumes the backend planning contracts and workflows already defined rather than re-inventing them in UI form | `#556`, `#558`, `#559`, `#560` |
| The resulting frontend layer is sufficient to support an end-to-end user-facing planning experience once the backend issues land | `#556`, `#557`, `#558`, `#559`, `#560` |

## Design References

Use these documents together when implementing the child issues:

- [Product architecture brief](product-architecture-brief.md)
- [Planner UI integration](planner-ui-integration.md)
- [Orchestration, interactive planning, and in-trip adjustment epic](orchestration-interactive-planning-epic.md)
- [Policy integration execution epic](policy-integration-execution-epic.md)
- [Shared planning contracts](shared-planning-contracts.md)
- [Trip plan proposal contracts](contracts/trip-plan-proposal.md)
- [Issue #560 delivery plan](issue-560-delivery-plan.md)

## Working Rule

If a child issue needs to blur app shell, workspace composition, map visualization, and planner interaction into one opaque frontend rewrite, the epic is being violated and the design should be corrected before the PR lands.
