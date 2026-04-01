# Business Ranking

Business ranking converts `BusinessTravelProfile`, `BusinessPlanningObjectives`, optional `PolicyConstraintSet`, and bundle feasibility into ordered planning alternatives.

## Boundary

- Ranking is policy-aware but not policy-authoritative.
- The engine can reward compliant-first posture or policy-nearest fallback readiness.
- Final policy evaluation, approvals, and reimbursement logic still belong to the policy-facing workflow and external evaluation contracts.

## Output Expectations

- Ranked results use the canonical ranking contracts from `trip_planner.ranking.models`.
- Score breakdowns keep policy compliance, schedule protection, cost posture, comparables, justification readiness, comfort floors, and exception-path fit explicit.
- Confidence and risk records call out missing proposal material or unresolved feasibility friction instead of hiding them inside a single score.
