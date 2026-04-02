# Account-State Contracts

Issue #538 introduces the first persisted account-state layer for the planner.

## What This Adds

- `trip_planner.state.accounts.User` as the durable account owner for saved trips and planning sessions
- `trip_planner.state.accounts.TravelerProfile` as the per-context profile record that can point at leisure and business planning profiles without collapsing them together
- `AccountPreferenceRecord`, `RegionalDefaults`, and `NotificationPreference` for interaction defaults, notification behavior, and locale/origin defaults
- backend-neutral repository protocols in `trip_planner.state.repositories.accounts` for loading, saving, and versioning account records

## Ownership Boundary

- Account state owns user identity, traveler contexts, defaults, and version metadata.
- Trip containers in `trip_planner.contracts.trip` should reference persisted account and profile ids instead of copying account preferences inline.
- Later persistence issues can build on this boundary:
  - issue `#539` for trip containers and lifecycle storage
  - issue `#540` for saved scenarios and checkpoints
  - issue `#542` for mutable planning-session state and activity logs

## Design Notes

- Traveler profiles can support leisure, business, or mixed planning modes through explicit profile references.
- Regional defaults remain account-level and profile-level so a user can keep one home locale while maintaining specialized traveler contexts.
- Repository protocols return lightweight `AccountVersion` metadata so implementations can keep audit history without baking in a storage backend.
