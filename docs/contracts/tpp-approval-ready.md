# Approval-Ready Packaging And Local Simulator

Issue `#554` adds two local-only helpers around the existing policy contract boundary:

- `trip_planner.business.approval_ready.build_approval_ready_package(...)`
- `trip_planner.business.simulator.PolicyEvaluationSimulator`

## Purpose

`trip-planner` still stops at the policy boundary:

- it prepares a `TripPlanProposal`
- it can package that proposal into an approval-ready or exception-ready evidence bundle
- it can run contract-faithful local simulations for CI and development
- it does not replace the authoritative policy decisions made by `Travel-Plan-Permission`

## Approval-Ready Package

`ApprovalReadyPackage` is a local business-planning artifact that bundles:

- business justification and required presence windows
- selected options, comparables, and justification records
- booking-channel summaries and approval routing
- receipt and justification field requirements
- policy posture, failure reasons, and exception guidance
- readiness checks that show whether the packet is ready to hand to an approval workflow

The package supports two planning postures:

- `compliant_first`
- `exception_nearest`

Those postures allow the same local planning state to be packaged for a clean compliant path or for an exception-oriented approval path.

## Simulator And Harness

`PolicyEvaluationSimulator` is a contract test harness for local development and CI:

- it loads fixture-backed policy evaluation cases
- it validates the proposal shape against the chosen case
- it returns a simulated `PolicyEvaluationResult`
- it can run an end-to-end simulated round trip and produce an `ApprovalReadyPackage`

This simulator is intentionally narrow:

- use it to exercise contract flows and approval-packet packaging
- do not treat it as a source of truth for policy logic
- do not embed organization-specific approval rules in the simulator beyond fixture-backed behavior
