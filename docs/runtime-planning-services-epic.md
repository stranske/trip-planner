# Runtime Planning Services Epic Plan

This document records the implementation contract for epic `#677`.

The goal is to sequence the runtime planning services that sit above normalized options, itinerary objectives, and planner workspace state so inventory assembly, feasibility evaluation, ranking, and route comparison land as separate inspectable services instead of one opaque planner step.

## Epic Boundary

Epic `#677` exists to define the delivery order and dependency rules for the first runtime-backed planning-service layer consumed by the workspace.

It is complete when:

- the child issues are shipped in dependency order
- inventory assembly, feasibility evaluation, ranking/scenario generation, and route comparison remain separate concerns
- the workspace consumes explicit service-layer outputs instead of seeded placeholder planner state
- the resulting service surfaces leave a coherent base for later orchestration, policy execution, and richer trip comparisons

## Dependency Chain

This epic depends on the normalized contracts and candidate-shaping work from `#519`, `#525`, and `#531`, plus the runtime workspace slice from `#676`, because the service layer should consume explicit option, objective, and workspace boundaries instead of reaching back into raw provider payloads or frontend-only state.

Within the epic itself, the expected order is:

1. `#690` inventory bundle assembly surfaced in the workspace
2. `#691` feasibility and move-cost evaluation surfaced in planner outputs
3. `#692` ranking and scenario-generation services with workspace-visible results
4. `#693` route-search and scenario-comparison behavior in the workspace

Issue `#691` should build on the workspace-visible inventory surfaces from `#690` instead of recalculating its own candidate bundle shape. Issue `#692` should consume the explicit feasibility and move-cost outputs from `#691` so ranking behavior stays explainable. Issue `#693` should assemble route and scenario comparisons from the service seams created by `#690` through `#692` instead of bypassing them with route-specific planner logic.

## Shared Design Rules

Every child issue in this epic should preserve these rules:

- Keep `trip_planner/services/` as the canonical home for runtime planning-service orchestration above contracts, options, and state primitives.
- Keep `trip_planner/app/routes/` and the frontend workspace loaders as the user-visible seam for service outputs rather than letting the React app invent its own planning pipeline.
- Keep normalized contracts in `trip_planner/contracts/`, `trip_planner/options/`, `trip_planner/itinerary/`, and `trip_planner/business/` as lower-level inputs; this epic should compose them, not redefine them.
- Keep inventory assembly, feasibility, ranking, and route comparison as distinct service handoffs even when a single workspace screen renders the combined results.
- Favor inspectable, testable intermediate outputs over opaque end-to-end planner decisions so later orchestration and policy layers can reuse the same service surfaces.
- Progressively replace seeded workspace state with real runtime planning services instead of blocking the first workspace render on a fully finished planner stack.

## Child Issue Map

| Issue | Role | Must Consume | Must Produce |
|---:|---|---|---|
| `#690` | Workspace-visible inventory bundle assembly | normalized option contracts from `#519`, ingestion/candidate outputs from `#525`, trip/workspace seams from `#676` | service-layer bundle assembly, explicit workspace inventory payloads, deterministic inventory handoff for later services |
| `#691` | Feasibility and move-cost evaluation | inventory bundles from `#690`, itinerary-objective and move-cost vocabulary from prior contracts, workspace planner output seams | reusable feasibility and move-cost service outputs surfaced in planner results |
| `#692` | Ranking and scenario-generation services | inventory services from `#690`, feasibility outputs from `#691`, ranking/result contracts from `#531`, workspace state seams from `#676` | workspace-visible ranked alternatives, scenario-generation outputs, explanation-ready service results |
| `#693` | Route-search and scenario-comparison behavior | ranking/scenario outputs from `#692`, route and comparison vocabulary from `#531`, workspace route/render seams from `#676` | route-search orchestration, scenario comparison behavior, stable workspace comparison payloads |

## Contract Surface

The first pass of this epic should stabilize the following surfaces before deeper orchestration and policy work expands:

- `trip_planner/services/` for inventory, feasibility, ranking, and route-comparison orchestration
- `trip_planner/app/routes/` for planner workspace APIs that expose runtime service outputs
- `frontend/src/` workspace loaders and planner components that render service-backed inventory, ranking, and comparison results
- runtime and frontend tests that prove the workspace can progress from seeded state toward real inventory, feasibility, ranking, and route outputs without losing inspectable boundaries

This keeps later orchestration and policy-facing work additive instead of forcing those layers to bootstrap the first real runtime planning services while also delivering their own feature scope.

## Acceptance Mapping

The epic acceptance criteria from `#677` map to child issue outcomes as follows:

| Epic requirement | Owning issues |
|---|---|
| All child issues needed for the runtime planning-service layer are complete | `#690`, `#691`, `#692`, `#693` |
| The epic preserves clear boundaries between inventory, feasibility, ranking, and route comparison | `#690`, `#691`, `#692`, `#693` |
| The resulting work leaves a coherent next-stage surface for the remaining product backlog | `#690`, `#691`, `#692`, `#693` |

## Relationship To Earlier Planning Docs

The repo already contains broader lower-level planning documents such as [normalized-inventory-contracts-epic.md](normalized-inventory-contracts-epic.md), [source-ingestion-epic.md](source-ingestion-epic.md), [ranking-route-search-epic.md](ranking-route-search-epic.md), and the contract references under `docs/contracts/`. Those remain useful design references, but epic `#677` is the runtime-backed sequencing contract for the current service layer consumed by the planner workspace and should be treated as the active parent lane for issues `#690` through `#693`.

## Design References

Use these documents together when implementing the child issues:

- [Product and architecture brief](product-architecture-brief.md)
- [Implementation plan](implementation-plan.md)
- [Planner workspace vertical slice epic plan](planner-workspace-vertical-slice-epic.md)
- [Normalized inventory contracts epic](normalized-inventory-contracts-epic.md)
- [Source ingestion epic](source-ingestion-epic.md)
- [Ranking, route feasibility, and explainable search epic](ranking-route-search-epic.md)
- [Shared planning contracts](shared-planning-contracts.md)
- [Ranking result contracts](contracts/ranking-results.md)
- [Itinerary feasibility contracts](contracts/itinerary-feasibility.md)
- [Business ranking contracts](contracts/business-ranking.md)

## Working Rule

If a child issue needs to collapse inventory assembly, feasibility, ranking, scenario generation, and route comparison into one undifferentiated planner engine or one oversized workspace patch, the epic is being violated and the design should be corrected before the PR lands.
