# Provider-Rich Route/Map Depth Audit

Issue: #1191

## Classification

The provider-rich route/map follow-up is implemented for the default deterministic runtime path and intentionally deferred for live Google Maps distance verification.

## Evidence

- `trip_planner/app/services/workspace.py` builds route markers and rough geometry for each runtime route option from ranked scenario data.
- `trip_planner/app/services/planner_tools.py` exposes that payload through `read_map_provider_status` and `read_route_geometry`.
- `frontend/src/components/maps/mapSurface.ts` prefers `map_view.place_markers` and `map_view.rough_route_geometry` when the runtime payload supplies them.
- `frontend/src/components/maps/TripMap.tsx` keeps provider diagnostics out of the default traveler view while still showing segment timing, confidence, and unavailable-state copy.

## Decision

The default local and CI path must not require live Google Maps credentials. Instead, the runtime now makes the route-depth state inspectable with bounded metadata:

- Route stop markers include a traveler-safe description and source references back to ranked scenario evidence.
- Route segments include duration, confidence, source references, and an explicit `distance_verification_state`.
- When provider distance is absent, segments report `duration_estimate_only` and keep the existing unavailable reason instead of fabricating distance.
- Missing route scenarios still return `not_available` from `read_map_provider_status` and `read_route_geometry`.

Live provider distance/geometry verification remains opt-in through the Google Maps adapter path and explicit local or release verification, not the default test path.

## Validation

- `tests/app/test_planner_routes.py` asserts planner tools expose source-backed markers, segment verification state, and preserved missing-route `not_available` behavior.
- `tests/app/test_workspace.py` asserts workspace route comparison payloads carry source-backed marker and segment metadata.
- `frontend/src/components/maps/mapSurface.test.ts` asserts provider-supplied marker descriptions and source refs flow into the map surface model.
