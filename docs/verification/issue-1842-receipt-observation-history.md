# Issue 1842: receipt observation history

Reviewed recent consumer commits through `e5fe25b5` and the accepted producer
receipt contract in merged TPP PR1659 at
`3010e3e39eb0ae039a1e648f957d8e87441d8e2a`.

`validate_portal_receipt` now optionally checks the previous validated observation
for the same immutable preparation. It rejects an older observation, a changed
preparation timestamp, replacement or missing persisted submission/review evidence,
and a decision that disappears, predates its predecessor, or changes without a
new decision timestamp. It accepts identical retries and a later recorded manager
decision. Previous metadata is revalidated and checked against the current binding;
failed validation leaves the previous object unchanged and emits a metadata-free
error.

This is contract validation for the pending status integration. There is still no
consumer receipt transport or workspace caller passing the previous observation.
The change supplies neither authentication nor completed traveler answers, and does
not complete authenticated status/decision return. The existing browser handoff
continues to report manager submission and decision as unknown.

## Verification on 2026-10-11

- Before this change, the focused proposal/handoff, receipt and checkout suite
  passed 519 tests with `-m "not slow"`.
- The new history API regression failed on the prior implementation with the
  missing `previous` argument; the final receipt suite passes 70 tests, including
  20 added history cases.
- The final receipt, checkout/import gate and saved-handoff suite passes 128 tests
  with `-m "not slow"`.
- Changed-source Mypy and changed-file Ruff pass.
- The required repository-wide Black check passes: 481 files unchanged.
- Whitespace checks pass.

ASGI tests and parallel Black checks use the existing sandbox selector-wait
workaround under `/tmp/trip_planner_sandbox_checks`, plus
`BLACK_NUM_WORKERS=1`. This changes no repository source or test assertions.

## Reconciliation and blockers

The original five browser tasks and four security criteria have implementation
and regression evidence. The existing real pinned-app browser contract passed
hosted Cross-Repo Smoke run 38069836670 at producer
`ac3bfb9f39e7a3144cbe19fd1894d333dfe93b75`. Current local frontend tests cannot
run: the offline npm cache lacks `xmlchars-2.2.0.tgz`, and registry DNS/network
access fails. No sibling producer checkout is present, so the actual two-app
contract was not rerun here.

The original final preparation-only criterion is superseded by the recovery scope.
Producer issue #1658 is implemented by merged PR #1659, but full consumer
acceptance remains incomplete. The accepted receipt API requires complete portal
answers and a trusted individual traveler identity. The consumer currently has
partial prefill and its own account session. The established identity bridge was
requested from the owner; a shared service identity cannot establish ownership.

The owning high-privilege lane must update `TPP_PINNED_REF` in the protected
`.github/workflows/cross-repo-smoke.yml` to the accepted receipt revision and run
the real two-app contract after the consumer integration. No workflow file was
changed in this standard run.

Automatic approval review rejected the reconciled PR-body update, `needs-human`
label and blocker comment because connector mutations require approval and this
run's policy is `never`. The proposed body is saved at
`/tmp/trip-planner-1872-reconciled-body.md`; remote checkboxes remain unchanged.
PR1872 was verified open and ready for review (`draft=false`).

After passing the formatting/test gates, staging failed because `.git` is mounted
read-only and Git cannot create `index.lock`. No commit was created. The source
and evidence changes remain in the working tree, with an applyable patch at
`/tmp/trip-planner-1872-receipt-history.patch` for the owning automation.
