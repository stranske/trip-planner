# Persistence Architecture

This document defines the first-pass storage boundaries for the persistence epic tracked by issue `#537`.

The goal is to make saved trips, user state, scenario history, budgets, and long-lived planning sessions durable without collapsing them into one opaque payload.

## Design Intent

- Keep persistence concerns aligned with the domain boundaries already established in `trip_planner/contracts/`, `trip_planner/preferences/`, `trip_planner/business/`, and the persisted-state layer under `trip_planner/state/`.
- Preserve version history and auditability for planning artifacts that are expected to change over time.
- Keep repository and storage interfaces abstract so later implementation can target local files, SQL stores, document stores, or hybrid backends without redesigning the core records.

## Bounded Contexts

### 1. User And Traveler Profiles

Owned by issue `#538`.

- durable user identity references
- leisure profile snapshots and revisions
- business profile snapshots and revisions
- traveler-party defaults and reusable travel preferences

Design rule:
Profile persistence should store versioned profile records and references from trips rather than embedding mutable profile blobs inside every trip record.

### 2. Trip Records

Owned by issue `#539`.

- canonical trip record
- trip metadata and lifecycle state
- trip-to-profile references
- artifact references for downstream planning outputs

Design rule:
The trip record is the durable container and index key, but it should not inline scenario history, session logs, or spend ledgers.

### 3. Saved Scenarios And History

Owned by issue `#540`.

- named scenarios
- checkpoints
- version history
- branch/fork lineage for alternate plans
- immutable snapshots of scenario inputs and outputs

Design rule:
Scenario history should be append-oriented and auditable so the planner can explain how a recommendation evolved instead of only exposing the latest state.

### 4. Budgets And Actual Spend

Owned by issue `#541`.

- planned budget envelopes
- category allocations
- actual spend events
- variance summaries
- business-policy-sensitive cost tracking artifacts

Design rule:
Budget plans and actual spend should remain separate ledgers so later comparison and compliance logic can reason about drift instead of overwriting planned assumptions.

### 5. Planning Sessions And Activity Logs

Owned by issue `#542`.

- long-lived planning sessions
- orchestrator handoff state
- decision checkpoints
- user/system activity logs
- resumable workflow status for collaborative and in-trip planning

Design rule:
Session state should capture interaction and workflow continuity, not replace the canonical trip or scenario records.

## Shared Persistence Rules

Every persistence context above should follow the same baseline rules:

- every durable record gets a stable primary identifier
- mutable records expose an explicit schema version
- audit-relevant updates capture `created_at` and `updated_at`
- append-only history records capture lineage to the parent trip and, where relevant, scenario or session identifiers
- cross-context references use identifiers instead of embedded mutable blobs

## Recommended Repository Shape

The implementation work for this epic should align with the current `trip_planner.state` module layout, with submodules that map to the bounded contexts above:

- `trip_planner.state.profiles`
- `trip_planner.state.trips`
- `trip_planner.state.scenarios`
- `trip_planner.state.budgets`
- `trip_planner.state.sessions`

Those `trip_planner.state.*` modules should define repository contracts and storage-facing record shapes while continuing to reuse the planning contracts from `trip_planner/contracts/` as the canonical domain layer. The lightweight `trip_planner.persistence` namespace in this PR is only a planning marker for the bounded contexts and child-issue map; it does not replace the existing `trip_planner.state` package.

## Child Issue Map

Issue `#537` remains the epic and sequencing layer for the persistence work:

- `#538` defines persisted user and traveler-profile contracts
- `#539` defines trip repositories and trip persistence boundaries
- `#540` defines saved scenario, checkpoint, and version-history contracts
- `#541` defines budget-plan and actual-spend persistence contracts
- `#542` defines planning-session and activity-log persistence contracts

## Non-Goals For This Epic

- final database or cloud vendor selection
- frontend account implementation
- collaborative sharing features
- a single serialized state blob that mixes user, trip, scenario, spend, and session data
