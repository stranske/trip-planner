# Issue #1973: dev-tool pin verification

## Current reconciliation — 2026-11-08

This note supersedes all previous open-head, uncommitted-file and local full-suite
pass claims in this file. The retained implementation is committed on
`vibe/issue-1973`; this continuation changes only this verification note.
Implementation/test head: `a5dc565c88a8c04d52772f6911515c2b665af5b6`.

Before changes, the real-input outcome was defined as all focused cross-repo
checks passing without live-check skips against the workflow's exact producer
revision. Proving command (check date 2026-11-08):

```sh
TPP_REPO_PATH=../Travel-Plan-Permission /opt/anaconda3/bin/python3 -m pytest tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -q -m 'not slow'
```

Stop rule: two attempts per relevant failure, 45 minutes total. Repair only an
observed relevant failure; preserve the implementation and dependency-pin writer.

## Diff review and local evidence

Reviewed the complete current diff against `origin/main` for both test files,
including all offline extras resolver assertions. Retain it unchanged:

- Offline wheels declare both projects' real tool requirements through `[dev]`.
  Old-producer and individual Ruff/Mypy/Pytest conflicts require
  `ResolutionImpossible`, both extras, and old/current requirements in diagnostics.
  The successful report requires both projects and all three current tools.
- The live guard compares checkout HEAD with `TPP_PINNED_REF` and compares runtime
  and dev metadata with the reviewed snapshot. Temporary Git repositories and
  live HEAD reads isolate inherited repository-location variables.
- Workflow assertions require the live pin check between planner and TPP installs.
- Re-read all three PR review threads: all resolved; no remaining thread repair.

No repository `.venv` exists. `/opt/anaconda3/bin/python3 --version` printed
`Python 3.12.2`. The exact command above printed **75 passed in 4.11s**, no skips.
`git -C ../Travel-Plan-Permission rev-parse HEAD` printed
`b56d92b389736c70370aa9134f379ac8cd1f3ad1`, equal to workflow `TPP_PINNED_REF`.

The project requires `>=3.13,<3.15` and selects Python 3.14 in `.python-version`.
The local repository command (`python -m pytest`, Makefile target `test`) has
**not** been established as passing on the required runtime. The earlier
2668-pass run excluded packaging on Python 3.12 and was not a complete pass.
No full suite was run in this continuation, per the task's explicit restriction;
no unrelated authentication code or dependency pins were changed.

## Current remote evidence and delivery linkage

PR [#2005](https://github.com/stranske/trip-planner/pull/2005) was open and ready,
mergeable at implementation head `a5dc565c88a8c04d52772f6911515c2b665af5b6`.
These are source-PR results, not regenerated-delivery acceptance:

- `gh run view 42466924662 --repo stranske/trip-planner` printed successful
  `cross-repo-full-product` (job `128688458010`, 1m33s).
- `gh run view 42466924979 --repo stranske/trip-planner --json headSha,conclusion,jobs`
  confirmed that exact source head, overall success, and successful Python 3.13
  and 3.14 jobs (`128688512781` and `128688512784`). CI is remote evidence;
  it does not supply the missing local required-runtime result.
- Original delivery #1972 is closed without merging, head
  `d679b90ac41e91f80fa96f4b43cd05a28f592680`.
- Current dev-tool delivery [#2006](https://github.com/stranske/trip-planner/pull/2006)
  is open and ready at `4ea6a28d050bbcf2233b725de13ade495f132002`.
  Its native record names plan `dev-tool-91791b44e525`, producer commit
  `7e377b7ad8cc06e506393218bc7459ba47757f01`, and empty predecessor/successor
  lists. It is the current candidate delivery, but its record does not prove a
  formal replacement relationship to #1972.
- `gh run view 42449207902 --repo stranske/trip-planner` printed failed
  `Cross-Repo Smoke / cross-repo-full-product`, job `128634653364`, at
  `Install Travel-Plan-Permission dependencies`, and failed `gate-summary`.
- Re-read issue #1973: no subsequent sync-core classification. The original
  finding remains round `20261105T030005Z` on #1972 head `d679b90ac41e`.

## Remaining acceptance

- [x] Review and retain complete current test implementation.
- [x] Reconcile focused local test evidence, including exact producer metadata.
- [ ] Establish local repository-command result using required Python version.
- [ ] Complete existing #2005 lifecycle with current-head review/merge gates.
- [ ] Owning producer/controller regenerates the affected delivery after integration
  and identifies its relationship to #1972/#2006.
- [ ] Verify regenerated delivery current-head named cross-repo job using
  `gh run view <run-id> --repo stranske/trip-planner`.
- [ ] Obtain next controller-owned sync-core classification.

Blocking/drainable pair: required-runtime local acceptance and regenerated-delivery
acceptance remain unproven / retain the implementation, reconcile evidence, push
this note and attempt normal guarded integration. Do not edit generated deliveries
or protected dependency pins, bypass merge gates, or substitute source CI for the
missing regenerated-delivery and controller evidence.
