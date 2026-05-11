# Workspace Timeline Contract

The workspace timeline surface intentionally derives from existing trip and scenario contracts instead of introducing a separate itinerary-specific persistence model.

## Source data

- `trip_record.trip.trip_frame.start_date`, `end_date`, and `duration_days` define the visible trip window.
- `session.current_saved_scenario_id` identifies the saved scenario the workspace should treat as active.
- `saved_scenarios[].versions[].snapshot_refs.itinerary_scenario_id` links persisted saved-scenario history back to a route scenario.
- `scenario_search.scenarios[].scenario_summary.route_sequence` provides the ordered route shape the UI renders as timeline stops.
- `route_comparison.scenarios[].map_view.rough_route_geometry` may provide selected segment identity, per-leg duration, distance, confidence, and unavailable-state detail. When present, this augments the timeline and map segment review without introducing a separate itinerary persistence model.

## Current UI behavior

The frontend matches the active saved scenario to a runtime route-comparison entry and then distributes the persisted trip duration across the ordered `route_sequence` stops. Segment focus is shared with the map surface: switching route options updates the day plan, and switching segment-level review highlights the two timeline stops connected by the active route leg. If `map_view.rough_route_geometry` includes per-leg timing or confidence details, the timeline summary uses those fields; otherwise it keeps the bounded equal-distribution adapter.

## Forward-compatibility expectation

When route/scenario producers start emitting explicit per-stop timing metadata, the workspace UI should keep using the same join points above and replace only the equal-distribution adapter. The timeline surface should continue to consume trip + saved-scenario + route-comparison state, not a parallel itinerary-only record.
