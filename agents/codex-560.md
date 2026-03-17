# Issue #560 Workloop Bootstrap

This branch advances issue #560 (`[Agent] [UI] Build planner interaction and business approval-readiness surfaces`) beyond placeholder setup by defining a concrete delivery slice tied to existing planner contracts.

## Scope For This PR Iteration

- Establish an implementation-ready UI delivery plan tied to current contracts in `bundle/planner/orchestration-contracts.d.ts`.
- Define first-pass component ownership for interaction surfaces and approval-readiness surfaces.
- Capture validation targets to keep follow-up pushes issue-scoped.

## Implementation Targets

1. Planner interaction shell
- Scenario summary header
- Pending-decision queue panel
- Structured response capture actions

2. Business approval-readiness
- Policy posture summary
- Comparable options evidence table
- Justification burden checklist
- Proposal readiness indicator

3. Contract + state glue
- Keep `PlannerPanelState` as the boundary object.
- Ensure UI sections render from orchestration output counts and policy state.

## Validation Targets

- `tests/planner/test_planner_ui_docs_examples.mjs`
- `tests/planner/test_side_panel_state.mjs`
- `tests/planner/test_side_panel_typecheck.mjs`

## Notes

- This iteration is intentionally scoped to delivery planning and interface ownership so subsequent commits can implement UI behavior incrementally without reopening contract questions.
