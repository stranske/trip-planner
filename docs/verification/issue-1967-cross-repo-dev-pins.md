# Issue #1967: retained repair and exact-target acceptance

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
