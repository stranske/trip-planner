# Issue 1842: native form numeric origins

Reviewed the recent keepalive commits through `ba72303e`. The first task already
builds a server-owned POST form, but Python's URL parser accepted numeric hosts
that a browser rejects or interprets as another address. For example,
`https://999.999.999.999` cannot receive the form, while `https://127.1` becomes
`https://127.0.0.1` in the browser.

Origin validation now rejects noncanonical numeric hosts before persisting
preparation. Canonical IPv4, IPv6, and ordinary DNS origins remain available.
Tests cover both server configuration settings and local, test, and production
environments. Route tests verify HTTP 503 leaves saved state unchanged and a
corrected configuration restores handoff preparation without a fresh policy
check. A regression failed against the prior implementation before the fix.

Verified on 2026-10-11:

- Existing backend handoff, saved-state, and schema baseline: 142 passed.
- Existing app proposal/handoff baseline: 108 passed.
- Updated backend handoff, saved-state, and schema checks: 193 passed.
- Updated origin rejection/recovery route checks: 17 passed.
- Final focused handoff and proposal regression selection: 243 passed,
  31 unrelated proposal tests deselected, using `-m "not slow"`.
- Changed files formatted with Black at line length 100. Required full-repository
  Black check passed: 481 files unchanged. Whitespace checks passed.
- Handoff module and integration test Ruff checks passed. The modified app test
  file has a pre-existing `PYI034` warning on `_FakeHTTPResponse.__enter__`;
  its remaining Ruff checks passed. Handoff module Mypy passed.
- Origin-validation function complexity is 24; its new numeric-label helper is 4.

App and Black checks used the previously documented temporary selector-wait
workaround in `/tmp/trip_planner_handoff_checks/sitecustomize.py` and
`BLACK_NUM_WORKERS=1`. Repository runner code and assertions were unchanged.

The proposed reconciliation is saved at
`/tmp/trip-planner-1872-reconciled-body.md`. Verified hash binding and rejection of
client-supplied fields, HTTPS enforcement, and private snapshot metadata are
checked there. GitHub rejected the PR-body update because the connector requires
approval while this run's approval policy is `never`; remote checkboxes are
unchanged.

Browser acceptance remains unverified: the frontend command reports
`vitest: not found`. The real producer contract test skips because the pinned TPP
checkout is absent. The accepted producer receipt contract at
`3010e3e39eb0ae039a1e648f957d8e87441d8e2a` supersedes the PR's no-endpoint claim;
authenticated consumer status integration and hosted gates remain incomplete.
This change advances browser preparation and does not claim full-product
acceptance or a manager submission/decision.

The shared checkout cannot stage changes because `.git` is read-only. The source
commit is preserved in `/tmp/trip-planner-1872-numeric-origin-commit`, with a patch
and bundle for the writable owning lane. No protected workflow was edited.
