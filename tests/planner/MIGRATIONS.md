# tests/planner — Migration notes

This file records xfail acceptance tests that have been removed because the
underlying capability shipped under different names. Each entry names the
removed test, the date of resolution, the shipped surface that satisfied the
original contract, and the auditing change-set.

Audit policy is in [#1046](https://github.com/stranske/trip-planner/issues/1046):
when an xfail in `tests/planner/test_planner_turn_acceptance.py`,
`tests/contracts/`, or `tests/integrations/` resolves, prefer the smallest
explicit signal: rewrite against the current contract, delete with a migration
note here, or tighten to `strict=True` with a precise `reason=`.

## 2026-04-30 — `test_tpp_approval_flow_round_trip_from_planner_turn` (deleted)

- **Removed by:** xfail audit for issue [#1046](https://github.com/stranske/trip-planner/issues/1046).
- **Original assertion:** module-level functions `request_approval` and
  `poll_approval_status` exported from `trip_planner.integrations.tpp`.
- **Why removed:** the live-TPP round-trip
  (permission request → approval evidence → confirmation) is satisfied by the
  shipped `HTTPTPPIntegrationClient` surface, not by module-level functions of
  those names. The contract is exercised end-to-end via:
  - `trip_planner/integrations/tpp/client.py` —
    `HTTPTPPIntegrationClient.submit_proposal` and `fetch_evaluation_result`.
  - `trip_planner/app/services/proposal.py` — planner-turn-driven booking
    actions construct a `TPPRequestEnvelope`, call the client, and surface the
    `TPPResponseEnvelope` confirmation back through the workspace payload.
  - `tests/integrations/test_submission.py`, `test_results.py`,
    `test_tpp_contracts.py`, and `test_tpp_cross_repo_smoke.py` — contract-level
    coverage of the round-trip.
- **Remaining gap:** end-to-end coverage against a live remote `Travel-Plan-Permission`
  HTTP endpoint is still tracked in
  `docs/live-tpp-execution-reoptimization-epic.md` and the design-coverage map
  §15 ("Live remote TPP transport"). That gap is owned by a future cross-repo
  smoke / live-transport lane, not by this acceptance file.

## 2026-04-30 — `test_map_target_uses_typed_route_context_contract` (deleted)

- **Removed by:** xfail audit for issue [#1046](https://github.com/stranske/trip-planner/issues/1046).
- **Original assertion:** at least one of
  `RouteContext` / `MapRouteContext` / `MapTargetRouteContext` is exported from
  `trip_planner.contracts`.
- **Why removed:** the route-context contract for the first map target shipped
  as a doc + fixture-validation contract under PR #1008, not as a Python type
  export from `trip_planner.contracts`. The canonical surface is:
  - `docs/contracts/route-context-map-target.md` — fielded contract document.
  - `tests/contracts/test_route_context_map_target.py` — schema-validation
    test against `tests/fixtures/maps/route_context_map_target.json`.
  - `frontend/src/components/maps/mapSurface.ts` — canonical TypeScript types
    (`TripMapSurfaceModel`, `MapSurfaceProvider`, `RouteStop`, `RouteSegment`,
    `MapMarker`, `MapMarkerKind`, `MapProviderLoadState`).
  Asserting a Python `trip_planner.contracts` export contradicts the shipped
  design and would prevent the documented surface from ever passing the test.
- **Remaining gap:** the dedicated map surface UI (`#699`) and the timeline
  view (`#698`) are still tracked in design-coverage map §16 as ❌ Missing.
  Those are UI gaps, not contract gaps; the route-context contract itself is
  no longer xfail-tracked here.
