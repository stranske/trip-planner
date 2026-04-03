# Business Orchestration Boundary

Issue #548 introduces the business-planning orchestration scaffold that sits between deterministic business objectives and the external policy-evaluation system.

## In Scope

- Convert persisted trip state, business profiles, planning objectives, comparable coverage, and optional proposal packets into an explicit business planner turn.
- Represent the major business phases directly:
  - profile confirmation
  - policy-input assembly
  - comparable collection
  - ranked-option review
  - proposal preparation
  - fallback or exception preparation
- Keep compliant-first and exception-nearest paths inspectable instead of collapsing them into generic planner notes.
- Surface missing policy-ready inputs and comparable shortfalls as structured pending decisions so later runs and UIs can track them deterministically.
- Emit policy-packet outputs that point back to saved-state layers such as `policy_state_id`, `saved_scenario_ids`, and ranked option-set references.

## Out Of Scope

- Final policy evaluation or approval execution.
- Live booking, ERP, or travel-management integrations.
- Replacing the business objective derivation layer, ranking engines, or the separate policy system.

## Contract Position

`PersistedTripRecord` + `BusinessTravelProfile` + `BusinessPlanningObjectives`
-> `BusinessWorkflowContext`
-> `PlannerTurn`
-> proposal-preparation / saved-state persistence / external policy evaluation

The orchestration layer owns progression and packaging. It decides what stage the business workflow is in, what information is still missing, whether the run is staying compliant-first or carrying an explicit exception-nearest branch, and what packet should be prepared next.

The orchestration layer does not decide whether a proposal is finally approved. It prepares policy-ready state and then hands that packet to the external policy-evaluation system.
