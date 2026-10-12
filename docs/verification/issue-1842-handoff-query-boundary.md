# Issue 1842: production handoff query boundary

This round advances the first unchecked task with 16 route-level regressions.
The existing unit tests call the JSON guard directly; the new tests exercise the
authenticated production handoff endpoint with an empty JSON body and caller facts
in query parameters. They cover destinations, form fields, traveler names, and
duplicate destination keys, for compliant and non-compliant saved verdicts and
both initial preparation and retries.

Each rejected request returns a generic 422 before generating traveler fields.
It preserves the private source snapshot, saved evaluation, preparation history,
and trip timestamp. A clean retry still returns the configured HTTPS destination,
POST method, saved traveler facts, and original snapshot hash, with manager
submission and decision unknown. No new policy transport operation occurs.

Validation on 2026-10-12:

- The new regression cases passed: 16 passed, 92 deselected.
- The broader handoff and proposal suite passed: 583 passed, using
  `pytest tests/app/test_portal_handoff_request.py tests/app/test_proposal_handoff_schema.py tests/app/test_portal_handoff_flow.py tests/app/test_proposal.py tests/integrations/test_tpp_portal_handoff.py tests/integration/test_saved_portal_handoff.py -m "not slow" -q`.
- The required full-repository Black check at line length 100 passed: 486 files
  would be left unchanged.
- Ruff and `git diff --check` passed.

The test and Black runners used a temporary selector timeout cap under
`/tmp/trip-planner-query-checks` to accommodate the sandbox's blocked asyncio
wakeups. Black used one worker and the standard asyncio loop. Repository runtime
code and test assertions were unchanged by these runner accommodations.

No task checkbox is newly marked complete. Frontend browser behavior and the
real pinned producer contract were not verified in this round. Full authenticated
correlated receipt/status return remains in scope pending accepted producer
#1658; these tests do not reduce that authorization to preparation only.

The shared checkout's `.git` directory is read-only, so staging and committing on
the working branch failed. The tested source change and this note are preserved
as a commit in `/tmp/trip-planner-query-commit`, with a patch and bundle under
`/tmp/trip-planner-query-checks` for application by the owning writable lane.
GitHub API access also failed, preventing PR checklist updates, blocker comments
and labels, and verification that PR #1872 remains open and ready for review.
