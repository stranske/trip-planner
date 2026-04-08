# Frontend Planner Panel Workspace Integration

Issues: [#688](https://github.com/stranske/trip-planner/issues/688), [#689](https://github.com/stranske/trip-planner/issues/689)

The React workspace now mounts the existing planner side-panel bundle instead of leaving that surface isolated in bundle demos.

## What Is Mounted

- The workspace API now returns `planner_panel_state` alongside trip, session, and scenario payloads.
- The workspace API also returns recent `activity_log` entries plus planner action endpoints that persist session changes.
- `frontend/src/components/planner/PlannerSidePanelSurface.tsx` mounts `bundle/planner/side-panel.js` inside the React route.
- `frontend/src/routes/WorkspacePage.tsx` keeps trip metadata, persisted activity, and scenario context around that mounted planner surface.

## Persisted Planner Actions

- Decision answers now POST through `/api/workspace/:tripId/planner/decisions/:decisionId/answer`.
- Structured option feedback now POST through `/api/workspace/:tripId/planner/options/:optionId/feedback`.
- The backend stores planner action state in the persisted planning-session record and appends activity entries tied to the trip/session trail.
- Reloading the workspace rehydrates the side panel from those persisted session/activity records instead of recomputing from local browser state.

## Data Contract

- Treat `PlannerPanelState` from `bundle/planner/orchestration-contracts.d.ts` as the contract boundary.
- Prefer extending the backend payload builder in `trip_planner/app/services/workspace.py` over inventing a second frontend-only planner shape.
- For early vertical slices it is acceptable to seed planner options from real trip context and fixture-backed scenario data, as long as they flow through `/api/workspace/:tripId`.
- Preserve the bundle event contract when adding new planner actions so the React wrapper can stay thin and state replacement can keep happening through `replaceState`.

## How Future Issues Should Build On This

- Replace seeded `planner_panel_state` sections with live orchestration outputs instead of replacing the mounted bundle renderer.
- Add planner mutations or structured-response handling through app APIs while preserving the side-panel contract keys.
- Keep trip context in the workspace shell and let the side panel own planner-specific sections such as outputs, decisions, options, and approval posture.
