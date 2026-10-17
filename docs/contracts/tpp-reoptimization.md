# TPP Reoptimization And Exception Routing

This scaffold defines the planner-side reaction layer that consumes a `PolicyEvaluationResult` and turns it into explicit scenario follow-up work.

## Canonical Modules

- `trip_planner/integrations/tpp/reoptimization.py`
- `trip_planner/business/policy_contracts.py`
- `trip_planner/state/scenarios.py`

## Design Rules

- Keep policy evaluation external: the planner reacts to `PolicyEvaluationResult`, but does not reinterpret policy rules locally.
- Produce deterministic routing:
  - preferred alternatives narrow or rerank the compliant lane
  - fixable blocking failures regenerate a compliant scenario
  - exception-required outcomes create an explicit `exception_nearest` candidate
- Preserve planner evidence:
  - comparable refs stay attached by affected category
  - justification refs stay attached for exception packets and later review
- Emit saved-scenario compatible outputs by building `ScenarioVersion` and `ScenarioComparison` scaffolds from the current business scenario lineage.

## Output Contract

`TPPReoptimizationService.plan_reoptimization(...)` returns a `PolicyReoptimizationPlan` that captures:

- the selected planner action (`rerank`, `narrow_candidates`, `regenerate_scenario`, `create_exception_candidate`, or `manual_review`)
- the target saved-scenario label (`compliant_first` or `exception_nearest`)
- affected categories and ranking focus areas
- preserved comparable and justification references
- required approval roles and failure-code summaries

The plan can then materialize:

- a follow-up `ScenarioVersion` via `build_candidate_version(...)`
- a `ScenarioComparison` via `build_comparison(...)`

That keeps the reaction step inspectable before later issues wire it into full business orchestration.

## Native submission lineage

The Policy-tab submission builder resolves the selected scenario's current persisted
`ScenarioVersion` from the owned workspace. Both its request payload and stored proposal
carry `source_version`; generic submission persistence independently derives it from the
validated scenario ID rather than trusting caller-supplied lineage. The version is a
submission-time snapshot: later scenario edits and application restarts do not change the
source version used by the reoptimization plan. Saved baseline/fallback versions can be
source snapshots; generated target labels remain `compliant_first`/`exception_nearest`.

When no persisted version matches the selected scenario (including a trip-level submission
without a materialized scenario), a non-compliant verdict exposes
`follow_up.status = no_scenario_lineage`, `path = manual_review`, and
`recommended_action = materialize_scenario`. `POST /api/workspace/{trip_id}/proposal/reoptimize`
returns HTTP 200 with that same explicit disposition and no `reoptimization_plan`. Plan and
save a scenario, then resubmit before requesting a plan; an unrelated bootstrap or
caller-provided version is not substituted.

Local gates: `pytest tests/app/test_proposal.py::test_native_submit_then_reoptimize_without_injected_source_version`
and `pytest tests/app/test_proposal.py::test_proposal_state_persists_across_create_app_restart`.
The native test materializes the scenario through the public saved-scenarios API and submits
through `/proposal/submit`; it never injects proposal lineage. Controlled TPP responses prove
planner persistence and routing, not deployed cross-repository approval. Raw JUnit and
serialized production removal/restoration evidence are retained in `docs/evidence/issue-1904/`.

When several saved scenarios share an itinerary ID, lineage follows the current saved scenario; an explicit saved-scenario ID takes precedence. `REOPTIMIZATION_SOURCE_LABELS` defines the supported source labels at storage, follow-up and reoptimization boundaries. Unsupported `in_trip_revision` snapshots, including older persisted records, receive the no-lineage disposition rather than an advertised operation ending in HTTP400.
