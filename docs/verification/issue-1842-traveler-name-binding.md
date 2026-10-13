# Issue 1842: saved traveler name at the browser handoff boundary

Six new route regression cases advance the first unchecked task's server-owned
browser POST handoff. They change the authenticated account's display name after
policy submission, evaluation, or preparation, for both compliant and noncompliant
verdicts. The owner and live session stay the same.

Each case proves that the existing snapshot check rejects the changed name before
form mapping and leaves the saved proposal unchanged. Refreshing the original
execution cannot rebind its evaluated traveler name. A fresh policy submission
and evaluation permit preparation with the current Unicode name, a different
snapshot hash, the fixed `/portal/handoff` action, and POST fields. Preparation
does not make another policy transport call; manager submission and decision stay
unknown, and the internal snapshot stays out of public handoff metadata.

Validation on 2026-10-13:

- Focused handoff suite: **592 passed**, with `-m 'not slow'`, across
  `tests/app/test_portal_handoff_flow.py`, `tests/app/test_portal_handoff_request.py`,
  `tests/app/test_proposal_handoff_schema.py`,
  `tests/integration/test_saved_portal_handoff.py`,
  `tests/integration/test_workspace_portal_preparation.py`, and
  `tests/integrations/test_tpp_portal_handoff.py`.
- All six new cases also passed after the final optional-metadata assertion was
  added for mypy.
- Relevant-file Black formatting and the required repository-wide Black check
  at line length 100 passed (489 files unchanged). Ruff, mypy for the changed test
  file, and `git diff --check` passed.

Normal async waits stalled in this sandbox. The HTTP suite and full Black check
used a temporary runner under `/tmp/trip-planner-handoff-checks` that caps idle
selector waits at 10 milliseconds. Application code and test assertions were
unchanged; this runner is not committed.

No task checkbox is marked complete. The accepted pinned TPP checkout is absent,
so the real two-app contract and manager decision/status round trip were not
verified. Hosted checks and exact-head review remain required. The newer
authenticated-status scope remains in force despite the older no-receipt wording
in the PR body.

Delivery: the shared `.git` is read-only, so local staging failed. GitHub tree
creation was rejected because it requires approval while this run's approval
policy is `never`. The source commit is preserved in
`/tmp/trip-planner-traveler-name-commit`, with an apply-ready patch and bundle at
`/tmp/trip-planner-traveler-name.patch` and
`/tmp/trip-planner-traveler-name.bundle`. The changed files remain in the workspace
for automation pickup. PR #1872 was observed open and ready for review at
`ac7d474c909505a4512355d76835ad642b0f7656`.
