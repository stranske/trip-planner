# Implementation Plan

This document records the recommended implementation order for the current `trip-planner` backlog.

The goal is to preserve the dependency order between planning layers instead of letting later UI or integration work outrun the core contracts and engines.

## Recommended Sequence

### 1. Preference And Contract Foundation

- `#507` leisure preference contracts and package layout
- `#508` leisure evidence model
- `#509` traveler fixture corpus
- `#514` shared trip, option-set, and itinerary-objective contracts
- `#515` `BusinessTravelProfile`
- `#517` source and provenance contracts

Epic `#506` is the sequencing contract for the leisure preference foundation.
See [leisure-preference-epic.md](leisure-preference-epic.md) for the dependency chain, shared design rules, and acceptance mapping spanning issues `#507` through `#512`.

### 2. Core Planning Engines

- `#510` leisure preference resolution
- `#511` autonomy and revealed-preference updates
- `#512` leisure itinerary objectives
- `#516` policy-facing proposal and evaluation contracts
- `#518` business planning objectives

Epic `#513` is the sequencing contract for the shared planning and business-foundation layer.
See [shared-business-foundation-epic.md](shared-business-foundation-epic.md) for the dependency chain, shared design rules, and acceptance mapping spanning issues `#514` through `#518`.

### 3. Normalized Planning Objects

- [Epic `#519`: normalized inventory contracts and option modeling](normalized-inventory-contracts-epic.md)
- `#520` destinations and place-context contracts
- `#521` `LodgingOption`
- `#522` `TransportOption`
- `#523` `ActivityOption`
- `#524` inventory bundles and mixed option assembly

### 4. Data Ingestion And Candidate Generation

- `#526` source adapter and raw snapshot contracts
- `#527` entity resolution and deduplication
- `#528` lodging and transport ingestion
- `#529` destination and activity ingestion
- `#530` candidate generation and filtering

Epic `#525` is the sequencing contract for this phase.
See [source-ingestion-epic.md](source-ingestion-epic.md) for the dependency chain, shared design rules, and acceptance mapping for issues `#526` through `#530`.

### 5. Runtime Planning Services

Epic `#677` is the current runtime-backed sequencing contract for the service layer above normalized options, itinerary objectives, and planner workspace state. It turns the earlier planning and ranking design work into a concrete workspace-consumed services lane. Use [runtime-planning-services-epic.md](runtime-planning-services-epic.md) as the parent contract, and treat [ranking-route-search-epic.md](ranking-route-search-epic.md) plus the lower-level contract docs as design references rather than the active issue lane.

- `#690` inventory bundle assembly surfaced in the workspace
- `#691` feasibility and move-cost evaluation surfaced in planner outputs
- `#692` ranking and scenario-generation services with workspace-visible results
- `#693` route-search and scenario-comparison behavior in the workspace

### 6. Persistence And Workflow State

Epic `#675` is the current runtime-backed sequencing contract for this layer. It turns the earlier persistence design work into a concrete application lane sized around small-business account access and durable planning state. Use [accounts-persistence-workflow-state-epic.md](accounts-persistence-workflow-state-epic.md) as the parent contract, and treat [persistence-architecture.md](persistence-architecture.md) plus the state-boundary docs as design references rather than the active issue lane.

- `#683` account registration, login, and session-backed app access
- `#684` database-backed trip creation, list, and detail flows
- `#685` saved scenario and planning-history persistence with UI access
- `#686` planning-session and activity-log persistence with a visible audit trail

### 7. Orchestration And In-Trip Adjustment

Epic `#543` is the sequencing contract for this phase.
See [orchestration-interactive-planning-epic.md](orchestration-interactive-planning-epic.md) for the dependency chain, shared design rules, and acceptance mapping for issues `#544` through `#548`.

- `#544` planner-turn and workflow contracts
- `#545` leisure orchestration
- `#546` feedback loops
- `#547` in-trip replanning
- `#548` business orchestration and policy prep

### 8. Policy Integration Execution

Epic anchor: `#549` defines the execution and approval-readiness sequencing boundary for this layer. See [policy-integration-execution-epic.md](policy-integration-execution-epic.md).

- `#550` integration-client and execution contracts
- `#551` policy sync
- `#552` proposal submission and result ingestion
- `#553` reoptimization and exception handling
- `#554` approval-ready packaging and integration harnesses

### 9. Frontend Application Layer

Epic `#676` is the current runtime-backed sequencing contract for the first usable planner workspace slice. It turns the broader frontend application design into a concrete delivery lane sized around trip launch, workspace composition, and persisted planner actions. Use [planner-workspace-vertical-slice-epic.md](planner-workspace-vertical-slice-epic.md) as the parent contract, and treat [frontend-application-layer-epic.md](frontend-application-layer-epic.md) plus the existing frontend boundary docs as broader design references.

- `#687` build the trip entry flow that launches users into the planner workspace
- `#688` integrate the planner side panel into the React workspace with real trip context
- `#689` persist planner decisions and option-feedback actions across reloads

## Cross-Cutting Runtime Foundation

Epic `#674` is an enabling track for the first runnable full-stack application surface. It should stay distinct from the deeper product layers above and below it, because its job is to make the repo executable end to end without collapsing backend bootstrap, frontend route loading, and local/CI workflow support into one change.

The expected order inside that epic is:

1. `#680` FastAPI runtime, React shell, and live health integration
2. `#681` typed frontend API client and route/data-loading foundation
3. `#682` full-stack local development and CI workflow support

Use [application-foundation-epic.md](application-foundation-epic.md) as the contract for those runtime-focused child issues.

## Broader Frontend Design References

Epic `#555` still defines the larger application-shell and planning-surface design envelope for the eventual frontend layer. Use [frontend-application-layer-epic.md](frontend-application-layer-epic.md), [frontend-app-shell-foundation.md](frontend-app-shell-foundation.md), [frontend-entry-flows.md](frontend-entry-flows.md), and [frontend-trip-workspace.md](frontend-trip-workspace.md) as design references while the near-term implementation lane runs through `#676`.

## Working Rule

The preferred delivery pattern is:

1. complete the root contracts for a layer
2. build the engine or workflow that consumes those contracts
3. only then add the user-facing or integration-facing surface on top

That keeps the repo from drifting into UI-first or integration-first shortcuts that would force data-model rework later.
