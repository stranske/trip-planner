# Application Foundation And Full-Stack Runtime Epic Plan

This document records the implementation contract for epic `#674`.

The goal is to sequence the first runnable application foundation so backend runtime bootstrap, frontend shell wiring, typed route/data seams, and local/CI workflow support land as separate concerns instead of collapsing into one opaque "app setup" task.

## Epic Boundary

Epic `#674` exists to define the delivery order and dependency rules for the first end-to-end application runtime layer.

It is complete when:

- the child issues are shipped in dependency order
- backend runtime bootstrap, frontend shell bootstrap, and runtime workflow support remain separate inspectable concerns
- the frontend consumes backend routes and typed seams instead of inventing a second domain model
- the resulting runtime leaves a coherent base for later persistence, workspace, and planner-surface work

## Dependency Chain

This epic is an enabling track for the broader planning backlog. It should reuse the shared planning and planner-panel contracts that already exist in the repo, but it does not need to wait for every later product issue before establishing a runnable app shell.

Within the epic itself, the expected order is:

1. `#680` FastAPI runtime, React shell, and live health integration
2. `#681` typed frontend API client plus route and data-loading foundation
3. `#682` full-stack local development and CI workflow support

Issue `#681` can begin once the runtime shell from `#680` stabilizes the basic route shape, but it should not invent a second transport contract. Issue `#682` can add tooling and workflow support alongside late `#681` work, but it should validate the concrete runtime surfaces instead of scaffolding against placeholders.

## Shared Design Rules

Every child issue in this epic should preserve these rules:

- Keep `trip_planner/app/` as the canonical backend runtime entrypoint.
- Keep `frontend/` as the user-facing application shell instead of extending the legacy static-demo path.
- Prefer typed request and response seams between frontend and backend over fixture-only or ad hoc JSON handling.
- Treat runtime health, app bootstrap, typed loading, and dev/CI workflow support as distinct handoffs.
- Reuse existing planning and planner bundle contracts where possible instead of redefining planning state inside the frontend bootstrap layer.

## Child Issue Map

| Issue | Role | Must Consume | Must Produce |
|---:|---|---|---|
| `#680` | Backend runtime and frontend shell bootstrap | existing planner bundle surfaces, shared repo docs, canonical package layout | FastAPI entrypoint, backend health route, Vite/React shell, integrated smoke path |
| `#681` | Typed API client and route/data-loading foundation | runtime route surface from `#680`, existing planner-side contract vocabulary | frontend API client boundary, route loaders/actions, typed fetch state, reusable shell data seams |
| `#682` | Local development and CI workflow support | concrete runtime surfaces from `#680` and `#681`, repo CI conventions | app-runtime dev commands, full-stack check targets, smoke coverage, documented local workflow |

## Contract Surface

The first pass of this epic should stabilize the following surfaces before deeper frontend and persistence work expands:

- `trip_planner/app/` for FastAPI app bootstrap, route registration, and runtime schemas
- `frontend/` for the React + TypeScript + Vite application shell and typed route-loading seams
- `Makefile`, CI wiring, and adjacent scripts for local full-stack execution and validation
- `tests/app/`, `tests/frontend/`, or equivalent runtime smoke coverage for backend/frontend integration

This keeps later persistence, planner workspace, and policy-facing surfaces additive instead of forcing them to bootstrap the entire runtime while also implementing their own product logic.

## Acceptance Mapping

The epic acceptance criteria from `#674` map to child issue outcomes as follows:

| Epic requirement | Owning issues |
|---|---|
| All child issues needed for the application foundation are complete | `#680`, `#681`, `#682` |
| The epic preserves clear boundaries between backend runtime, frontend shell, typed API seams, and runtime workflow support | `#680`, `#681`, `#682` |
| The resulting work leaves a coherent next-stage surface for the remaining product backlog | `#680`, `#681`, `#682` |

## Design References

Use these documents together when implementing the child issues:

- [Product and architecture brief](product-architecture-brief.md)
- [Implementation plan](implementation-plan.md)
- [Frontend app shell foundation](frontend-app-shell-foundation.md)
- [Frontend route loading foundation](frontend-route-loading-foundation.md)
- [Planner UI integration](planner-ui-integration.md)
- [Frontend application shell and planning surfaces epic](frontend-application-layer-epic.md)

## Working Rule

If a child issue needs to merge runtime bootstrap, API typing, and workflow support into one undifferentiated setup change, the epic is being violated and the design should be corrected before the PR lands.
