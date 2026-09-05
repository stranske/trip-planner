# TPP Policy Sync Scaffold

This scaffold imports policy constraints and organization context from `Travel-Plan-Permission` into planning-ready local contracts without making `trip-planner` the source of truth for policy evaluation.

## Canonical Modules

- `trip_planner/integrations/tpp/policy_sync.py`
- `trip_planner/business/policy_contracts.py`

## Imported Output

`TPPPolicySyncService` normalizes a successful `fetch_policy_constraints` response into:

- `PolicyConstraintSet` for ranking, candidate filtering, and business-objective derivation
- `OrganizationContextSnapshot` for approved channels, comparable requirements, approval triggers, comfort preferences, and class-of-service limits
- `PolicyFreshness` for snapshot versioning, freshness windows, and invalidation markers

## Requirement Normalization

`parse_policy_requirements` in `policy_sync.py` owns requirement parsing for HTTP
snapshots, fixture imports, and persisted workspace reloads. A boolean
`blocking: true` or wire `severity: error` normalizes to `blocking`. Canonical
`blocking` and `warning` severities are preserved, including when `blocking` is
false; an omitted severity defaults to `warning`. Code and summary must be
nonempty strings and are trimmed. Invalid severity, nonboolean blocking flags,
and malformed collections fail validation instead of silently becoming warnings.
The HTTP and persistence boundaries retain their respective `TPPContractError`
and `PersistedPolicyStateValidationError` exception types.

The regression gate is
`pytest tests/integrations/test_policy_sync.py::test_http_and_fixture_paths_normalize_blocking_requirement_severity_identically`.
It checks expected severities across all three paths. To verify sensitivity,
temporarily remove the `blocking is True` condition in the shared parser (the
HTTP adapter now delegates there), run the gate and observe the blocking cases
fail, then restore the condition and confirm the gate passes.

## Consumption Rules

- Ranking and candidate-generation flows may read imported channels, class-of-service limits, documentation rules, and comparable requirements as planning inputs.
- Orchestration flows may use freshness and invalidation metadata to decide whether policy imports must be refreshed before candidate generation or proposal submission.
- Imported policy data must stay advisory inside `trip-planner`; final compliance decisions still belong to `Travel-Plan-Permission`.
- When a snapshot is stale or invalidated, the planner should treat it as unsuitable for final business recommendations and request a fresh import rather than silently trusting it.

## Persisted Workspace Boundary

- Persisted workspace policy state stores imported constraint sets, organization context, freshness metadata, and approval-readiness guidance for the current business trip.
- That storage is intentionally not the proposal-submission system of record. It exists so the workspace can load real policy posture and required constraints before submission APIs are wired.
- Proposal submission, final policy evaluation, and exception-resolution workflows remain later execution stages and should consume the stored constraint-state as input rather than overwrite its boundary.

## Issue Boundary

- issue `#551` owns import and normalization only
- issue `#552` should wrap proposal submission in the same execution envelope boundary
- issue `#553` should use stale or failed sync outcomes to trigger retries or alternative flows
- issue `#554` should plug the sync layer into approval-readiness and end-to-end harnesses
