# TPP Proposal Lifecycle Boundary

The workspace now persists two bounded proposal-lifecycle artifacts per business trip:

- proposal submission transport state, including the normalized `TripPlanProposal`
- evaluation-result transport state, including the latest normalized `PolicyEvaluationResult`

This slice is intentionally limited to submission/evaluation persistence and workspace display.
Later reoptimization work should treat these records as inputs, not as a replacement for re-ranking or exception handling.

Downstream work should consume:

- `proposal_state.proposal` as the last submitted approval packet snapshot
- `proposal_state.submission` for execution metadata such as `execution_id`, retry posture, and transport summaries
- `proposal_state.evaluation` for the latest policy verdict and approval/failure details

Out of scope for this slice:

- automatic resubmission after non-compliant evaluations
- creating replacement scenarios from preferred alternatives
- approval-routing ownership beyond showing the required approvals in the workspace
