# Issue 1842: authenticated handoff session ownership

This round advances the first unchecked handoff task with ten integration cases.
The tests exercise the production app with real persisted authentication sessions
and no authentication or database dependency overrides. The producer client is a
test double; these tests establish consumer behavior, not accepted producer behavior.

The tests verify that forwarded identity headers cannot replace the session owner,
saved traveler facts, or server-configured portal origin. Missing, expired, revoked,
and different-owner sessions are rejected before producer preparation, browser
capability issuance, or receipt reads. Both initial authenticated preparation and
bound retries preserve the saved verdict on rejection and allow a valid owner retry.
Public workspace responses retain status metadata without exposing private authority.

Validation on 2026-10-12:

- 783 focused handoff, preparation, receipt, and request/schema tests passed with
  `-m "not slow"`, including all ten new session-owner cases.
- The required repository-wide Black check at line length 100 passed:
  489 Python files unchanged. Ruff and the staged diff whitespace check passed.
- The sandbox's blocked asyncio wakeups required a temporary polling runner under
  `/tmp/trip-planner-verification`; Black used one worker. These accommodations do
  not change repository code or test assertions.
- PR #1872 was verified open and ready for review using the GitHub connector.

The frontend dependencies are unavailable in the offline npm cache, and no pinned
TPP checkout is present. Native browser and real producer acceptance were not rerun;
the complete handoff task is not newly marked complete. The original `.git` directory
is read-only, so the source commit and apply-ready patch are prepared in a writable
isolated checkout under `/tmp/trip-planner-handoff-session`.
