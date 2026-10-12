# Issue 1842: recheck facts after browser form preparation

This round advances the first unchecked handoff task. The legacy browser form
path checked the proposal revision after mapping, but trip and price edits can
leave that revision unchanged. It now reloads the saved proposal, trip and prices
after validating the mapped fields and compares their snapshot hash before
persisting preparation or returning the form. The existing conditional proposal
write still prevents overwriting a newer verdict or authenticated preparation.

Eight regressions cover first preparation and retries with concurrent title edits,
price changes, price removal and a purpose edit through the production trip edit
service. A purpose edit deletes the saved verdict; preparation returns 409 without
recreating it. Other stale attempts retain the original handoff, verdict and
proposal revision, preserve the concurrent edit and refuse the obsolete verdict
on retry. The original six fact-change cases all failed before the fix because
the stale form was returned.

Verified on 2026-10-12:

- Saved-handoff regressions: 87 passed with `-m "not slow"`.
- Final eight concurrent-edit cases: 8 passed, 79 deselected.
- Final saved-handoff, production-route, authenticated preparation and receipt
  regressions: 262 passed with `-m "not slow"`.
- Portal field/origin, request-boundary and response-schema tests: 308 passed.
- Proposal route regressions: 92 passed. The final test groups total 662 passed.
- Required repository Black check at line length 100: 488 files unchanged.
- Mypy passed for both changed Python files; the changed test passes Ruff.
- Exact complexity command with `--changed-from origin/main --max-complexity 25`
  passed for 55 changed functions; `git diff --check` passed.
- The service has the same three Ruff findings as HEAD; this round adds none.

ASGI tests and Black use a temporary selector timeout cap under
`/tmp/trip-planner-handoff-freshness-checks` to accommodate sandbox-blocked asyncio
wakeups. Black uses one worker. These accommodations change no repository code or
test assertions.

No task checkbox is newly completed. The pinned sibling TPP checkout is unavailable,
so the real portal contract test skips; native browser and hosted exact-head
acceptance remain unverified. Authenticated receipt/status return remains in scope.
PR #1872 was verified open and ready for review. The shared `.git` mount rejected
staging as read-only; a writable temporary checkout is used to preserve the source
commit and patch for the owning lane.

The GitHub connector rejected adding `needs-human` and posting the verification
and blocker comment because it requires approval and this run's approval policy
is `never`; neither remote change was applied.
