# Route-Context Map Target Contract

This document is the source-of-truth contract for the **first map target** in the
trip-planner application: the route-and-context map surface for the active
scenario in the trip workspace. It consolidates the design rules in
[maps-timeline-comparison-epic.md](../maps-timeline-comparison-epic.md) and
[frontend-route-visualization.md](../frontend-route-visualization.md) into a
fielded contract that a coding agent can implement against without re-reading
the upstream design narrative.

## Why this exists

The map work was previously described across two design narratives plus a
TypeScript surface module, with no single doc naming the first artifact, the
required input shape, or the offline/fallback behavior in one place. Issue
[#959](https://github.com/stranske/trip-planner/issues/959) called for that
consolidation so subsequent map work has a single contract to extend.

## First map target

**Component:** [`frontend/src/components/maps/TripMap.tsx`](../../frontend/src/components/maps/TripMap.tsx)

**Surface module:** [`frontend/src/components/maps/mapSurface.ts`](../../frontend/src/components/maps/mapSurface.ts)
(canonical TypeScript types — `TripMapSurfaceModel`, `MapSurfaceProvider`,
`RouteStop`, `RouteSegment`, `MapMarker`, `MapMarkerKind`,
`MapProviderLoadState`).

The first map target renders **route context for the active route option** in
the trip workspace. It supports three traveler-facing scopes without changing
the selected route option:

| Scope | User intent | Map behavior |
|---|---|---|
| `global` | Understand the whole trip outline. | Keeps the main anchors and complete rough route visible. Labels the shape as approximate. |
| `regional` | Compare the selected route option. | Shows all legs for the active route option and remains synchronized with route-option selection. |
| `local` | Focus on one travel leg. | Narrows the visible route to a selected segment and nearby planning markers. If a route has fewer than two stops, the UI explains that segment detail is pending. |

It does not render timeline-only structure, saved-trip overviews, or multiple
simultaneous geography overlays. Those are separate surfaces in this epic
([#698](https://github.com/stranske/trip-planner/issues/698) and
[#700](https://github.com/stranske/trip-planner/issues/700) respectively) and
are explicitly deferred from this contract.

## Required input fields

The map target consumes pre-shaped route data from the workspace payload
produced by `trip_planner/app/services/workspace.py`. No browser-only planning
state is permitted; every visualizable signal must come from the workspace
contract below.

### From `runtime_scenario_comparison.scenarios[*]`

| Field | Type | Required | Notes |
|---|---|---|---|
| `scenario_id` | string | yes | Selects the active scenario. |
| `route_option_id` | string | recommended | Stable route-option identifier when it differs from `scenario_id`. |
| `route_sequence` | string[] | yes | Ordered destination/anchor identifiers driving stop generation. |
| `route_summary` | string | yes | Single-line route description shown when the provider adapter is unavailable. |
| `map_view` | object | yes | Traveler-facing map state. This is the normal UI source for scope, active route option, selected segment, markers, rough geometry, and confidence copy. |
| `map_diagnostics` | object | yes | Provider/debug details. Normal traveler UI must not render this payload directly. |
| `metrics.estimated_total` | object \| null | optional | Currency-typed total surfaced under route summary. |
| `metrics.travel_burden_score` | number \| null | optional | Drives the burden warning highlight. |
| `policy_posture` | string | yes | Mirrored as the policy-posture chip on the map. |

### `map_view` fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `active_scope` | `global`\|`regional`\|`local` | yes | Initial scope for the route option. The frontend can change scope locally without changing `active_route_option_id`. |
| `active_route_option_id` | string | yes | Route option currently driving the map. |
| `selected_segment_id` | string \| null | yes | Segment focus for local mode. Null is valid when geometry is sparse. |
| `place_markers` | object[] | yes | User-facing route anchors with label and normalized fallback coordinates. |
| `rough_route_geometry` | object[] | yes | Approximate route segments. These are planning shapes, not turn-by-turn directions. |
| `confidence.level` | `high`\|`medium`\|`low` | yes | Coarse confidence label for route precision. |
| `confidence.summary` | string | yes | Traveler-facing copy explaining approximate versus more detailed map state. |

### From `feasibility_summary`

| Field | Type | Required | Notes |
|---|---|---|---|
| `assessments` | object[] | yes | Source of route-attention and bundle-readiness signals; map summarizes only — does not recompute. |
| `summary_text` | string | optional | Used when no per-scenario summary is available. |

### From `inventory_summary.bundles[*]`

| Field | Type | Required | Notes |
|---|---|---|---|
| `destination_names` | string[] | yes | Anchors the destination context list and stop labels. |
| `bundle_id` | string | yes | Stable identifier for marker provenance. |

### Trip-level context (workspace payload root)

| Field | Type | Required | Notes |
|---|---|---|---|
| `trip.primary_regions` | string[] | yes | Drives the destination anchors when route_sequence is sparse. |
| `policy_evaluation.posture` | string | optional | Used as the displayed policy posture if the active scenario lacks one. |

## Provider and offline behavior

The map target supports two provider modes, selected by environment
configuration in the frontend bundle. The contract treats both as legitimate
runtime states; neither is permitted to blank the workspace. Provider state
belongs in `map_diagnostics` and the internal `MapSurfaceProvider`; the normal
traveler UI should show route confidence and scope language instead of raw
provider labels such as API adapter names, load errors, or key configuration.

| Mode | Trigger | UI behavior |
|---|---|---|
| **Live (`google-maps-js`)** | `VITE_GOOGLE_MAPS_BROWSER_API_KEY` set; provider loaded successfully | Renders the Google Maps JavaScript adapter with the pre-shaped route segments, stop markers, option markers, and selected-marker detail. |
| **Fallback** | Key missing, provider load error, sparse route, or `VITE_GOOGLE_MAPS_PROVIDER_STATE=loading\|error` | Renders the bounded route schematic with the same route context (anchors, segments, markers, summaries, posture chip, feasibility highlights) using SVG/CSS only. |

### Required fallback fields on `MapSurfaceProvider` (kind: `fallback`)

| Field | Required | Notes |
|---|---|---|
| `kind` | yes | Literal `"fallback"`. |
| `label` | yes | Human-readable internal name of the fallback surface. Do not render this directly in normal traveler mode. |
| `status` | yes | One of `"fallback"`, `"misconfigured"`, `"provider-error"`, `"loading"`, `"sparse-route"`. |
| `summary` | yes | Single-line diagnostic explanation of why fallback is active. Use for debug/advanced surfaces, not the normal map header. |

The contract requires fallback rendering to remain feature-equivalent for
**route-context comprehension**: stop list, marker list, segment list, posture
chip, and feasibility summary all visible. Provider-native interactions
(zoom/pan/native-tile) are intentionally unavailable in fallback.

## Test mode

`make runtime-check` and `make runtime-smoke` validate the shipped map adapter
seam and fallback states without requiring a real Google Maps key. The
fallback surface is the **default test mode**; live adapter rendering requires
an explicit env var. Tests must not assume live provider rendering and must
assert against the documented fields produced by `buildTripMapSurfaceModel` in
`mapSurface.ts`.

## Deferred map features (non-goals for this contract)

Each of the following is explicitly **out of scope** for the first map target.
They are tracked as separate issues or future contract additions; do not
extend the route-context map to absorb them without a new contract.

- **Timeline-only views.** Owned by [#698](https://github.com/stranske/trip-planner/issues/698)
  and rendered via `frontend/src/components/timeline/`.
- **Scenario comparison maps.** Owned by [#700](https://github.com/stranske/trip-planner/issues/700);
  comparison reuses route-context outputs but is a separate surface in
  `frontend/src/components/workspace/`.
- **Geography-first state model.** The route-context map must not introduce a
  parallel browser-only model for trips, routes, or scenarios. All inputs come
  from `trip_planner/app/` workspace contracts.
- **Live route recomputation in the browser.** Movement scoring, meeting
  feasibility, and route shape are produced by backend ranking/feasibility
  services. The map summarizes only.
- **Directions-iframe fallback.** When the live adapter is unavailable, the
  fallback is the bounded route schematic, not a directions iframe.
- **Real-time updates from external map providers.** Out of scope for the
  workspace surface; would belong to an in-trip adjustment epic.
- **Multiple simultaneous provider adapters.** Only `google-maps-js` is wired
  today. Adding a second provider requires extending `MapSurfaceProvider`'s
  discriminated union explicitly.

## Validation

This contract has two validation layers:

1. **Existing TypeScript test:** [`frontend/src/components/maps/mapSurface.test.ts`](../../frontend/src/components/maps/mapSurface.test.ts)
   exercises `buildTripMapSurfaceModel` against representative scenario inputs.
2. **Backend payload schema test:** [`tests/contracts/test_route_context_map_target.py`](../../tests/contracts/test_route_context_map_target.py)
   asserts the workspace payload produced by `trip_planner/app/services/workspace.py`
   exposes the fields this contract requires, against a fixture in
   [`tests/fixtures/maps/route_context_map_target.json`](../../tests/fixtures/maps/route_context_map_target.json).
   The fixture is the canonical "what the map consumes" example for the
   route-context surface.

Any change that drops a field listed above must update both the contract here
and the schema test, or the test fails with an explicit "missing required map
target field" message.
