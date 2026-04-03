# Policy-Facing Proposal Contracts

The canonical policy-facing business-trip exchange contracts now live in:

- `trip_planner/business/policy_contracts.py`

These contracts define the boundary between `trip-planner` and `Travel-Plan-Permission`.

## Boundary

- `trip-planner` imports or stores a `PolicyConstraintSet`
- `trip-planner` produces a `TripPlanProposal`
- `Travel-Plan-Permission` returns a `PolicyEvaluationResult`

That boundary is intentional:

- this repo plans trips and packages policy-ready proposals
- the policy repo evaluates compliance, approvals, and exception handling

## Canonical Contracts

- `PolicyConstraintSet`
  - imported or synchronized policy input used during business-trip planning
- `TripPlanProposal`
  - proposal export with selected options, comparables, justifications, booking-channel summaries, and optional exception request
- `PolicyEvaluationResult`
  - structured response with compliance status, approval requirements, failure reasons, preferred alternatives, and exception guidance

## Planner Reaction Boundary

Once `Travel-Plan-Permission` returns a `PolicyEvaluationResult`, planner-side follow-up should move through `trip_planner/integrations/tpp/reoptimization.py`.

- `trip-planner` may rerank or narrow the compliant lane around preferred alternatives
- `trip-planner` may regenerate a compliant scenario when failures are fixable
- `trip-planner` may create an explicit `exception_nearest` candidate when policy requires escalation
- planner-side reaction should preserve comparable and justification refs so saved-scenario history remains inspectable

## Design Rules

- Keep policy constraints distinct from selected proposal content.
- Keep proposal export distinct from evaluation result.
- Avoid opaque blobs for comparables, justifications, or failure reasons.
- Do not re-encode organization-specific policy logic in this repo.
