# Issue 1842: live traveler session isolation

This round advances the first unchecked task with HTTP regressions for first
preparation and retries. Two independent cookie jars hold live server-issued
sessions, each owning a different saved trip and policy verdict. Each session
receives only its own form, using the same server-configured POST destination.
Cross-owner preparation returns the same public error as a missing trip before
the form mapper runs, and leaves private snapshots and trip timestamps unchanged.
Authorized retries retain the original preparation metadata. The tests also
verify that preparation does not contact the policy transport.

Verified on 2026-10-12:

- Existing handoff and saved-state baseline: 303 passed with `-m "not slow"`.
- New session-isolation regressions: 2 passed, 82 deselected.
- Combined app handoff, schema and proposal regression run: 187 passed with
  `-m "not slow"`.
- Changed-file Black, Ruff and mypy passed; `git diff --check` passed.
- Required repository Black check at line length 100: 481 files unchanged.
- Exact Complexity guard command with `--changed-from origin/main
  --max-complexity 25`: passed for 36 changed functions.

ASGI tests and the repository Black check used a temporary selector timeout cap
in `/tmp/trip-planner-handoff-owner-checks/sitecustomize.py`. This accommodates
sandbox-blocked asyncio wakeups without changing repository code or assertions.

No task checkbox is completed by these HTTP checks. Native browser verification
remains unavailable: offline npm installation lacks `xmlchars-2.2.0.tgz`, and
Chromium fails because its socket operation is prohibited. The accepted producer
receipt/status integration and hosted checks remain pending; these tests do not
reduce the owner-authorized product scope or claim manager submission or decision.

The shared `.git` mount rejected staging as read-only. The source commit is
preserved in `/tmp/trip-planner-handoff-owner-commit`, with a patch and bundle in
`/tmp/trip-planner-handoff-owner-checks` for the owning writable lane. GitHub API
connectivity was unavailable, so PR readiness and remote task state could not be
verified or updated. No protected workflow was edited.
