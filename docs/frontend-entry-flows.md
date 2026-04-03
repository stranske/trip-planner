# Frontend Entry Flows

This document records the implementation boundary for issue `#557`.

The goal is to make the dashboard route act like a real application entry layer instead of a passive list of saved trips.

## What Issue #557 Owns

Issue `#557` adds:

- recent-session entry cards that reopen saved planner or approval work
- launch surfaces for new leisure trips, new business trips, and resume-existing-trip flows
- traveler-profile context panels that show what account state should seed each launch path
- representative dashboard fixtures for first-time leisure, returning leisure, and business policy-start entry states
- deterministic tests for launch selection, resume behavior, and invalid-session handling

It does not yet own the full trip workspace, maps, or deeper planner interaction surfaces. Those stay with `#558` through `#560`.

## Entry Surface Model

The dashboard now carries a typed `account_entry` payload with four responsibilities:

1. `traveler_profiles`
   The account-side profiles that should seed launch behavior without redefining domain meaning in UI-local models.
2. `recent_sessions`
   Resume targets with a saved `trip_id`, human summary, and the route that should reopen first.
3. `launch_flows`
   Mode-specific entry options for leisure, business, and resume flows.
4. `selected_launch_id`
   The currently focused launch detail so the dashboard can explain what startup data needs to be persisted.

## Persistence Expectations

The entry layer should connect to persisted state in this order:

- account identity and traveler profiles provide the initial launch context
- saved trip summaries determine whether the user is resuming or creating a new trip
- recent session records reopen the last meaningful route without recreating trip state
- workspace hydration happens after entry selection, not before

Practical rule:

- keep launch-specific meaning inside the canonical account, trip, and session records
- use shell-local state only for launch selection and deterministic resume/error handling

## Mode-Specific Startup Needs

The dashboard should keep leisure and business launches intentionally distinct:

- leisure launch emphasizes trip brief, traveler party, pace, and preference cues
- business launch emphasizes travel purpose, employer policy posture, and approval context
- resume flow emphasizes session identity, last route, and deterministic fallback handling

## Representative Fixtures

Issue `#557` ships three dashboard entry fixtures:

- first-time leisure user with no saved trips yet
- returning leisure user with saved trips and resumable planner work
- business user with policy-linked trip start and approval-aware launch context

Later issues should extend these entry states instead of replacing them with page-local mocks.
