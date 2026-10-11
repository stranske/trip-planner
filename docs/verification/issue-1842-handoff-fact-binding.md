# Issue 1842: saved handoff fact binding

The first task's browser verification remains blocked in this runner: offline npm
installation lacks `xmlchars-2.2.0.tgz`, and the pinned producer checkout is absent.
This round therefore advances the second task's hash-binding verification.

Five additional route cases prove that changing the saved trip title, business
purpose, return date, price contributor or price capture time rejects preparation
with HTTP 409. Fetching the original policy result cannot rebind these changed facts.
An isolated mutation omitting those facts from the snapshot makes all five cases
fail because preparation incorrectly returns HTTP 200.

Four saved-route cases cover adding a price or removing the final price, for both
eligible and already-prepared handoffs. Rejection occurs before form-field mapping
and preserves the original verdict, hash, preparation history and trip timestamp.
Private snapshots remain absent from the reloaded public metadata.

Validation on 2026-10-11: 406 focused handoff, proposal and schema tests passed with
`-m "not slow"`; Black's required repository check passed (481 files unchanged);
mypy passed for both changed Python files; Ruff passed for the saved-route test;
`git diff --check` passed. HTTP tests and Black used a temporary selector timeout
cap in `/tmp/trip-planner-handoff-binding-checks/sitecustomize.py` because sandbox
socket wakeups are blocked. Repository code and test assertions were unchanged.
The real TPP contract test skipped for missing `TPP_REPO_PATH`.

No full-product acceptance checkbox is completed. Authenticated correlated status
return still requires the accepted pinned producer contract and consumer workspace
integration. Hosted checks and exact-head review gates remain required.

The shared `.git` directory is read-only. The source commit is preserved in
`/tmp/trip-planner-handoff-binding-commit`, with an apply-ready commit patch at
`/tmp/trip-planner-handoff-binding-commit.patch` and bundle at
`/tmp/trip-planner-handoff-binding.bundle`. The owning writable lane must publish it.
