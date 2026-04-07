# Maps, Timeline, And Comparison Application Surfaces Epic Plan

This document records the implementation contract for epic `#679`.

The goal is to sequence the visualization layer so timeline views, route/context maps, and saved-scenario or trip comparison surfaces land as separate inspectable concerns instead of one opaque "visualization upgrade" task.

## Epic Boundary

Epic `#679` exists to define the delivery order and dependency rules for the first visualization-focused application layer above the runtime, persistence, and planner workspace spine.

It is complete when:

- the child issues are shipped in dependency order
- timeline, map, and comparison surfaces remain separate inspectable concerns
- the app renders persisted trip and scenario state through runtime-backed UI seams instead of introducing parallel client-only planning models
- the resulting visualization layer leaves a coherent next-stage surface for richer route context and scenario analysis

## Dependency Chain

This epic depends on the application foundation from `#674`, the persistence and workflow-state surfaces from `#675`, and the planner workspace slice from `#676`, because timeline, map, and comparison views need a runnable app shell, durable trip and scenario state, and a real workspace context before they can become useful product behavior.

Within the epic itself, the expected order is:

1. `#698` timeline view for trip structure and day sequencing
2. `#699` map surface for route and option context
3. `#700` saved-scenario and trip comparison views

Issue `#699` should build on the workspace trip structure and route outputs exposed by `#698` instead of introducing a separate geography-first state model. Issue `#700` should reuse the persisted trip and scenario seams established by `#675` and the visualization primitives from `#698` and `#699` so comparison remains an inspectable application workflow rather than static mock content.

## Shared Design Rules

Every child issue in this epic should preserve these rules:

- Keep `frontend/src/components/timeline/`, `frontend/src/components/maps/`, and `frontend/src/components/workspace/` as the canonical frontend seams for these visualization surfaces.
- Keep `trip_planner/app/` and the existing typed frontend data-loading contracts as the canonical source for trip, route, and scenario data instead of inventing parallel browser-only models.
- Treat timeline structure, route/context maps, and scenario comparison as distinct service and UI handoffs even when a single workspace screen renders them together.
- Reuse persisted trip, route, and saved-scenario state from earlier epics instead of replacing those seams with visualization-specific stores.
- Favor bold, intentional UX that clarifies trip shape and option tradeoffs rather than default dashboard furniture.
- Keep comparison grounded in live persisted application state and route outputs, not static fixtures or one-off mock summaries.

## Child Issue Map

| Issue | Role | Must Consume | Must Produce |
|---:|---|---|---|
| `#698` | Timeline view for trip structure and day sequencing | persisted trip/session state from `#675`, planner workspace seams from `#676`, runtime app shell/bootstrap from `#680`, and typed API client/data-loading seams from `#681` | timeline components, day-sequencing view model, workspace-visible trip structure surfaces |
| `#699` | Map surface for route and option context | timeline/trip structure from `#698`, typed route/loading seams from `#681`, workspace route context from `#676` | route/context map surface, option-location visualization, map-ready route context contracts |
| `#700` | Saved-scenario and trip comparison views | persisted scenario history from `#675`, timeline/map primitives from `#698` and `#699`, workspace-visible planner state from `#676` | saved-scenario comparison UI, trip-to-trip comparison surfaces, persisted comparison context rendered in the app |

## Contract Surface

The first pass of this epic should stabilize the following surfaces before deeper reporting or analytics work expands:

- `frontend/src/components/timeline/` for day sequencing and trip-structure rendering
- `frontend/src/components/maps/` for route and option context visualization
- `frontend/src/components/workspace/` for integrating those views into the planner workspace without collapsing existing state boundaries
- typed runtime/frontend seams that let the UI consume persisted trip, route, and scenario data without re-deriving them in the browser

This keeps later route intelligence, scenario analytics, and richer collaboration surfaces additive instead of forcing those lanes to invent the first usable visualization layer at the same time.

## Acceptance Mapping

The epic acceptance criteria from `#679` map to child issue outcomes as follows:

| Epic requirement | Owning issues |
|---|---|
| All child issues needed for the visualization layer are complete | `#698`, `#699`, `#700` |
| The epic preserves clear boundaries between timeline, map, and comparison concerns | `#698`, `#699`, `#700` |
| The resulting work leaves a coherent next-stage surface for the remaining product backlog | `#698`, `#699`, `#700` |

## Relationship To Earlier Planning Docs

The repo already contains broader frontend and planner-surface design references such as [frontend-application-layer-epic.md](frontend-application-layer-epic.md), [frontend-trip-workspace.md](frontend-trip-workspace.md), [planner-ui-integration.md](planner-ui-integration.md), and [workspace_timeline_contract.md](workspace_timeline_contract.md). Those remain useful design references, but epic `#679` is the runtime-backed sequencing contract for the current maps, timeline, and comparison application layer and should be treated as the active parent lane for issues `#698` through `#700`.

## Design References

Use these documents together when implementing the child issues:

- [Product and architecture brief](product-architecture-brief.md)
- [Implementation plan](implementation-plan.md)
- [Application foundation epic plan](application-foundation-epic.md)
- [Accounts, persistence, and workflow state epic plan](accounts-persistence-workflow-state-epic.md)
- [Planner workspace vertical slice epic plan](planner-workspace-vertical-slice-epic.md)
- [Frontend application shell and planning surfaces epic](frontend-application-layer-epic.md)
- [Frontend trip workspace](frontend-trip-workspace.md)
- [Planner UI integration](planner-ui-integration.md)
- [Workspace timeline contract](workspace_timeline_contract.md)

## Working Rule

If a child issue needs to hide timeline rendering, map context, and comparison behavior inside one oversized workspace patch or one generic visualization helper, the epic is being violated and the design should be corrected before the PR lands.
