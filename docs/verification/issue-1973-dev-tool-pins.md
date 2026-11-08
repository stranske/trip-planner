# Issue #1973: dev-tool pin verification

## Completion summary — 2026-11-08

PR #2005 (commit `29c6aa01064f9eb3cbf15debd32cac3327ec43b8`) was merged to main on
2026-11-08, delivering the implementation for issue #1973. This document records the
local verification of the merged state and the deliberate incompatibility test.

The retained implementation was originally developed on `vibe/issue-1973`.
Latest merged implementation head: `29c6aa01064f9eb3cbf15debd32cac3327ec43b8`.

## Local verification results

Required runtime: Python 3.13 (project requires `>=3.13,<3.15`).
TPP checkout: `/Users/teacher/.codex/orchestrator/worktrees/Travel-Plan-Permission` at
`b56d92b389736c70370aa9134f379ac8cd1f3ad1` (matches `TPP_PINNED_REF`).

### Required-runtime local repository test — PASS

Command:
```sh
TPP_REPO_PATH=/Users/teacher/.codex/orchestrator/worktrees/Travel-Plan-Permission /opt/homebrew/bin/python3.13 -m pytest tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -q
```

Result: **79 passed in 6.00s** (exit status 0, no failures, no skips)
Runtime: Python 3.13.13
Date: 2026-11-08

### Deliberate incompatibility test — FAIL as expected

Created isolated producer copy at `/tmp/tpp_test_incompatible` with `ruff==0.17.2`
(replacing `ruff==0.17.3`). Ran:

```sh
TPP_REPO_PATH=/tmp/tpp_test_incompatible /opt/homebrew/bin/python3.13 -m pytest tests/scripts/test_cross_repo_dev_pins.py::test_planner_dev_pins_resolve_with_pinned_tpp_checkout -q
```

Result: **FAILED** (exit status 1) with message:
```
AssertionError: trip-planner and the pinned TPP revision cannot be installed together:
  ruff: trip-planner 'ruff==0.17.3' vs TPP 'ruff==0.17.2'
Move TPP_PINNED_REF in .github/workflows/cross-repo-smoke.yml to a TPP revision with matching pins, in the same PR as the pin update.
```

This correctly identifies the incompatible Ruff requirements.

### Restoration test — PASS

Restored `/tmp/tpp_test_incompatible/pyproject.toml` to `ruff==0.17.3`. Ran same command.
Result: **1 passed in 0.18s** (exit status 0)

This confirms the guard correctly rejects incompatible pins and passes with matching pins.

## Implementation relationship

PR #2005 implementation addresses the root cause identified in issue #1972:
- Issue #1972 bumped dev-tool pins (ruff, mypy, pytest) in the planner
- PR #1973 (delivered by PR #2005) applies matching pin updates and moves TPP_PINNED_REF
  to TPP commit `b56d92b389736c70370aa9134f379ac8cd1f3ad1` which carries compatible pins
- The pre-install check in `test_planner_dev_pins_resolve_with_pinned_tpp_checkout` 
  prevents the ResolutionImpossible failure described in #1973

PR #2005 commit log explicitly states: "Sync PR #1972 bumps ruff/mypy/pytest/coverage,
but the cross-repo smoke job co-installs TPP[dev] at TPP_PINNED_REF acc4aed, which still
pins the old versions -> pip ResolutionImpossible. Apply the same pin update and move
TPP_PINNED_REF to TPP main b56d92b (matching pins)."

## Acceptance criteria status

All acceptance criteria for issue #1973 are now met:

- [x] Review and retain complete current test implementation — Implementation retained from PR #2005
- [x] Reconcile focused local test evidence, including exact producer metadata — Verified with TPP at b56d92b
- [x] Establish local repository-command result using required Python version — Python 3.13: 79 passed
- [x] Deliberate incompatibility failure followed by restoration and pass — ruff==0.17.2 fails, ruff==0.17.3 passes
- [x] Complete PR #2005 lifecycle — Merged to main at commit 29c6aa01 on 2026-11-08
- [x] Establish relationship to #1972 — PR #2005 explicitly syncs with #1972 pin updates
- [x] Verify TPP_PINNED_REF alignment — Set to b56d92b389736c70370aa9134f379ac8cd1f3ad1 with matching pins

Note: Full repository test suite (`make test`) was not run per task restriction.
The focused cross-repo tests are the acceptance criterion for this issue.

## Remaining unknowns

None. All acceptance criteria are met. The implementation from PR #2005 is retained
and verified.

## Evidence summary

- PR #2005 merged to main at commit 29c6aa01 on 2026-11-08
- Local verification with Python 3.13: 79 tests pass
- Incompatibility guard correctly fails with ruff==0.17.2
- Restoration to ruff==0.17.3 passes
- TPP_PINNED_REF aligned to b56d92b with matching dev-tool pins
- Relationship to #1972: PR #2005 explicitly applies matching pin updates

Refs #1973


