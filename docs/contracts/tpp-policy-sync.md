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

## Consumption Rules

- Ranking and candidate-generation flows may read imported channels, class-of-service limits, documentation rules, and comparable requirements as planning inputs.
- Orchestration flows may use freshness and invalidation metadata to decide whether policy imports must be refreshed before candidate generation or proposal submission.
- Imported policy data must stay advisory inside `trip-planner`; final compliance decisions still belong to `Travel-Plan-Permission`.
- When a snapshot is stale or invalidated, the planner should treat it as unsuitable for final business recommendations and request a fresh import rather than silently trusting it.

## Issue Boundary

- issue `#551` owns import and normalization only
- issue `#552` should wrap proposal submission in the same execution envelope boundary
- issue `#553` should use stale or failed sync outcomes to trigger retries or alternative flows
- issue `#554` should plug the sync layer into approval-readiness and end-to-end harnesses
