# TPP Execution Contracts

This contract layer owns transport and execution semantics for the `trip-planner` to `Travel-Plan-Permission` boundary.

## Purpose

- keep request and response envelopes consistent across policy fetch, proposal submission, result fetch, and status polling
- represent synchronous, asynchronous, and deferred exchange patterns without forcing one transport choice
- make retry state, correlation identifiers, and integration failures explicit and testable

## Canonical Modules

- `trip_planner/integrations/tpp/contracts.py`
- `trip_planner/integrations/tpp/client.py`
- `trip_planner/integrations/tpp/policy_sync.py`
- `trip_planner/integrations/tpp/submission.py`
- `trip_planner/integrations/tpp/results.py`

## Design Rules

- Keep policy meaning in the existing business proposal and evaluation contracts.
- Use the execution layer only for request routing, status, retry, and error semantics.
- Preserve correlation IDs and request IDs across every round-trip so later sync and submission services can trace a plan through the external system.
- Allow deferred or async workflows to surface polling metadata without pretending a result is already available.

## How Later Issues Build On This

- issue `#551` uses these envelopes when importing policy constraints and organization context.
- issue `#552` should submit `TripPlanProposal` payloads inside these envelopes and read deferred or failed execution state from the same layer.
- issue `#553` should consume retry and failure records when deciding whether to reoptimize or branch into exception handling.
- issue `#554` should use the same client abstraction in test harnesses so approval-readiness flows can run against mocks or simulators.

See [tpp-proposal-execution.md](tpp-proposal-execution.md) for the submission and evaluation-result persistence boundary built on top of this execution layer.
