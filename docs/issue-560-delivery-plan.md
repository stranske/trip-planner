# Issue #560 Delivery Plan

Issue: [#560](https://github.com/stranske/trip-planner/issues/560)

## Goal

Build planner interaction and business approval-readiness surfaces on top of the existing `PlannerPanelState` contract with clear module ownership and validation gates.

## Existing Foundation

- Contract boundary: `bundle/planner/orchestration-contracts.d.ts`
- Side-panel renderer + section switching: `bundle/planner/side-panel.js`
- Orchestration-to-UI mapping examples: `docs/scripts/planner_ui_consumption_example.js`
- Integration reference: `docs/planner-ui-integration.md`

## Work Slices

### Slice A: Interaction Surface Hardening

Files:
- `bundle/planner/side-panel.js`
- `bundle/planner/mock-state.js`
- `tests/planner/test_side_panel_state.mjs`

Outputs:
- Stable rendering for outputs / decisions / options sections.
- Deterministic empty-state copy when orchestration buckets are absent.
- Basic keyboard navigation support for section switching.

### Slice B: Approval-Readiness Surface

Files:
- `bundle/planner/side-panel.js`
- `docs/planner-ui-integration.md`
- `tests/planner/test_planner_ui_docs_examples.mjs`

Outputs:
- Consistent `policy_evaluation` to approval widget mapping.
- Visible distinction for `compliant`, `exception_required`, and `non_compliant` states.
- Proposal-readiness rendering that includes blocker counts and next required actions.

### Slice C: Type and Contract Guardrails

Files:
- `bundle/planner/orchestration-contracts.d.ts`
- `tests/planner/test_side_panel_typecheck.mjs`

Outputs:
- Explicit shape checks for interaction payloads and approval payloads.
- Failing type tests when required contract fields drift.

## Exit Criteria For Issue #560

- Planner interaction sections render correctly from contract data.
- Approval-readiness section reliably reflects policy posture and readiness state.
- Planner UI tests for state behavior, docs examples, and type checks pass.

## Follow-up Issue Routing

- If implementation requires new contract fields, file a contract-specific follow-up under epic #555 before widening UI scope.
- If policy mapping conflicts with evaluator outputs, file a policy-integration follow-up under epic #549.
