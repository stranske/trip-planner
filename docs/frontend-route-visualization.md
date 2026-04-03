# Frontend Route Visualization

Issue `#559` adds visualization-oriented shell surfaces that consume route and feasibility outputs without duplicating route logic client-side.

## Surface family

- `trip_workspace` now carries scenario route alternatives, a textual map surface, and timeline structure for the selected scenario.
- `planner_workspace` mirrors the selected scenario's burden warnings so route coherence stays visible next to canonical planner actions.
- The shell only renders route and timeline artifacts already produced upstream. It does not calculate route shapes, meeting feasibility, or movement scoring on the client.

## Consumption boundary

- `visualization_scenarios` should arrive as pre-shaped route visualization records attached to the workspace payload.
- Each scenario record should already encode anchor points, route segments, movement burden labels, timeline blocks, and any warnings surfaced by backend ranking or feasibility layers.
- `active_visualization_scenario_id` selects the currently rendered scenario. Switching scenarios in the shell changes presentation only.
- When map provider output is absent, the shell should degrade to textual route summaries instead of synthesizing route logic locally.

## Representative states

- Leisure regional loop: low-friction base with one regional excursion.
- Scenic transit route: higher transfer load because route delight is part of the traveler objective.
- Business constrained-window route: meeting timing and arrival certainty dominate the route presentation.
