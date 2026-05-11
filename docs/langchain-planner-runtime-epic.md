# LangChain Planner Runtime Epic Plan

This document records the implementation contract for epic `#754`.

The goal is to sequence the trip-scoped planner runtime so conversation handling, tool-backed planner actions, and persisted planner memory land as separate inspectable seams instead of one opaque "add LangChain" patch.

## Epic Boundary

Epic `#754` exists to define the delivery order and contract rules for turning the mounted planner panel into a real trip-scoped runtime feature.

It is complete when:

- the child issues are shipped in dependency order
- the planner runtime reads and mutates meaningful persisted workspace state instead of fixture-only UI payloads
- the conversation loop is grounded in explicit application tools and service boundaries
- planner memory, checkpoints, and user-visible summaries are persisted per trip so later revisions can resume coherently

## Current Runtime Posture

The first-pass planner runtime now exists and should be treated as the baseline rather than a deferred design:

- `trip_planner/app/routes/planner.py` exposes trip-scoped session, resume, and turn endpoints.
- `trip_planner/app/services/planner.py` owns deterministic fallback replies, the model-backed runnable, model-request metadata, structured planner blocks, explicit tool-call execution, and persisted turn payloads.
- `trip_planner/app/services/planner_tools.py` exposes the current application tool registry for workspace state, inventory and scenario refresh, budget state and updates, policy/proposal reads, pending decisions, option feedback, and planning-notebook actions.
- `trip_planner/persistence/models/planner_memory.py` and `trip_planner/app/services/planner_memory.py` persist checkpoint and summary records that make planner sessions resumable.
- `frontend/src/components/planner/PlanningModeSelector.tsx`, `trip_planner/app/routes/workspace.py`, and `trip_planner/app/services/workspace.py` persist the selected planning mode for delegated, collaborative, revealed-preference, and in-trip work.

The remaining runtime gap is depth rather than absence. The repo still needs dynamic model routing, richer source/map/provider-backed planner tools, semantic recall for scattered planning notes, and live-provider verification for release confidence.

## Runtime Configuration

Planner turns use a deterministic fallback unless a planner model is configured. The fallback is intentionally visible in the planner session payload so local development and `make runtime-check` do not require live model credentials.

Set these variables only when exercising the model-backed path:

- `TRIP_PLANNER_PLANNER_MODEL_PROVIDER=openai`
- `TRIP_PLANNER_PLANNER_MODEL=<OpenAI chat model name>`
- `OPENAI_API_KEY=<key with model access>`

When those values are present, the planner conversation service creates a LangChain-backed runnable and passes structured trip context, inventory, scenario, budget, policy, proposal, memory, activity, and available tool metadata into the model. The model may request only registered planner tools; unsupported tool names and malformed requests are persisted as visible tool errors rather than treated as successful state transitions. When configuration or credentials are absent, the deterministic fallback remains active and the response payload reports the fallback reason.

CI should cover the model-backed path with fake chat models rather than live provider credentials. Live provider checks belong in explicit integration runs.

## Dependency Chain

This epic depends on the persisted trip, workspace, and runtime seams established by the current app stack on `main`, especially the workspace route/service surfaces that now assemble persisted trip state, scenario search state, and planner panel payloads.

Within the epic itself, the first-pass delivery order was:

1. `#760` trip-scoped planner session and conversation API
2. `#761` tool-backed planner actions for inventory, ranking, budget, and policy state
3. `#762` persisted planner checkpoints, summaries, and user-visible memory

The implementation follows that ordering: `#761` builds on the session and conversation seam from `#760`, and `#762` builds on the conversation and tool-action seams from `#760` and `#761` so persisted memory reflects real planner state transitions rather than UI-only snapshots.

## Shared Design Rules

Every child issue in this epic should preserve these rules:

- Keep LangChain on top of explicit app tools and deterministic services; do not let prompts bypass ranking, feasibility, budget, proposal, or policy logic.
- Treat conversation transport, tool execution, and planner memory as distinct seams even if one workspace payload later exposes all of them.
- Use persisted trip and workspace identifiers as the canonical planner scope; do not invent planner-only trip IDs or fixture-only state roots.
- Make planner actions consume and mutate the same persisted workspace/session records that power the existing app routes.
- Preserve one planner thread per trip for the first pass unless later product work proves a need for branching planner sessions.
- Keep the mounted planner panel as a consumer of runtime state, not the source of truth for planner behavior.
- Preserve bounded fallback behavior so the planner can explain incomplete inventory or policy state without fabricating hidden success paths.

## Child Issue Map

| Issue | Role | Must Consume | Must Produce |
|---:|---|---|---|
| `#760` | Planner session + conversation boundary | persisted trip identity, workspace route/service seams, planner panel contract, autonomy metadata | trip-scoped planner session API, canonical conversation request/response shape, bounded planner turn lifecycle |
| `#761` | Tool-backed planner action execution | planner session seam from `#760`, inventory/workspace/budget/policy services, deterministic domain contracts | explicit planner tool registry/executor, tool-grounded planner outputs, workspace-visible action results |
| `#762` | Planner memory + checkpoint persistence | conversation seam from `#760`, tool traces from `#761`, persisted trip/workspace/session models | persisted planner checkpoints, summaries, user-visible memory trail, resumable planner state per trip |

## Contract Surface

The first pass of this epic stabilized the following surfaces before broader multi-agent or provider-specific work expands:

- `trip_planner/app/routes/workspace.py`, `trip_planner/app/routes/planner.py`, and adjacent app routes for trip-scoped planner API entrypoints
- `trip_planner/app/services/workspace.py`, `trip_planner/app/services/planner.py`, and `trip_planner/app/services/planner_tools.py` for conversation orchestration and tool execution
- persisted planner/session models alongside the existing trip and planning-session persistence surfaces
- `trip_planner/preferences/autonomy.py` and `docs/contracts/planning-autonomy.md` as the planner pacing and checkpoint contract inputs
- `bundle/planner/orchestration-contracts.d.ts` and `bundle/planner/side-panel.js` as consumers of runtime planner state rather than mock-only state

This keeps later planner UX work additive instead of forcing the UI layer to hide runtime concerns that belong in explicit backend service boundaries.

## Acceptance Mapping

The epic acceptance criteria from `#754` map to child issue outcomes as follows:

| Epic requirement | Owning issues |
|---|---|
| All child issues needed for the planner runtime are complete | `#760`, `#761`, `#762` |
| The planner runtime reads and mutates meaningful persisted workspace state rather than fixture-only UI data | `#760`, `#761`, `#762` |
| The resulting planner surface is a real trip-scoped product feature rather than a mounted component demo | `#760`, `#761`, `#762` |

## Relationship To Existing Docs

The repo already contains broader planner and workspace references such as [product-architecture-brief.md](product-architecture-brief.md), [planner-ui-integration.md](planner-ui-integration.md), [planner-workspace-vertical-slice-epic.md](planner-workspace-vertical-slice-epic.md), and [contracts/planning-autonomy.md](contracts/planning-autonomy.md). Those remain important design references, but epic `#754` is the active sequencing contract for turning the planner panel into a real LangChain-backed trip runtime and should be treated as the parent lane for issues `#760` through `#762`.

## Design References

Use these documents together when implementing the child issues:

- [Product and architecture brief](product-architecture-brief.md)
- [Planner UI integration](planner-ui-integration.md)
- [Planner workspace vertical slice epic plan](planner-workspace-vertical-slice-epic.md)
- [Live runtime completion epic plan](live-runtime-completion-epic.md)
- [Planning autonomy and revealed preference contracts](contracts/planning-autonomy.md)
- [Frontend trip workspace](frontend-trip-workspace.md)
- [Workspace comparison contract](workspace-comparison-contract.md)
- [Workspace timeline contract](workspace_timeline_contract.md)

## Working Rule

If a child issue tries to hide conversation handling, tool execution, and planner memory inside frontend mocks or one oversized LangChain patch, the epic is being violated and the design should be corrected before the PR lands.
