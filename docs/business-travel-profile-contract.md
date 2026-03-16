# Business Travel Profile Contract

The canonical business-travel profile now lives in `trip_planner/business/`.

This contract is separate from the leisure preference engine by design. Business planning needs to optimize for policy fit, approved channels, documentation, schedule protection, and exception handling, not just traveler taste.

## Canonical Modules

- `trip_planner/business/schema.py`
  - schema constants for the business profile
- `trip_planner/business/profile.py`
  - `BusinessTravelProfile` and its nested records
- `tests/fixtures/business/*.json`
  - representative US-first business-travel examples for conference, client meeting, and site-visit planning

## Design Intent

- `BusinessTravelProfile` is not a variant of `LeisurePreferenceProfile`.
- Policy constraints, vendor constraints, and traveler operational needs remain distinct nested contracts.
- The contract should be rich enough to support later policy import, comparable capture, and exception handling without depending on the policy repo at runtime.

## Current Boundaries

- This package defines the profile contract only.
- It does not yet implement `TripPlanProposal`, policy-evaluation payloads, or the business optimization engine.
- It is meant to plug into the shared `trip_planner/contracts/` layer rather than replace it.
