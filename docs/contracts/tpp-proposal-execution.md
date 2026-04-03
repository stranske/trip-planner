# TPP Proposal Submission And Result Storage

This scaffold defines how `trip-planner` should submit a `TripPlanProposal`, persist execution metadata, and normalize later `PolicyEvaluationResult` payloads without mixing transport state into business planning contracts.

## Canonical Modules

- `trip_planner/integrations/tpp/submission.py`
- `trip_planner/integrations/tpp/results.py`
- `trip_planner/business/policy_contracts.py`

## Submission Rules

- Submit a `TripPlanProposal` through `TPPProposalSubmissionService` using the existing `TPPRequestEnvelope` / `TPPResponseEnvelope` boundary.
- Persist the returned `ProposalSubmissionRecord` with explicit linkage for `trip_id`, `proposal_id`, `proposal_version`, and optional `scenario_id`.
- Treat `execution_id`, queue state, retry metadata, and status endpoints as transport metadata, not as business-policy verdicts.

## Evaluation Result Rules

- Normalize fetched results through `TPPEvaluationResultIngestionService`.
- Persist `PersistedEvaluationResult` records with the same proposal linkage fields so later reoptimization and approval-packaging work can follow one stable lineage chain.
- Allow pending or deferred execution states to persist without inventing a final compliance outcome.
- Only create `PolicyEvaluationResult` objects once the execution status is `succeeded` and the payload is complete.

## Separation Of Concerns

- `TripPlanProposal` remains the canonical planner-side proposal payload.
- `PolicyEvaluationResult` remains the canonical compliance and approval outcome payload.
- The new integration services only add correlation, execution, retry, and lineage metadata around those business contracts.
