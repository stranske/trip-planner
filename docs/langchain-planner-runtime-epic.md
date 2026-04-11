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

The repo already contains planner-facing design and UI contract surfaces, but it does not yet expose a first-class planner runtime:

- `bundle/planner/mock-state.js`, `bundle/planner/side-panel.js`, and `bundle/planner/orchestration-contracts.d.ts` define the mounted planner panel shape and demo payloads
- `docs/product-architecture-brief.md` and `docs/contracts/planning-autonomy.md` define the intended LangChain and autonomy behaviors
- `trip_planner/preferences/autonomy.py` already converts autonomy preferences into concrete planner pacing metadata
- `trip_planner/app/routes/workspace.py` and `trip_planner/app/services/workspace.py` expose workspace planner decision and option-feedback endpoints, but they do not yet provide a trip-scoped conversation API, planner tool runner, or persisted planner checkpoint trail

That means the repo can render planner state and accept bounded planner interactions, but it still lacks the runtime layer that owns conversational planning, explicit tool use, and long-lived planner memory for arbitrary persisted trips.

## Dependency Chain

This epic depends on the persisted trip, workspace, and runtime seams established by the current app stack on `main`, especially the workspace route/service surfaces that now assemble persisted trip state, scenario search state, and planner panel payloads.

Within the epic itself, the expected order is:

1. `#760` trip-scoped planner session and conversation API
2. `#761` tool-backed planner actions for inventory, ranking, budget, and policy state
3. `#762` persisted planner checkpoints, summaries, and user-visible memory

Issue `#761` should build on the session and conversation seam from `#760` instead of introducing a separate planner entrypoint. Issue `#762` should build on the conversation and tool-action seams from `#760` and `#761` so persisted memory reflects real planner state transitions rather than UI-only snapshots.

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

The first pass of this epic should stabilize the following surfaces before broader multi-agent or provider-specific work expands:

- `trip_planner/app/routes/workspace.py` and adjacent app routes for trip-scoped planner API entrypoints
- `trip_planner/app/services/workspace.py` plus new planner-specific service seams for conversation orchestration and tool execution
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
