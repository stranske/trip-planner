# Issue 1842: preserve preparation across unchanged verdict refreshes

Refreshing an unchanged saved verdict reset a prepared handoff to `eligible` and
erased its preparation timestamp. The binder now preserves `prepared` and the
original timestamp only when the evaluated snapshot hash, prior handoff hash and
current trip/price/verdict snapshot hash agree. Changed verdicts or current facts
reset preparation; fetching an old verdict cannot authorize changed trip prices.
Manager submission and decision remain unknown, and source snapshots stay private.

Four route regressions cover compliant and refused verdicts, repeated refreshes
and reloads, and verdict changes in both directions. Before the fix, the two
unchanged-verdict cases failed; all four now pass.

Checklist reconciliation after reviewing commits through `0fb378a0`:

- [x] bind the handoff to saved trip, prices and policy-result hashes
- [x] the client cannot choose the destination or supply handoff fields
- [x] require HTTPS outside local/test environments
- [x] keep internal source snapshots server-side

Verification: 312 focused backend tests passed with `-m "not slow"`; the required
repository-wide Black check at line length 100 passed (481 files unchanged).
Mypy passed for both changed Python files. Ruff passes for the changed test; the
service retains the same two pre-existing Ruff findings as HEAD. Tests and Black
used a temporary selector-wait cap under `/tmp/trip_planner_handoff_checks` because
the sandbox blocks asyncio socket wakeups; Black used one worker.

Browser-dependent tasks remain unchecked: the offline npm cache lacks `xmlchars`,
and online installation fails resolving the registry. The real TPP contract test
skips without the pinned sibling checkout. Authenticated receipt/status integration
and hosted exact-head gates remain outstanding.

Delivery: the shared `.git` mount rejects staging. A source commit, patch, bundle
and reconciled PR body are preserved under `/tmp/trip-planner-1872-preserve-handoff`.
Automatic approval review rejected updating the PR body, adding `needs-human`, and
posting the blocker comment because connector mutations require approval while
this run's policy is `never`. None of those remote changes was applied. PR #1872
was verified open and ready for review at its original head.
