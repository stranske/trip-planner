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

## Local keepalive round 3/12: recover T7 and verify real producer inputs

Check date: 2026-11-16, 09:02 UTC. Tested parent head:
`d74997aa9573141ef5c58832729021db1dba650b`.
Outcome: planner and the workflow-selected TPP source have no dev-tool pin
conflicts, and the focused pin/smoke guards pass against a real producer checkout.
Command printing the outcome:

```sh
TPP_REPO_PATH=/tmp/issue2038-tpp-round3 /opt/anaconda3/bin/python3 -m pytest tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -q -m 'not slow'
```

Stop rule: three attempts per failing step or 30 minutes. No implementation
repair was necessary. Result: **97 passed in 4.07s, zero skips** on Python 3.12.2.
This interpreter is below the application's supported range; the result verifies
these metadata/guard tests, not supported-runtime application execution. The full
suite was not run, following this round's explicit focused-tests-only instruction.

T7 is a formatter elision. The complete
[optimizer suggestion](https://github.com/stranske/trip-planner/issues/2038#issuecomment-6910331424)
continues the mypy sentence with Ruff compatibility and asks for the assertions
at historical lines 179 and 369 to pass. It defines four proposed tasks in total,
not four additional implementation requirements. Its claim of three independent
current pin conflicts is inaccurate: the previous TPP revision already matched
mypy and pytest; Ruff was the remaining mismatch. Existing source selection of
TPP `50992156e4a1f97c1115b6c7af84a219a3b9aae7` resolves that mismatch.

A fresh, clean TPP checkout was fetched at that exact SHA. The focused suite
verifies its HEAD, runtime/dev metadata against the reviewed snapshot, the live
planner/producer compatibility assertion, and the historical negative cases.
Thus T7's recovered compatibility and assertion requirements are verified.
No dependency pin, workflow, fixture or test code was edited in this round.
Earlier commit failures recorded above are historical; the tested changes are
already committed in the parent head.

A1 remains incomplete. Fresh `gh run view 43820524287 --repo
stranske/trip-planner --json headSha,conclusion,jobs` reports `failure` on
`65b25b559ea631d494e3dcfd624fb0126b098bbf`, including `Python CI / python 3.14`.
PR #2037 remains open and ready on that original head, rather than regenerated.
The focused result above is not a full repository test result.

A3 remains incomplete. The latest target-specific entry read from canonical
`~/.codex/orchestrator/sync-core/rounds.jsonl`, round `20261116T090144Z` at
09:01:47 UTC, still classifies #2037 as `pin-conflict`, terminal `pin-held`,
with handoff #2038. This is positive evidence that the requested clean
classification has not yet been observed, rather than an unavailable readback.

Blocking/drainable pair: regenerated-sync CI and clean classification missing /
the owning sync/controller lane can integrate the existing source repair,
regenerate #2037 through its normal source workflow, then read back the new
Python 3.14 run and subsequent classification. This round neither edits the
generated PR nor dispatches or takes over that lane. PR #2039 was read back open
and ready before this documentation-only update. T7 is complete; A1 and A3 stay
unchecked.

## Local keepalive round 4/12

On 2026-11-16, `gh run view 43820524287 --repo stranske/trip-planner --json headSha,conclusion,jobs`
confirmed that Python 3.14 still fails on #2037 head `65b25b559ea6`. The PR
still has that head. Sync-core round `20261116T091416Z` recorded the same
`pin-conflict` and `pin-held` disposition. Gate run `43836319557` passed
Python 3.14 on the repair head `358dd71e2d01`.

The focused command from round 3 passed again on the repair head with the
same TPP checkout. All 97 cases passed on Python 3.12.2. The local full suite
was outside this round's test scope.

The existing repair commit `a99e01e558b7` changes Ruff from 0.17.4 to 0.17.5
in `.github/workflows/autofix-versions.env`, `pyproject.toml`, and
`requirements.lock`. Those files have a sole writer,
`maint-auto-update-pypi-versions.yml`. The pin changes need reconciliation
through that owner as part of integrating the compatible TPP revision and
regenerating the sync PR. A1 needs the Python 3.14 run on the regenerated
head. A3 needs a subsequent sync-core result for #2037 without `pin-conflict`.

## Local keepalive round 5/12

On 2026-11-16, `gh run view 43820524287 --repo stranske/trip-planner --json headSha,status,conclusion,jobs`
confirmed that `Python CI / python 3.14` failed on #2037 head
`65b25b559ea631d494e3dcfd624fb0126b098bbf`. GitHub still reports that head.
The focused test command from round 3 passed against TPP
`50992156e4a1f97c1115b6c7af84a219a3b9aae7` on Python 3.12.2 (97 passed).
The full local suite was outside this round's scope. A1 remains open.

The latest sync-core entry for #2037, round `20261116T093115Z`, still records
`pin-conflict` and `pin-held`, with #2038 as its open handoff. A3 remains open.

The [original delivery job](https://github.com/stranske/Workflows/actions/runs/43820042445/job/133141022631)
identifies **Maint 52 Sync Dev Versions** as the workflow that created #2037
and pushed that exact head. Route regeneration through the Maint 52 owner.
The latest workflow definition prepares the generated branch from consumer main
and reuses an open PR for the same wave when it has a generated change to ship.
The pin owner and sync owner need to coordinate the Ruff 0.17.5 delivery with
the compatible TPP checkout. Verify a passing Python 3.14 job on the regenerated
#2037 head, then read the next sync-core record for that target.

## Local keepalive round 6/12

On 2026-11-16, `gh run view 43820524287 --repo stranske/trip-planner --job 133144833914 --log-failed`
showed six failures in `test_cross_repo_dev_pins.py` on the original #2037
head `65b25b559ea6`. The live configuration rejected the old TPP revision,
and synthetic negative cases and offline resolver cases also failed after
the Ruff bump. The negative guard expected planner Ruff 0.17.4 in its
diagnostic, while the generated branch supplied 0.17.5. Regenerate from main
with the #2039 workflow and regression fixes integrated so the retry includes
both sets of changes.

The two-file focused command above passed on `07a9bbfa6ff54` with the live
TPP checkout (97 passed on Python 3.12.2). The round excludes the full local
suite. Sync-core round `20261116T094313Z` still records `pin-conflict` and
`pin-held` for #2037. A1 and A3 remain open.

## Marker-aware local pin verification

On 2026-11-16, extended the guard to evaluate dependency markers for the
running interpreter with both the base distribution and the requested `dev`
extra. Previously it reported conflicts even for pins excluded from the smoke
job's installation. The 24 new cases cover both projects and dependency
sections, including active, inactive, and combined Python/extra markers.
Before the fix, 12 cases failed with false conflict reports; after the fix,
the focused two-file command passes on Python 3.14.10: **119 passed, 2 skipped**.
The two skips require a live TPP checkout. Ruff and mypy pass on the changed
test file.

The full `python -m pytest -q -m 'not slow' -x` command exits during setup
because the sandbox denies the local socketpair I/O required by `TestClient`.
This does not satisfy A1's local-suite requirement. GitHub readback shows
#2037 still open and ready at the original head `65b25b559ea6`, and #2039
open and ready. `gh run view 43820524287 --repo stranske/trip-planner --json
headSha,status,conclusion` cannot connect to the GitHub API in this sandbox.
A1 and A3 remain unchecked; regeneration and sync-core classification require
the owning external lane. No repository workflow or dependency pin was changed.

The required repository-wide Black command passes: **530 files unchanged**.
The sequential-cache workaround above was used with the project's inferred
Python 3.13/3.14 target versions. `git diff --check` passes. Committing is
blocked: `git add` cannot create `.git/index.lock` because Git metadata is
mounted read-only. The test change and this record remain uncommitted.
The blocker comment and `needs-human` label could not be applied: both GitHub
tools require approval, while this run's approval policy is `never`.
