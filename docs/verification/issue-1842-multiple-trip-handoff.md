# Issue 1842: isolate handoffs between a traveler's trips

This round advances the first task with a production-route regression for two
business trips owned by the same traveler. A saved verdict on the first trip
cannot authorize the second trip while its evaluation is pending. Once both
verdicts are saved, each server-owned POST contains its own destination, purpose,
prices, trip reference, policy outcome, and snapshot hash. Preparing either trip
preserves the other trip's state and requires no additional policy-service call.
Submission and decision remain unknown, and internal snapshots remain private.

Validation on 2026-10-11:

- The new regression passed independently after the final edit.
- 308 tests passed across `tests/app/test_portal_handoff_flow.py`,
  `tests/app/test_proposal.py`, `tests/app/test_proposal_handoff_schema.py`,
  `tests/integrations/test_tpp_portal_handoff.py`, and
  `tests/integration/test_saved_portal_handoff.py`, with `-m "not slow"`.
- Full repository Black check at line length 100 passed: 481 files unchanged.
- Ruff on the changed test and `git diff --check` passed.

App checks used a temporary `/tmp/trip_planner_handoff_checks/sitecustomize.py`
selector wait cap of 10 milliseconds to accommodate the sandbox's asyncio
wakeup restriction. Repository implementation and assertions were unchanged.
Black used one worker.

Frontend verification remains blocked: `npm ci --ignore-scripts --no-audit
--no-fund --prefer-offline` failed resolving the registry for
`xmlchars-2.2.0.tgz`. The pinned sibling TPP checkout is unavailable. These checks
do not establish full browser or authenticated receipt/status acceptance; no
task checkbox is newly marked complete.

The shared `.git` mount rejected staging with a read-only filesystem error.
The changes are preserved as a source commit, patch, and bundle under
`/tmp/trip-planner-1872-multiple-trip-handoff` for a writable delivery lane.
Hosted checks and exact-head review gates remain required.
