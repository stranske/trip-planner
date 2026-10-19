# Bounded coverage-map reconciliation: issue 1908

Source baseline `4f78d2d1a` (merged transition audit #1927). The historical
May 11 suite total and May 14 live-TPP log remain dated history. They are
not current-head execution claims. This change edits the coverage map and
its bounded docs regression; no production repair or new findings issue.

## Current local observation

Repository-selected CPython3.14 `.venv/bin/python` ran:

```sh
python -m pytest -o addopts= tests/preferences/test_legacy_request_adapter.py tests/app/test_inventory.py tests/integrations/test_canonical_state_seam.py tests/app/test_workspace.py::test_workspace_endpoint_creates_non_seeded_persisted_leisure_trip_with_runtime_frame tests/app/test_workspace.py::test_workspace_endpoint_creates_non_seeded_persisted_business_trip_with_runtime_frame tests/app/test_workspace.py::test_workspace_endpoint_avoids_fixture_bundle_ids_and_fixture_adapter_markers_for_persisted_trips -q
```

The incoming test set passed 21 tests. After the three docs regressions,
the same bounded selection passed 24 tests (exit 0). This covers the
existing dedicated legacy adapter, persisted-record inventory, the reachable
workspace input with `allow_fixture_fallback=False`, non-seeded business/leisure
runtime frames, and sequential app-close/cache-reset/reopen against file SQLite.
The default adapter flag remains True for other callers. Offline synthetic
source and policy boundaries do not establish live provider completeness.
Existing Alembic deprecation warnings are retained as warnings.

The new regression validates normalized explicit source/test references and
same-directory Markdown targets; a nonexistent path is rejected. Temporarily
removing the actual legacy-adapter dedicated-test citation makes the Scope
regression fail; exact-byte restoration returns GREEN. Path validity is only
a documentation check, not behavioral verification.

## Separate TPP evidence states

1. Historical `docs/verification-logs/live-tpp-pass-2026-05-14.log`: preserved,
   including its old producer revision. It does not establish today's pair.
2. Configured `.github/workflows/cross-repo-smoke.yml`: current producer pin
   `aa36ad2cc4e85da634347541480f2784363ccdbb` and real local HTTP/auth/SQLite
   tests in `tests/integration/test_authenticated_two_app_handoff.py` with
   checkout/import provenance checks. This round did not execute those tests.
3. Required configured full-product command:
   `python scripts/check_full_product_verification.py --live-tpp=required`.
   Current execution is UNVERIFIED; a future PASS needs both full revisions,
   actual environment, run URL and retained artifact. Default skips and
   `--live-tpp off` are not positive evidence.

F50 lineage (#1904/#1915), F51 SDK-boundary tests (#1905/#1923) and F52
sequential restart (#1906/#1926) retain their existing owners. The inherited
`docs/reports/production-transition-audit.md` classifies each narrower control;
this round does not rerun maps, contact providers, or claim OS-process restart,
PostgreSQL restart, remote service, live model or deployment acceptance.
