# Issue #1967: retained repair and exact-target acceptance

## Closer continuation readback — 2026-11-11 America/Chicago (2026-11-12 UTC)

Recorded before acceptance execution at 2026-11-12T04:05Z (check date:
2026-11-11 America/Chicago / 2026-11-12 UTC):

- **Outcome command**:
  ```sh
  TPP_REPO_PATH=/private/tmp/issue2017-tpp /opt/anaconda3/bin/python3 -m pytest tests/scripts/test_cross_repo_dev_pins.py -q
  ```
- **Bounded stop rule**: one attempt per acceptance step, at most 30 minutes from
  2026-11-12T04:05Z; stop at the first unresolved failure and do not add
  diagnostic permutations or downgrade pins.

### Worktree and branch preservation

`git worktree list --porcelain` listed `refs/heads/codex/issue-1967` only at
`/Users/teacher/.codex/orchestrator/worktrees/stranske__trip-planner__2029__closer`
at HEAD `d82f0537428fbcddfd687c931baced3f3dbffcd4`, with a clean working tree.
No `preserved/` holder worktree existed for PR #2029, and no worktree was reset
or cleaned. All prior regression tests (`test_cross_repo_dev_pins.py`) and
compatible dependency pins (`ruff==0.17.4`, `mypy==2.4.1`, `pytest==9.2.0`,
`TPP_PINNED_REF: 5c9ec6e15ac959023b9fc9cdd1099d70a6073396`) are retained
unchanged.

### Acceptance step results

- [x] **Retain #2029's useful changes and run focused validation against the real workflow-pinned TPP checkout without skips**:
  ```sh
  TPP_REPO_PATH=/private/tmp/issue2017-tpp /opt/anaconda3/bin/python3 -m pytest tests/scripts/test_cross_repo_dev_pins.py -q
  ```
  Exited **0** and printed **`77 passed in 21.55s`** with **0 skipped** (plus the
  `pytest_asyncio` `asyncio_default_fixture_loop_scope` deprecation warning)
  under `/opt/anaconda3/bin/python3` (Python 3.12.2, since no repository `.venv`
  is present). This includes all 77 expanded tests on branch head
  `d82f0537428fbcddfd687c931baced3f3dbffcd4` — including the real-checkout
  compatibility and `git --no-replace-objects` provenance checks against
  `/private/tmp/issue2017-tpp` at `5c9ec6e15ac959023b9fc9cdd1099d70a6073396`
  and the offline pip resolver checks.
- [x] **PR #2029 exact-head hosted CI and Gate**:
  `gh pr view 2029 --repo stranske/trip-planner --json headRefOid,state,isDraft,statusCheckRollup`
  and `gh run view 43145189282 --repo stranske/trip-planner --json conclusion,headSha,status,url,jobs`
  confirm PR #2029 is `OPEN` (`isDraft: false`) at head
  `d82f0537428fbcddfd687c931baced3f3dbffcd4` with all checks green:
  - [Cross-Repo Smoke 43145189282](https://github.com/stranske/trip-planner/actions/runs/43145189282):
    `conclusion: "success"`, `headSha: "d82f0537428fbcddfd687c931baced3f3dbffcd4"`,
    job `cross-repo-full-product` (`databaseId: 130941249382`, `conclusion: "success"`).
  - [Gate 43145189857](https://github.com/stranske/trip-planner/actions/runs/43145189857):
    `conclusion: "success"` across `Cross-Repo Smoke / cross-repo-full-product`
    (`130941397759`), `Python CI / python 3.13` (`130941554487`),
    `Python CI / python 3.14` (`130941554513`), and `gate-summary` (`130943245487`).
  - [CI 43145189990](https://github.com/stranske/trip-planner/actions/runs/43145189990):
    `conclusion: "success"` across `Python CI / python 3.13` (`130941347406`),
    `Python CI / python 3.14` (`130941347386`), and `Product contract observations`
    (`130941252608`), resolving the earlier transient `CreateArtifact` failure on
    `92e779d3feee5de8d768f6476cf177ea53c34c14`.
- [ ] **Record the configured local test-command result (`python -m pytest`) for the final branch**:
  Explicitly unmet locally. The repository's configured test command (`Makefile`
  target `test`) is `python -m pytest`. This continuation's execution rules
  explicitly forbid running the full test suite locally
  (`Never run the full test suite locally: CI runs it on the PR`). Accordingly,
  `python -m pytest` was not executed locally, and hosted CI is not substituted
  for local full-suite execution.
- [ ] **Establish explicit native successor lineage for #1966 and successful exact-head `cross-repo-full-product` evidence**:
  Exact-head `cross-repo-full-product` evidence is verified on functional Maint 52
  successor [#2006](https://github.com/stranske/trip-planner/pull/2006), but
  explicit native `predecessor_prs`/`successor_prs` marker lineage from #1966
  remains absent:
  ```sh
  gh pr view 1966 --repo stranske/trip-planner --json headRefOid,state,mergedAt,body
  gh pr view 2006 --repo stranske/trip-planner --json headRefOid
  gh run view 42484305260 --repo stranske/trip-planner --json conclusion,headSha,status,url,jobs
  gh run view 42484305671 --repo stranske/trip-planner --json conclusion,headSha,status,url,jobs
  gh run view 41674233862 --repo stranske/trip-planner --json conclusion,headSha,status,url,jobs
  ```
  - `#1966` remains `CLOSED` (`mergedAt: null`) at `headRefOid`
    `164ed1a02b126e72ce407620829e40aa92925a53` (`plan_id: "dev-tool-44505f50de37"`,
    `source_commit: "2bd1aa094698d3e9f2ce91f754f6b00fb748a52d"`,
    `desired_tree_hash: "2824d328ae1c8b645d07f9e73aecf0a51145efc5"`,
    `"predecessor_prs":[],"successor_prs":[]`). Original [run 41674233862](https://github.com/stranske/trip-planner/actions/runs/41674233862)
    on `164ed1a02b126e72ce407620829e40aa92925a53` remains `conclusion: "failure"`.
  - `#2006` (`plan_id: "dev-tool-91791b44e525"`, regenerated by Maint 52
    `maint-52-sync-dev-versions.yml` run `42484255917` and merged at
    `419015e6035cc77db18de3ab58c60651d8e51bc8`) delivered the same
    `ruff==0.17.3`, `mypy==2.4.1`, `pytest==9.2.0` payload at `headRefOid`
    `fcb6e97a291bd620629aa228561d36c3ee6cdf0d`. At that exact head, both
    [Cross-Repo Smoke 42484305260](https://github.com/stranske/trip-planner/actions/runs/42484305260)
    (job `cross-repo-full-product`, `databaseId: 128742727094`,
    `conclusion: "success"`) and [Gate 42484305671](https://github.com/stranske/trip-planner/actions/runs/42484305671)
    (job `Cross-Repo Smoke / cross-repo-full-product`, `databaseId: 128742800569`,
    `conclusion: "success"`) succeeded.
  - However, Maint 52 initializes `"predecessor_prs":[],"successor_prs":[]` empty
    and exposes only `repos`, `dry_run`, and `source_sha` inputs, while `main`
    has since advanced to `ruff==0.17.4` (`#2016`/`#2018`). A coding agent in
    this repository cannot populate native `predecessor_prs`/`successor_prs`
    lineage on `#1966` without hand-editing generated PR markers or modifying
    `stranske/Workflows` producer logic.
- [x] **Capture a subsequent canonical sync-core classification without this finding**:
  Executed the exact scoped canonical sync-core command from this seat:
  ```sh
  /opt/anaconda3/bin/python3 /Users/teacher/.codex/sync-core/sync_core.py run --targets stranske/trip-planner#1966 --no-judge
  ```
  Exited **0** and printed:
  ```text
  sync-core 20261112T040500Z scope=targets apply=no: targets 1; terminal 1 (superseded 1); waiting 0 (); handoffs filed 0 (dups 0, deferred 0); refresh dispatched 0; maint71 nudged 0; model calls 0; maint71 run 43136579085 refresh_skips 0; blocking 0, drainable 0, next idle (fully terminal)
  ```
  Round `20261112T040500Z` (with `maint71 run 43136579085`) completed without
  `PermissionError` and recorded `targets 1; terminal 1 (superseded 1); waiting 0 (); handoffs filed 0 (dups 0, deferred 0); ... blocking 0, drainable 0, next idle (fully terminal)` —
  confirming that the `#1967` pin-conflict finding is absent. Note: because
  `--targets` runs in `scope=targets apply=no` mode and `#1966` is closed without
  a native `successor_prs` link, `#1966`'s classification remains `superseded`
  (whereas merged Maint 52 delivery `#2006` was classified `delivered` with
  `0 mismatches` in controller apply round `20261108T133016Z`).

## Keepalive follow-up: each tool through pytest — 2026-11-12 UTC

Reviewed commits through `97c2acaf`. Tasks 3 and 4 are verified; tasks 1 and 2
remain unchecked because the owner interpreter/producer paths are absent and
repository workflow edits require an approved high-privilege run.

The subprocess regression now removes versions from mypy, pytest and Ruff
independently, as well as together. Each named historical pytest invocation
passes initially, fails with the selected incomplete diagnostic, then passes
after byte-for-byte restoration. The focused module reports **75 passed,
2 skipped** under Python 3.14.10 with `-m "not slow"`; the skips require the live
producer checkout. After the final lint adjustment, all four subprocess cases
pass again. Focused Ruff and mypy pass. The required repository-wide Black
command passes with **530 files unchanged**, using a writable cache populated
by serial checks. Only focused pytest checks ran; Python 3.12.2 remains the
owner-directed fallback and supported-runtime application validation relies
on hosted checks. No protected repository file or dependency pin changed.

PR checklist reconciliation, `needs-human` and the blocker comment were rejected
because connector writes require approval under policy `never`. The proposed
body is saved at `/tmp/issue1967-pr-body.md`. Staging failed because `.git` is
read-only; the validated diff is saved at `/tmp/issue1967-each-tool-cli.patch`
for commit on the existing PR branch by the owning automation lane.

## Keepalive follow-up: original Git object readback — 2026-11-12 UTC

Reviewed recent commits through `ca937c9e` and reconciled tasks 3 and 4 as
verified. Tasks 1 and 2 remain unchecked: the exact owner interpreter and live
producer checkout are absent, Git cannot resolve `github.com`, and repository
workflow edits require an explicitly approved high-privilege run. The connector
rejected the PR-body update, `needs-human` label and blocker comment because
those writes require approval under this run's `never` policy. The reconciled
body is saved in `/tmp/issue1967-pr-body.md`.

The live guard now reads the pinned Git object with `--no-replace-objects`.
Previously, local replacement refs could substitute reviewed dependency metadata
while HEAD still identified a commit with different runtime or dev requirements.
Four regression cases reproduce that false acceptance, with and without inherited
Git locations. All four fail against the previous guard and pass with the fix.
This strengthens task 1's source readback without claiming a live-checkout run.

Focused validation: **72 passed, 2 skipped** under Python 3.14.10 with
`-m "not slow"`; the skips require the live producer checkout. Focused Ruff and
mypy pass. No application suite ran. Python 3.12.2 remains the owner-directed
fallback; supported-runtime application validation relies on hosted checks.

The required repository-wide Black check passes with **530 files unchanged**
using `BLACK_CACHE_DIR=/tmp/issue1967-replacement-black-cache` and
`BLACK_NUM_WORKERS=1` after serial checks populated that writable cache.
The commit attempt failed at staging because `.git/index.lock` cannot be created
on the read-only Git filesystem. The validated source and note changes are saved
at `/tmp/issue1967-original-object.patch` for commit on the existing PR branch.
Fresh GitHub readback confirms #2029 remains open with `draft=false`.

## Keepalive follow-up: historical pytest process — 2026-11-12 UTC

Reviewed the current branch through `2b6abca6`. The new subprocess regression
copies only the test module and the original planner/producer metadata into a
temporary repository. The named historical case passes initially, then fails
at its exact-diagnostic assertion when the copy prints package names without
versions. Byte-for-byte source restoration makes the same pytest command pass.
The repository test source and protected workflow are unchanged by that check.

`python -m pytest tests/scripts/test_cross_repo_dev_pins.py -q -m "not slow"`
reports **68 passed, 2 skipped** under Python 3.14.10. Both skips require the live
producer checkout. Focused Ruff and mypy pass.

- [ ] Task 1: the literal owner interpreter and producer checkout are absent;
  the historical 45-test result is not a fresh result for this expanded suite.
- [ ] Task 2: repository workflow mutation requires an approved high-privilege
  run. Existing temporary-fixture checks do not discharge this restriction.
- [x] Task 3: removing version diagnostics fails the named historical regression;
  restoring the exact source bytes passes, verified through separate pytest processes.
- [x] Task 4: only focused pytest checks ran. Python 3.12.2 remains the
  owner-directed fallback; supported-runtime application validation relies on hosted checks.

The connector rejected `needs-human` and the blocker comment because those
writes require approval while this run's approval policy is `never`.
The PR checklist update was rejected for the same reason; its proposed body is
saved at `/tmp/issue1967-diagnostic-cli-pr-body.md`.

The required repository-wide Black check passes with **530 files unchanged**
using `BLACK_CACHE_DIR=/tmp/issue1967-diagnostic-cli-black-cache` and
`BLACK_NUM_WORKERS=1` after serial checks populated the cache. Staging failed
because `.git/index.lock` cannot be created on the read-only Git filesystem;
no commit was created. The validated changes are saved at
`/tmp/issue1967-diagnostic-cli.patch` for commit on the existing PR branch from
a writable checkout. Fresh PR readback confirms #2029 is open with `draft=false`.

## Keepalive follow-up: named pytest process — 2026-11-12 UTC

Reviewed recent commits through `1c2a8595`. Tasks 3 and 4 remain verified;
tasks 1 and 2 remain unchecked because the literal owner paths are absent and
repository workflow edits are prohibited. The connector rejected PR checklist
reconciliation, the `needs-human` label and the blocker comment because those
writes require approval under policy `never`.

The new subprocess regression copies the current workflow, planner metadata,
test module and reviewed producer snapshots into a temporary repository. It
invokes the named compatibility check through `python -m pytest` before changing
only the temporary workflow's TPP ref to the original producer. The pytest
process must exit 1 with all three exact conflict diagnostics. Byte-for-byte
restoration must return the same command to exit 0. This supplements direct
function tests without claiming protected-file acceptance.

Focused validation reports **67 passed, 2 skipped** under Python 3.14.10 using
`-m "not slow"`. Both skips require a live producer checkout. Focused Ruff and
mypy pass. No application suite ran; Python 3.12.2 remains the owner-directed
fallback, and supported-runtime application validation relies on hosted checks.

The required repository-wide Black check passes with **530 files unchanged**,
using `BLACK_CACHE_DIR=/tmp/issue1967-cli-black-cache` and `BLACK_NUM_WORKERS=1`
after serial checks populated the cache. Fresh readback confirms #2029 is open
with `draft=false`.

Staging failed because Git cannot create `.git/index.lock` on the read-only Git
directory. No commit was created. The validated changes are saved at
`/tmp/issue1967-named-pytest.patch`, and the reconciled PR checklist is saved at
`/tmp/issue1967-pr-body.md` for the owning lane.

## Keepalive reconciliation and exact conflict set — 2026-11-12 UTC

Reviewed recent commits through `bee8bb08` before continuing. Tasks 3 and 4
remain verified by the diagnostic sensitivity/restoration tests and focused-only
validation. Tasks 1 and 2 remain unchecked for literal revalidation: the owner
interpreter and live checkout paths are absent, Git cannot resolve `github.com`,
and standard agent permissions prohibit repository workflow mutations. The
historical 45-pass result is not the current module's test count.

The existing offline workflow regression now requires the complete ordered
conflict set, followed immediately by the repair guidance. Previously, matching
substrings allowed additional spurious conflicts to pass. This advances the
temporary-fixture alternative for task 2 without claiming protected-file
acceptance. Injecting one extra conflict through a temporary pytest plugin makes
the Ruff case fail at the new assertion; running without the plugin restores
all four original-pin break/restoration cases to passing.

`python -m pytest tests/scripts/test_cross_repo_dev_pins.py -q -m "not slow"`
reports **66 passed, 2 skipped** under Python 3.14.10. Both skips still require
a real producer checkout. Focused Ruff and mypy pass. Only focused pytest checks
ran; Python 3.12.2 remains the owner-directed fallback, and supported-runtime
application validation relies on hosted checks.

The connector rejected the reconciled PR checklist, `needs-human` label and
blocker comment because those writes require approval under policy `never`.
The proposed PR body is saved at `/tmp/issue1967-pr-body.md` for the owning lane.

The required repository-wide Black check passes with **530 files unchanged**
after serial checks populated `/tmp/issue1967-exact-conflicts-black-cache`.
Staging fails because `.git/index.lock` cannot be created on the read-only Git
directory; no commit was created. The source and note changes are saved in
`/tmp/issue1967-exact-conflicts.patch` for commit on the checked-out PR branch
from a writable checkout. Fresh readback confirms #2029 is open with `draft=false`.

## Sandbox follow-up — 2026-11-12 UTC

The exact-diagnostic sensitivity regression now also swaps the planner and TPP
requirements while retaining both original versions. Each tool and the combined
case must fail the historical regression, then pass after function restoration.
This checks attribution as well as presence of the original version details.

`python -m pytest tests/scripts/test_cross_repo_dev_pins.py -q -m "not slow"`
reports **66 passed, 2 skipped** under Python 3.14.10. Focused Ruff and mypy pass.
The skips require a real producer checkout; the literal owner interpreter and
`/private/tmp/issue2017-tpp` are absent here. This does not reproduce the owner's
zero-skip acceptance command. Python 3.12.2 remains the owner-directed fallback;
supported-runtime application validation relies on hosted checks. No full suite,
workflow edit, or dependency-pin change was made. The workflow mutation task
remains blocked under the standard agent permissions.

The required repository-wide Black check passes with **530 files unchanged**,
using `BLACK_CACHE_DIR=/tmp/issue1967-attribution-black-cache` and
`BLACK_NUM_WORKERS=1` after serial checks populated the writable cache.

The connector rejected adding `needs-human` and the blocker comment to #2029
because those writes require approval and this run's approval policy is `never`.
Staging failed because `.git/index.lock` cannot be created on the read-only Git
directory, so no commit was created. The validated changes are saved in
`/tmp/issue1967-diagnostic-attribution.patch` for commit on the existing PR branch
from a writable checkout. Readback confirms #2029 is open with `draft=false`.

## Current continuation readback — 2026-11-11 Central

Recorded before acceptance execution at 2026-11-12T00:20Z: Outcome 1 is a
zero-skip pass against the real workflow-pinned producer. Outcome command:

```sh
TPP_REPO_PATH=/private/tmp/issue2017-tpp /opt/anaconda3/bin/python3 -m pytest tests/scripts/test_cross_repo_dev_pins.py -q
```

Stop rule: one attempt per acceptance step, at most 30 minutes from 00:20 UTC;
stop at the first unresolved failure. This supersedes earlier attempt windows
for this continuation only. No diagnostic permutations or break/restoration
work were repeated.

`git worktree list --porcelain` showed this branch only at the current closer
worktree, clean at `92e779d3feee5de8d768f6476cf177ea53c34c14`. No separate
preserved/holder worktree for #2029 was registered. No holder was reset or
cleaned. Existing regression work and dependency pins remain intact.

- [x] Current-branch focused validation: **64 passed in 3.98s**, zero skips,
  with no marker exclusions. The existing real producer checkout has origin
  `https://github.com/stranske/Travel-Plan-Permission.git`, clean status and HEAD
  `5c9ec6e15ac959023b9fc9cdd1099d70a6073396`, exactly matching workflow
  `env.TPP_PINNED_REF`. No repository venv is present; the selected fallback
  `/opt/anaconda3/bin/python3` reports Python 3.12.2. Pytest emitted an
  `asyncio_default_fixture_loop_scope` deprecation warning. This is metadata
  acceptance, not supported-runtime application acceptance.
- [ ] Configured local command: Makefile `test` runs `python -m pytest`.
  It was **not run**, because the continuation explicitly prohibits the full
  local suite. Black or focused tests are not substituted for that result.
- [x] Substantiate observed CI failures: inspected complete failed-job logs
  and artifact inventory for [run 43094025285](https://github.com/stranske/trip-planner/actions/runs/43094025285),
  whose head is the branch SHA above. Python 3.13 printed **2934 passed,
  5 skipped, 800 warnings in 148.32s**; Python 3.14 printed **2934 passed,
  5 skipped, 800 warnings in 174.04s**. Both report **91%** coverage,
  `PYTEST_OUTCOME=success`, `COVERAGE_MIN_OUTCOME=success`, and `All checks passed!`.
  Their jobs failed at `actions/upload-artifact@v4` with `Failed to CreateArtifact`
  after five requests returned HTML instead of JSON. Product contract
  observations printed `WORKS 4, PARTIAL 3, BROKEN 0, FABRICATED 0 of 7`, then
  failed uploading `product-probe.json` with the same CreateArtifact error.
  The run artifact inventory contains only `langsmith-fleet.ndjson` (ID
  `13891345012`); the product-probe and Python test artifacts are absent.
  Thus their contents cannot be independently inspected. Logs establish
  artifact-service failures, not branch test regressions. No baseline rerun
  was performed, so no broader baseline-health claim is made.
- [ ] Explicit #1966 successor and regenerated exact-head Evidence: incomplete.
  Fresh #1966 readback remains closed at
  `164ed1a02b126e72ce407620829e40aa92925a53`, with empty predecessor/successor
  arrays. Maint 52's current producer accepts `repos`, `dry_run`, and
  `source_sha`; its generated delivery marker also initializes those arrays
  empty. Successful #2006 evidence in the #1973 document does not establish
  a native replacement edge from #1966. No producer was dispatched, obsolete
  pins reopened, generated output edited, or Maint 68 substituted.
- [ ] Subsequent canonical classification: incomplete. The supported scoped
  readback attempt was:

  ```sh
  /opt/anaconda3/bin/python3 /Users/teacher/.codex/sync-core/sync_core.py run --targets stranske/trip-planner#1966 --no-judge
  ```

  It exited **1** before running a round:
  `PermissionError: [Errno 1] Operation not permitted: '/Users/teacher/.codex/orchestrator/sync-core/round.lock'`.
  Canonical sync-core state is outside this seat's writable roots. No lock
  was bypassed, state redirected, or independent classification substituted.
  The retained target still says `superseded`, last round
  `20261105T054444Z`, at the original head. This is the first unresolved
  acceptance step; the stop rule ended further acceptance execution.

Blocking/drainable pair: canonical successor reconciliation and classification
cannot execute from this restricted seat / retain this source PR and let the
owning sync-core controller, with canonical-state access, explicitly reconcile
#1966 to a Maint 52 successor, regenerate through that producer, capture
`gh run view <successor-evidence-run-id> --repo stranske/trip-planner --json conclusion,headSha,status,url,jobs`
with successful `cross-repo-full-product` at its exact head, and retain the
subsequent canonical round without the finding. These boxes remain unchecked;
the current branch's passing focused tests do not discharge them.

Check date: 2026-11-11 (America/Chicago).

Outcome 1: the real workflow-pinned TPP checkout and current planner requirements
pass the pin guard, including a deliberate return to the original incompatible
producer followed by byte-for-byte restoration.

```sh
TPP_REPO_PATH=/private/tmp/issue2017-tpp /opt/anaconda3/bin/python3 -m pytest tests/scripts/test_cross_repo_dev_pins.py -q
```

Stop rule: two failed repair attempts or 45 minutes from 18:46 UTC. Run only
the focused pytest module; do not run the full suite locally.

## Source reconciliation

PR #1990 is closed and unmerged. Its useful dependency pairing and workflow
guard have since reached main through other deliveries, including #2005 and
#2018. Retain current Ruff 0.17.4, mypy 2.4.1, pytest 9.2.0, and TPP revision
`5c9ec6e15ac959023b9fc9cdd1099d70a6073396`. Reapplying #1990's older TPP
revision would reintroduce the later Ruff conflict.

The planner metadata at #1966 head
`164ed1a02b126e72ce407620829e40aa92925a53` has Git blob
`9721fb639a0389d6ab8527f04dda6d4641668e66`, identical to the existing
`tests/fixtures/issue_2025_ledger/failed-trip-planner.toml`. The historical
guard and offline pip tests therefore already exercise the original planner
input together with TPP `acc4aeddee5f4ffefbdc73fcb07505cd3d198197`.
This PR strengthens that guard's regression to require the exact conflicting
versions, preserving the finished source repair without another pin change.

## Acceptance evidence

- Before and after the regression extension, the focused command above passed
  **45 tests, zero skips**, including both real-checkout checks and offline pip
  resolution. The final result was **45 passed in 3.03 seconds**.
- Deliberately replaced only the workflow's TPP ref with original producer
  `acc4aeddee5f4ffefbdc73fcb07505cd3d198197`. Running
  `pytest tests/scripts/test_cross_repo_dev_pins.py::test_workflow_tpp_pin_resolves_with_planner_dev_pins -q`
  through `/opt/anaconda3/bin/python3 -m` failed in 0.35 seconds (exit 1), naming
  incompatible Ruff, mypy and pytest pins. A `finally` block restored the exact
  workflow bytes; the same check passed in 0.31 seconds (exit 0).
- Removing the diagnostic versions while retaining conflict detection makes
  `test_smoke_pin_guard_with_historical_editable_checkouts[issue-1967-original-install-inputs]`
  fail at the new exact-message assertion. Restoring the exact test-module bytes
  makes the same regression pass. This verifies the added assertion's sensitivity.
- The owner-directed fallback interpreter is Python 3.12.2; no repository venv
  exists. These are focused dependency-metadata results, not a supported-runtime
  application test. The full suite was not run.

Fresh GitHub readback:

```sh
gh run view 41674233862 --repo stranske/trip-planner --json conclusion,headSha,status,url
gh run view 43035261628 --repo stranske/trip-planner --json conclusion,headSha,status,url,jobs
```

The original evidence run remains **failure** on #1966 head
`164ed1a02b126e72ce407620829e40aa92925a53`. PR #1966 remains **closed,
unmerged**. Current-main smoke run
[43035261628](https://github.com/stranske/trip-planner/actions/runs/43035261628)
passes `cross-repo-full-product` on
`114ca378c040c609fe0d25e301318dcc00e81bbb`; it does not prove a regenerated
#1966 gate.

The canonical sync-core log's latest retained entry for #1966 is round
`20261105T054444Z`, recorded at `2026-11-05T05:45:07Z`: disposition and terminal
are `superseded`, reasons and handoffs are empty. This predates the subsequent
source fixes, so it is not the requested post-repair classification. Later
#2006 evidence in `docs/verification/issue-1973-dev-tool-pins.md` has no formal
native replacement edge from #1966; do not substitute it silently.

## Remaining operational acceptance

The literal regenerated-#1966 gate and next-round classification are **not
complete**. No generated sync PR was hand-edited. The named Maint 68 workflow
syncs consumer templates; #1966 was produced by Maint 52 dev-tool sync (the
same distinction is recorded for #1972/#2006). Dispatching Maint 68 cannot
establish a regenerated dev-tool #1966, and reviving the obsolete failed
delivery would reintroduce old pins. This PR retains the correct current
source instead of manufacturing that evidence.

Blocking/drainable pair: exact-target downstream acceptance missing / the
owning sync-core delivery lane can establish an explicit successor for #1966,
regenerate it through the actual dev-tool producer, verify its exact-head
cross-repo gate and capture the subsequent canonical classification. This is
an unresolved acceptance dependency, not a new gate or a claim of completion.
No automatic merge is enabled by this repair.

## Keepalive follow-up: offline break and restoration

Check date: 2026-11-11 UTC. This sandbox uses Python 3.14.10, Black 26.10.1,
Ruff 0.17.4 and mypy 2.4.1. The earlier Python 3.12.2 fallback results above
describe the owner's environment; that interpreter is not available here.

The `all` case of
`test_offline_workflow_guard_rejects_original_producer_pins` now selects the
actual original producer `acc4aeddee5f4ffefbdc73fcb07505cd3d198197` and its
complete reviewed metadata. It calls the named
`test_workflow_tpp_pin_resolves_with_planner_dev_pins` check and verifies all
three conflicts. Each case then restores the current workflow selection and
the current producer's exact metadata and requires that same check to pass.
All workflow changes take place in temporary test fixtures. The repository's
protected workflow and dependency pins remain unchanged.

The historical regression now requires the complete ordered diagnostic lines,
including all three exact version pairs and the full repair guidance. Pytest's
added assertion indentation and expression trace are excluded from this comparison.

- [ ] Reproduce the literal owner command with **45 passed, zero skips**.
  `/opt/anaconda3/bin/python3` and `/private/tmp/issue2017-tpp` are absent.
  `python -m pytest tests/scripts/test_cross_repo_dev_pins.py -q -m "not slow"`
  passes **43 tests with 2 skips**; both skips require a live producer checkout.
  Git cannot resolve `github.com` to obtain that checkout. Reviewed metadata
  fixtures are not a substitute for live-checkout acceptance.
- [ ] Repeat the literal workflow-file break and restoration. Protected workflow
  edits are not authorized in this run. The isolated original-ref regression
  and all three single-tool break/restoration cases pass instead.
- [x] Remove version diagnostics: extended regression fails; exact restoration
  passes. Removing Ruff, mypy and pytest diagnostics separately produces an
  expected failure in the historical regression on each of the three runs.
  Restoring the exact test-module bytes returns that regression to **1 passed**.
- [x] Only focused pytest checks ran locally. Python 3.12.2 remains the
  owner-directed fallback; supported-runtime application validation relies on
  hosted checks. This sandbox instead used Python 3.14.10 for the focused
  module, with `-m "not slow"`; no application suite ran.

Focused Ruff and mypy checks pass. The required repository-wide command
`black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .`
passes with **530 files left unchanged**. Individual checks populated
`BLACK_CACHE_DIR=/tmp/issue1967-black-cache` first; the global check then ran
with that cache and `BLACK_NUM_WORKERS=1` because uncached multi-file checks
do not finish in this sandbox. No downstream regeneration or classification
criterion is inferred from these offline test results.

Commit handoff is blocked: `git add` cannot create `.git/index.lock` because
the repository's Git directory is mounted read-only. The patch is saved at
`/tmp/issue1967-keepalive.patch` for application from a writable checkout.
Adding `needs-human` and posting the blocker comment through the GitHub
connector were denied because those tools require approval and this run's
approval policy is `never`. Fresh PR readback shows #2029 open and ready for
review; no PR or branch was created by this run.

## Keepalive follow-up: exact workflow fixture restoration

Reviewed commits `9539a3bd`, `1fabd3cc` and `a5226e57` before proceeding.
The diagnostic-removal and focused-validation tasks are verified by the prior
iteration and remain checked above. The literal owner-command and protected
workflow-mutation tasks remain unchecked. Updating the PR body, adding
`needs-human` and posting the blocker comment were each denied by the GitHub
connector: the tools require approval, while this run's approval policy is
`never`. The proposed reconciled PR body is saved in
`/tmp/issue1967-pr-body.md` for the owning automation lane.

The offline break/restoration regression now copies the complete current
workflow bytes into its temporary fixture and establishes a passing baseline.
It replaces only the pinned SHA for the original-producer case, verifies the
named compatibility check rejects the selected producer, and restores both
workflow and producer metadata in a `finally` block. It checks exact restored
bytes and requires the same compatibility check to pass again. It also verifies
the repository workflow bytes are unchanged. All four cases, including the
three isolated tool conflicts, use this sequence.

`python -m pytest tests/scripts/test_cross_repo_dev_pins.py -q -m "not slow"`
passes **44 tests with 2 skips** before and after this change. The current
module collects 46 tests; the earlier 43-pass note does not describe this
checkout. Both skipped checks still require the unavailable live TPP checkout.
Python is 3.14.10 here; the owner's Python 3.12.2 fallback remains unavailable.
Only the focused dependency-metadata module ran; supported-runtime application
validation still relies on hosted checks.

Sensitivity checks deliberately broke the revised temporary-fixture regression
in two ways: leaving the current ref selected caused the expected missing-error
failure, and restoring an environment-only YAML document failed the exact-byte
assertion. Both mutations failed the `all` case as intended. The exact test-module
bytes were restored in a `finally` block afterward.

Final focused run: **44 passed, 2 skipped**. Focused Ruff and mypy pass.
The required repository-wide Black command passes with **530 files left
unchanged** after serial verification populated its cache; uncached worker
runs stalled in this sandbox. Fresh GitHub readback confirms #2029 is open
with `draft=false`.

Committing this follow-up is also blocked: `git add` fails to create
`.git/index.lock` because `.git` is read-only. The validated source and note
changes are saved in `/tmp/issue1967-exact-restoration.patch`; apply and commit
them on the existing PR branch from a writable checkout. No branch, PR or
workflow change was made.

## Keepalive follow-up: automated diagnostic sensitivity

Reviewed commits `9539a3bd`, `1fabd3cc`, `a5226e57` and `00f8bce2` before
continuing. Tasks 3 and 4 remain verified; tasks 1 and 2 remain blocked for
literal revalidation in this sandbox, as documented above. The reconciled PR
checklist is saved in `/tmp/issue1967-pr-body.md`. The GitHub connector rejected
the PR-body update and `needs-human` label because those mutations require
approval and this run's approval policy is `never`.

Added four parameterized sensitivity checks to the focused module. Each removes
the version details for Ruff, mypy, pytest or all three while preserving conflict
detection. The actual historical regression must then fail. Exiting the isolated
monkeypatch context restores the original conflict function, and the same
historical regression must pass with unchanged metadata. The checks use temporary
checkouts and never modify a repository workflow or dependency pin.

- [ ] Literal owner command: the requested interpreter and live TPP checkout
  remain absent; no zero-skip result is inferred from metadata fixtures.
- [ ] Literal workflow mutation: protected workflow edits remain unauthorized.
- [x] Diagnostic removal and restoration: all four automated cases pass.
- [x] Focused validation only: the module passes **48 tests, 2 skipped** under
  Python 3.14.10 with `-m "not slow"`. The two skips require the live checkout.
  Python 3.12.2 remains the owner-directed fallback; supported-runtime application
  validation relies on hosted checks.

Focused Ruff and mypy pass. No downstream delivery or classification acceptance
is inferred from these results.

The required repository-wide Black command passes with **530 files left
unchanged** using `BLACK_CACHE_DIR=/tmp/issue1967-diagnostics-black-cache` and
`BLACK_NUM_WORKERS=1` after individual checks populated the cache. `git add`
fails creating `.git/index.lock` because `.git` is read-only, so no commit was
created. The changes are saved in `/tmp/issue1967-diagnostic-sensitivity.patch`
for commit on the existing PR branch from a writable checkout.
The required blocker comment was also rejected by the GitHub connector under
the same approval policy. Fresh readback confirms #2029 is open and ready for
review (`draft=false`).

## Keepalive follow-up: version loss from either project

Reviewed commits `9539a3bd` through `7ae2b727`. Tasks 3 and 4 remain verified;
tasks 1 and 2 remain blocked by the absent owner interpreter/live checkout and
the prohibition on repository workflow edits. The owner's recorded 45-test
result predates the expanded suite and is not a fresh sandbox result.

The diagnostic sensitivity test now removes version details from planner, TPP
or both, independently for each tool and all three tools. All 12 cases require
the historical regression to fail, then pass after restoring the original
function. The focused module passes **56 tests, 2 skipped** under Python
3.14.10 with `-m "not slow"`; both skips need the live producer checkout.
Focused Ruff and mypy pass. No application suite was run.

The required repository-wide Black check passes with **530 files left
unchanged**, using `BLACK_CACHE_DIR=/tmp/issue1967-side-diagnostics-black-cache`
and `BLACK_NUM_WORKERS=1` after individual checks populated the cache with the
repository's Python 3.13/3.14 target versions.

PR-body reconciliation, `needs-human` and the blocker comment were rejected
because the connector requires approval and this run's policy is `never`.
The reconciled body is saved in `/tmp/issue1967-pr-body.md`. Fresh readback
confirms #2029 remains open with `draft=false`. `git add` again fails to create
`.git/index.lock` because `.git` is read-only, so committing requires the owning
automation lane. The source and note patch is saved in
`/tmp/issue1967-side-diagnostics.patch`.

## Keepalive follow-up: committed producer metadata

Reviewed recent commits through `74194e4c`. Tasks 3 and 4 remain verified;
tasks 1 and 2 remain unchecked for fresh validation because the owner interpreter
and real TPP checkout are absent and repository workflow edits are prohibited.
The PR-body reconciliation, `needs-human` label and blocker comment were rejected
because the connector requires approval while this run's policy is `never`.
The reconciled body is saved in `/tmp/issue1967-pr-body.md`.

The live checkout guard now reads `pyproject.toml` from the verified commit as
well as the working tree and compares both sets of runtime and dev dependencies
with the reviewed snapshot. A locally changed file matching the snapshot can no
longer conceal different committed dependencies. Four new regression cases
cover committed runtime/dev mismatches with and without inherited Git locations.
All four failed against the previous guard because it accepted those inputs.

After the guard change, the focused command
`python -m pytest tests/scripts/test_cross_repo_dev_pins.py -q -m "not slow"`
passes **60 tests, 2 skipped** under Python 3.14.10. The two live-checkout skips
remain; this does not reproduce the historical owner's 45-test, zero-skip run.
Focused Ruff and mypy pass. No application tests, workflow edits or dependency
pin changes were made. Supported-runtime application validation still relies
on hosted checks; Python 3.12.2 remains the owner-directed fallback.

The required repository-wide Black command passes with **530 files left
unchanged** after serial checks populated `BLACK_CACHE_DIR=/tmp/issue1967-committed-black-cache`;
the final command used that cache and `BLACK_NUM_WORKERS=1`.

The commit attempt failed because `git add` cannot create `.git/index.lock`
on the read-only Git directory. The source and note changes are saved in
`/tmp/issue1967-committed-metadata.patch` for commit on the existing PR branch
from a writable checkout. Fresh readback confirms #2029 is open and ready for
review (`draft=false`). No branch or pull request was created.

## Keepalive follow-up: producer repository root

Reviewed recent commits through `9899bbba`. Tasks 3 and 4 remain verified;
tasks 1 and 2 remain unchecked because the literal owner interpreter and live
checkout are absent, Git cannot resolve GitHub, and workflow edits are prohibited.
PR-body reconciliation, `needs-human` and the blocker comment were rejected
because those connector writes require approval under policy `never`.
The reconciled checklist is saved at `/tmp/issue1967-pr-body.md`.

The live guard now requires `TPP_REPO_PATH` to identify the producer repository
root. Previously a nested directory with copied metadata could pass using its
ancestor's HEAD and committed metadata. Both new regression cases, with and
without inherited Git locations, failed against the previous guard. With the
root check they pass, and the focused module reports **62 passed, 2 skipped**
under Python 3.14.10 with `-m "not slow"`. The skips still require a real TPP
checkout. Focused Ruff and mypy pass; no application suite ran. This advances
the live-checkout guard without claiming literal owner-command acceptance.

The required repository-wide Black command passes with **530 files left
unchanged**, using `BLACK_CACHE_DIR=/tmp/issue1967-root-serial-cache` and
`BLACK_NUM_WORKERS=1` after individual serial checks populated the cache.
Staging fails because `.git/index.lock` cannot be created on the read-only Git
directory, so no commit was created. The validated changes are saved at
`/tmp/issue1967-producer-root.patch`. Fresh readback confirms #2029 remains
open and ready for review (`draft=false`).
