# Issue 1842: preserve the authenticated path after a fresh policy check

A fresh policy result moves the previous producer binding into private version
history. The handoff route checked only the active binding when its trusted owner
client was unavailable, allowing an uncorrelated legacy browser form for the new
snapshot. It now requires the authenticated client when producer history exists.

Three regressions ingest a new evaluation through the production service after an
approved, rejected or changes-requested receipt. Each verifies HTTP 409 without
the client, unchanged stored state and timestamps, then successful preparation
with the restored client and a new snapshot/version retry key. The old decision
remains in private history; the new version reports unknown manager state. Private
snapshots, history and browser capabilities remain absent from public metadata.
These use the existing consumer client double, not a real producer acceptance test.

Validation on 2026-10-12:

- All three new regressions failed on the original guard and passed with the fix.
- 813 focused preparation, receipt, saved-handoff, proposal-route, schema, request
  boundary and portal integration tests passed with `-m "not slow"`.
- Relevant-file Black and the required repository-wide Black check at line length
  100 passed (488 files unchanged). Mypy passed for both changed Python files.
- The exact changed-function complexity command passed with maximum 25; the
  changed handoff function has complexity 21. Whitespace checks passed.
- Ruff passed for the test file. The service retains its three HEAD findings.

ASGI tests and Black used the documented selector-wait cap under
`/tmp/trip-planner-handoff-history-checks`; Black used one worker. This adjusts the
runner's blocked asyncio wakeups without changing repository tests or app code.

Browser acceptance remains blocked: npm lacks an offline package, registry DNS
fails, and installed Chromium cannot start because required socket operations are
blocked. The real portal contract skips without the pinned `TPP_REPO_PATH` checkout.
No task checkbox is completed or authenticated two-app acceptance claimed.

The shared `.git` is read-only. A source commit is retained in the writable Git
repository `/tmp/trip-planner-handoff-history-commit.git`, with its patch and bundle
under `/tmp/trip-planner-handoff-history-checks` for the owning automation to apply.
