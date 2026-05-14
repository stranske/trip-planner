# Runtime Seam Audit

Issue: [#1188](https://github.com/stranske/trip-planner/issues/1188)
Generated: 2026-05-14
Baseline: `origin/main` at `65b2f587c` (`Issue #1186: finish source quality summary coverage (#1189)`)

## Audit Method

Seed commands:

```bash
rg -n 'not_available|SKIPPED|notebook_item_id' trip_planner/ scripts/ tests/
rg -n 'placeholder|stub|TODO|not implemented|NotImplemented|skip|skipped|category-only|category only|None\}|None\)|return None|return \{\}' trip_planner/ scripts/ tests/
```

Scope was limited to Python planner tools, integration clients, verifier surfaces, and their tests. Frontend-only surfaces and per-instance fixes already tracked by the weekly review were not reimplemented in this audit PR.

## Findings

| Site | Classification | Evidence | Follow-up |
| --- | --- | --- | --- |
| `trip_planner/app/services/planner_tools.py:408` (`_read_source_quality_summary`) | confirmed-gap - covered by per-instance issue; current main is already-correct | The originally reported seam is now closed on main: the tool builds `SourceQualityScorer` rows from attached bundle `source_records` and reports `missing_source_records` rather than the old blanket `not_available`. `tests/app/test_planner_routes.py:697` asserts the quality state is not `not_available`, rows exist, and at least one completed row has a score, confidence label, and contributing source count. | Covered by [#1186](https://github.com/stranske/trip-planner/issues/1186) / PR [#1189](https://github.com/stranske/trip-planner/pull/1189); no new issue filed. |
| `scripts/check_full_product_verification.py:379` / `scripts/check_full_product_verification.py:603` (`live-tpp`) | confirmed-gap - covered by per-instance issue; current main is already-correct in configured mode | The verifier still intentionally reports `SKIPPED` when live TPP is off or unconfigured, but configured live mode is now proven. `docs/verification-logs/live-tpp-pass-2026-05-14.log` records `PASS live-tpp` in sibling-checkout mode. `docs/design-coverage-map.md:258` and `docs/design-coverage-map.md:267` mark live remote TPP transport implemented with the captured verifier run. | Covered by [#1187](https://github.com/stranske/trip-planner/issues/1187) / PR [#1190](https://github.com/stranske/trip-planner/pull/1190); no new issue filed. |
| `trip_planner/app/services/planner_tools.py:902` (`_set_notebook_focus`) | confirmed-gap - covered by per-instance issue; residual design claim remains | The current tool accepts explicit `category` and optional `notebook_item_id`, then returns exactly that focus. `tests/app/test_planner_routes.py:945` exercises the phrase "I was working on lodging" and asserts `{"category": "lodging", "notebook_item_id": None}`. `docs/design-coverage-map.md:231` and `docs/design-coverage-map.md:328` still call semantic/vector recall and notebook reorientation a remaining claim. This audit did not re-open it as a new gap because #1188 explicitly excludes re-auditing planner-memory artifact resolution as new work. | Covered historically by [#1125](https://github.com/stranske/trip-planner/issues/1125). No new issue filed from this audit because the issue scope names this seam as already tracked. |
| `trip_planner/app/services/planner_tools.py:392` (`read_source_summary`) | already-correct | The tool reports `not_available` only when a workspace has no source references and no inventory bundle summary items. When data exists, it returns source refs and bounded bundle summaries. This is an explicit no-data state, not a placeholder success. | None. |
| `trip_planner/app/services/planner_tools.py:470` and `trip_planner/app/services/planner_tools.py:523` (`read_map_provider_status`, `read_route_geometry`) | already-correct | For missing route scenarios, both tools return explicit `not_available` state instead of fabricated provider or geometry data. `tests/app/test_planner_routes.py:785` asserts `read_map_provider_status.status == "not_available"` with `route_state == "missing"` and `read_route_geometry.status == "not_available"` with empty geometry. | None; this is the correct no-data behavior. |
| `trip_planner/app/services/planner_tools.py:601` (`refresh_route_comparison`) | already-correct | The tool reports `not_available` only when no deterministic route-comparison scenarios are available. When scenarios exist, it returns bounded scenario rows, lead scenario metadata, and source refs. | None. |
| `scripts/check_full_product_verification.py:316` (`classify_map_prerequisite`) | intentionally-deferred | Missing Google Maps credentials are reported as `SKIPPED` with `provider_state: fallback` and the exact missing env var. `tests/app/test_full_product_verification.py:52` pins this fallback so the default local/CI path does not require live map credentials. | None; this is an opt-in integration seam, not a silent runtime gap. |
| `scripts/check_full_product_verification.py:379` (`tpp_prerequisite_status`) | intentionally-deferred | `live_tpp=off` and auto mode without `TPP_BASE_URL` / `TPP_REPO_PATH` return `SKIPPED` with remediation. `tests/app/test_full_product_verification.py:77` asserts the missing transport target details. Configured `required` mode is separately covered by the live pass log above. | None; default skip is intentional and configured live mode is verified. |
| `docs/design-coverage-map.md:291` and `docs/design-coverage-map.md:329` (provider-rich timeline/map depth claim) | needs-investigation | The seed search did not find a silent placeholder in the missing-route path, but the current design map still names live distance/geometry verification and richer source-backed option-marker detail as a remaining follow-up claim. This is separate from the correct sparse-route `not_available` behavior. | Filed [#1191](https://github.com/stranske/trip-planner/issues/1191). |

## Follow-Up Issues Filed

- [#1191](https://github.com/stranske/trip-planner/issues/1191) - Investigate provider-rich map and route depth beyond sparse-route fallback.

## Summary

The audit found no untracked confirmed runtime seam that should be fixed inside this PR. Two originally known seams have already been remediated on `main` by #1186/#1189 and #1187/#1190. The missing-route and missing-provider states are explicit, tested fallbacks rather than silent success. One remaining design-map follow-up claim needs a focused investigation and was filed as #1191.
