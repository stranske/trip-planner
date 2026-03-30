# Business Objective Derivation Boundary

Issue #518 introduces a deterministic handoff layer between business-profile inputs and later option generation or ranking.

## In Scope

- Convert `BusinessTravelProfile` plus `PolicyConstraintSet` inputs into `BusinessPlanningObjectives`.
- Preserve structured explanation output for channel restrictions, schedule protection, comparable capture, justification readiness, comfort-floor protection, cost posture, and exception-path posture.
- Keep objective shaping deterministic so fixture-driven tests can assert materially different business planning postures.

## Out of Scope

- Final ranking of airfare, lodging, or transport options.
- Policy evaluation execution inside this repository.
- Live booking-channel integrations or approval workflow UI.

## Contract Position

`BusinessTravelProfile` + `PolicyConstraintSet` -> `BusinessPlanningObjectives` -> option generation / proposal assembly / ranking

This derivation layer owns planning posture only. Later proposal assembly and ranking layers consume the objective bundle but remain responsible for concrete option selection and policy-review packaging.
