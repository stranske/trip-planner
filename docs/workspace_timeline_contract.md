# Workspace Timeline Contract

The workspace timeline surface intentionally derives from existing trip and scenario contracts instead of introducing a separate itinerary-specific persistence model.

## Source data

- `trip_record.trip.trip_frame.start_date`, `end_date`, and `duration_days` define the visible trip window.
- `session.current_saved_scenario_id` identifies the saved scenario the workspace should treat as active.
- `saved_scenarios[].versions[].snapshot_refs.itinerary_scenario_id` links persisted saved-scenario history back to a route scenario.
- `scenario_search.scenarios[].scenario_summary.route_sequence` provides the ordered route shape the UI renders as timeline stops.

## Current UI behavior

The frontend matches the active saved scenario to a `ScenarioSearchResult` entry and then distributes the persisted trip duration across the ordered `route_sequence` stops. This keeps the timeline anchored to route/scenario output while richer per-leg timing data is still evolving.

## Forward-compatibility expectation

When route/scenario producers start emitting explicit per-stop timing metadata, the workspace UI should keep using the same join points above and replace only the equal-distribution adapter. The timeline surface should continue to consume trip + saved-scenario + scenario-search state, not a parallel itinerary-only record.
