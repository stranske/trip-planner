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
