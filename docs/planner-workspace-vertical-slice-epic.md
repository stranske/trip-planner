# Planner Workspace Vertical Slice Epic Plan

This document records the implementation contract for epic `#676`.

The goal is to sequence the first usable planner workspace slice so trip entry, workspace composition, and persisted planner interaction land as separate concerns instead of becoming one opaque "finish the app" task.

## Epic Boundary

Epic `#676` exists to define the delivery order and dependency rules for the first end-to-end planner workspace flow inside the runtime-backed application.

It is complete when:

- the child issues are shipped in dependency order
- trip entry, workspace rendering, and persisted planner interactions remain separate inspectable concerns
- the frontend consumes the same backend trip, planner, and persistence seams that the runtime exposes instead of inventing a client-only workspace model
- the resulting slice leaves a coherent base for later maps, policy execution, and deeper orchestration work

## Dependency Chain

This epic depends on the application foundation from `#674` and the persistence foundation from `#675`, because the workspace slice needs a real app shell, typed route/data seams, session-aware trip ownership, and durable planner state before it can behave like a real product surface.

Within the epic itself, the expected order is:

1. `#687` trip entry flow that launches users into the planner workspace
2. `#688` planner side-panel integration inside the React workspace with real trip context
3. `#689` persisted planner decisions and option-feedback actions across reloads

Issue `#688` should build on the explicit launch and route-entry boundary from `#687` instead of inventing another startup path into the workspace. Issue `#689` should build on the concrete workspace and planner-action seams from `#688` so persistence captures real user-visible planner decisions rather than placeholder UI state.

## Shared Design Rules

Every child issue in this epic should preserve these rules:

- Keep `frontend/` as the user-facing application shell and workspace surface.
- Keep `trip_planner/app/routes/` as the canonical backend route boundary for trip and planner workspace access.
- Keep `trip_planner.state.*` as the contract boundary for trip, scenario, session, and planner-state meaning, with persistence-backed implementation work flowing underneath those contracts rather than around them.
- Reuse the existing planner-side-panel and workspace docs as design references instead of forking a second workspace vocabulary for the React app.
- Treat trip entry, workspace composition, and planner-action persistence as distinct handoffs even when they share the same visible route tree.
- Favor a usable end-to-end trip workflow over broad placeholder UI coverage; each child issue should deepen the real workspace path instead of adding disconnected mock pages.

## Child Issue Map

| Issue | Role | Must Consume | Must Produce |
|---:|---|---|---|
| `#687` | Trip entry and workspace launch boundary | runtime shell from `#674`, account/session access from `#683`, trip ownership seams planned in `#684`, frontend route/loading conventions | launch route, signed-in trip creation/open flow, deterministic handoff into the planner workspace |
| `#688` | Planner workspace composition and side-panel integration | route/entry boundary from `#687`, planner-side-panel contracts, existing workspace docs, typed frontend/backend seams from `#674` | React workspace route, planner side-panel mounted against real trip context, workspace state composition rules |
| `#689` | Persisted planner decisions and feedback actions | workspace composition from `#688`, persisted trip/session scaffolding from `#675`, canonical planner and scenario vocabulary | durable planner-action writes, reload-safe workspace state, visible persistence-backed planner history/feedback behavior |

## Contract Surface

The first pass of this epic should stabilize the following surfaces before maps, timeline views, policy execution, and deeper orchestration work expand:

- `frontend/src/routes/` and adjacent workspace components for trip entry and planner workspace composition
- `trip_planner/app/routes/` for trip-launch and planner workspace APIs
- `trip_planner/state/` and the persistence-backed implementation beneath it for planner-action durability
- runtime and frontend tests that prove a user can enter a trip, open the workspace, interact with planner state, and reload without losing the visible workflow

This keeps later visualization and policy-facing work additive instead of forcing those layers to bootstrap the first real workspace path while also delivering their own feature scope.

## Acceptance Mapping

The epic acceptance criteria from `#676` map to child issue outcomes as follows:

| Epic requirement | Owning issues |
|---|---|
| All child issues needed for the first planner workspace slice are complete | `#687`, `#688`, `#689` |
| The epic preserves clear boundaries between trip launch, workspace rendering, and persisted planner interaction | `#687`, `#688`, `#689` |
| The resulting work leaves a coherent next-stage surface for the remaining product backlog | `#687`, `#688`, `#689` |

## Relationship To Earlier Frontend Docs

The repo already contains broader frontend-planning documents such as [frontend-application-layer-epic.md](frontend-application-layer-epic.md), [frontend-app-shell-foundation.md](frontend-app-shell-foundation.md), [frontend-entry-flows.md](frontend-entry-flows.md), and [frontend-trip-workspace.md](frontend-trip-workspace.md). Those remain useful design references, but epic `#676` is the runtime-backed sequencing contract for the current first usable workspace slice and should be treated as the active parent lane for issues `#687` through `#689`.

## Design References

Use these documents together when implementing the child issues:

- [Product and architecture brief](product-architecture-brief.md)
- [Implementation plan](implementation-plan.md)
- [Application foundation epic plan](application-foundation-epic.md)
- [Accounts, persistence, and workflow state epic plan](accounts-persistence-workflow-state-epic.md)
- [Frontend application shell and planning surfaces epic](frontend-application-layer-epic.md)
- [Frontend app shell foundation](frontend-app-shell-foundation.md)
- [Frontend entry flows](frontend-entry-flows.md)
- [Frontend trip workspace](frontend-trip-workspace.md)
- [Planner UI integration](planner-ui-integration.md)

## Working Rule

If a child issue needs to merge trip launch, workspace composition, and planner-state durability into one undifferentiated "workspace build" change, the epic is being violated and the design should be corrected before the PR lands.
