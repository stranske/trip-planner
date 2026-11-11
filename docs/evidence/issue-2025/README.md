# Issue 2025 acceptance evidence

## Planner diagnosis regression check — 2026-11-11T03:06Z

The consumer ledger tests now verify the complete planner metadata blobs from
both historical heads against `fixture-provenance.json`. All three planner
tool pins already match the successful TPP checkout; the new checks reject
task-03 notes that restore the old planner-pin diagnosis. Mutating only that
sentence produces three failures; restoring the exact proposal bytes passes.
On Python 3.14.10, the existing focused command below passes 28 tests in 1.85s.
These are consumer evidence checks, not owning Workflows CI.

Both exact `gh run view ... --log` commands fail to connect from this seat.
The GitHub connector successfully reread jobs `128634593803` (failed) and
`128742727094` (successful); their checkout inputs and Ruff diagnostics match
the retained excerpts. PR #2006 is still merged at the recorded final head.
Workflows main remains five commits ahead of the regression's base and does
not include its source commit. The actual ledger is still read-only, so no
task checkbox is newly complete.

This seat also mounts `.git` read-only: staging fails when creating
`.git/index.lock`, so the test changes remain uncommitted. Attempts to add
`needs-human` and a blocker comment to #2028 were refused because connector
approval is required and this run's approval policy is `never`. An authorized
writer must commit these changes and apply the ledger proposal.

Black formats and checks the changed Python file successfully. The required
repository-wide command fails when starting multiprocessing in this sandbox.
With `BLACK_NUM_WORKERS=1` and a writable `BLACK_CACHE_DIR`, it reports 530 files
unchanged when interrupted, but the bounded invocation exits 124; this is not
a passing formatting gate. No commit or push was attempted past that gate.

Checked 2026-11-11T00:19:36+00:00. The executable acceptance checks have evidence. A2 and tasks T1, T3 and T4
still require records in the actual ledger; the proposed patch does not satisfy
that requirement. Workflows main integration is also still open.

The owning regression is published in [Workflows commit
f1ae1a4b8f704bf147938880c0010ded18d51022](https://github.com/stranske/Workflows/commit/f1ae1a4b8f704bf147938880c0010ded18d51022),
branch `codex/issue-2025`, based on `a54f412a4aea3a49241b502abf415bf769e08dea`.
It is not integrated into Workflows main. No second PR was opened, respecting
the one-PR instruction. These consumer artifacts contain no exported Workflows
source or source patch series. The previous implementation remains preserved at
`salvage/pr-2026-d9273628` in trip-planner.

## Resolver verification

From `/tmp/trip-2025-workflows`:

```sh
/tmp/trip-2025-workflows/.venv/bin/python -m pytest tests/test_dependency_resolution.py
```

The venv was created with `/opt/anaconda3/bin/python3` and uses Python 3.12.2,
pytest 9.2.0, and packaging 26.3. This is the fallback expressly permitted by
the issue; Workflows declares Python >=3.13, so supported-runtime CI remains
unverified. No warning policy or tests were disabled. The shared environment
initially failed before collection because of an unrelated pytest-asyncio
plugin; the isolated environment avoids loading that plugin.

At the linked owning commit, the eight-case suite exits 0 in 4.653 seconds.
Changing only the successful TPP fixture's Ruff pin from 0.17.3 to 0.17.2 makes
the same command exit 1 in 3.258 seconds. The successful wheels and editable
cases then print `ResolutionImpossible`. Restoring the original bytes exits 0
in 4.582 seconds. A diff against HEAD confirmed exact restoration. See
`receipts.json`, `baseline.log`, `mutation.log`, and `restored.log`.

The test uses offline metadata wheels and editable metadata preparation for
Ruff, mypy and pytest, including each historical tool mismatch independently.
It calls the production `parse_env_file` and `sync_pyproject` functions against
Workflows' actual `.github/workflows/autofix-versions.env`; one-consumer
propagation fails, and updating both consumers resolves. Full product builds
and runtime dependency installation are outside this bounded test.

Pip gets at most twenty seconds per call and shares a 100-second total budget,
leaving overhead within the issue's two-minute limit. Timeouts report an
explicit resolver failure. `fixture-provenance.json` verifies every historical
fixture's runtime dependencies and dev extra against the four original Git
blobs. TPP extras not selected by `[dev]` are omitted intentionally.

## Historical install and current classification

`failed-install-excerpts.log` and `successful-install-excerpts.log` come from
the issue's two exact `gh run view ... --log` commands. Both runs install the
local editable projects with dev extras. The failed TPP checkout is `acc4aed`;
the successful checkout is `b56d92b`. Ruff moves from 0.17.2 to 0.17.3, mypy
from 2.4.0 to 2.4.1 and pytest from 9.1.1 to 9.2.0, matching planner. The old
PyPI republication proposal is unsupported by those install inputs.

`smoke-run.json` is the exact requested `gh run view 42484305260 --repo
stranske/trip-planner --json headSha,conclusion,jobs` result. It confirms the
successful `cross-repo-full-product` job at final PR head
`fcb6e97a291bd620629aa228561d36c3ee6cdf0d`; `merged-pr.json` independently
confirms #2006 merged on 2026-11-08 at 13:23:04Z.

`sync-core-report.json` retains a fresh read of the subsequent canonical round
`20261108T133016Z`, completed 2026-11-08T13:30:21Z. It explicitly classifies
#2006 as delivered, with zero mismatches, no error and no handoffs. Canonical
target state binds that round to the final PR head. The report also records
Maint 68's `consumer-sync-run-report` artifact path; native template-sync
artifacts do not themselves classify the Maint 52 dev-pin PR. The canonical
sync-core result supplies the acceptance criterion's superseding classification.

The first Maint 68 run after the merge, [42485644055](https://github.com/stranske/Workflows/actions/runs/42485644055),
listed trip-planner in its registry inputs and had no result row for it. The
next run, [42499084007](https://github.com/stranske/Workflows/actions/runs/42499084007),
generated its report at `2026-11-08T16:19:22.356Z`. Its trip-planner result
was `created_pr` for template-sync PR #2014, with no #2006 entry. The
sync-core `delivered` record at 13:30:21Z is the post-merge disposition for
#2006 and carries no dependency-pin finding.

## Documented local check and ledger reconciliation

At the linked Workflows commit:

```sh
TMPDIR=/private/tmp npm_config_cache=/private/tmp/trip-2028-npm-cache PATH="/opt/homebrew/opt/coreutils/libexec/gnubin:/tmp/trip-2025-workflows/.venv/bin:$PATH" /opt/homebrew/bin/bash ./scripts/dev_check.sh --verbose
```

Exit 0 at the linked Workflows commit. GNU mktemp honors the writable
`TMPDIR`, Bash 5 supplies `mapfile`, and npm uses a writable cache for the
Renovate validator. The script's mypy and keepalive JS steps suppress their
own exit codes, so this receipt establishes the script's exit status.
See `owner-dev-check.log`.

At the same commit, the focused rerun passed in 4.914 seconds. The Ruff
fixture mutation failed with `ResolutionImpossible` in 3.342 seconds, and
exact restoration passed in 4.421 seconds. The owning checkout had no diff
against HEAD after restoration.

GitHub marked both Autofix jobs flagged in round 2 as canceled with no
executed steps ([run 42929978596](https://github.com/stranske/trip-planner/actions/runs/42929978596)).
The later run at the same head succeeded, with Resolve Context passing and
dispatch completion skipped ([run 42929979836](https://github.com/stranske/trip-planner/actions/runs/42929979836)).

This seat has read-only access to `.agents`. `ledger-reconciliation.patch` is
an **unapplied proposal**, not current ledger state. It reconciles tasks 05 and
14, records the owning commit and exact commands/outcomes, documents regression
coverage and mutation evidence, and records the subsequent sync classification.
Task 05 is deferred because the proposed pin/publication fix was superseded;
the proposed task 14 records the passing smoke and documented local check.
Source integration into Workflows main and the actual ledger write remain
outstanding.

## Keepalive round 3 readback

The two named run logs and final-head smoke JSON were fetched again. The owning
checkout remains clean at `f1ae1a4b8f704bf147938880c0010ded18d51022`. The focused
resolver command passed all eight tests in 4.85 seconds; the exact documented
local command above exited 0 again. See `round-3-dev-check.log` and
`round-3-readback.json` for the checked time, commands and commit. Existing
mutation/restoration receipts remain unchanged. No dependency pins were edited.

A fresh read of canonical sync-core round `20261108T133016Z` again identifies
#2006 as delivered, with zero mismatches and no dependency-pin finding in its
reasons or handoffs. The workflow report artifact path was independently
rechecked in Maint 68 at the owning commit.

T1, T3 and T4 remain incomplete because each requires writing the actual
`.agents/issue-2007-ledger.yml`, which this execution seat explicitly makes
read-only. A2 likewise remains incomplete despite the passing command. The
existing reconciliation patch is still an unapplied proposal. An authorized
writer with access to the ledger must apply and verify it; changing the path
or bypassing the restriction would not resolve the access boundary.

The reconciliation proposal now also repairs malformed YAML notes, normalizes
schema timestamps, supplies local evidence commits for completed records, and
keeps task 07 blocked pending owning-source integration. Previously, applying
the patch cleanly still produced invalid YAML. Six regression cases in
`tests/test_issue_2025_ledger_reconciliation.py` apply the proposal only to a
temporary copy of the ledger at `6f2bbe03c8b1c36c3feadf4cc56b0965c927cf5f`,
validate the entire result with the existing ledger validator (strict commit
checking), and cross-check its records against the saved install, smoke,
mutation and sync receipts. On Python 3.14.10, this command passes all 22 tests:

```sh
python -m pytest tests/test_issue_2025_ledger_reconciliation.py tests/test_dependency_version_alignment.py tests/scripts/test_validate_dependency_test_setup.py -m 'not slow' -q
```

This verifies the handoff proposal, not an actual ledger write or supported-runtime
CI for the owning Workflows regression. The ledger and the incomplete task
checkboxes remain unchanged.

This execution seat also makes `.git` read-only: staging fails while creating
`index.lock`. The attempt to add `needs-human` to PR #2028 through the GitHub
connector was rejected because it requires approval and the run's approval
policy is `never`. An authorized writer is still needed to publish these
changes and apply the ledger proposal.

The repository-wide formatting gate exited 0 with 530 files unchanged:

```sh
BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/issue-2025-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

Ruff, `git diff --check`, and `git apply --check` also passed. GitHub commit-tree
creation was separately rejected by the same approval policy, so no commit or
push was made. PR #2028 was verified open with `draft=false` at its unchanged
head `dc166cc9e14e0551b6d4c8ba5fac7718c22f809f`.

The latest reconciliation checks require the logged `TPP_PINNED_REF` selection
to match fixture provenance, require all three historical tool pins in the
proposal, and require the resolver, editable install and product-check steps to
complete successfully before #2006 merged. An in-memory mutation marking only
the resolver step skipped makes the smoke-record check fail; the unchanged
receipts pass. Timestamp comparisons now parse the recorded UTC offsets.
These checks strengthen the handoff for T1; they do not apply the ledger patch.
A fresh GitHub comparison still reports the owning source commit as diverged
from Workflows main, and no pull-request CI runs exist at that commit. The
exact `gh run view ... --log` commands could not reach GitHub from this runner;
the GitHub connector independently confirmed both historical jobs and steps.


## Keepalive round 7 readback

Checked 2026-11-11T01:47:38Z (2026-11-10 America/Chicago). Both exact
`gh run view 42484305260 --repo stranske/trip-planner --log` and
`gh run view 42449207754 --repo stranske/trip-planner --log` now succeed.
Their editable install commands and TPP checkout inputs confirm the diagnosis
above. Fresh smoke JSON and PR metadata confirm success at final head
`fcb6e97a291bd620629aa228561d36c3ee6cdf0d` and merge commit
`419015e6035cc77db18de3ab58c60651d8e51bc8`.

At owning Workflows commit `f1ae1a4b8f704bf147938880c0010ded18d51022`,
`/tmp/trip-2025-workflows/.venv/bin/python -m pytest tests/test_dependency_resolution.py`
exited 0: eight cases passed in 4.45 seconds. The exact documented local
command in the preceding section also exited 0; see `round-7-dev-check.log`.
The owning checkout remained clean. Existing mutation/restoration receipts
were retained; no dependency pins were edited.

A fresh canonical `rounds.jsonl` read confirms round `20261108T133016Z`,
timestamp `2026-11-08T13:30:21Z`, explicitly identifies #2006 as delivered,
with zero mismatches, no error and no handoffs. No dependency-pin finding
appears in its reasons or handoffs. Maint 68 at the checked owning commit
still uploads `consumer-sync-run-report` from
`artifacts/consumer-sync-run-report.json`. This remains the evidence-backed
superseding classification, rather than a claim that the template report
classifies the dev-pin PR.

`git apply --check docs/evidence/issue-2025/ledger-reconciliation.patch`
exited 0 against the actual current ledger. However, the current seat still
explicitly makes `.agents` read-only. T1, T3, T4 and A2 remain incomplete:
the verified proposal has not been applied to the required actual ledger.
No alternate path or remote write was used to bypass that access boundary.
Workflows main integration and supported-runtime CI remain unverified.

## Supported-runtime local verification

On 2026-11-11, a focused source snapshot at owning commit
`f1ae1a4b8f704bf147938880c0010ded18d51022` passed on Python 3.13.18:

```sh
cd /tmp/issue-2025-supported-runtime
/tmp/issue-2025-python313/bin/python -m pytest tests/test_dependency_resolution.py -m 'not slow'
```

All eight tests passed in 3.943 seconds of wall time. Changing the successful
TPP fixture's Ruff pin from 0.17.3 to 0.17.2 failed with `ResolutionImpossible`
in 2.871 seconds; exact restoration passed in 3.929 seconds. The JSON receipt
and `python313-*.txt` logs preserve the command, interpreter, source blob hashes
and phase results. The reconciliation test now checks this supported-runtime
evidence alongside the earlier fallback receipts.

Git clone and both historical `gh run view ... --log` commands could not reach
GitHub from this seat. The GitHub connector supplied the focused source files
and their Git blob hashes at the owning commit. Every hash was verified before
execution and after restoration, including the original pytest configuration,
conftest and production sync script. The pre-existing canonical pin file has
the identical blob hash and was read through a directory link. No protected
workflow file was changed or created.

The runner's shared Python 3.14 environment failed collection because its
AnyIO plugin imports pytest's deprecated `CallSpec2` under the owning warning
policy. The isolated Python 3.13 venv uses already-installed pure-Python pytest
and supporting distributions; no warning filter or test was disabled.

This is local verification of a source snapshot, not a complete owning checkout
or a CI result. The connector returned no workflow runs for the owning commit.
Supported-runtime CI, source integration and the actual ledger write remain
incomplete; no task checkbox was marked complete.

The updated consumer checks pass all 23 targeted tests, and Ruff, whitespace
and ledger patch checks pass. Staging the source test and receipts failed with
`index.lock: Read-only file system`, so this seat could not commit the changes.
Automatic approval review also rejected the blocker comment and `needs-human`
label because GitHub writes require approval and this run's policy is `never`.
All 530 files passed individual Black checks; the required repository-wide
Black command then exited 0 with 530 files unchanged. Its initial batch attempt
had stalled and a bounded retry timed out. Final PR #2028 readback confirmed
`state=open`, `draft=false`, at unchanged head
`7fe8ce7c414385750c0242ae1cc58b7a7e4f5f42`.

## Keepalive round 9 readback

On 2026-11-11 UTC (2026-11-10 in Chicago), both requested logs were available.
The failed and successful jobs ran the same joint editable install. The
[trip-planner fix](https://github.com/stranske/trip-planner/commit/29c6aa01)
changed `TPP_PINNED_REF` and added a dev-pin check before that install. The
new check passed all 38 cases in the successful job. The final PR head adds
the generated lockfile change on top of that fix. The failed-to-successful
head diff has no change to `.github/workflows/autofix-versions.env`.

At clean Workflows commit `f1ae1a4b8f704bf147938880c0010ded18d51022`, the
documented `dev_check.sh` invocation above exited 0 again. The focused
resolver command above passed all eight cases in 5.34 seconds using the
owning checkout's Python 3.12.2 virtual environment. A fresh sync-core
read confirmed `2026-11-08T13:30:21Z`, `delivered`, zero mismatches, no
dependency-pin finding, and the same final #2006 head in target state.

Opening the actual ledger for writing returned `Operation not permitted`.
The reconciliation proposal records these results for an authorized ledger
writer. T1, T3, T4 and A2 still require that writer to apply and verify the
records in `.agents/issue-2007-ledger.yml`.

## Checkout-metadata reconciliation check

The task-05 handoff now checks the successful checkout clause against the
selected TPP revision's preserved Ruff, mypy and pytest requirements. This
prevents a stale requirement from passing merely because it appears in the
failed-checkout clause of the same note. Changing only the preserved successful
TPP mypy requirement from 2.4.1 to 2.4.0 makes the new test fail (exit 1);
restoring the exact bytes passes (exit 0). All 24 targeted consumer checks pass.
The actual ledger and task checkboxes remain unchanged. Staging the Python test
fails creating `.git/index.lock` because `.git` is read-only. Both the blocker
comment and `needs-human` label were rejected because GitHub writes require
approval and this run's approval policy is `never`.
The required repository-wide Black gate passes with all 530 files unchanged
after individually checking the same files to populate its cache. Ruff,
whitespace and ledger-patch application checks also pass. PR #2028 remains open,
with `draft=false`, at `21bac5a711cda14fd1f16a3170b2d2737f94ad7e`.

## Keepalive round 10 readback

Both exact historical log commands and the final-head smoke JSON succeeded
again. The editable sibling checkout inputs confirm the existing diagnosis.
At clean owning commit `f1ae1a4b8f704bf147938880c0010ded18d51022`, the named
resolver command passed eight cases in 5.10 seconds; the documented local
check exited 0, including Renovate validation. Exact commands and results are
in `round-10-readback.json`; terminal local-check output is retained alongside it.

The canonical subsequent sync-core record still explicitly classifies #2006
as delivered at `2026-11-08T13:30:21Z`, with zero mismatches and no handoffs.
Maint 68's report artifact path was rechecked. The existing ledger proposal
still passes `git apply --check`. No dependency pins were changed.

Blocking: `.agents` is explicitly read-only for this execution seat. T1, T3,
T4 and A2 still require actual ledger records; a proposal cannot satisfy them.
Drainable: publish these receipts on the existing branch for the authorized
ledger writer. Source integration and supported-runtime CI remain unverified.

## Keepalive round 11 readback

Checked 2026-11-11 UTC (November 10 in Chicago). Both historical logs and the
final-head smoke receipt were retrieved again. The proposed task-03 notes now
identify the editable checkout as the conflict source and distinguish smoke
fix `29c6aa01` from the lockfile-only final PR commit. The documented Workflows
check exited 0 at clean commit `f1ae1a4b8f704bf147938880c0010ded18d51022`, and
its focused resolver suite passed 8 cases in 4.12 seconds.

Both Maint 68 artifacts were downloaded again. The first was generated at
`2026-11-08T13:36:35.802Z` and has no trip-planner result. The second reports
template PR #2014. The first post-merge sync-core record for #2006 remains
`20261108T133016Z` at `2026-11-08T13:30:21Z`. It records delivery with zero
mismatches and no dependency-pin finding. Live target state matches the merged
PR's final head.

The actual ledger is read-only in this worktree. The revised proposal awaits
application and verification by a writer with access to the ledger.

## Failed-checkout metadata and post-push review

The task-05 check now verifies the complete failed TPP `pyproject.toml` against
its original Git blob `d34416935f17cecd6aa17563e9acfd6c7f19ad51`, then derives
the Ruff, mypy and pytest requirements from that source. An incorrect mypy
diagnosis in a temporary proposed ledger fails; restoring the note passes.
All 25 targeted consumer tests and Ruff pass. The actual ledger is untouched.

At `2026-11-11T02:42:37Z`, post-push review of unchanged head `6be78cf5`
confirmed successful CI, Gate and Cross-Repo Smoke, more than seven minutes
after the latest PR update. See `post-push-review.json`. The active Workflows
integration and actual-ledger findings remain unresolved. The older shallow
checkout finding is superseded by committed fixtures. These results concern
the existing pushed head; they do not establish owning Workflows CI or review
of the current local follow-up. Reviewing the recent commits found no other
newly completed task. Automatic approval review rejected the PR-body update
and `needs-human` label because GitHub writes require approval and this run's
policy is `never`; remote task checkboxes remain unchanged.

The full repository Black gate passed with all 530 files unchanged after
verifying files individually and saving their verified results in a writable
cache. Whitespace and ledger patch checks pass. Staging the focused test,
original producer fixture and review receipt failed at `.git/index.lock` with
`Read-only file system`, so no commit or push was made. Final PR readback
confirmed open, `draft=false`, at unchanged head `6be78cf5`.

## Keepalive round 12 readback

Both exact historical log commands and the requested smoke JSON command exited
0. The successful run confirms the joint editable install with TPP checkout
`b56d92b389736c70370aa9134f379ac8cd1f3ad1`, replacing failing checkout
`acc4aeddee5f4ffefbdc73fcb07505cd3d198197`; no PyPI republication was needed.
PR #2006 remains merged at final head
`fcb6e97a291bd620629aa228561d36c3ee6cdf0d`.

At clean owning Workflows commit `f1ae1a4b8f704bf147938880c0010ded18d51022`,
the named resolver command passed eight cases in 4.92 seconds and the exact
documented local command exited 0. See `round-12-readback.json` for the check
time, commands and commits, and `round-12-dev-check.log` for terminal output.
No source or pin changes were made. Existing mutation receipts remain unchanged.

The canonical subsequent sync-core round `20261108T133016Z` was read again;
its #2006 record remains delivered with zero mismatches, no error and no
handoffs. Maint 68 still reports through `consumer-sync-run-report` at
`artifacts/consumer-sync-run-report.json`. The existing patch passes
`git apply --check`.

Blocking: the execution profile explicitly grants read-only access to `.agents`.
The actual ledger remains unchanged, so T1, T3, T4 and A2 remain incomplete.
Drainable: publish these fresh receipts on this existing branch; a writer with
ledger access must apply and verify the reconciliation proposal. Source
integration into Workflows main and supported-runtime CI remain unverified.
