# Canonical State Seam For Broader Orchestration

This document names the **single persisted state model** that broader
orchestration work must build on. Issue
[#960](https://github.com/stranske/trip-planner/issues/960) calls this out as a
prerequisite: planner turns, tool calls, checkpoints, feedback, and TPP policy
follow-up all flow through one trip-scoped persistence model with a single
`trip_id` foreign key. New orchestration features must extend this seam, not
create parallel shortcuts.

## The seam

For a given `trip_id`, the canonical persisted state spans these tables (all
foreign-keyed to `persisted_trips.trip_id`):

| Layer | SQLAlchemy model | Module | What it owns |
|---|---|---|---|
| Session state | `PersistedPlanningSessionState` | `trip_planner.persistence.models.session` | Per-trip planning session shell (active stage, autonomy, recent presentations) |
| Planner actions | `PersistedPlannerAction` | `trip_planner.persistence.models.activity` | One row per planner turn step (user message, planner reply, tool calls) |
| Activity log | `PersistedActivityLogEvent` | `trip_planner.persistence.models.activity` | Audit trail visible in the workspace activity panel |
| Planner memory | `PersistedPlannerCheckpoint` + `PersistedPlannerMemoryArtifact` | `trip_planner.persistence.models.planner_memory` | Checkpoints + user-visible memory artifacts derived from turns |
| Proposal lifecycle | `PersistedProposalState` | `trip_planner.persistence.models.proposal` | TPP submission record, evaluation record, summary, follow-up |

The orchestration contracts in `trip_planner/orchestration/` (`PlannerTurn`,
`FeedbackLoopResult`, `InTripAdjustmentResult`, `WorkflowStateSnapshot`,
`PlannerAction`, `PlannerOutput`, `PendingDecision`, `WorkflowTransition`,
`NextStepSummary`) are the **in-memory** vocabulary. They do not own
persistence directly. The seam between in-memory orchestration and on-disk
state is:

```
PlannerTurn / FeedbackLoopResult / InTripAdjustmentResult
   --(produced by trip_planner.orchestration.* / trip_planner.app.services.planner)-->
   PersistedPlannerAction + PersistedActivityLogEvent + PersistedPlannerCheckpoint
       + PersistedPlannerMemoryArtifact + PersistedPlanningSessionState
   --(routed through trip_planner.app.services.workspace.proposal handler)-->
   PersistedProposalState
   --(reloaded through trip_planner.app.services.workspace.get_workspace_payload)-->
   workspace API consumers
```

All five persistence layers share the same `trip_id` FK. There is no parallel
"orchestration-only" persistence path. Test-only shortcuts that bypass these
tables are out of scope for production code; they belong only in unit tests
that explicitly probe a single contract.

## Design rules for new orchestration

1. **One trip-scoped state model.** Any new orchestration feature must read
   trip state from these tables (via the workspace service) and persist its
   results back through them. Do not introduce a sibling persistence model
   keyed on something other than `trip_id`.
2. **Reload-equivalent state.** Every orchestration outcome must round-trip
   cleanly: closing the FastAPI app instance, re-binding to the same SQLite
   file, and re-fetching via the workspace API must surface every artifact
   that was created. The integration test in
   [`tests/integrations/test_canonical_state_seam.py`](../../tests/integrations/test_canonical_state_seam.py)
   is the executable contract for this rule.
3. **No bypass shortcuts.** Tests that exercise orchestration must drive the
   real route handlers (or the real services they call). Do not write tests
   that mutate persistence directly to "set up" orchestration state — that
   creates shortcuts the production path has no equivalent for, and they hide
   regressions when persistence schema changes.
4. **Extending the seam adds a new persisted layer.** If a new orchestration
   feature needs persistence the table list above does not cover, extend
   `trip_planner/persistence/models/` with a new `PersistedX` table FK'd to
   `persisted_trips.trip_id` and add it to this document. The integration
   test should be extended to assert the new artifact survives reload.

## Validation

The integration test
[`tests/integrations/test_canonical_state_seam.py`](../../tests/integrations/test_canonical_state_seam.py)
demonstrates one trip moving through:

1. A planner turn (POST `/api/planner/{trip_id}/turns`)
2. A proposal submission (PUT `/api/workspace/{trip_id}/proposal`)
3. A proposal evaluation (PUT `/api/workspace/{trip_id}/proposal/evaluation`)
4. A second `create_app()` instance reading from the same SQLite file

The test fails if any of the five persisted layers loses its rows across the
app-instance boundary, or if the reload payload is missing the documented
contract fields (planner messages, planner memory checkpoint id, proposal
summary, evaluation status, follow-up state). It is the single executable
piece of evidence required by acceptance criterion 1 of #960 ("One test
demonstrates the canonical state model across planner turn, checkpoint,
feedback, and policy follow-up").

## Out of scope

- Live external travel providers (TPP is exercised via the workspace handler
  that accepts request/response envelopes; the live HTTP client path has its
  own coverage in `tests/app/test_proposal.py`).
- Frontend rendering (covered by frontend test seams).
- Workflows automation maintenance.

## Future orchestration work checklist

Before opening a PR that extends orchestration, confirm:

- [ ] The new persistence is FK'd to `persisted_trips.trip_id` (no parallel state)
- [ ] The new artifact reloads via the workspace service (no read-side shortcut)
- [ ] The integration test in `test_canonical_state_seam.py` is extended (or a sibling test added) so the new artifact's reload is asserted by name
- [ ] This document is updated with the new table and its module location
