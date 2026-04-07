# Accounts, Persistence, And Workflow State Epic Plan

This document records the implementation contract for epic `#675`.

The goal is to sequence the first database-backed product memory layer so account access, trip persistence, scenario/history storage, and workflow activity storage land as separate concerns instead of becoming one opaque "save everything" implementation.

## Epic Boundary

Epic `#675` exists to define the delivery order and dependency rules for the first small-business-oriented persistence layer.

It is complete when:

- the child issues are shipped in dependency order
- account/session access, trip persistence, scenario/history persistence, and workflow activity storage remain separate inspectable concerns
- the frontend consumes the same backend persistence seams that the runtime exposes instead of inventing parallel client-only state
- the resulting persistence layer leaves a coherent base for later workspace, policy, and orchestration work

## Dependency Chain

This epic depends on the full-stack runtime foundation from epic `#674`, because the persistence work needs a real app shell, backend entrypoint, and typed request/response seams before durable state can be added safely.

Within the epic itself, the expected order is:

1. `#683` account registration, login, and session-backed app access
2. `#684` database-backed trip creation, list, and detail flows
3. `#685` saved scenario and planning-history persistence with UI access
4. `#686` planning-session and activity-log persistence with a visible audit trail

Issue `#684` should build on the session-aware app access from `#683` so trip ownership is real from the start. Issue `#685` should build on the persisted trip container from `#684` rather than storing scenario state in isolated UI memory. Issue `#686` can overlap late `#685` work, but it should write activity and session state against the same trip and account boundaries instead of inventing a separate workflow store.

## Shared Design Rules

Every child issue in this epic should preserve these rules:

- Keep `trip_planner.state.*` as the canonical contract and repository boundary already established in the repo, and treat `trip_planner/persistence/` as the storage-facing implementation layer for runtime-backed persistence work.
- Keep `trip_planner/app/routes/` as the canonical backend route surface for persistence access.
- Keep `frontend/` as the user-facing application shell for auth, trip, scenario, and activity surfaces.
- Use `SQLAlchemy` + `Alembic` with `SQLite` for the first production-quality baseline and optimize for correctness over scale theater.
- Reuse the canonical trip and planning contracts already defined in the repo instead of creating app-only persistence models with divergent vocabulary.
- Treat account/session access, trip containers, scenario/history state, and activity memory as distinct handoffs even when they share the same database.

## Child Issue Map

| Issue | Role | Must Consume | Must Produce |
|---:|---|---|---|
| `#683` | Account and session foundation | runtime foundation from `#674`, backend app entrypoint, frontend shell bootstrap | user/session models, auth routes, login/signup flows, protected app access |
| `#684` | Persisted trip container and list/detail flows | session-aware access from `#683`, canonical trip contract vocabulary | trip models, trip routes, signed-in create/list/detail flows |
| `#685` | Saved scenario and planning-history persistence | persisted trip ownership from `#684`, planning artifact vocabulary already used elsewhere in the repo | scenario/history models, trip-scoped routes, readable scenario/history UI surface |
| `#686` | Planning-session and activity-log memory | persisted trip ownership from `#684`, scenario/history context from `#685` where useful | session/activity models, append/read routes, visible audit trail for planner actions |

## Contract Surface

The first pass of this epic should stabilize the following surfaces before deeper workspace and policy work expands:

- `trip_planner/persistence/` for engine/session setup, models, and migrations
- `trip_planner/app/routes/` for auth, trip, scenario/history, and activity endpoints
- `frontend/src/routes/` and trip-facing components for session-aware UI entry and persisted-state views
- tests that prove persisted app state survives refresh and later re-entry

This keeps later planner workspace, policy execution, and collaboration work additive instead of forcing those later issues to bootstrap product persistence while also delivering their own feature scope.

## Acceptance Mapping

The epic acceptance criteria from `#675` map to child issue outcomes as follows:

| Epic requirement | Owning issues |
|---|---|
| All child issues needed for the persistence foundation are complete | `#683`, `#684`, `#685`, `#686` |
| The epic preserves clear boundaries between account access, trip persistence, scenario/history state, and workflow memory | `#683`, `#684`, `#685`, `#686` |
| The resulting work leaves a coherent next-stage surface for the remaining product backlog | `#683`, `#684`, `#685`, `#686` |

## Relationship To Earlier Persistence Docs

The repo already contains earlier persistence-planning documents such as [persistence-architecture.md](persistence-architecture.md), [state-trip-persistence.md](state-trip-persistence.md), and [state-session-persistence.md](state-session-persistence.md). Those remain useful design references, but epic `#675` is the runtime-backed sequencing contract for the current issue set and should be treated as the parent lane for implementation order.

## Design References

Use these documents together when implementing the child issues:

- [Product and architecture brief](product-architecture-brief.md)
- [Implementation plan](implementation-plan.md)
- [Application foundation epic plan](application-foundation-epic.md)
- [Persistence architecture](persistence-architecture.md)
- [Trip persistence boundary](state-trip-persistence.md)
- [Planning session and activity-log persistence](state-session-persistence.md)

## Working Rule

If a child issue needs to merge authentication, trip containers, scenario history, and workflow memory into one undifferentiated persistence change, the epic is being violated and the design should be corrected before the PR lands.
