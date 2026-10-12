# Issue 1842: revalidate parsed receipt evidence

The accepted producer receipt contract remains a dependency of the first handoff
task. Full authenticated preparation and workspace status return are incomplete:
the planner has partial portal answers and its own account session, while producer
`3010e3e39eb0ae039a1e648f957d8e87441d8e2a` requires complete answers and an
individual TPP identity. A shared service identity cannot authorize receipt reads.

This round advances truthful receipt handling. Pydantic previously reran the
receipt's model validator but skipped field validation for an existing model
instance. A transport model changed with `model_copy` could establish an invalid
producer digest or preserve invalid submission identifiers, states and decisions;
an invalid observation timestamp escaped as `TypeError`. Receipt models now
always revalidate their fields before preparation or observation validation.
Errors retain the existing generic contract message, and valid observations keep
their original evidence. This change grants no authentication or read authority.

Validation on 2026-10-12:

- Existing focused backend baseline: 397 passed with `-m "not slow"`.
- New regression selection before the fix: 10 failed, 4 passed. After the fix,
  all cases pass in the focused suite.
- Portal receipt, portal mapping, saved handoff and public schema suite:
  411 passed with `-m "not slow"`.
- Changed-file Black at line length 100, Ruff, mypy and `git diff --check` pass.
- Required repository Black check passes: 481 files unchanged. One worker and
  a temporary selector timeout cap under `/tmp/trip-planner-receipt-checks`
  accommodate the sandbox's blocked asyncio wakeup sockets; repository validation
  rules and assertions are unchanged.
- Exact complexity command `python scripts/measure_complexity.py --changed-from
  origin/main --max-complexity 25` passes for all 36 changed functions.

Recent commits through `7eb753e6` were reviewed. Saved trip/price/full-policy-result
hash binding, caller payload rejection, HTTPS origin validation and private source
snapshots are verified; the reconciled PR body is saved at
`/tmp/trip-planner-1872-reconciled-body.md`. No full-product criterion is newly
completed. The run-context claim that authenticated receipt integration is complete
is contradicted by the implementation and the live PR's unchecked recovery task.

Automatic approval review rejected the PR body update, `needs-human` label and
blocker comment because connector writes require approval while this run's policy
is `never`. No remote mutation was applied. The protected cross-repo workflow still
pins `ac3bfb9f39e7a3144cbe19fd1894d333dfe93b75`; an authorized lane must update
that pin and run the real two-app gate after full integration. Browser checks and
hosted exact-head gates remain required.

The shared `.git` mount rejects staging with a read-only filesystem error. The
source commit is preserved in `/tmp/trip-planner-1872-receipt-commit`, with an
apply-ready patch at `/tmp/trip-planner-1872-receipt.patch` and a portable bundle
at `/tmp/trip-planner-1872-receipt.bundle`. The owning writable lane must apply
and publish the commit; the tested edits also remain in this working tree.
