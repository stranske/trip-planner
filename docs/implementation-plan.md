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

### 3. Normalized Planning Objects

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

### 5. Ranking And Route Assembly

- `#532` ranking and explanation contracts
- `#533` feasibility and move-cost evaluation
- `#534` leisure ranking
- `#535` business ranking
- `#536` route-search and multi-scenario assembly

### 6. Persistence And Workflow State

- `#538` account and traveler-profile persistence
- `#539` trip persistence
- `#540` saved scenarios and history
- `#541` budgets and actual spend
- `#542` planning sessions and activity logs

### 7. Orchestration And In-Trip Adjustment

- `#544` planner-turn and workflow contracts
- `#545` leisure orchestration
- `#546` feedback loops
- `#547` in-trip replanning
- `#548` business orchestration and policy prep

### 8. Policy Integration Execution

- `#550` integration-client and execution contracts
- `#551` policy sync
- `#552` proposal submission and result ingestion
- `#553` reoptimization and exception handling
- `#554` approval-ready packaging and integration harnesses

### 9. Frontend Application Layer

- `#556` frontend app shell
- `#557` account and trip entry flows
- `#558` trip workspace
- `#559` maps and timeline visualization
- `#560` planner interaction and business approval-readiness UI

## Working Rule

The preferred delivery pattern is:

1. complete the root contracts for a layer
2. build the engine or workflow that consumes those contracts
3. only then add the user-facing or integration-facing surface on top

That keeps the repo from drifting into UI-first or integration-first shortcuts that would force data-model rework later.
