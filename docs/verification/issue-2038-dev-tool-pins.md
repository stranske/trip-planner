# Issue #2038: dev-tool pin verification

## Outcome and bounded check

Check date: 2026-11-16, local keepalive round 2. The real repository inputs must
co-resolve with the producer selected by `.github/workflows/cross-repo-smoke.yml`.
The command printing this outcome is:

```sh
/opt/anaconda3/bin/python3 -m pytest tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -q -m 'not slow'
```

Result: **86 passed, 2 skipped in 4.16s** on source head
`65c557bedde7f70f229da121fc7d93acbd2588f1`. The two skips require a live TPP
checkout. This round changes only this verification record, leaving those tested
inputs unchanged. Stop rule: two focused repair attempts or 20 minutes; no
implementation repair was needed.

## Source findings

Planner defines its development pins in `pyproject.toml`, with matching entries
in `requirements.lock`; generated pin updates have a single automation writer.
The existing source fix is commit `a99e01e55`. The workflow selects TPP
`50992156e4a1f97c1115b6c7af84a219a3b9aae7`.

| Tool | Planner | Previous TPP `5c9ec6e` | Selected TPP `50992156` |
| --- | --- | --- | --- |
| Ruff | 0.17.5 | 0.17.4 | 0.17.5 |
| mypy | 2.4.1 | 2.4.1 | 2.4.1 |
| pytest | 9.2.0 | 9.2.0 | 9.2.0 |

The selected producer's immutable `pyproject.toml` was read from GitHub again
in this round and confirms these versions. The issue's pytest 9.1.1 and mypy
2.4.0 conflicts are historical negative-test cases. The actual previous producer
already matches pytest and mypy; its Ruff pin causes this delivery's conflict.
No dependency pins were edited in round 2.

## Focused verification

Using the owner-selected fallback `/opt/anaconda3/bin/python3` (Python 3.12.2):

- The command above passed, including the existing `issue-2038-producer` pip
  resolver regression using the actual previous producer snapshot.
- `python -m ruff check tests/scripts/test_cross_repo_dev_pins.py`: passed.
- `python -m mypy --follow-imports=silent tests/scripts/test_cross_repo_dev_pins.py`:
  passed.

This runtime is below the application's Python >=3.13 requirement. These focused
metadata tests passed locally; supported-runtime execution is evidenced separately
by CI, not inferred from the local run.

For A2, only the workflow's TPP ref was temporarily restored to
`5c9ec6e15ac959023b9fc9cdd1099d70a6073396`. No dependency file was edited.
These exact tests failed (exit 1, two failures), naming Ruff 0.17.5 versus 0.17.4
and pip's `ResolutionImpossible`:

```text
tests/scripts/test_cross_repo_dev_pins.py::test_workflow_tpp_pin_resolves_with_planner_dev_pins
tests/scripts/test_cross_repo_dev_pins.py::test_pip_resolves_paired_dev_tool_pins_offline[None-None]
```

The workflow was restored byte-for-byte in a `finally` block. The same command
then passed (exit 0, two passed in 0.63s). `git diff --exit-code` confirmed no
workflow change remained. Session logs:
`/tmp/issue-2038-round2-break.log` and `/tmp/issue-2038-round2-restored.log`.

## CI and remaining acceptance

PR #2039 was read back open and ready (`draft=false`). On head `65c557bed`,
Python 3.14 and cross-repo smoke passed in
[run 43827284404](https://github.com/stranske/trip-planner/actions/runs/43827284404).
This is evidence for this repair PR, not regenerated sync PR #2037.

`gh run view 43820524287 --json headSha,status,conclusion,jobs` still reports
failure on sync PR #2037's original head
`65b25b559ea631d494e3dcfd624fb0126b098bbf`, including Python 3.14 and cross-repo
smoke. The PR readback confirms it has not been regenerated. A1 remains open;
the full suite was not run locally, as round 2 explicitly prohibits it.

A3 remains unverified: no subsequent sync-core classification was established.
The controller/sync owner must regenerate #2037 after source integration, then
read back its Python 3.14 run and the next sync-core classification. No generated
sync PR was edited or workflow dispatched by this round. While that acceptance
is pending, the focused local guard and mutation check remain runnable.

T7 contains only an elided placeholder, so its four unspecified subtasks cannot
be marked complete. T1-T6 and T8 are verified by source readback and focused
checks; A2 is verified by the deliberate-break/revert above. T4 and T6 need no
new pin edits because the required pytest and mypy values are already present.

## Round 3: fixed historical resolver inputs

On 2026-11-16, added an immutable dependency snapshot from sync PR #2037's
failed planner head `65b25b559ea631d494e3dcfd624fb0126b098bbf`. Two pip resolver
cases now use that same planner snapshot against the original TPP `5c9ec6e`
and repaired TPP `50992156`. The original pair must fail with
`ResolutionImpossible`; changing only the TPP source must resolve. These cases
retain the #2038 regression when current planner pins or the workflow ref change.
The offline wheels isolate Ruff, mypy and pytest; this does not prove a complete
cross-repo installation.

Using the available Python **3.14.10**, the focused command is:

```sh
python -m pytest tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -q -m 'not slow'
```

Result: **88 passed, 2 skipped in 4.97s**. The skips still require a live TPP
checkout. Ruff and mypy on the changed test file pass.
The required repository-wide Black command passes: **530 files unchanged**.
To avoid the sandbox's blocked asynchronous wakeups, each file was checked
sequentially first, using a temporary Black cache; the unchanged full command
then passed with that cache and `BLACK_NUM_WORKERS=1`.

- [x] Extend the regression with both original #2038 installation inputs.
- [x] Verify deliberate-break/revert: temporarily replacing Ruff 0.17.5 with
  0.17.4 in the repaired producer snapshot makes
  `test_pip_resolves_paired_dev_tool_pins_offline[issue-2038-repaired-install]`
  fail with `ResolutionImpossible`. Restoring the snapshot byte-for-byte makes
  it pass. Logs: `/tmp/issue-2038-round3-{broken,restored}.log`.

The broader `pytest -q -m 'not slow' -x` run exits during setup because the
sandbox denies local socketpair I/O needed by `TestClient`; it is not a passing
full-suite result. PR #2037 is still open and ready at its original failed head
`65b25b559ea631d494e3dcfd624fb0126b098bbf`, so regenerated-sync CI and the next
sync-core classification remain unverified. No workflow was modified this round.

Committing this round was blocked: `git add` could not create `.git/index.lock`
because `.git` is mounted read-only. The test, fixture and this record remain
uncommitted in the workspace; a run with writable Git metadata must commit them.
Attempts to add a blocker comment and `needs-human` label to PR #2039 were also
rejected: the GitHub tools require approval, while this run's approval policy is
`never`. Neither remote update was applied.

## Round 4: exercise the smoke guard with #2038 source inputs

Extended `test_smoke_pin_guard_with_historical_editable_checkouts` with the
fixed #2038 planner snapshot and both original and repaired TPP snapshots. This
exercises the smoke job's actual pin guard, in addition to round 3's isolated
pip resolver. The original pair must report only Ruff as conflicting; the
repaired pair must pass without changing planner's pytest or mypy pins.

- [x] Focused verification on Python 3.14.10: **90 passed, 2 skipped** using
  the two-file pytest command above with `-m 'not slow'`. The skips require
  a live TPP checkout. Ruff and mypy pass on the changed test file.
- [x] Deliberate-break/revert: replacing Ruff 0.17.5 with 0.17.4 in the repaired
  producer snapshot makes
  `test_smoke_pin_guard_with_historical_editable_checkouts[issue-2038-repaired-install]`
  fail with the expected Ruff diagnostic (exit 1). Restoring the snapshot
  byte-for-byte makes it pass (exit 0). Logs:
  `/tmp/issue-2038-round4-{broken,restored}.log`.

The full `python -m pytest -q -m 'not slow' -x` command exits during setup:
the sandbox still denies local socketpair I/O required by `TestClient`.
This is not a passing full-suite result. GitHub readback confirms #2037 is
still open and ready at its original head `65b25b559ea6`; #2039 is also open
and ready. `gh run view 43820524287 --json headSha,status,conclusion --repo
stranske/trip-planner` cannot connect to the GitHub API in this sandbox.
Regenerated-sync CI and the next sync-core classification remain pending.
No workflow or dependency pin was edited this round.

The required repository-wide Black check passes: **530 files unchanged**.
As in round 3, files were checked sequentially to populate a temporary cache
before running the unchanged full command with `BLACK_NUM_WORKERS=1`.
The final focused pytest rerun also passes: **90 passed, 2 skipped**.

The commit remains blocked: `git add` fails to create `.git/index.lock` with
`Read-only file system`. These two changed files need to be committed on the
existing `codex/issue-2038` branch in a run with writable Git metadata.
The blocker comment and `needs-human` label were also rejected because the
GitHub tools require approval and this run's approval policy is `never`;
neither remote update was applied.

## Round 5: verify historical workflow source selection

Extended the historical smoke-guard regression to run through both the live
checkout and offline workflow-snapshot entry points. The offline cases select
the original or repaired TPP revision using temporary test metadata and ignore
an inherited `TPP_REPO_PATH`. This verifies that source selection detects the
original Ruff conflict and accepts the repaired producer. No repository workflow
file was modified.

- [x] On Python 3.14.10, the focused two-file pytest command above passes:
  **95 passed, 2 skipped**. The skips require a live TPP checkout. Ruff and mypy
  pass on the changed test file.
- [x] Deliberate-break/revert: restoring Ruff 0.17.4 in the repaired snapshot
  makes the `workflow-snapshot-issue-2038-repaired-install` case fail with the
  expected Ruff conflict. Restoring the snapshot byte-for-byte makes it pass.
  Logs: `/tmp/issue-2038-round5-{broken,restored}.log`.

The full `python -m pytest -q -m 'not slow' -x` command still exits during setup
because the sandbox denies local socketpair I/O required by `TestClient`.
PR #2037 remains open and ready at its original head `65b25b559ea6`; PR #2039
is also open and ready. Regenerated-sync CI and the next sync-core classification
remain pending, and their acceptance checkboxes remain incomplete.

The required repository-wide Black command passes: **530 files unchanged**,
using the sequential-cache workaround documented above. `gh run view
43820524287 --repo stranske/trip-planner --json headSha,status,conclusion`
cannot connect to the GitHub API; the PR metadata readback used the GitHub tool.

Committing remains blocked: `git add` cannot create `.git/index.lock` because
Git metadata is mounted read-only. The two changed files remain uncommitted.
Attempts to add the blocker comment and `needs-human` label to PR #2039 were
rejected because the tools require approval and the approval policy is `never`.
Neither remote update was applied.
