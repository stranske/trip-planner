# Workspace Comparison Contract

Issue `#700` treats comparison as a persisted application surface instead of a planner-only summary.

## Inputs

- Workspace route data from `GET /api/workspace/{trip_id}`
  - `saved_scenarios[]` supplies persisted saved-scenario versions.
  - `runtime_scenario_comparison` supplies side-by-side scenario rows, metrics, and lead/alternative state.
- Persisted trip list data from `GET /api/trips`
  - used to compare the current workspace against other saved trips without inventing browser-only trip models.

## Scenario Comparison Expectations

- At least two runtime scenarios should be renderable when ranking output exists.
- Each rendered comparison row should preserve:
  - scenario title
  - saved-scenario label/title when a persisted saved scenario maps to the runtime scenario
  - comparison metrics from `comparison_axes`
  - delta versus the lead scenario
- Selection behavior must let the user switch the active compared scenario without leaving the workspace route.

## Trip Comparison Expectations

- The current workspace trip is the fixed anchor.
- Compared trips come from persisted trip records returned by `GET /api/trips`.
- The first pass compares:
  - mode
  - status
  - duration
  - primary regions
  - traveler count summary
- If no other saved trips exist, the UI should render an explicit empty state rather than mock data.
