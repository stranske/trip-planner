# Test Coverage Audit

Source issue: [#1247](https://github.com/stranske/trip-planner/issues/1247)  
Generated: 2026-05-27

This audit classifies every table row in `docs/design-coverage-map.md` that is marked
`Partial`. It separates missing dedicated tests from partial product/runtime work so
the next repo-review cycle can avoid sending implementation agents after the wrong
kind of gap.

## Summary

| Count | Classification |
|-------|----------------|
| 11 | Partial table rows reviewed |
| 4 | Missing-test rows |
| 1 | New follow-up issue filed |
| 1 | Already addressed on `main` |
| 2 | Covered by existing open repo-review issues/PRs |
| 7 | Missing-functionality, live-provider, or release-confidence gaps |

`grep -n "🟡 Partial" docs/design-coverage-map.md` currently returns 12 lines because
the legend also contains the phrase. The actionable audit surface is the 11 table rows
listed below.

## Partial Row Inventory

| Section | Commitment | Source | Expected dedicated test | Classification | Disposition |
|---------|------------|--------|-------------------------|----------------|-------------|
| 2 | Explanation generation | `trip_planner/preferences/explanations.py` | `tests/preferences/test_explanations.py` | `missing-tests` | `covered-by-existing-candidate`: issue [#1243](https://github.com/stranske/trip-planner/issues/1243) / PR [#1244](https://github.com/stranske/trip-planner/pull/1244) |
| 2 | Legacy request adapter | `trip_planner/preferences/legacy_request_adapter.py` | `tests/preferences/test_legacy_request_adapter.py` | `missing-tests` | `already-addressed`: dedicated test file exists on `main` |
| 4 | Scenario generation | `trip_planner/itinerary/scenarios.py` | `tests/itinerary/test_scenarios.py` | `missing-tests` | `new-issue-filed`: issue [#1250](https://github.com/stranske/trip-planner/issues/1250) |
| 14 | Reoptimization + exception-handling after policy results (`#697`) | `trip_planner/integrations/tpp/reoptimization.py` | `tests/integrations/test_reoptimization.py` | `missing-functionality` | `already-tracked`: coverage map says live TPP call is deferred, not a missing unit-test file |
| 15 | Reoptimization seam | `trip_planner/integrations/tpp/reoptimization.py` | `tests/integrations/test_reoptimization.py` | `missing-functionality` | `already-tracked`: seam exists; remaining gap is no live round-trip |
| 16 | Timeline view for trip structure + day sequencing (`#698`) | `frontend/src/routes/WorkspacePage.tsx` | `frontend/src/routes/WorkspacePage.test.tsx` | `missing-functionality` | `already-tracked`: source-backed per-stop timing is pending |
| 16 | Saved-scenario + trip comparison views (`#700`) | `frontend/src/components/workspace/ScenarioComparison.tsx`, `frontend/src/components/trips/TripComparison.tsx` | `frontend/src/components/workspace/ScenarioComparison.test.tsx`, `frontend/src/components/trips/TripComparison.test.tsx` | `missing-tests` | `covered-by-existing-candidate`: issue [#1245](https://github.com/stranske/trip-planner/issues/1245) / PR [#1246](https://github.com/stranske/trip-planner/pull/1246) |
| 16 | Workspace timeline contract | `docs/workspace_timeline_contract.md`, `frontend/src/routes/WorkspacePage.tsx` | `frontend/src/routes/WorkspacePage.test.tsx` | `missing-functionality` | `already-tracked`: row is a partial seam/timing gap, not absent dedicated test coverage |
| 17 | Persisted-trip-driven inventory assembly (`#757`) | `trip_planner/app/services/inventory.py` | `tests/app/test_inventory.py` | `missing-functionality` | `already-tracked`: seeded IDs gate still present |
| 17 | Persisted default workspace bootstrap (`#758`) | `trip_planner/app/services/workspace.py` | `tests/app/test_workspace.py` | `missing-functionality` | `already-tracked`: runtime completion gap remains beyond tests |
| 17 | Runtime ranking + feasibility from persisted inventory (`#759`) | `trip_planner/app/services/scenarios.py` | none listed | `missing-functionality` | `already-tracked`: fixture branch remains and needs implementation, not just a dedicated test file |

## Evidence

- `tests/preferences/test_legacy_request_adapter.py` exists and directly exercises `adapt_legacy_request` and `load_legacy_request`, so that coverage-map row is stale.
- `tests/itinerary/test_search.py` imports `ScenarioSearchResult`, but there is no `tests/itinerary/test_scenarios.py` with direct contract/validation coverage for the scenario dataclasses.
- `tests/integrations/test_reoptimization.py`, `frontend/src/routes/WorkspacePage.test.tsx`, `tests/app/test_inventory.py`, and `tests/app/test_workspace.py` already exist for the rows classified as functionality/live-confidence gaps.
- Open PRs [#1244](https://github.com/stranske/trip-planner/pull/1244) and [#1246](https://github.com/stranske/trip-planner/pull/1246) cover the two high-priority missing-test rows already selected by the opener lane.

## Follow-Up Issues

- [#1250 Add dedicated tests for itinerary scenario generation contracts](https://github.com/stranske/trip-planner/issues/1250)
