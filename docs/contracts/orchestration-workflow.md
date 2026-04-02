# Orchestration Workflow Contracts

The canonical orchestration contracts now live in:

- `trip_planner/orchestration/actions.py`
- `trip_planner/orchestration/models.py`
- `trip_planner/orchestration/leisure.py`

These contracts define the shared workflow layer that later leisure, business, and in-trip orchestrators should build on.

## Canonical Objects

- `WorkflowStateSnapshot`
  - records the planner's current stage, status, pending decisions, and action/output references
- `PlannerAction`
  - captures explicit internal work such as deriving objectives, ranking options, or preparing policy summaries
- `PlannerOutput`
  - captures user-visible results such as questions, option sets, ranked scenarios, warnings, and policy summaries
- `PendingDecision`
  - represents a structured user checkpoint rather than an opaque free-form prompt
- `WorkflowTransition`
  - records why the planner moved from one stage to the next
- `PlannerTurn`
  - packages a single planning or adjustment pass with state, actions, outputs, transition metadata, and next-step guidance
- `NextStepSummary`
  - tells later orchestrators which action to continue next and which decision/output references are still blocking

## Design Rules

- Keep workflow state, planner actions, and planner outputs as separate concerns.
- Keep transition metadata explicit so orchestration remains explainable and testable.
- Reuse the same action and output vocabularies across leisure, business, and in-trip flows.
- Represent decision requests as structured options, not free-form strings.
- Let later orchestrators compose these contracts instead of inventing mode-specific action containers.

## Representative Fixtures

Representative fixtures live in:

- `tests/fixtures/orchestration/turns/leisure_planning_turn.json`
- `tests/fixtures/orchestration/turns/business_planning_turn.json`
- `tests/fixtures/orchestration/turns/in_trip_adjustment_turn.json`
- `tests/fixtures/orchestration/leisure/delegated_planning_flow.json`
- `tests/fixtures/orchestration/leisure/collaborative_iterative_flow.json`
- `tests/fixtures/orchestration/leisure/revised_after_feedback_flow.json`

These fixtures show how the same contract layer can express:

- a leisure checkpoint with ranked scenario outputs
- a business planning turn gated by policy posture
- an in-trip replanning turn triggered by disruption
- a delegated leisure scaffold that can auto-advance to a save-ready checkpoint
- a collaborative leisure flow that waits on a structured traveler decision
- a revision flow that returns to explicit reranking after surfaced-option feedback
