# Frontend App Shell Foundation

This document records the implementation boundary for issue `#556`.

The goal is to stand up the first reusable application shell for `trip-planner` without prematurely locking the repo into a heavyweight frontend framework rewrite.

## What Issue #556 Owns

Issue `#556` establishes:

- a mode-aware route shell for dashboard, trip workspace, planner, and approval surfaces
- shared workspace loading, empty, and error-state treatment
- explicit seams between persisted trip state, orchestration planner payloads, and business approval output
- representative frontend fixtures for signed-in, active leisure, and active business trip contexts
- deterministic frontend tests that prove route, shell, and state transitions

It does not yet own full account-entry flows, workspace panes, maps, or final side-panel interaction polish. Those stay with `#557` through `#560`.

## Current Implementation Surface

The shell foundation lives in:

- `bundle/app-shell/contracts.d.ts`
- `bundle/app-shell/mock-state.js`
- `bundle/app-shell/app-shell.js`
- `tests/planner/test_app_shell_state.mjs`

This keeps the application shell close to the existing planner bundle until a later dedicated frontend package exists.

## Route Model

The shell currently treats these routes as canonical:

| Route | Purpose | Visibility rule |
| --- | --- | --- |
| `dashboard` | signed-in home, saved-trip selection, launch surface | always visible |
| `trip_workspace` | active trip context, scenario staging, persistence summary | requires active trip |
| `planner_workspace` | orchestration-driven checkpoints and next-step actions | requires active trip |
| `approval_center` | business approval posture, comparables, and packet seams | business mode or active policy evaluation |

The shell is responsible for deciding which routes are visible from the active trip context. Later issues should not hard-code their own mode-specific nav trees.

## State Integration Seams

The shell composes three state sources:

1. session and saved-trip summaries from the persistence layer (`#537`)
2. active planning payloads from orchestration (`#543`) through `PlannerPanelState`
3. business approval posture from proposal plus policy evaluation outputs (`#549`)

The shell should summarize those states, not redefine them.

Practical rule:

- use shell-local UI state only for route selection, active trip selection, and workspace-status handling
- keep trip, option, proposal, and policy meaning in the canonical contracts and planner mirrors

## Shared Status Rules

All child frontend issues should reuse the shell status boundary model:

- `loading`: a route is mounted but still hydrating saved state or planner payloads
- `empty`: there is no trip or no route-specific payload yet
- `error`: the shell has enough context to describe a deterministic blocker
- `ready`: the route can render its primary content

This avoids each later page inventing a different loading or empty-state vocabulary.

## Representative Fixtures

Issue `#556` ships three shell fixtures:

- signed-in dashboard with saved leisure and business trips
- active leisure trip workspace with planner checkpoint state
- active business trip workspace with approval-readiness state

Later issues should extend those fixtures instead of replacing them with unrelated page-local mocks.

## Handoff To Later Issues

- `#557` now plugs trip-entry and account-launch flows into the dashboard route through `account_entry` launch, profile, and recent-session surfaces.
- `#558` should deepen the trip workspace route with scenario, ranking, and budget panes.
- `#559` should attach maps and timeline views to the trip workspace without changing the shell route contract.
- `#560` should connect the planner and approval routes to the more detailed planner-side-panel surfaces already living under `bundle/planner/`.
