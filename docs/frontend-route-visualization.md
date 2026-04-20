# Frontend Route Visualization

Issue `#559` adds visualization-oriented shell surfaces that consume route and feasibility outputs without duplicating route logic client-side.

## Surface family

- `trip_workspace` now carries scenario route alternatives, a provider-backed map surface, fallback route context, and timeline structure for the selected scenario.
- `planner_workspace` mirrors the selected scenario's burden warnings so route coherence stays visible next to canonical planner actions.
- The shell only renders route and timeline artifacts already produced upstream. It does not calculate route shapes, meeting feasibility, or movement scoring on the client.

## Consumption boundary

- `visualization_scenarios` should arrive as pre-shaped route visualization records attached to the workspace payload.
- Each scenario record should already encode anchor points, route segments, movement burden labels, timeline blocks, and any warnings surfaced by backend ranking or feasibility layers.
- `active_visualization_scenario_id` selects the currently rendered scenario. Switching scenarios in the shell changes presentation only.
- When map provider output is absent or fails to load, the shell should degrade to route summaries, markers, and option detail panels instead of synthesizing route logic locally.

## Current runtime contract

- `frontend/src/components/maps/TripMap.tsx` is the current route/context map surface for workspace rendering, with provider-independent map state shaped in `frontend/src/components/maps/mapSurface.ts`.
- The component consumes `runtime_scenario_comparison.scenarios[*].route_sequence`, `route_summary`, `metrics`, and `inventory_summary.bundles[*].destination_names`.
- `feasibility_summary.assessments` remains the source of route-attention and bundle-readiness signals; the map surface may summarize those signals, but it must not recalculate feasibility in the browser.
- Scenario preview changes are local presentation changes. The selected map preview should start from persisted workspace state and then update the rendered map surface without mutating backend route logic.
- When `VITE_GOOGLE_MAPS_BROWSER_API_KEY` is configured, the workspace renders the Google Maps JavaScript adapter path for the selected scenario. The adapter receives already-shaped route segments, stop markers, option markers, selected-marker detail, and route-burden warnings from workspace data.
- Missing map configuration, provider load errors, provider loading state, or sparse route data must fall back to the bounded route schematic with the same route context visible instead of blanking the workspace or falling back to a directions iframe.
- The workspace route should keep three review surfaces visible as distinct concerns: provider/fallback map state, day-sequencing timeline review, and a compact scenario tradeoff board for cost, travel burden, feasibility, and current policy posture.
- Mobile rendering should stack those same review surfaces without hiding the route-state explanation or the scenario toggle affordances behind separate navigation.

## Local setup note

- `make runtime-check` and `make runtime-smoke` validate the shipped map adapter seam, fallback states, and workspace shell; they do not require a Google Maps key.
- `VITE_GOOGLE_MAPS_BROWSER_API_KEY` is optional local configuration for exercising the provider adapter seam. If it is unset, the expected behavior is the fallback surface, not a failed runtime bootstrap.
- `VITE_GOOGLE_MAPS_PROVIDER_STATE=loading` or `error` can be used in local/test runs to verify non-ready provider states without live Google Maps access.

## Representative states

- Leisure regional loop: low-friction base with one regional excursion.
- Scenic transit route: higher transfer load because route delight is part of the traveler objective.
- Business constrained-window route: meeting timing and arrival certainty dominate the route presentation.
