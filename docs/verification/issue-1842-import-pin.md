# Issue 1842: pinned portal dependency imports

The real portal contract now checks every loaded `travel_plan_permission` module
and package search path against the selected checkout, before and after importing
the producer and after handling portal requests. Checking only `http_service.py`
could accept a cached policy/authentication dependency from another installation.
The gate rejects foreign paths, unresolved source metadata and source symlinks
that resolve outside the selected checkout. It does not replace cached modules.

## Verification on 2026-10-10

- Checkout/import/handoff/receipt tests: **194 passed**, using `-m "not slow"`.
- Existing app handoff/proposal/schema and saved-handoff tests: **98 passed**,
  using `-m "not slow"`.
- Replacing the new guard with a no-op in the test process: **6 failed, 1 passed**;
  each failure is the intended missing rejection. Repository source was unchanged.
- Changed-file Mypy and Ruff passed; `git diff --check` passed.
- Required repository-wide Black check at line length 100: **481 files unchanged**.

App/Black checks used the temporary selector-wait workaround documented in
`issue-1842-handoff-metadata.md`. Pytest plugin autoload was disabled; these suites
use no plugin-specific fixtures. No existing tests were skipped or disabled.

## Reconciliation and remaining work

Recent commits through `7ea4c0e6` implement the original preparation, snapshot
binding, unknown-state display and policy-check/Print wording tasks. Their
existing backend regressions pass above. Frontend tests could not rerun: the
offline cache lacks `xmlchars`, and the registry is unreachable. The current
real producer checkout is absent; cloning it also failed due to unavailable DNS.
The new pinned-app gate therefore still requires a hosted real-producer rerun.

Producer PR1659 is merged at `3010e3e39eb0ae039a1e648f957d8e87441d8e2a`.
Its accepted `portal-receipt/v1` contract requires complete answers and individual
TPP authentication. This consumer retains partial answers and a local account
session. Full receipt/status integration remains incomplete. Updating the hosted
producer pin belongs to the high-privilege lane; no workflows were edited here.

The reconciled checklist is saved at `/tmp/trip-planner-1872-reconciled-body.md`.
The connector rejected the PR-body update because approval is required and this
run's policy is `never`. Git staging failed because `.git` is read-only, so no
commit was created. A patch is saved at `/tmp/trip-planner-1872-import-pin.patch`.
