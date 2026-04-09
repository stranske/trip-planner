# TPP Proposal Lifecycle Boundary

The workspace now persists three bounded proposal-lifecycle artifacts per business trip:

- proposal submission transport state, including the normalized `TripPlanProposal`
- evaluation-result transport state, including the latest normalized `PolicyEvaluationResult`
- a persisted follow-up lane derived from the latest policy result and any explicit workspace updates

This slice remains intentionally bounded: it does not auto-rerank scenarios or take ownership of enterprise approvals.
It does make the next step concrete inside the workspace so non-compliant and exception-required results are no longer a dead end.

Downstream work should consume:

- `proposal_state.proposal` as the last submitted approval packet snapshot
- `proposal_state.submission` for execution metadata such as `execution_id`, retry posture, and transport summaries
- `proposal_state.evaluation` for the latest policy verdict and approval/failure details
- `proposal_state.follow_up` for the current reoptimization or exception path, including selected alternatives, guidance, and any drafted exception request

Out of scope for this slice:

- automatic resubmission after non-compliant evaluations
- creating replacement scenarios from preferred alternatives
- approval-routing ownership beyond showing the required approvals and exception path in the workspace
