# Live Runtime Completion Epic Plan

This document records the implementation contract for epic `#753`.

The goal is to sequence the runtime-completion work so inventory assembly, workspace bootstrap, and scenario generation for arbitrary persisted trips land as separate inspectable concerns instead of becoming one opaque "make the runtime real" patch.

## Epic Boundary

Epic `#753` exists to define the delivery order and dependency rules for replacing fixture-only runtime branches in the main application path with persisted-trip-driven behavior.

It is complete when:

- the child issues are shipped in dependency order
- arbitrary persisted trips can move through inventory assembly, workspace bootstrap, and scenario comparison without seeded trip-ID gates as the primary path
- the runtime preserves bounded fallback behavior for partial or missing inventory instead of failing the workspace outright
- the resulting services leave a coherent handoff surface for later LangChain planner work, live policy execution, and Google Maps-backed route surfaces

## Current Runtime Posture

The repo already has a partial persisted-trip path, but the richest runtime behavior still depends on seeded branches:

- `trip_planner/app/services/inventory.py` only assembles inventory bundles for `trip-leisure-kyoto-draft` and `trip-business-client-summit`
- `trip_planner/app/services/workspace.py` can open a persisted trip workspace, but the richer scenario and comparison path still prefers seeded fixtures
- `trip_planner/app/services/scenarios.py` still carries the seeded scenario branch that later runtime work needs to demote or replace

That means new trips can enter the app, but they do not yet receive the same normalized inventory and scenario depth as the seeded examples. This epic keeps that gap explicit and sequences the work needed to close it.

## Dependency Chain

This epic depends on the persistence and workspace foundation already established by `#675` and `#676`, because runtime completion needs persisted trip ownership, session state, planner workspace seams, and typed app routes before it can replace seeded runtime branches coherently.

Within the epic itself, the expected order is:

1. `#757` persisted-trip-driven inventory assembly
2. `#758` persisted default workspace bootstrap
3. `#759` runtime ranking, feasibility, and scenario comparison from persisted inventory

Issue `#758` should build on the adapter-backed inventory seam from `#757` instead of inventing another app-local bootstrap source. Issue `#759` should build on the persisted inventory and workspace seams from `#757` and `#758` so ranking and comparison use real runtime outputs rather than another fixture branch.

## Shared Design Rules

Every child issue in this epic should preserve these rules:

- Keep `trip_planner/app/services/inventory.py`, `trip_planner/app/services/workspace.py`, and `trip_planner/app/services/scenarios.py` as the canonical runtime seams for application assembly.
- Use persisted trip metadata from `trip_planner/persistence/models/` and `trip_planner/state/` instead of inventing new runtime-only identifiers.
- Treat inventory assembly, workspace bootstrap, and scenario generation as distinct service handoffs even when a single workspace payload exposes all three.
- Preserve bounded empty-or-partial fallback behavior so a newly created trip can still render a coherent workspace while richer inventory sources are incomplete.
- Reuse the existing deterministic ranking, feasibility, and itinerary contracts rather than bypassing them with app-local ad hoc payload generation.
- Demote seeded fixture branches to compatibility or test support paths; do not let them remain the primary runtime behavior for newly created trips.

## Child Issue Map

| Issue | Role | Must Consume | Must Produce |
|---:|---|---|---|
| `#757` | Persisted inventory assembly boundary | persisted trip records, option and ingestion contracts, current inventory route/API shape | adapter-backed inventory seam, normalized bundles for arbitrary trips, bounded empty/partial fallback payload |
| `#758` | Persisted workspace bootstrap | inventory seam from `#757`, persisted trip/session/scenario models, current workspace route/UI contract | deterministic default workspace session, saved-scenario/comparison scaffolding, coherent planner-panel bootstrap for new trips |
| `#759` | Runtime ranking and scenario comparison | persisted inventory from `#757`, workspace scaffolding from `#758`, feasibility/ranking/itinerary services | live scenario search outputs, runtime comparison payloads, workspace-visible ranking and feasibility state for arbitrary trips |

## Contract Surface

The first pass of this epic should stabilize the following surfaces before LangChain conversation and live provider integrations expand:

- `trip_planner/app/routes/inventory.py` and `trip_planner/app/services/inventory.py` for persisted inventory payloads
- `trip_planner/app/routes/workspace.py` and `trip_planner/app/services/workspace.py` for persisted workspace bootstrap and planner-panel hydration
- `trip_planner/app/services/scenarios.py` plus existing feasibility, ranking, and itinerary modules for runtime scenario generation
- service and route tests that prove newly created leisure and business trips can move through these runtime seams without depending on seeded trip IDs

This keeps later planner, policy, and map work additive instead of forcing those layers to finish the first real runtime path while also delivering their own feature scope.

## Acceptance Mapping

The epic acceptance criteria from `#753` map to child issue outcomes as follows:

| Epic requirement | Owning issues |
|---|---|
| All child issues needed for runtime completion are complete | `#757`, `#758`, `#759` |
| Arbitrary persisted trips can reach meaningful inventory and workspace state without seeded-ID gates | `#757`, `#758`, `#759` |
| The resulting runtime leaves a clean handoff surface for LangChain and live policy integration | `#757`, `#758`, `#759` |

## Relationship To Existing Docs

The repo already contains broader product and workspace references such as [implementation-plan.md](implementation-plan.md), [planner-workspace-vertical-slice-epic.md](planner-workspace-vertical-slice-epic.md), [frontend-trip-workspace.md](frontend-trip-workspace.md), and [planner-ui-integration.md](planner-ui-integration.md). Those remain useful design references, but epic `#753` is the active sequencing contract for replacing fixture-only runtime branches with persisted-trip-driven application behavior and should be treated as the parent lane for issues `#757` through `#759`.

## Design References

Use these documents together when implementing the child issues:

- [Product and architecture brief](product-architecture-brief.md)
- [Implementation plan](implementation-plan.md)
- [Accounts, persistence, and workflow state epic plan](accounts-persistence-workflow-state-epic.md)
- [Planner workspace vertical slice epic plan](planner-workspace-vertical-slice-epic.md)
- [Frontend trip workspace](frontend-trip-workspace.md)
- [Planner UI integration](planner-ui-integration.md)
- [Workspace comparison contract](workspace-comparison-contract.md)
- [Workspace timeline contract](workspace_timeline_contract.md)

## Working Rule

If a child issue needs to hide inventory assembly, workspace bootstrap, and scenario generation inside one oversized runtime patch or another seeded fixture branch, the epic is being violated and the design should be corrected before the PR lands.
