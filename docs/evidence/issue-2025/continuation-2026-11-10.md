# Continuation check, 2026-11-10

Acceptance outcome 1: the delivered Workflows resolver tests pass within 120 seconds
and its documented local validation exits 0 against an identified owning commit.
The required commands, from the owning checkout with its selected environment, are:

```sh
/Users/teacher/Library/CloudStorage/Dropbox/Learning/Code/Workflows/.venv/bin/python -m pytest tests/test_dependency_resolution.py
PATH="/Users/teacher/Library/CloudStorage/Dropbox/Learning/Code/Workflows/.venv/bin:$PATH" ./scripts/dev_check.sh
```

Before any edits, the stop rule was two failed attempts at the same access or
provisioning step, or 30 minutes. No implementation was started. The first access
failure was conclusive, so it was not retried.

## Access and preserved work

Starting consumer commit: `5862daf24e11da0bb8c3a92dc255ddf5b3923085`, branch
`codex/issue-2025`. `git worktree list --porcelain` showed this as the sole holder
of the PR branch. The two `preserved/` refs refer to issues 1973 and 1990; their
tips were inspected, and neither was changed. This worktree started clean.

The existing Workflows checkout is at
`/Users/teacher/Library/CloudStorage/Dropbox/Learning/Code/Workflows`, commit
`e0ce646599ecc6f95a604b7ce204d588b62f3754`. Its selected `.venv/bin/python`
reports Python 3.12.2. Module discovery found pytest, black, isort,
docformatter, ruff, flake8 and mypy. Their presence does not prove their versions
match the declared pins. That checkout has pre-existing untracked files and was
left intact. Both existing Workflows checkouts are outside the runner's writable
roots; owner test delivery is therefore incomplete. No substitute reconstruction
or new receipt-helper feature was made.

`git apply --check docs/evidence/issue-2025/ledger-reconciliation.patch` exited 0.
Applying that same reviewed patch exited 128:

```text
warning: unable to unlink '.agents/issue-2007-ledger.yml': Operation not permitted
error: unable to write file '.agents/issue-2007-ledger.yml' mode 100644: Operation not permitted
```

The runner explicitly makes `.agents` read-only. `git diff` confirms the ledger
is unchanged. Task 14 remains incomplete; no successful local owning validation
is claimed. The retained patch, deferred task-05 classification, dated task-16
receipt, resolver fixtures and mutation/restoration evidence remain intact.
The owning commands above were not executed because delivery access failed.

## Successful independent readback

```sh
gh run view 42484305260 --repo stranske/trip-planner --json headSha,conclusion,jobs
```

Exit 0: conclusion `success`, head
`fcb6e97a291bd620629aa228561d36c3ee6cdf0d`, job
`cross-repo-full-product` conclusion `success`. Full CLI output is retained in
`continuation-2026-11-10-smoke-run.json`. No smoke rerun was triggered.

GraphQL review-thread readback returned five threads, all resolved, with
`hasNextPage=false`; full output is retained in
`continuation-2026-11-10-review-threads.json`. No resolved finding was reopened.
`gh pr checks 2026 --repo stranske/trip-planner --required` printed:

```text
Gate / gate  pass  0  https://github.com/stranske/trip-planner/actions/runs/42871177968  Python, runtime, and cross-repo CI passed
```

PR 2026 was OPEN and `isDraft=false` at the starting head.

## Focused consumer validation

The consumer has no selected local `.venv`, so the owner-specified fallback was
used:

```sh
/opt/anaconda3/bin/python3 -m pytest tests/scripts/test_reconcile_issue_2007.py tests/scripts/test_cross_repo_dev_pins.py tests/test_dependency_version_alignment.py -q -m 'not slow'
```

Exit 0: `170 passed, 2 skipped in 5.06s`. Startup printed the installed
pytest-asyncio warning that `asyncio_default_fixture_loop_scope` is unset.
No dependency pins, existing source, tests, or fixtures were changed.

Outcome 1 remains BLOCKED on write access. Blocking/drainable pair: owning
delivery and ledger writes are blocked; CLI readback and focused consumer
validation were drainable and completed. The remaining tasks are not complete.
