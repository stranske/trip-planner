# Issue #1973: dev-tool pin verification

## Outcome and scope — 2026-11-08

The required focused check passes: 79 tests on supported Python 3.13.13 against
the workflow-pinned producer, followed by a deliberate Ruff conflict failure and
restoration pass. The regenerated delivery's exact-head cross-repo gate passes, and the next
controller-owned sync-core classification records delivery without this finding.

Before edits, the real-input outcome was defined as: the named focused pytest
command passes without skips against the exact producer, the incompatible copy
fails naming both Ruff requirements and passes after restoration, and the
regenerated delivery passes its cross-repo gate with the finding absent from the
next controller classification. Check date: 2026-11-08. Stop rule: three failed
attempts at a required step or 45 minutes. Only this evidence file is changed.

## Integrated implementation and complete review

Current GitHub readback of [#2005](https://github.com/stranske/trip-planner/pull/2005)
reports `MERGED`, merged at `2026-11-08T11:44:37Z`, source head
`b20e73f66422d12f255aca4e2e35858f21c37781`, and merge commit
`29c6aa01064f9eb3cbf15debd32cac3327ec43b8`. A fresh fetch established that main
contains that merge. `git diff --quiet` between the fetched source head and merge
commit exited 0: their complete trees match. The old review-floor refusal is
historical and does not describe current integration.

Reviewed all nine paths in the merged diff, including the complete 535-line
`tests/scripts/test_cross_repo_dev_pins.py` and 347-line
`tests/scripts/test_cross_repo_smoke_workflow.py`. Retain the implementation:

- The producer snapshot and live guard check both runtime/dev metadata and the
  exact workflow-pinned checkout HEAD, isolating inherited Git location variables.
- Compound/prefix constraints and repeated runtime/dev requirements have regression
  coverage. Original-producer cases exercise all three tool conflicts separately.
- Offline pip resolver tests use metadata-only wheels with each project's `[dev]`
  extra, require `ResolutionImpossible` and both conflicting requirements, and
  verify the successful resolution report. They prove the selected tool resolution,
  not a complete real-package installation.
- Workflow assertions require the live compatibility check before joint producer
  installation. Existing integration exports and client-method guards remain.
- The remaining merged changes pair the producer revision and dev pins, add the
  `packaging` test dependency, and align the design-map/evidence documentation.

The provisioned `closer-r1/issue-1973` branch already contained evidence commit
`e2a3ed5ab14548d6820a839e81685b6e48787a4e` and ready PR
[#2011](https://github.com/stranske/trip-planner/pull/2011). No other local
`closer*/issue-1973` branch existed. That commit is retained; its unsupported
“All acceptance criteria are met” and “None” remaining-unknown claims are
superseded here. No replacement implementation or evidence PR is created.
No dependency pins, lockfiles, implementation, or tests are edited by this repair.

## Required-runtime local evidence

No repository `.venv` exists. `.python-version` selects deployment Python 3.14;
`pyproject.toml` supports `>=3.13,<3.15`. These focused local repository-command
results use supported Python **3.13.13**, executable
`/opt/homebrew/opt/python@3.13/bin/python3.13`, invoked through
`/opt/homebrew/bin/python3.13`. No full local suite or release/verify pipeline was run.
The original issue's unrestricted full-suite result remains unverified locally;
the checked repair criterion below covers only the two explicitly requested files.
This follows the repair instruction forbidding a full local suite and does not
replace that missing full-suite evidence with source-PR CI.

The producer checkout is clean at
`/Users/teacher/.codex/orchestrator/worktrees/Travel-Plan-Permission`, HEAD
`b56d92b389736c70370aa9134f379ac8cd1f3ad1`, matching `TPP_PINNED_REF`.
The passing live snapshot test also verifies its runtime/dev requirements.

```sh
TPP_REPO_PATH=/Users/teacher/.codex/orchestrator/worktrees/Travel-Plan-Permission /opt/homebrew/bin/python3.13 -m pytest tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -q
```

Observed output, exit **0**:

```text
........................................................................ [ 91%]
.......                                                                  [100%]
79 passed in 3.20s
```

Created `/tmp/issue-1973-producer-p07xzrhs` using `git archive` of that exact
producer commit. Changed only the isolated copy's `pyproject.toml` from
`ruff==0.17.3` to `ruff==0.17.2`; the real producer checkout was untouched.

```sh
TPP_REPO_PATH=/tmp/issue-1973-producer-p07xzrhs /opt/homebrew/bin/python3.13 -m pytest tests/scripts/test_cross_repo_dev_pins.py::test_planner_dev_pins_resolve_with_pinned_tpp_checkout -q
```

Observed output excerpt, exit **1**, expected:

```text
AssertionError: trip-planner and the pinned TPP revision cannot be installed together:
  ruff: trip-planner 'ruff==0.17.3' vs TPP 'ruff==0.17.2'
Move TPP_PINNED_REF in .github/workflows/cross-repo-smoke.yml to a TPP revision with matching pins, in the same PR as the pin update.
FAILED tests/scripts/test_cross_repo_dev_pins.py::test_planner_dev_pins_resolve_with_pinned_tpp_checkout
1 failed in 0.19s
```

Restored the copy's original metadata byte-for-byte; `cmp` with the real pinned
checkout's metadata exited **0**. Repeated the same pytest command, exit **0**:

```text
.                                                                        [100%]
1 passed in 0.14s
```

## Producer regeneration and delivery linkage

Original delivery [#1972](https://github.com/stranske/trip-planner/pull/1972)
is closed without merging, at head
`d679b90ac41e91f80fa96f4b43cd05a28f592680`. Issue #1973 originally records its
pin-conflict finding from sync-core round `20261105T030005Z`. #2005's merged
commit explicitly names #1972 and fixes that same incompatible producer/tool pair.

[#2006](https://github.com/stranske/trip-planner/pull/2006) is the current delivery
of those dev-tool versions, generation `91791b44e525`, plan
`dev-tool-91791b44e525`. Its predecessor/successor arrays are empty: the evidence
establishes a shared payload/failure and current delivery, not a formal native
replacement edge from #1972. The named producer is Maint 52 Sync Dev Versions;
Maint 68 is the generic source-sync path named in the original issue.

After confirming no active Maint 52 run and unchanged canonical tool versions,
requested only this consumer through the producer:

```sh
gh workflow run maint-52-sync-dev-versions.yml --repo stranske/Workflows --ref main -f repos=stranske/trip-planner -f dry_run=false
```

[Producer run 42484255917](https://github.com/stranske/Workflows/actions/runs/42484255917)
concluded **success**, including `Sync stranske/trip-planner`. It regenerated
existing #2006 at head `fcb6e97a291bd620629aa228561d36c3ee6cdf0d` on base
`29c6aa01064f9eb3cbf15debd32cac3327ec43b8`, retaining the generation and recording
source commit `e8f9dc2373563dea50a708501a63a9ad58f8db06` and desired tree
`52a50c1ce7ac5ca86891f5dea3ce26d01f591c16`. No generated branch was edited manually.
The owning delivery lane subsequently merged #2006 at `2026-11-08T13:23:04Z`,
merge commit `419015e6035cc77db18de3ab58c60651d8e51bc8`. This repair branch
merges that current main while preserving the pre-existing evidence commit;
its net PR diff still changes only this document.

## Regenerated-head gate

```sh
gh run view 42484305671 --repo stranske/trip-planner --json headSha,conclusion,jobs
gh run view 42484305260 --repo stranske/trip-planner --json headSha,conclusion,jobs
```

Both commands exited **0** and returned head SHA
`fcb6e97a291bd620629aa228561d36c3ee6cdf0d`, equal to current #2006 head:

| Run | Overall conclusion | Named job | Job conclusion |
| --- | --- | --- | --- |
| [Gate 42484305671](https://github.com/stranske/trip-planner/actions/runs/42484305671) | success | Cross-Repo Smoke / cross-repo-full-product, job 128742800569 | success |
| [Cross-Repo Smoke 42484305260](https://github.com/stranske/trip-planner/actions/runs/42484305260) | success | cross-repo-full-product, job 128742727094 | success |

Gate's `gate-summary` also succeeded. This is regenerated-delivery evidence,
separate from the earlier successful source-PR runs. The prior #2006 Gate
`42449207902` failed at producer installation on old head
`4ea6a28d050bbcf2233b725de13ade495f132002`; that failure remains historical.

## Subsequent controller-owned classification

The controller launch log records `2026-11-08T13:30:16Z start apply`.
Its next completed canonical round, `20261108T133016Z` at
`2026-11-08T13:30:21Z`, retained this #2006 item in
`~/.codex/orchestrator/sync-core/rounds.jsonl`:

```json
{
  "target": "stranske/trip-planner#2006",
  "disposition": "delivered",
  "terminal": "delivered",
  "error": null,
  "handoffs": [],
  "owner": "-",
  "reasons": ["merged 2026-11-08T13:23:04Z; 1 files, 0 mismatches"]
}
```

The canonical target state also binds `last_round: 20261108T133016Z` to head
`fcb6e97a291bd620629aa228561d36c3ee6cdf0d`. The pin-conflict finding is absent
from both the reasons and handoffs. This was the existing controller's apply
round, not an independently run classifier or a replacement state directory.
The old #1972 target remains historically `superseded`; its finding is discharged
through the regenerated #2006 delivery described above.

## Repair acceptance

- [x] Inspect the complete merged or current PR diff, including omitted resolver tests, and establish #2005 integration from current GitHub state.
- [x] Record a required-runtime local repository test result and a deliberate incompatibility failure followed by restoration and pass.
- [x] Establish the regenerated delivery's relationship to #1972, verify its current-head cross-repo gate, and obtain the next controller-owned classification without this finding.

Blocking/drainable pair for the repaired finding: blocking 0, drainable 0 /
retain the successful producer, delivery and controller evidence. The evidence
PR still follows its normal CI/review lifecycle. The original unrestricted full
local suite remains unverified under this repair's explicit test restriction;
no formal predecessor edge was added to the producer metadata. Source-PR CI and
issue closure were not used to establish downstream acceptance.

## Issue #2012 local full-suite follow-up — 2026-11-08

This follow-up attempts the previously missing unrestricted local suite. The
earlier repair restriction and its focused, deliberate-break, regenerated-gate,
and controller results above remain historical evidence; they do not establish
a full-suite pass.

### Checkout and supported runtime

Created an isolated checkout with
`git clone --shared --no-hardlinks . /tmp/trip-planner-issue-2012` at
`795b770dadce7002a912d857ff592f1f087c5242`. Both ancestry checks exited **0**:

```sh
git merge-base --is-ancestor 29c6aa01064f9eb3cbf15debd32cac3327ec43b8 HEAD
git merge-base --is-ancestor 4c6ff3e81b412db4039f7d1a48fa95d0aecff753 HEAD
```

These are the merged #2005 and #2011 revisions. `.python-version` selects
**3.14**, and `pyproject.toml` supports **>=3.13,<3.15**. The selected local
interpreter is **CPython 3.14.10**, executable
`/opt/hostedtoolcache/Python/3.14.10/x64/bin/python`, built with GCC 15.2.0.
Installed pytest is **9.2.0**, Black **26.10.1**, and Ruff **0.17.3**.
`PYTEST_ADDOPTS` and `TPP_REPO_PATH` are unset.

### Initial attempt and failure classification

From the isolated checkout, ran the Makefile's exact test command:

```sh
python -m pytest
```

Output was redirected to `/tmp/issue-2012-initial-pytest.log`. The process
stalled during setup of the first test and was interrupted; observed exit
status **130**. Its complete terminal output before interruption was:

```text
============================= test session starts ==============================
platform linux -- Python 3.14.10, pytest-9.2.0, pluggy-1.7.0
rootdir: /tmp/trip-planner-issue-2012
configfile: pyproject.toml
testpaths: tests
plugins: cov-7.1.0, regressions-2.11.0, platformdirs-4.14.5, datadir-1.9.0, langsmith-0.14.17, pytest_httpserver-1.1.5, anyio-4.14.2
collected 2671 items / 2 skipped

tests/app/test_auth.py
```

No pytest terminal result or assertion failure was produced. The first blocked
node is
`tests/app/test_auth.py::test_signup_creates_account_sets_cookie_and_restores_session`,
inside its `client` fixture at `tests/app/test_auth.py:21`. A separate diagnostic
run used:

```sh
python -m pytest tests/app/test_auth.py::test_signup_creates_account_sets_cookie_and_restores_session -vv -o faulthandler_timeout=10
```

It also stalled and was interrupted with exit **130**. The timeout traceback
excerpt identifies the wait before the test body executes:

```text
tests/app/test_auth.py::test_signup_creates_account_sets_cookie_and_restores_session Timeout (0:00:10)!
Thread [asyncio-portal-] (most recent call first):
  File ".../python3.14/selectors.py", line 452 in select
  File ".../python3.14/asyncio/base_events.py", line 2026 in _run_once
  File ".../python3.14/asyncio/base_events.py", line 678 in run_forever
  File ".../python3.14/asyncio/base_events.py", line 707 in run_until_complete
  File ".../python3.14/asyncio/runners.py", line 128 in run
  File ".../site-packages/anyio/_backends/_asyncio.py", line 2481 in run
  File ".../site-packages/anyio/_core/_eventloop.py", line 83 in run
  File ".../site-packages/anyio/from_thread.py", line 536 in run_blocking_portal
Thread [python] (most recent call first):
  File ".../python3.14/threading.py", line 369 in wait
  File ".../python3.14/concurrent/futures/_base.py", line 449 in result
  File ".../site-packages/anyio/_backends/_asyncio.py", line 2715 in run_sync_from_thread
  File ".../site-packages/anyio/from_thread.py", line 118 in run_sync
  File ".../site-packages/anyio/from_thread.py", line 301 in _spawn_task_from_thread
  File ".../site-packages/anyio/from_thread.py", line 382 in start_task_soon
  File ".../site-packages/starlette/testclient.py", line 696 in __enter__
  File "/tmp/trip-planner-issue-2012/tests/app/test_auth.py", line 21 in client
```

Independent standard-library probes establish a sandbox restriction. Creating
an IPv4 socket raises `PermissionError: [Errno 1] Operation not permitted`.
Creating a local socketpair succeeds, but sending one byte fails, exit **1**:

```sh
python -c 'import socket; a, b = socket.socketpair(); print("socketpair created"); a.send(b"x"); print(b.recv(1))'
```

```text
socketpair created
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import socket; a, b = socket.socketpair(); print("socketpair created"); a.send(b"x"); print(b.recv(1))
                                                                            ~~~~~~^^^^^^
PermissionError: [Errno 1] Operation not permitted
```

Classification: **environmental blocker, with high confidence**, rather than
evidence of a changed dev-tool pin regression. Asyncio's cross-thread wakeup
requires the socketpair operation denied here; the diagnostic waits at that
boundary. The socket probes do not import repository code or dev tools. The
focused pin/workflow tests still pass, as recorded below. This does not prove
the remainder of the full suite passes: rerun on a supported local interpreter
where socket operations are permitted before granting acceptance. No dependency
or application changes are proposed to conceal this restriction.

### Restoring default collection

The original pytest configuration also contained
`--ignore=tests/test_build_html.py`, so the initial run cannot satisfy
"without exclusions." Removed that ignore and changed the renderer smoke test
to create its JSON and templates under `tmp_path`, assert both rendered bundle
contents, and cover populated and empty itineraries. It can now run during
default collection without overwriting the repository's HTML source files.

The focused validation command, exit **0**, was:

```sh
python -m pytest tests/test_build_html.py tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -m 'not slow' -q
```

```text
79 passed, 2 skipped, 14 warnings in 3.31s
```

The two skips require `TPP_REPO_PATH`; these focused results do not replace the
earlier exact-producer verification. In the isolated checkout the renderer test
alone also passed: **2 passed, 14 warnings in 0.15s**, exit **0**.

### Unrestricted attempt against the committed test change

Tested source commit **`0f30404dbead0e1c4dcca3a4f37a50dc2b443ca6`**, based on
`795b770dadce7002a912d857ff592f1f087c5242`, in the clean isolated checkout
`/tmp/trip-planner-issue-2012`, using the same **CPython 3.14.10** executable
listed above. This commit includes both merged PRs and the restored HTML test.

The exact test command was **`python -m pytest`**, with no command-line or
configured test exclusions and no marker filter. A watchdog bounded the
already-reproduced hang; the complete shell invocation was:

```sh
timeout --signal=INT --kill-after=5s 30s python -m pytest > /tmp/issue-2012-unrestricted-pytest.log 2>&1
```

Observed wrapper exit status: **137**. After 30 seconds the watchdog sent
SIGINT; the blocked process did not exit within the next five seconds and was
killed. This is a terminated run, not a pytest assertion-failure exit or a
passing full-suite result. Complete terminal output:

```text
============================= test session starts ==============================
platform linux -- Python 3.14.10, pytest-9.2.0, pluggy-1.7.0
rootdir: /tmp/trip-planner-issue-2012
configfile: pyproject.toml
testpaths: tests
plugins: cov-7.1.0, regressions-2.11.0, platformdirs-4.14.5, datadir-1.9.0, langsmith-0.14.17, pytest_httpserver-1.1.5, anyio-4.14.2
collected 2673 items / 2 skipped

tests/app/test_auth.py
```

Terminal result: **no tests finished and no pytest result summary was emitted**.
The first blocked node and diagnostic traceback remain those recorded above.
Collection includes the two restored HTML cases (2,673 versus 2,671); the two
collection-time skips are existing suite behavior, not added exclusions.

The required Black gate initially failed when multiprocessing attempted a
denied socket operation; setting one worker still stalled on an asyncio
wakeup. Checked all 522 tracked Python files individually with Black, with
**522 passing and 0 failing**, to populate a writable cache without parallel
socket operations. The required whole-tree command then exited **0**:

```sh
BLACK_CACHE_DIR=/tmp/issue-2012-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

```text
All done! ✨ 🍰 ✨
522 files would be left unchanged.
```

`ruff check tests/test_build_html.py` and `git diff --check` also exited **0**.
The original workspace's `.git` directory is read-only (`git add` failed to
create `.git/index.lock`), so the source commit was made in the isolated
checkout. The workspace's changed source files were verified byte-for-byte
against that commit. The documentation update is a subsequent evidence-only
commit; it does not change the tested source.

### Follow-up status

- [x] Restore the excluded HTML renderer test to default collection and verify its populated and empty cases.
- [x] Record the tested source commit, supported interpreter, exact full-suite invocation, nonzero exit, terminal output, and first blocked node with diagnostic traceback.
- [x] Distinguish the observed environmental blocker from the changed-pin regression before proposing application or dependency changes.
- [ ] Complete an unrestricted local `python -m pytest` run with exit 0 on a supported interpreter.

Remaining action: repeat the exact test command against the recorded source
in a local environment permitting socket operations, then record its actual
terminal summary. Full-suite acceptance remains **unverified**.

Attempted to add `needs-human` and a blocker comment to PR #2013. Both GitHub
write tools refused the operation: `MCP tool call requires approval, but approval
policy is never`. Neither remote change was applied. PR #2013 was read back as
open and ready for review. The original workspace retains the three changed
files; the isolated checkout holds the commits, also exported to
`/tmp/issue-2012-commits.patch` for handoff.

Refs #1973, #2012

## Issue #2012 retry after autofix — 2026-11-08

### Remove both default-collection exclusions

Autofix commit `780981c4dacba38315a156f750c8f80d519215ee` restored
`--ignore=tests/test_build_html.py`. Inspection also found that
`norecursedirs = ["scripts"]` excluded `tests/scripts`, including the merged
#2005 pin regressions. Consequently, the earlier claim of no configured
exclusions was incomplete even after removing the HTML ignore. The earlier
runtime, focused, deliberate-break, regenerated-gate, and controller evidence
above remains historical evidence, not a full-suite pass.

Removed both exclusions. Added
`tests/test_pytest_collection.py::test_default_collection_includes_html_and_pin_regressions`,
which runs the real default pytest collection in a subprocess and requires both
HTML cases plus the live-producer snapshot and pre-install workflow guard nodes.
It only collects tests, so it does not recursively execute itself. The guard
failed before removing the HTML ignore, and its expanded assertion failed while
the script-directory exclusion remained. Both failures named the missing nodes.

After removing both exclusions, the following command from the isolated checkout
exited **0**:

```sh
python -m pytest tests/test_pytest_collection.py tests/test_build_html.py tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -m 'not slow' -q -rs
```

```text
SKIPPED [1] tests/scripts/test_cross_repo_dev_pins.py:173: TPP_REPO_PATH not set; the cross-repo smoke workflow provides it
SKIPPED [1] tests/scripts/test_cross_repo_dev_pins.py:191: TPP_REPO_PATH not set; the cross-repo smoke workflow provides it
SKIPPED [1] tests/scripts/test_cross_repo_smoke_workflow.py:222: actionlint not found (checked .workflows-lib/actionlint and PATH)
79 passed, 3 skipped, 14 warnings in 8.04s
```

### Committed source, runtime, and unrestricted result

Created `/tmp/trip-planner-issue-2012-retry` with
`git clone --shared --no-hardlinks . /tmp/trip-planner-issue-2012-retry`.
The tested source commit is
**`1356aebdf1be7744edde79b683c26d30346b5939`**, based on
`780981c4dacba38315a156f750c8f80d519215ee`. The checkout was clean before the
recorded committed-source run. Both merged-PR ancestry checks exited **0**:

```sh
git merge-base --is-ancestor 29c6aa01064f9eb3cbf15debd32cac3327ec43b8 HEAD
git merge-base --is-ancestor 4c6ff3e81b412db4039f7d1a48fa95d0aecff753 HEAD
```

`.python-version` selects **3.14**; `pyproject.toml` supports **>=3.13,<3.15**.
Selected **CPython 3.14.10**, built with GCC 15.2.0, executable
`/opt/hostedtoolcache/Python/3.14.10/x64/bin/python`, with pytest **9.2.0**.
`PYTEST_ADDOPTS` and `TPP_REPO_PATH` were unset.

The Makefile:test equivalent was exactly **`python -m pytest`**, without marker
filters or configured test exclusions. The shell invocation bounded the known
hang without changing pytest's arguments:

```sh
timeout --signal=INT --kill-after=5s 30s python -m pytest > /tmp/issue-2012-retry-committed-full-pytest.log 2>&1
```

Observed wrapper exit status: **137**. Complete terminal output:

```text
============================= test session starts ==============================
platform linux -- Python 3.14.10, pytest-9.2.0, pluggy-1.7.0
rootdir: /tmp/trip-planner-issue-2012-retry
configfile: pyproject.toml
testpaths: tests
plugins: cov-7.1.0, regressions-2.11.0, platformdirs-4.14.5, datadir-1.9.0, langsmith-0.14.17, pytest_httpserver-1.1.5, anyio-4.14.2
collected 2871 items / 2 skipped

tests/app/test_auth.py
```

Terminal result: **no tests finished; no pytest result summary was emitted**.
The watchdog sent SIGINT after 30 seconds and killed the process five seconds
later. This is a terminated run, not an assertion failure or an exit-0 result.
Default collection now includes 197 previously excluded script tests, both HTML
cases, and the new collection guard, compared with the 2,671-test baseline.

### First blocked node and classification

The first blocked node remains
`tests/app/test_auth.py::test_signup_creates_account_sets_cookie_and_restores_session`.
A separate diagnostic run, bounded at 20 seconds plus five seconds to exit, used:

```sh
python -m pytest tests/app/test_auth.py::test_signup_creates_account_sets_cookie_and_restores_session -vv -o faulthandler_timeout=10
```

Its timeout traceback again identifies fixture setup, before the test body:

```text
tests/app/test_auth.py::test_signup_creates_account_sets_cookie_and_restores_session Timeout (0:00:10)!
Thread [asyncio-portal-] (most recent call first):
  File ".../python3.14/selectors.py", line 452 in select
  File ".../python3.14/asyncio/base_events.py", line 2026 in _run_once
  File ".../python3.14/asyncio/base_events.py", line 678 in run_forever
  File ".../site-packages/anyio/from_thread.py", line 536 in run_blocking_portal
Thread [python] (most recent call first):
  File ".../python3.14/threading.py", line 369 in wait
  File ".../python3.14/concurrent/futures/_base.py", line 449 in result
  File ".../site-packages/anyio/_backends/_asyncio.py", line 2715 in run_sync_from_thread
  File ".../site-packages/anyio/from_thread.py", line 301 in _spawn_task_from_thread
  File ".../site-packages/anyio/from_thread.py", line 382 in start_task_soon
  File ".../site-packages/starlette/testclient.py", line 696 in __enter__
  File "/tmp/trip-planner-issue-2012-retry/tests/app/test_auth.py", line 21 in client
```

The standard-library socketpair probe again created the pair but failed on
`a.send(b"x")` with `PermissionError: [Errno 1] Operation not permitted`.
Classification remains **environmental blocker, high confidence**: the denied
cross-thread socket wakeup is independent of repository imports and changed dev
pins. The focused offline pin tests pass. This does not establish the behavior
of tests after the blocked fixture; no application or dependency changes were
made to mask it.

### Formatting and handoff

Black **26.10.1** formatted the new test. The whole-tree check initially hit the
same socket restriction in multiprocessing. After checking all 523 Python files
individually with a writable cache, the required gate exited **0**:

```sh
BLACK_CACHE_DIR=/tmp/issue-2012-retry-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

```text
All done! ✨ 🍰 ✨
523 files would be left unchanged.
```

`ruff check tests/test_pytest_collection.py` and `git diff --check` exited **0**.
The workspace's `.git` directory is still read-only, so the source commit was
created in the isolated checkout. Its two changed source files match the
workspace byte-for-byte. The evidence update follows in a separate commit;
the exported commits are `/tmp/issue-2012-retry-commits.patch`.

Attempted to add `needs-human` and a blocker comment to PR #2013 for this retry.
Both GitHub write tools again refused: `MCP tool call requires approval, but
approval policy is never`. Neither remote change was applied.

- [x] Remove both configured exclusions and verify that default collection includes the renderer and dev-pin regressions.
- [x] Record the supported runtime, exact source commit, unrestricted command, nonzero result, first blocked node, traceback, and failure classification.
- [ ] Complete unrestricted local `python -m pytest` with exit 0 on a supported interpreter.

Full-suite acceptance remains **unverified**. The remaining action is to run
the recorded source on a supported interpreter where socket operations are
permitted, then record the actual terminal summary.

## Issue #2012 current-source collection repair — 2026-11-08

### Remove the later collection hook

Commits `5f9b16e7`, `cd69a40e`, and `ed95fe4c` added and adjusted a
`pytest_ignore_collect` hook after the preceding evidence run. It excluded all
but two Python script test modules during default collection. Removed the hook
and its allowlist from `tests/conftest.py`: that exclusion conflicts with the
required unrestricted run. No workflow, dependency pin, or application code changed.

Strengthened the collection regression to compare default collection against
explicit collection of every `tests/scripts/test_*.py` file. This exercises real
pytest collection and detects omitted test nodes, including parametrized cases.
The new assertion failed with the hook present (**1 failed, 14 warnings in
11.30s**) and passes after its removal. Default `python -m pytest --collect-only
-q` exits **0** with **2,871 tests collected**, including **197 script cases
across all 10 Python script modules**.

### Exact source and unrestricted terminal result

Created `/tmp/trip-planner-issue-2012-final` using
`git clone --shared --no-hardlinks . /tmp/trip-planner-issue-2012-final`.
Tested source commit **`d7e1b0ddc5fe6735b27d9bdc186b938ffc41b830`**, based on
**`ed95fe4c47c9896ea9a8eaaaad0d34739dcf45b8`**, contains the hook removal and
expanded regression. The checkout was clean before the full run. Both ancestry
checks exited **0**, confirming merged #2005 and #2011 are included:

```sh
git merge-base --is-ancestor 29c6aa01064f9eb3cbf15debd32cac3327ec43b8 HEAD
git merge-base --is-ancestor 4c6ff3e81b412db4039f7d1a48fa95d0aecff753 HEAD
```

Selected **CPython 3.14.10**, built with GCC 15.2.0, executable
**`/opt/hostedtoolcache/Python/3.14.10/x64/bin/python`**, with pytest **9.2.0**.
This matches `.python-version` (**3.14**) and satisfies `pyproject.toml`
(**>=3.13,<3.15**). `PYTEST_ADDOPTS` and `TPP_REPO_PATH` were unset.

The exact Makefile:test equivalent was **`python -m pytest`**, with no test
exclusions or marker filters. A watchdog bounded the reproduced environmental
hang without changing pytest's arguments:

```sh
timeout --signal=INT --kill-after=5s 30s python -m pytest > /tmp/issue-2012-final-full-pytest.log 2>&1
```

Observed wrapper exit status: **137**. Complete terminal output:

```text
============================= test session starts ==============================
platform linux -- Python 3.14.10, pytest-9.2.0, pluggy-1.7.0
rootdir: /tmp/trip-planner-issue-2012-final
configfile: pyproject.toml
testpaths: tests
plugins: cov-7.1.0, regressions-2.11.0, platformdirs-4.14.5, datadir-1.9.0, langsmith-0.14.17, pytest_httpserver-1.1.5, anyio-4.14.2
collected 2871 items / 2 skipped

tests/app/test_auth.py
```

**No tests finished; pytest emitted no result summary.** SIGINT was sent after
30 seconds, followed by a kill five seconds later. Exit 137 is the watchdog's
termination result, not a pytest assertion-failure result or a full-suite pass.

### First blocked node and classification

The first blocked node remains
`tests/app/test_auth.py::test_signup_creates_account_sets_cookie_and_restores_session`.
The separate diagnostic command was:

```sh
timeout --signal=INT --kill-after=5s 20s python -m pytest tests/app/test_auth.py::test_signup_creates_account_sets_cookie_and_restores_session -vv -o faulthandler_timeout=10 > /tmp/issue-2012-final-auth.log 2>&1
```

It exited **137**. Its timeout traceback excerpt again identifies fixture setup:

```text
tests/app/test_auth.py::test_signup_creates_account_sets_cookie_and_restores_session Timeout (0:00:10)!
Thread [asyncio-portal-] (most recent call first):
  File ".../python3.14/selectors.py", line 452 in select
  File ".../python3.14/asyncio/base_events.py", line 2026 in _run_once
  File ".../python3.14/asyncio/base_events.py", line 678 in run_forever
  File ".../site-packages/anyio/from_thread.py", line 536 in run_blocking_portal
Thread [python] (most recent call first):
  File ".../python3.14/threading.py", line 369 in wait
  File ".../python3.14/concurrent/futures/_base.py", line 449 in result
  File ".../site-packages/anyio/_backends/_asyncio.py", line 2715 in run_sync_from_thread
  File ".../site-packages/anyio/from_thread.py", line 301 in _spawn_task_from_thread
  File ".../site-packages/anyio/from_thread.py", line 382 in start_task_soon
  File ".../site-packages/starlette/testclient.py", line 696 in __enter__
  File "/tmp/trip-planner-issue-2012-final/tests/app/test_auth.py", line 21 in client
```

The independent standard-library socketpair probe still raises
`PermissionError: [Errno 1] Operation not permitted` at `a.send(b"x")`, exit
**1**, without importing the repository or dev tools. Classification remains
**environmental blocker, high confidence**. The traceback and denied wakeup
operation do not establish a changed-pin regression. Tests after this fixture
remain unverified; the collection repair does not resolve the socket restriction.

### Focused validation and handoff

In the isolated checkout, the following focused command exited **0**:

```sh
python -m pytest tests/test_pytest_collection.py tests/test_build_html.py tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -m 'not slow' -q -rs
```

```text
SKIPPED [1] tests/scripts/test_cross_repo_dev_pins.py:173: TPP_REPO_PATH not set; the cross-repo smoke workflow provides it
SKIPPED [1] tests/scripts/test_cross_repo_dev_pins.py:191: TPP_REPO_PATH not set; the cross-repo smoke workflow provides it
SKIPPED [1] tests/scripts/test_cross_repo_smoke_workflow.py:222: actionlint not found (checked .workflows-lib/actionlint and PATH)
79 passed, 3 skipped, 14 warnings in 10.17s
```

Black **26.10.1** formatted both changed Python files individually. Its parallel
runner hit the socket restriction, so all 523 tracked Python files were checked
individually to populate the cache. The required whole-tree gate then exited **0**:

```sh
BLACK_CACHE_DIR=/tmp/issue-2012-final-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

```text
All done! ✨ 🍰 ✨
523 files would be left unchanged.
```

`ruff check tests/conftest.py tests/test_pytest_collection.py` and
`git diff --check` exited **0**. The workspace's `.git` remains read-only, so
commits were created in the isolated checkout; the changed files match the
workspace byte-for-byte. Commits are exported to
`/tmp/issue-2012-final-commits.patch`.

PR #2013 was read back as **open**, **draft=false**. Attempts to add
`needs-human` and a blocker comment were rejected by both GitHub write tools:
`MCP tool call requires approval, but approval policy is never`. Neither remote
change was applied.

- [x] Remove the default script-test allowlist and verify all script nodes remain in default collection.
- [x] Record the current tested source, supported runtime, exact unrestricted command, terminal result, and diagnostic traceback.
- [ ] Obtain an unrestricted local `python -m pytest` exit 0 on a supported interpreter.

Full-suite acceptance remains **unverified**. Rerun the **current source with
the collection exclusions removed** in an environment permitting socket
operations, and record that run's exact commit and terminal summary. Earlier
recorded commits that still contain collection exclusions cannot satisfy this
acceptance requirement. Retain all earlier focused, deliberate-break,
regenerated-gate, and controller evidence above.

## Issue #2012 whole-suite collection guard — 2026-11-08

### Verified test change

Extended `tests/test_pytest_collection.py` beyond script tests: its explicit
collection reference now includes all **186 Python test modules** under `tests`,
using both default pytest filename patterns (`test_*.py` and `*_test.py`). It
compares actual test nodes, including parametrized cases, against default
collection. This protects the unrestricted-suite requirement against exclusions
in application and other test directories as well as scripts.

In the isolated checkout, temporarily added the configured exclusion
`--ignore=tests/app/test_auth.py`. The expanded regression failed, exit **1**,
naming all five omitted authentication nodes:

```text
FAILED tests/test_pytest_collection.py::test_default_collection_includes_all_regressions
1 failed, 14 warnings in 11.62s
```

Restored `pyproject.toml` byte-for-byte before validation and commit. No test
exclusion, dependency, workflow, or application change is included. The focused
command exited **0**:

```sh
python -m pytest tests/test_pytest_collection.py tests/test_build_html.py tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -m 'not slow' -q -rs
```

```text
SKIPPED [1] tests/scripts/test_cross_repo_dev_pins.py:173: TPP_REPO_PATH not set; the cross-repo smoke workflow provides it
SKIPPED [1] tests/scripts/test_cross_repo_dev_pins.py:191: TPP_REPO_PATH not set; the cross-repo smoke workflow provides it
SKIPPED [1] tests/scripts/test_cross_repo_smoke_workflow.py:222: actionlint not found (checked .workflows-lib/actionlint and PATH)
79 passed, 3 skipped, 14 warnings in 14.73s
```

### Isolated checkout and exact full-suite result

Created `/tmp/trip-planner-issue-2012-round4` using
`git clone --shared --no-hardlinks . /tmp/trip-planner-issue-2012-round4`, based
on **`b1b1ac7b712c53dcc33ccdd7c358285ab30abb33`**. The tested source commit is
**`ac815af9487b1d424248fd989adf7a228674c6f4`**; the checkout was clean before its full-suite
run. Both ancestry commands exited **0**, establishing inclusion of merged
#2005 and #2011:

```sh
git merge-base --is-ancestor 29c6aa01064f9eb3cbf15debd32cac3327ec43b8 HEAD
git merge-base --is-ancestor 4c6ff3e81b412db4039f7d1a48fa95d0aecff753 HEAD
```

Selected **CPython 3.14.10**, GCC **15.2.0**, executable
**`/opt/hostedtoolcache/Python/3.14.10/x64/bin/python`**, pytest **9.2.0**.
This matches `.python-version` (**3.14**) and satisfies `pyproject.toml`
(**>=3.13,<3.15**). `PYTEST_ADDOPTS` and `TPP_REPO_PATH` were unset.

The exact Makefile:test equivalent was **`python -m pytest`**, with no
exclusions or marker filter. The shell wrapper bounded the known hang:

```sh
timeout --signal=INT --kill-after=5s 30s python -m pytest > /tmp/issue-2012-round4-committed-full-clean.log 2>&1
```

Observed wrapper exit status: **137**. Complete terminal output:

```text
============================= test session starts ==============================
platform linux -- Python 3.14.10, pytest-9.2.0, pluggy-1.7.0
rootdir: /tmp/trip-planner-issue-2012-round4
configfile: pyproject.toml
testpaths: tests
plugins: cov-7.1.0, regressions-2.11.0, platformdirs-4.14.5, datadir-1.9.0, langsmith-0.14.17, pytest_httpserver-1.1.5, anyio-4.14.2
collected 2871 items / 2 skipped

tests/app/test_auth.py
```

**No tests finished; pytest emitted no result summary.** The wrapper sent
SIGINT after 30 seconds, then killed the process five seconds later. This
termination does not establish a pytest assertion failure or a suite pass.

### First blocked node, traceback, and classification

The first blocked node remains
`tests/app/test_auth.py::test_signup_creates_account_sets_cookie_and_restores_session`.
A separate diagnostic command exited **137**:

```sh
timeout --signal=INT --kill-after=5s 20s python -m pytest tests/app/test_auth.py::test_signup_creates_account_sets_cookie_and_restores_session -vv -o faulthandler_timeout=10 > /tmp/issue-2012-round4-auth.log 2>&1
```

Its traceback again identifies fixture setup before the test body:

```text
tests/app/test_auth.py::test_signup_creates_account_sets_cookie_and_restores_session Timeout (0:00:10)!
Thread [asyncio-portal-] (most recent call first):
  File ".../python3.14/selectors.py", line 452 in select
  File ".../python3.14/asyncio/base_events.py", line 2026 in _run_once
  File ".../python3.14/asyncio/base_events.py", line 678 in run_forever
  File ".../site-packages/anyio/from_thread.py", line 536 in run_blocking_portal
Thread [python] (most recent call first):
  File ".../python3.14/threading.py", line 369 in wait
  File ".../python3.14/concurrent/futures/_base.py", line 449 in result
  File ".../site-packages/anyio/_backends/_asyncio.py", line 2715 in run_sync_from_thread
  File ".../site-packages/anyio/from_thread.py", line 301 in _spawn_task_from_thread
  File ".../site-packages/anyio/from_thread.py", line 382 in start_task_soon
  File ".../site-packages/starlette/testclient.py", line 696 in __enter__
  File "/tmp/trip-planner-issue-2012-round4/tests/app/test_auth.py", line 21 in client
```

An independent standard-library socketpair probe, before repository imports,
again failed at `a.send(b"x")` with
`PermissionError: [Errno 1] Operation not permitted`, exit **1**.
Classification: **environmental blocker, high confidence**. The denied
cross-thread wakeup and passing offline pin tests do not indicate a changed-pin
regression. Later tests remain unverified. The collection guard does not resolve
the environment restriction.

### Formatting and handoff

Black **26.10.1** formatted the changed Python file. After checking all
**523 tracked Python files** individually to populate a cache without parallel
socket operations, the required whole-tree gate exited **0**:

```sh
BLACK_CACHE_DIR=/tmp/issue-2012-round4-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

```text
All done! ✨ 🍰 ✨
523 files would be left unchanged.
```

`ruff check tests/test_pytest_collection.py` and `git diff --check` exited **0**.
The workspace `.git` directory is read-only, so commits were created in the
isolated checkout; changed files match the workspace byte-for-byte. Exported
commits: `/tmp/issue-2012-round4-commits.patch`.

PR #2013 was read back as **open**, **draft=false**. Both the `needs-human`
label and blocker comment were rejected by the GitHub tools:
`MCP tool call requires approval, but approval policy is never`. Neither remote
change was applied.

- [x] Extend unrestricted-collection protection to every Python test module and verify detection of a deliberately excluded application module.
- [x] Record the current source, supported runtime, exact unrestricted invocation, termination result, first blocked node, diagnostic traceback, and failure classification.
- [ ] Obtain unrestricted local `python -m pytest` exit 0 on a supported interpreter.

Full-suite acceptance remains **unverified**. Run the current source on supported
Python in an environment permitting local socket operations, and record the
actual exit status and terminal summary. Retain all earlier focused,
deliberate-break, regenerated-gate, and controller evidence above.

## Issue #2012 collection-hook audit and task reconciliation — 2026-11-08

Reviewed the recent commits through `b171d4a9`, including the collection-hook
removal, Jinja2 dependency declaration, and whole-suite collection guard.
The isolated execution and failure-diagnosis tasks have recorded evidence and
can be checked in both copies of the PR checklist. The unrestricted exit-0
acceptance criterion remains unchecked.

### Clean, reviewer-accessible source and unrestricted attempt

Created `/tmp/trip-planner-issue-2012-round5` with
`git clone --shared --no-hardlinks . /tmp/trip-planner-issue-2012-round5`.
The checkout was clean at tested commit
[`b171d4a9757f7d91b5b51946229227d7a1fbf8af`](https://github.com/stranske/trip-planner/commit/b171d4a9757f7d91b5b51946229227d7a1fbf8af).
Both merged-PR ancestry checks exited **0**:

```sh
git merge-base --is-ancestor 29c6aa01064f9eb3cbf15debd32cac3327ec43b8 HEAD
git merge-base --is-ancestor 4c6ff3e81b412db4039f7d1a48fa95d0aecff753 HEAD
```

Selected **CPython 3.14.10**, GCC **15.2.0**, executable
`/opt/hostedtoolcache/Python/3.14.10/x64/bin/python`, pytest **9.2.0**.
This matches `.python-version` (**3.14**) and satisfies `pyproject.toml`
(**>=3.13,<3.15**). `PYTEST_ADDOPTS` and `TPP_REPO_PATH` were unset.
The exact Makefile:test equivalent was **`python -m pytest`**, without
exclusions or a marker filter. The watchdog invocation was:

```sh
timeout --signal=INT --kill-after=5s 30s python -m pytest > /tmp/issue-2012-round5-full.log 2>&1
```

Observed wrapper exit: **137**. The terminal output ended with:

```text
collected 2871 items / 2 skipped

tests/app/test_auth.py
```

**No tests finished and no pytest result summary was emitted.** SIGINT after
30 seconds did not stop the blocked process; the watchdog killed it five
seconds later. This is a terminated run, not a successful suite or an assertion
failure.

The first blocked node was again
`tests/app/test_auth.py::test_signup_creates_account_sets_cookie_and_restores_session`.
The separate diagnostic command exited **137**:

```sh
timeout --signal=INT --kill-after=5s 20s python -m pytest tests/app/test_auth.py::test_signup_creates_account_sets_cookie_and_restores_session -vv -o faulthandler_timeout=10 > /tmp/issue-2012-round5-auth.log 2>&1
```

Its traceback showed the same fixture-setup wait:

```text
Timeout (0:00:10)!
Thread [asyncio-portal-]:
  File ".../python3.14/selectors.py", line 452 in select
  File ".../python3.14/asyncio/base_events.py", line 2026 in _run_once
Thread [python]:
  File ".../python3.14/threading.py", line 369 in wait
  File ".../python3.14/concurrent/futures/_base.py", line 449 in result
  File ".../site-packages/anyio/_backends/_asyncio.py", line 2715 in run_sync_from_thread
  File ".../site-packages/starlette/testclient.py", line 696 in __enter__
  File "/tmp/trip-planner-issue-2012-round5/tests/app/test_auth.py", line 21 in client
```

An independent standard-library socketpair write again raised
`PermissionError: [Errno 1] Operation not permitted` before repository imports.
Classification remains **environmental blocker, high confidence**, rather than
a demonstrated changed-pin regression. The focused pin tests pass below;
later full-suite tests remain unverified.

### Close the shared-filter blind spot

The previous collection comparison could miss a hook that silently removed
the same nodes from both default and explicit-file collection. Added an audit
plugin, loaded only by the guard's collection subprocesses, that compares nodes
before and after collection-modification hooks and fails with the removed
nodes. Parametrized subprocess regressions verify unchanged collection,
reordering, and silent removal of one parametrized case.

In the isolated checkout, temporarily added a hook removing the first
authentication node from both collections. The guard failed, exit **1**,
with `Collection hooks removed regressions` and the omitted node's name.
Restored `tests/conftest.py` byte-for-byte before validation. This change
protects unrestricted collection; it does not resolve the socket restriction.

Focused validation of the changed guard and existing renderer/pin tests exited
**0** in the isolated checkout:

```sh
python -m pytest tests/test_pytest_collection.py tests/test_pytest_collection_audit.py tests/test_build_html.py tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -m 'not slow' -q -rs
```

```text
82 passed, 3 skipped, 14 warnings in 18.79s
```

The skips require the live producer checkout (two) and actionlint (one).
The clean full-suite attempt above predates this audit change and remains
separate from these focused results.

Black **26.10.1** formatted the changed Python files. Serial checks populated a
writable cache without socket operations; the required whole-tree gate exited
**0**, reporting **525 files would be left unchanged**:

```sh
BLACK_CACHE_DIR=/tmp/issue-2012-round5-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

Ruff on the three changed Python files and `git diff --check` also exited **0**.
The workspace's `.git` directory is read-only, so the changes are committed in
the isolated checkout and exported to `/tmp/issue-2012-round5-commits.patch`.
The committed files match the workspace byte-for-byte.

GitHub rejected the PR-body reconciliation, `needs-human` label, and blocker
comment with `MCP tool call requires approval, but approval policy is never`.
None of those remote writes was applied. The prepared reconciled body is
`/tmp/issue-2012-round5-pr-body.md`; only the duplicated execution and diagnosis
checkboxes change. Full-suite acceptance stays **unverified** until the current
source exits **0** under `python -m pytest` on supported Python with local
socket operations permitted.

## Issue #2012 explicit runtime failure — 2026-11-08

Created a fresh isolated checkout using
`git clone --shared --no-hardlinks . /tmp/trip-planner-issue-2012-round6`,
initially clean at `d2ca5e40cc4e8f4240bccbd411d5fd396ae964b3`.
Both merged-PR ancestry checks exited **0**:

```sh
git merge-base --is-ancestor 29c6aa01064f9eb3cbf15debd32cac3327ec43b8 HEAD
git merge-base --is-ancestor 4c6ff3e81b412db4039f7d1a48fa95d0aecff753 HEAD
```

Selected **CPython 3.14.10**, GCC **15.2.0**, executable
`/opt/hostedtoolcache/Python/3.14.10/x64/bin/python`, with pytest **9.2.0**.
This matches `.python-version` (**3.14**) and satisfies `pyproject.toml`
(**>=3.13,<3.15**). `PYTEST_ADDOPTS` and `TPP_REPO_PATH` were unset.

The initial unrestricted attempt used the exact Makefile:test command with an
external watchdog:

```sh
timeout --signal=INT --kill-after=5s 30s python -m pytest > /tmp/issue-2012-round6-initial-full.log 2>&1
```

It collected **2874 items / 2 skipped**, then stalled before completing the
first authentication test; wrapper exit **137**. A separate diagnostic
invocation of
`tests/app/test_auth.py::test_signup_creates_account_sets_cookie_and_restores_session`
with `-vv -o faulthandler_timeout=10` and a 20-second watchdog also exited
**137**, identifying the same fixture-setup wait:

```text
Thread [asyncio-portal-]:
  File ".../python3.14/selectors.py", line 452 in select
  File ".../python3.14/asyncio/base_events.py", line 2026 in _run_once
Thread [python]:
  File ".../python3.14/threading.py", line 369 in wait
  File ".../python3.14/concurrent/futures/_base.py", line 449 in result
  File ".../site-packages/anyio/_backends/_asyncio.py", line 2715 in run_sync_from_thread
  File ".../site-packages/starlette/testclient.py", line 696 in __enter__
  File "/tmp/trip-planner-issue-2012-round6/tests/app/test_auth.py", line 21 in client
```

A standalone `socket.socketpair()` write again raised
`PermissionError: [Errno 1] Operation not permitted`, before repository imports.
Classification remains **environmental blocker, high confidence**; no evidence
implicates the changed dev-tool pins. Later full-suite tests remain unverified.

### Fail explicitly before entering the blocked portal

Added a session fixture in the app test directory that verifies bounded local
socketpair I/O before TestClient starts. A denied operation now terminates
pytest with exit **1** and the underlying error. It neither excludes tests nor
turns the restriction into a successful run. Eight regressions exercise allowed
I/O, denial during socket creation/setup/write/read, an empty read, resource
cleanup, and subprocess execution of the actual app fixture on both allowed and
denied runtimes.

Committed source in the isolated checkout at
**`6d528142da7c34f88f22f9f108c4b70285403310`**. The checkout was clean, and the
same merged-PR ancestry checks still exited **0**. Ran the exact unrestricted
command on that commit without a watchdog, exclusions, or a marker filter:

```sh
python -m pytest > /tmp/issue-2012-round6-committed-full.log 2>&1
```

Observed exit **1**; terminal result:

```text
collected 2882 items / 2 skipped
tests/app/test_auth.py
======================= 2 skipped, 14 warnings in 2.42s ========================
! _pytest.outcomes.Exit: TestClient runtime unavailable: local socketpair I/O failed ([Errno 1] Operation not permitted). Run the unchanged suite in an environment permitting local socket operations. This is an environment failure, not a passing test run. !
```

No test bodies completed in this full-suite attempt. The two collection-time
skips predate the runtime check. The first selected authentication node remains
blocked, now explicitly at the new runtime fixture.

Focused validation in the isolated checkout exited **0**:

```sh
python -m pytest tests/test_runtime_requirements.py tests/test_pytest_collection.py tests/test_pytest_collection_audit.py tests/test_build_html.py tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -m 'not slow' -q -rs
```

```text
90 passed, 3 skipped, 14 warnings in 21.34s
```

The existing skips require the live producer checkout (two) and actionlint
(one). Black **26.10.1** formatted the changed files. After serial checks of
all Python files populated a writable cache, the required whole-tree gate
exited **0**, reporting **527 files would be left unchanged**:

```sh
BLACK_CACHE_DIR=/tmp/issue-2012-round6-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

Ruff on the three changed Python files and `git diff --check` passed.
The workspace `.git` directory is read-only; source and evidence commits are
created in the isolated checkout, with matching files in the workspace and an
export at `/tmp/issue-2012-round6-commits.patch`.

PR #2013 readback was **open**, **draft=false**. GitHub rejected both the
`needs-human` label and blocker comment with
`MCP tool call requires approval, but approval policy is never`; neither remote
write was applied.

- [x] Run the unrestricted Makefile:test equivalent on an isolated checkout containing merged #2005 and #2011 with a supported interpreter.
- [x] Verify explicit runtime failure and record the tested commit, command, exit status, terminal result, and failure classification.
- [ ] Obtain unrestricted local `python -m pytest` exit 0 on supported Python.

Full-suite acceptance remains **unverified**. The required next step is to run
the current source in an environment permitting local socket operations and
record an actual unrestricted exit **0**. All earlier producer, deliberate-break,
regenerated-gate, and controller evidence remains above.

## Issue #2012 operation-specific runtime evidence — 2026-11-08

Created `/tmp/trip-planner-issue-2012-round7` with
`git clone --shared --no-hardlinks . /tmp/trip-planner-issue-2012-round7`.
The initial clean checkout at `0f501cb1ab9fa5d087f0ee6fd76018a86faacead`
ran unrestricted `python -m pytest`, exited **1**, and reported the existing
socketpair precondition failure before any test body completed.

Improved that diagnostic to name the failing operation and exception class.
Expanded regressions cover receiver timeout setup and send/receive timeouts,
alongside the existing denial, empty-read, cleanup, and fixture checks.
The source is committed in the isolated checkout at
**`17b68e66a48f0357d7103afc37782413a303dd4a`**. Its working tree was clean
before the final run. Both ancestry checks exited **0** on this commit:

```sh
git merge-base --is-ancestor 29c6aa01064f9eb3cbf15debd32cac3327ec43b8 HEAD
git merge-base --is-ancestor 4c6ff3e81b412db4039f7d1a48fa95d0aecff753 HEAD
```

Selected **CPython 3.14.10**, GCC **15.2.0**, executable
`/opt/hostedtoolcache/Python/3.14.10/x64/bin/python`, pytest **9.2.0**.
This matches `.python-version` (**3.14**) and `pyproject.toml`
(**>=3.13,<3.15**). `PYTEST_ADDOPTS` and `TPP_REPO_PATH` were unset.
The exact unrestricted Makefile:test equivalent, without a watchdog or filters:

```sh
python -m pytest > /tmp/issue-2012-round7-committed-full.log 2>&1
```

Exit **1**; terminal output excerpt:

```text
collected 2885 items / 2 skipped
tests/app/test_auth.py
======================= 2 skipped, 14 warnings in 2.62s ========================
! _pytest.outcomes.Exit: TestClient runtime unavailable: local socketpair I/O failed during send wakeup byte (PermissionError: [Errno 1] Operation not permitted). Run the unchanged suite in an environment permitting local socket operations. This is an environment failure, not a passing test run. !
```

No test bodies completed. The first selected node remains
`tests/app/test_auth.py::test_signup_creates_account_sets_cookie_and_restores_session`,
blocked during `require_app_test_runtime` setup. A separate direct invocation
of the helper exited **1** and exposed the underlying traceback:

```text
File "/tmp/trip-planner-issue-2012-round7/tests/runtime_requirements.py", line 19, in require_testclient_socket_io
  sender.sendall(b"x")
PermissionError: [Errno 1] Operation not permitted
```

A standalone standard-library socketpair write also failed with the same error
before repository imports. Classification: **environmental blocker, high
confidence**, with no evidence of a changed-pin regression. The diagnostic
change does not resolve the restriction; later tests remain unverified.

Focused validation in the isolated checkout exited **0**:

```sh
python -m pytest tests/test_runtime_requirements.py tests/test_pytest_collection.py tests/test_pytest_collection_audit.py -m 'not slow' -q
```

Terminal summary: **15 passed, 14 warnings in 22.22s**. Black formatted both
changed Python files. After serial Black checks populated a writable cache,
the required gate exited **0**, reporting **527 files would be left unchanged**:

```sh
BLACK_CACHE_DIR=/tmp/issue-2012-round7-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

Ruff on both changed files and `git diff --check` passed. Source and evidence
commits reside in the isolated checkout because the workspace `.git` is
read-only; the export is `/tmp/issue-2012-round7-commits.patch`. Changed files
match the workspace byte-for-byte. PR #2013 readback was **open, draft=false**.
Both the `needs-human` label and blocker comment were rejected with
`MCP tool call requires approval, but approval policy is never`; neither was
applied remotely.

- [x] Execute unrestricted `python -m pytest` on an isolated checkout containing merged #2005 and #2011 with a supported interpreter.
- [x] Verify the operation-specific diagnostic and record the committed-source full-suite failure.
- [ ] Obtain unrestricted local `python -m pytest` exit 0 on supported Python.

The exit-0 acceptance criterion remains unmet. Run the current source in an
environment permitting local socket operations and record the resulting full
terminal summary. Further collection or diagnostic changes cannot establish
that acceptance while this runtime restriction remains.

## Issue #2012 repeatable isolated-suite verification — 2026-11-08

Reviewed the preceding keepalive and autofix commits before continuing. They
verify unrestricted execution and failure documentation, but do not establish
exit-0 acceptance. The duplicate execution checkbox in PR #2013's embedded issue
text is stale; the corresponding task in its automated summary is already checked.
An attempted PR-body reconciliation was rejected with
`MCP tool call requires approval, but approval policy is never`. The remote body
therefore remains unchanged; the exit-0 acceptance boxes must remain unchecked.

Added `scripts/verify_local_suite.py` and five real-repository regressions. This
repository-local verification tool clones the committed source into a new output
directory, validates required merge ancestry, reads `.python-version` and
`pyproject.toml`, and checks the selected interpreter against `requires-python`.
It runs exactly the selected interpreter's `-m pytest`, with no exclusions,
marker filters, watchdog, or dependency installation. Inherited `PYTEST_ADDOPTS`,
`PYTHONPATH`, and Git location variables are removed. The tool retains combined
terminal output in `pytest.log` and writes the tested commit, runtime, ancestry,
command, checkout directory, timestamps, and actual exit status into `result.json`.
Existing evidence directories are never overwritten.

The tests verify that dirty source edits and inherited exclusions cannot hide a
committed failing test, failure tracebacks and nonzero statuses are retained,
passing runs record zero, old evidence survives another attempt, unsupported
interpreters are rejected, and required commits must actually be ancestors.
These synthetic passing runs test the tool; they are not repository acceptance.

### Committed-source full-suite result

Source commit: **`ec168e79590e97121c2b11f9a73c90a892e6798d`**, committed in
`/tmp/trip-planner-issue-2012-round8`. Its working tree was clean before running.
The runner verified ancestry of merged #2005
(`29c6aa01064f9eb3cbf15debd32cac3327ec43b8`) and #2011
(`4c6ff3e81b412db4039f7d1a48fa95d0aecff753`).

Reproduction from a checkout containing the committed source:

```sh
python scripts/verify_local_suite.py --source . --output /tmp/issue-2012-round8-full --python /opt/hostedtoolcache/Python/3.14.10/x64/bin/python --require-ancestor 29c6aa01064f9eb3cbf15debd32cac3327ec43b8 --require-ancestor 4c6ff3e81b412db4039f7d1a48fa95d0aecff753
```

Use a new output directory for another run and the absolute path to the supported
interpreter in that environment. Selected runtime: **CPython 3.14.10**, executable
`/opt/hostedtoolcache/Python/3.14.10/x64/bin/python`; pytest **9.2.0**.
This matches `.python-version` (**3.14**) and `pyproject.toml`
(**>=3.13,<3.15**). The runner's unrestricted child command, from isolated
`/tmp/issue-2012-round8-full/checkout`, was exactly:

```sh
/opt/hostedtoolcache/Python/3.14.10/x64/bin/python -m pytest
```

Both child and runner exited **1**. Terminal result:

```text
collected 2890 items / 2 skipped
tests/app/test_auth.py
======================= 2 skipped, 14 warnings in 7.17s ========================
! _pytest.outcomes.Exit: TestClient runtime unavailable: local socketpair I/O failed during send wakeup byte (PermissionError: [Errno 1] Operation not permitted). Run the unchanged suite in an environment permitting local socket operations. This is an environment failure, not a passing test run. !
```

The first selected node remains
`tests/app/test_auth.py::test_signup_creates_account_sets_cookie_and_restores_session`,
blocked in `require_app_test_runtime` before any test body executes. The underlying
`sender.sendall(b"x")` failure and traceback recorded above remain applicable;
a fresh standalone standard-library socketpair write failed identically before
repository imports. Classification: **environmental blocker, high confidence**;
there is no evidence of a changed-pin regression. Later test bodies remain
unverified. Complete artifacts are `/tmp/issue-2012-round8-full/result.json` and
`/tmp/issue-2012-round8-full/pytest.log`.

Focused validation on that same committed isolated checkout exited **0**:

```sh
python -m pytest tests/scripts/test_verify_local_suite.py tests/test_runtime_requirements.py tests/test_pytest_collection.py tests/test_pytest_collection_audit.py -m 'not slow' -q
```

Terminal summary: **20 passed, 14 warnings in 28.12s**.

Black formatted the new Python files. After serial cache preparation, the
required whole-tree command exited **0**, reporting **529 files would be left
unchanged**:

```sh
BLACK_CACHE_DIR=/tmp/issue-2012-round8-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

Ruff on both new Python files and `git diff --check` passed. Source commits reside
in the isolated checkout because workspace `.git` is read-only; matching files
remain in the workspace for automation pickup. The commit export is
`/tmp/issue-2012-round8-commits.patch`.

GitHub also rejected the requested `needs-human` label and blocker comment with
`MCP tool call requires approval, but approval policy is never`; neither remote
write was applied. Final PR #2013 readback was **open, draft=false**.

- [x] Reconcile prior evidence and execute the unrestricted command on an isolated supported-runtime checkout containing both required merges.
- [x] Implement and verify reproducible full-suite execution and exact evidence capture.
- [ ] Obtain unrestricted local `python -m pytest` exit 0 on supported Python.

Run this committed source in an environment permitting local socket operations
to establish the remaining exit-0 acceptance. Earlier producer, deliberate-break,
regenerated-gate, and controller evidence is retained above.

## Issue #2012 inherited-plugin isolation — 2026-11-08

Reviewed the latest commits before continuing. The duplicate unrestricted-run
task is already verified; both exit-0 acceptance boxes remain unverified.
Attempted to reconcile the PR body, add `needs-human`, and document the blocker
in a PR comment. Each write was rejected with `MCP tool call requires approval,
but approval policy is never`; no remote updates were applied. PR #2013 readback
remains **open, draft=false**.

Found and reproduced an evidence gap in `scripts/verify_local_suite.py`:
inherited `PYTEST_PLUGINS` can load a collection hook that removes a failing
test and makes the verifier report exit 0. The new regression demonstrates the
false pass before exercising the verifier; it failed against the previous
implementation. The verifier now removes this inherited setting alongside
`PYTEST_ADDOPTS` and `PYTHONPATH`. Repository-declared and installed plugins
remain available, and the child command remains unchanged. After the fix the
regression confirms both tests execute and the committed failure is retained.

Source commit **`f6f34298d8ac82108c1205b05d614c77b9e27f80`** resides in
`/tmp/trip-planner-issue-2012-round9`, whose working tree was clean before
verification. The verifier confirmed merged #2005
(`29c6aa01064f9eb3cbf15debd32cac3327ec43b8`) and #2011
(`4c6ff3e81b412db4039f7d1a48fa95d0aecff753`) are ancestors. Selected
**CPython 3.14.10**, executable
`/opt/hostedtoolcache/Python/3.14.10/x64/bin/python`, matches `.python-version`
**3.14** and satisfies `requires-python = ">=3.13,<3.15"`; pytest is **9.2.0**.
From the fresh isolated `/tmp/issue-2012-round9-full/checkout`, the exact
Makefile:test equivalent ran without exclusions or a watchdog:

```sh
/opt/hostedtoolcache/Python/3.14.10/x64/bin/python -m pytest
```

Exit **1**; terminal result:

```text
collected 2891 items / 2 skipped
tests/app/test_auth.py
======================= 2 skipped, 14 warnings in 7.01s ========================
! _pytest.outcomes.Exit: TestClient runtime unavailable: local socketpair I/O failed during send wakeup byte (PermissionError: [Errno 1] Operation not permitted). Run the unchanged suite in an environment permitting local socket operations. This is an environment failure, not a passing test run. !
```

The first selected node remains
`tests/app/test_auth.py::test_signup_creates_account_sets_cookie_and_restores_session`,
blocked in `require_app_test_runtime` before any test body executes. A fresh
standalone socketpair write also raised the same `PermissionError`, before
repository imports; the underlying helper traceback recorded above still
applies. Classification remains **environmental blocker, high confidence**,
with no evidence of a changed-pin regression. Full artifacts are
`/tmp/issue-2012-round9-full/result.json` and `pytest.log` in that directory.

Focused validation of the changed source and existing runtime/collection guards:

```sh
python -m pytest tests/scripts/test_verify_local_suite.py tests/test_runtime_requirements.py tests/test_pytest_collection.py tests/test_pytest_collection_audit.py -m 'not slow' -q
```

Exit **0**: **21 passed, 14 warnings in 35.41s**. Black formatted both changed
Python files; after serial cache preparation the required whole-tree gate
exited **0**, reporting **529 files would be left unchanged**:

```sh
BLACK_CACHE_DIR=/tmp/issue-2012-round9-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

Ruff on both changed Python files and `git diff --check` passed. Commits are
retained in the isolated checkout because workspace `.git` is read-only;
matching files remain in the workspace, and the commit export is
`/tmp/issue-2012-round9-commits.patch`.

- [x] Verify the unrestricted supported-runtime attempt on committed source containing both required merges.
- [x] Reproduce and prevent an inherited plugin from silently hiding a failing test.
- [ ] Obtain unrestricted local `python -m pytest` exit 0 on supported Python.

The remaining acceptance requires a runtime permitting local socket operations.
Additional diagnostic changes cannot supply the missing exit-0 evidence here.

## Issue #2012 relative-interpreter execution fix — 2026-11-08

Rechecked the first unchecked execution task in a fresh isolated checkout. The
baseline run on `d0a5214a7c3175d8833948501364553424dd7216` exited **1** with the
same socketpair restriction before the first test body. This establishes an
environmental blocker rather than a reason to change the planner/producer pins.

Found a separate execution bug in `scripts/verify_local_suite.py`: passing a
relative virtual-environment executable to `--python` looked for that executable
inside the new clone, where the local environment is absent. A real-venv regression
failed before the fix with `FileNotFoundError: 'local environment/bin/python'`.
Explicit interpreter paths are now made absolute before changing the subprocess
working directory, without dereferencing venv symlinks. The regression verifies
that the selected venv executes both committed tests, retains the deliberate
failure, and records its own executable path. It uses no dependency installation.
This corrects execution setup; it does not resolve the runner's socket restriction.

### Full suite on committed source

Tested source commit: **`0eca47878bfda800b1c5378377390604b98e9241`**, committed in
`/tmp/issue-2012-round10-baseline/checkout`, with a clean working tree before
verification. The verifier confirmed ancestry of merged #2005
(`29c6aa01064f9eb3cbf15debd32cac3327ec43b8`) and #2011
(`4c6ff3e81b412db4039f7d1a48fa95d0aecff753`). Selected **CPython 3.14.10**,
executable `/opt/hostedtoolcache/Python/3.14.10/x64/bin/python`, matches
`.python-version` **3.14** and satisfies `requires-python = ">=3.13,<3.15"`;
pytest is **9.2.0**. From the fresh isolated checkout
`/tmp/issue-2012-round10-full/checkout`, the exact Makefile:test equivalent ran
without exclusions or a watchdog:

```sh
/opt/hostedtoolcache/Python/3.14.10/x64/bin/python -m pytest
```

Exit **1**; terminal result:

```text
collected 2892 items / 2 skipped
tests/app/test_auth.py
======================= 2 skipped, 14 warnings in 7.59s ========================
! _pytest.outcomes.Exit: TestClient runtime unavailable: local socketpair I/O failed during send wakeup byte (PermissionError: [Errno 1] Operation not permitted). Run the unchanged suite in an environment permitting local socket operations. This is an environment failure, not a passing test run. !
```

First selected node:
`tests/app/test_auth.py::test_signup_creates_account_sets_cookie_and_restores_session`,
blocked in `require_app_test_runtime` before any test body. A direct call to the
unchanged runtime helper reproduced the underlying traceback:

```text
File "tests/runtime_requirements.py", line 19, in require_testclient_socket_io
  sender.sendall(b"x")
PermissionError: [Errno 1] Operation not permitted
```

Classification: **environmental blocker, high confidence**, with no evidence of a
changed-pin regression. Later tests remain unverified. Complete artifacts are
`/tmp/issue-2012-round10-full/result.json` and `pytest.log` in that directory.

Focused validation of the source fix and existing execution guards:

```sh
python -m pytest tests/scripts/test_verify_local_suite.py tests/test_runtime_requirements.py tests/test_pytest_collection.py tests/test_pytest_collection_audit.py -m 'not slow' -q
```

Exit **0**: **22 passed, 14 warnings in 39.28s**. Black formatted the changed
Python files. After serial cache preparation to avoid Black's blocked worker
sockets, the required whole-tree gate exited **0**, reporting **529 files would
be left unchanged**:

```sh
BLACK_CACHE_DIR=/tmp/issue-2012-round10-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

Ruff on both changed Python files and `git diff --check` passed. Commits reside
in the isolated checkout because workspace `.git` is read-only; matching files
remain in the workspace for automation pickup. The export is
`/tmp/issue-2012-round10-commits.patch`.

PR #2013 readback was **open, draft=false**. GitHub rejected both the requested
`needs-human` label and blocker comment with `MCP tool call requires approval,
but approval policy is never`; neither write was applied.

- [x] Execute the unrestricted suite on isolated committed source containing both required merges with a supported interpreter.
- [x] Reproduce and verify the fix for relative virtual-environment interpreter paths.
- [ ] Obtain unrestricted local `python -m pytest` exit 0 on supported Python.

The remaining acceptance still requires a runtime permitting local socket
operations. Earlier focused, deliberate-break, regenerated-gate, and controller
evidence is retained above.

## Issue #2012 runtime-abort evidence regression — 2026-11-08

Reviewed the six recently changed paths and reconciled the task list: execution
of the unrestricted command is verified; exit-0 acceptance is still incomplete.
The attempted duplicate-checkbox update, `needs-human` label, and blocker comment
were each rejected by GitHub tooling with `MCP tool call requires approval, but
approval policy is never`. No remote writes were applied. PR #2013 remains
**open, draft=false**.

Added an end-to-end regression in `tests/scripts/test_verify_local_suite.py`.
It runs the real socket-runtime helper in a committed fixture repository through
the verifier, simulates the denied wakeup write, and confirms exit 1, finished
evidence, the failure diagnostic, and that the test body never executes. This
checks evidence handling without changing the suite's runtime requirement.
Focused verifier, runtime, and collection checks exited **0**: **23 passed,
14 warnings in 46.44s**. Ruff and `git diff --check` passed. After serial cache
preparation, the required whole-tree Black command exited **0**:

```sh
BLACK_CACHE_DIR=/tmp/issue-2012-round11-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

Result: **529 files would be left unchanged**. The test change is committed as
**`990cb8a36bd8f41d4d4c516dfd0210be3ba42bb8`** in
`/tmp/issue-2012-round11-source`; workspace `.git` is read-only.

The verifier checked both required merge ancestors and ran that exact committed
source in fresh `/tmp/issue-2012-round11-full/checkout`. Selected **CPython
3.14.10**, executable `/opt/hostedtoolcache/Python/3.14.10/x64/bin/python`, matches
`.python-version` **3.14** and satisfies `>=3.13,<3.15`. Exact unrestricted command:

```sh
/opt/hostedtoolcache/Python/3.14.10/x64/bin/python -m pytest
```

Exit **1**, with terminal summary:

```text
======================= 2 skipped, 14 warnings in 8.24s ========================
! _pytest.outcomes.Exit: TestClient runtime unavailable: local socketpair I/O failed during send wakeup byte (PermissionError: [Errno 1] Operation not permitted). Run the unchanged suite in an environment permitting local socket operations. This is an environment failure, not a passing test run. !
```

The first selected node remains
`tests/app/test_auth.py::test_signup_creates_account_sets_cookie_and_restores_session`,
blocked in `require_app_test_runtime`. An independent socketpair write reproduced
`PermissionError` at `sender.sendall(b"x")`, matching the helper traceback above.
Classification remains **environmental blocker, high confidence**; no changed-pin
regression is established. Full artifacts: `/tmp/issue-2012-round11-full/result.json`
and `/tmp/issue-2012-round11-full/pytest.log`. The exit-0 boxes remain unchecked.

## Issue #2012 optimized-interpreter evidence guard — 2026-11-08

Reproduced a false-pass bug: inherited `PYTHONOPTIMIZE=1` disabled an application
assertion, and the verification helper recorded exit **0** for a deliberately
failing fixture. The new regression failed before the fix. The helper now probes
the selected interpreter's optimization level, records it with runtime metadata,
and rejects optimized execution before pytest starts. Real-subprocess regressions
cover levels **1** and **2**, proving the same fixture fails normally, passes
under optimization, and cannot produce evidence through the fixed helper.
These fixture passes are not repository acceptance.

Source fix commit: **`fad6a110bfedaf537444dcd1158159e72d126610`**, committed in
`/tmp/issue-2012-round12-baseline/checkout` because workspace `.git` is read-only.
Matching source files remain in the workspace for automation pickup.
Focused verification exited **0**: **25 passed, 14 warnings in 51.06s**:

```sh
python -m pytest tests/scripts/test_verify_local_suite.py tests/test_runtime_requirements.py tests/test_pytest_collection.py tests/test_pytest_collection_audit.py -m 'not slow' -q
```

Ruff and `git diff --check` passed. Black formatted both changed Python files.
After serial cache preparation, the required whole-tree Black check exited **0**
with **529 files would be left unchanged**:

```sh
BLACK_CACHE_DIR=/tmp/issue-2012-round12-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

The unrestricted suite ran on that exact committed source in fresh isolated
`/tmp/issue-2012-round12-full/checkout`. The verifier confirmed both required
merge ancestors, #2005 (`29c6aa01064f9eb3cbf15debd32cac3327ec43b8`) and #2011
(`4c6ff3e81b412db4039f7d1a48fa95d0aecff753`). Selected **CPython 3.14.10** matches
`.python-version` **3.14** and satisfies `>=3.13,<3.15`; optimization is **0**,
and pytest is **9.2.0**. Exact command without exclusions or watchdog:

```sh
/opt/hostedtoolcache/Python/3.14.10/x64/bin/python -m pytest
```

Exit **1**, terminal result:

```text
======================= 2 skipped, 14 warnings in 7.01s ========================
! _pytest.outcomes.Exit: TestClient runtime unavailable: local socketpair I/O failed during send wakeup byte (PermissionError: [Errno 1] Operation not permitted). Run the unchanged suite in an environment permitting local socket operations. This is an environment failure, not a passing test run. !
```

The first selected node remains
`tests/app/test_auth.py::test_signup_creates_account_sets_cookie_and_restores_session`,
blocked in `require_app_test_runtime` before its test body. A fresh standalone
socketpair probe reproduced `PermissionError` at `sender.sendall(b"x")`, matching
the helper traceback above. Classification: **environmental blocker, high
confidence**; no changed-pin regression is established. Artifacts:
`/tmp/issue-2012-round12-full/result.json` and `pytest.log` in that directory.
Exit-0 acceptance remains unchecked and requires a runtime permitting local
socket operations. Earlier producer and controller evidence is retained above.

GitHub rejected this round's `needs-human` label and blocker comment with
`MCP tool call requires approval, but approval policy is never`; neither remote
write was applied. PR #2013 readback was **open, draft=false**.
