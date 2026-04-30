# Issue 1049 TPP Migration Verifier Disposition

Source PR: https://github.com/stranske/trip-planner/pull/1054
Verifier report: https://github.com/stranske/trip-planner/pull/1054#issuecomment-4351273331

## Scope

PR #1054 moved TPP-specific production modules out of `trip_planner/app/*` and into the canonical `trip_planner/integrations/tpp/*` tree. The provider comparison agreed the functional migration was correct, but Anthropic returned `CONCERNS` because several tracking and verifier-evidence checks were not durable after merge.

This follow-up records the durable disposition for those concerns and tightens the guard so it is only treated as an enforcing check when a pull-request diff is available.

## Canonical Choice

Chosen sub-decision: B-1.

The canonical TPP package location is `trip_planner/integrations/tpp/`, with services under `trip_planner/integrations/tpp/services/` and models under `trip_planner/integrations/tpp/models.py`.

## Rename Inventory

| Old path | New path |
| --- | --- |
| `trip_planner/app/models/tpp.py` | `trip_planner/integrations/tpp/models.py` |
| `trip_planner/app/services/tpp_polling_service.py` | `trip_planner/integrations/tpp/services/tpp_polling_service.py` |
| `trip_planner/app/services/tpp_proposal_submission_service.py` | `trip_planner/integrations/tpp/services/tpp_proposal_submission_service.py` |
| `trip_planner/app/services/tpp_result_service.py` | `trip_planner/integrations/tpp/services/tpp_result_service.py` |
| `trip_planner/app/services/workspace_state.py` | `trip_planner/integrations/tpp/services/workspace_state.py` |

No legacy shim is required on current `main`: production imports resolve through `trip_planner.integrations.tpp.*`, and the repo hygiene tests reject new production TPP imports from `trip_planner.app.services`, `trip_planner.app.models`, or `trip_planner.app.clients`.

## Guard Disposition

`scripts/tpp_migration_guard.py` enforces the PR-body decision requirement from pull-request diff context. It is intentionally skipped outside PR context because a post-merge main checkout no longer exposes the original rename diff.

Post-merge protection is covered by separate canonical-layout checks:

- `tests/test_repo_hygiene.py::test_no_tpp_files_remain_under_legacy_app_tree`
- `tests/test_repo_hygiene.py::test_no_production_tpp_imports_from_legacy_app_namespaces`

The guard-specific tests cover both failure and success in PR context:

- missing PR body + guarded rename is rejected
- PR body with a single recorded B-1/B-2/B-3 choice is accepted

## Cross-Repo Smoke Disposition

`tests/integrations/test_tpp_cross_repo_smoke.py` closes its first `TestClient` before binding a second app instance to the same persisted database. The fixture context remains responsible for final cleanup. This keeps the same persistence boundary the smoke is intended to verify while avoiding hidden shared in-memory app state.
