# Frontend Trip Workspace

This document records the workspace surface built for issue `#558`.

## What Issue #558 Owns

Issue `#558` deepens the `trip_workspace` route from the app shell with:

- scenario comparison cards that stay linked to saved scenario ids
- ranked-alternative summaries anchored to the canonical planner option set
- checkpoint history that points back to saved planner checkpoints
- budget posture summaries tied to persisted budget-state variants

It does not own maps, route visualizations, side-panel interactions, or live collaboration flows.

## State Mapping

The workspace intentionally composes existing backend-facing seams instead of inventing parallel page models:

1. `PlannerPanelState` remains the source for ranked alternatives and active checkpoint outputs.
2. `FrontendWorkspaceRecord.scenario_summaries` provides a small UI summary layer over saved scenario branches.
3. `FrontendWorkspaceRecord.checkpoint_history` keeps checkpoint lineage visible without copying full planner turns.
4. `FrontendWorkspaceRecord.budget_summary` points to persisted budget-state ids and scenario-linked variants.

The practical rule is that the workspace may summarize scenario, checkpoint, and budget state, but it should not redefine canonical trip, planner, ranking, or budget contracts.

## Representative Fixtures

Issue `#558` extends the shell fixtures with three route-ready workspace contexts:

- leisure scenario comparison with an active and fallback branch
- business primary-versus-fallback approval review
- an in-trip revised scenario that preserves prior checkpoint history

These fixtures live in `bundle/app-shell/mock-state.js` so later route work can reuse them instead of inventing disconnected mocks.

## Handoff

- `#559` should attach maps and route/timeline views to these workspace summaries.
- `#560` should let the planner side panel drive the same scenario and checkpoint records instead of replacing them.

## Minimum Trip Data To Open The Workspace

Issue `#687` extends the shell so a freshly created persisted trip can open `/workspace/:tripId` before any saved scenarios exist.

The minimum required data is:

- a persisted `trip_id`
- `mode`
- `title`
- traveler-party basics (`kind`, `traveler_count`)
- whichever trip-frame fields are already known (`start_date`, `end_date`, `duration_days`, `primary_regions`)

Everything else may remain empty on first load. The workspace should still render the trip shell, initialize a minimal session reference, and show timeline/scenario empty states until later planning issues attach saved scenarios, comparisons, and activity history.
