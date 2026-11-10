The 2026-11-10 run comparison confirms that #2006 merged at
`fcb6e97a291bd620629aa228561d36c3ee6cdf0d` and smoke run `42484305260`
passed at that head. `run-reconciliation.json` retains fresh connected GitHub
API receipts and selected install/checkout log lines from both requested runs.
The requested `gh run view` commands still fail to connect to api.github.com.

Both logs install local editable dev extras. The failing run selects TPP
`acc4aeddee5f4ffefbdc73fcb07505cd3d198197`; the successful run selects
`b56d92b389736c70370aa9134f379ac8cd1f3ad1`. Publication is not established as
a prerequisite by these logs. Source pin edits and regeneration are superseded.

From the consumer root, generate the scoped reconciliation:

```sh
python scripts/reconcile_issue_2007.py > /tmp/issue-2007-ledger.patch
```

The command verifies the final merged head, run/job success, editable install
inputs, original Ruff conflict, pinned TPP checkouts and successful installation.
It prints a patch without writing the ledger. `ledger-reconciliation.patch` is
its retained output. Task 05 becomes deferred because no source-pin edit was
performed. Task 14 remains blocked on successful owning-repository validation.
Other tasks are preserved byte-for-byte. The existing ledger has invalid YAML
in unrelated historical notes (including line 28); this tool only parses and
repairs the two corrected task blocks. Applying the patch does not validate the
whole historical ledger.

Verification on consumer base `2cefe497` with the new source/tests:

```sh
python -m pytest tests/scripts/test_reconcile_issue_2007.py tests/scripts/test_cross_repo_dev_pins.py tests/test_dependency_version_alignment.py -q -m 'not slow'
```

Exit 0: 60 passed, 2 skipped in 4.23 seconds. The skips require a live sibling
TPP checkout. Tests also apply the generated patch in an isolated Git repository,
check idempotence, and reject mismatched heads, failed/ambiguous receipts and
missing install evidence.

The owning repository's documented command was retried from `.workflows-lib`
at commit `1ff1a3c5071824adc2fd421702f583b14dc6b477`, using selected interpreter
`/opt/hostedtoolcache/Python/3.14.10/x64/bin/python`:

```sh
PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_RETRIES=0 ./scripts/dev_check.sh
```

Exit 1 during provisioning of unavailable isort/docformatter/flake8; see
`owner-dev-check-reconciliation.log`. This is not successful broad validation.

The mounted ledger and shared Git metadata remain read-only. The patch is ready
for review/application in a writable checkout; the ledger task remains incomplete.
No additional task checkbox is marked complete by this change.

Follow-up on consumer base `69b41e1576038e3ff9650332c59309d8186d9798`, 2026-11-10:

The reconciliation now accepts the retained controller classification explicitly:

```sh
python scripts/reconcile_issue_2007.py --sync-core-document docs/evidence/issue-2025/sync-core-classification.md
```

The retained patch was regenerated with this option. It adds task 16's dated
classification and proposes marking that classification task done, while keeping
task 14 blocked on local validation. Without the option only tasks 05 and 14
change, as before. No ledger edit or PR task-checkbox update was applied: the
environment again rejected the ledger write. No protected files were changed.

The excerpt is copied from the immutable source and blob identified in
`sync-core-reconciliation.json`. Round `20261108T133016Z` completed at
`2026-11-08T13:30:21Z` with #2006 delivered, zero mismatches, no handoffs and the
final merged head. Validation rejects wrong targets/heads, pre-merge rounds,
inconsistent round bindings/times, ambiguous receipts and retained findings.
The successful smoke receipt now also requires the native run's `head_sha`;
the commit-lookup parameter alone cannot establish the run head.

Maint 68's `Build sync run report` step writes
`artifacts/consumer-sync-run-report.json`, uploaded as `consumer-sync-run-report`
with 14-day retention. Subsequent run `42761261918`, created
`2026-11-10T05:18:03Z`, succeeded; its summary job uploaded artifact `13737713043`
at `2026-11-10T05:21:26Z`. Metadata and upload logs were inspected; the ZIP body
was not. This producer report cannot establish #2006 clearance. The separate
retained controller receipt supplies the evidence-backed merged classification;
it does not claim a fresh read of canonical local `rounds.jsonl`.

Focused verification with the selected Python 3.14.10 interpreter:

```sh
python -m pytest tests/scripts/test_reconcile_issue_2007.py tests/scripts/test_cross_repo_dev_pins.py tests/test_dependency_version_alignment.py -q -m 'not slow'
```

Exit 0: 80 passed, 2 skipped in 9.10 seconds. The two existing skips require a
live sibling TPP checkout. CLI tests apply the optional patch in an isolated Git
repository and verify that input files are unchanged. Ruff and `git diff --check`
pass. The owning repository's documented-command exit-0 requirement remains
incomplete; the retained provisioning failure is not replaced by these checks.

Black formatted both changed Python files. After serial Black validation populated
its cache (the runner denies the normal worker socket), the required whole-tree
command exited 0: 532 files would be left unchanged.

```sh
BLACK_CACHE_DIR=/tmp/issue2025-sync-core-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

Shared `git add` failed because `.git/index.lock` is read-only. Delivery therefore
uses an isolated clone at `/tmp/issue2025-sync-core-delivery`, with the matching
source, tests and evidence left in the workspace for automation pickup. The
`needs-human` label and blocker comment were each rejected with `MCP tool call
requires approval, but approval policy is never`; neither remote write applied.
PR #2026 readback was open with draft=false. No PR task checkboxes were updated.

Follow-up on consumer base `bc9d0687359496d5b2c7580c0531f698fa147660`, 2026-11-10:

The reconciliation rejects missing, empty and non-string `checked_at`/`merged_at`
values before rendering receipts, with or without the optional classification.
Task 05 now has `started_at: null` when deferred; its original timestamp moves
to notes and survives repeated reconciliation. Task 14's timestamps are preserved.
New tests reject missing/duplicate task blocks and unsupported notes, status and
start layouts. The retained ledger patch was regenerated and passes
`git apply --check`; the actual ledger write was rejected by the filesystem policy.

The three requested `gh run view` commands were attempted again and could not
connect to api.github.com. Fresh connected GitHub PR, run-lookup, job and log
receipts confirm the same merged head, successful smoke and local editable
installation inputs already retained in `run-reconciliation.json`.

Validation with the selected Python 3.14.10 interpreter:

```sh
python -m pytest tests/scripts/test_reconcile_issue_2007.py tests/scripts/test_cross_repo_dev_pins.py tests/test_dependency_version_alignment.py --cov=scripts.reconcile_issue_2007 --cov-config=/tmp/issue2025-reconcile.coveragerc --cov-report=term-missing -q -m 'not slow'
```

Exit 0: 117 passed, 2 skipped in 4.10 seconds. The skips require a sibling TPP
checkout. The temporary coverage configuration sets only
`[run] source = scripts.reconcile_issue_2007` and `[report] show_missing = True`:
the repository's product coverage configuration otherwise omits scripts.
The targeted script reports 87%; this task has no percentage threshold.
Ruff and `git diff --check` pass. After serial Black verification prepared its
writable cache, the required command exits 0, with 532 files unchanged:

```sh
BLACK_CACHE_DIR=/tmp/issue2025-dates-black black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

PR checkbox reconciliation was attempted for the duplicated regression task,
the retained owning-repository resolver/mutation result and the evidence-backed
subsequent classification criterion. Automatic approval review rejected the
PR-body update, `needs-human` label and blocker comment with
`MCP tool call requires approval, but approval policy is never`; none applied.
The combined ledger tasks remain unchecked because the ledger is read-only.
The owning repository's documented-command exit-0 criterion remains incomplete.
The Git index is also read-only, so source, tests and evidence are committed in
the isolated delivery checkout `/tmp/issue2025-reconcile-delivery`, with matching
edits retained here for automation pickup.

Follow-up on consumer base `c17b1d7b2cf4abe9c071f64f383ea59d5937a678`, 2026-11-10:

The reconciliation now checks actual Git checkout lines, in addition to the
requested `TPP_PINNED_REF` environment values. Removing or changing the failed
planner checkout, failed TPP checkout, or successful TPP checkout previously
still produced a patch. Six new negative cases reproduced that problem before
the fix. The generated task-05 notes now retain both exact checkout pairs and
the successful `ruff-0.17.3` install result. The task-16 layout tests also cover
missing/duplicate task blocks and missing/duplicate completion fields. All test
functions in the changed test module now have docstrings.

Verification:

```sh
python -m pytest tests/scripts/test_reconcile_issue_2007.py tests/scripts/test_cross_repo_dev_pins.py tests/test_dependency_version_alignment.py -q -m 'not slow'
```

Exit 0: 130 passed, 2 skipped in 3.95 seconds with Python 3.14.10. The existing
skips require a sibling TPP checkout. Ruff and `git diff --check` pass.
Black formatted the changed Python files individually; serial checks populated
the writable cache because the runner denies Black's worker socket.

The requested `gh run view` commands again failed to connect to api.github.com.
Fresh connected GitHub PR, commit-run lookup and job receipts independently
confirm #2006 merged at `fcb6e97a291bd620629aa228561d36c3ee6cdf0d` and
`cross-repo-full-product` succeeded in run `42484305260`.

The currently selected Workflows checkout has advanced to
`8c678c19a4f9f60fa5be6a00f08794a9626c87bd`. From `.workflows-lib`, with the
selected Python 3.14.10 interpreter, this exact documented-command attempt:

```sh
PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_RETRIES=0 ./scripts/dev_check.sh
```

still exits 1 while provisioning unavailable isort/docformatter/flake8. See
`owner-dev-check-current.log`. This does not satisfy the exit-0 criterion.

The regenerated ledger patch passes `git apply --check`, but applying it fails
with `Read-only file system` for `.agents/issue-2007-ledger.yml`. No ledger task
is newly completed. PR checkbox reconciliation was attempted before continuing;
automatic approval review rejected the PR-body update with `MCP tool call
requires approval, but approval policy is never`. No PR checkbox change applied.

The required whole-tree formatting command exits 0 with 532 files unchanged:

```sh
BLACK_CACHE_DIR=/tmp/issue2025-checkout-black black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

The shared Git index also rejects writes with `Read-only file system`. Commit
delivery uses `/tmp/issue2025-checkout-delivery`, an isolated consumer clone;
matching source, tests and evidence remain in this workspace for automation.

Follow-up on consumer base `008bc316703fd3d9982c72e3b964cf78cf66d0f7`, 2026-11-10:

The install comparison now binds resolver output to the combined editable
install command. The historical log must identify the exact Ruff requirement
and dev extra for each project after that command. The successful log must
list `ruff-0.17.3`, `trip-planner-0.1.0` and `travel-plan-permission-0.1.0` in
one subsequent `Successfully installed` line. Earlier planner-only installs,
download messages, partial version matches and missing project installs cannot
establish that both projects resolved together. Eight negative cases failed
against the previous implementation before passing with this change.

Fresh connected GitHub job logs confirm why this distinction matters: both
runs first successfully install planner and Ruff 0.17.3 alone. Only the later
combined install fails in run `42449207754` and succeeds in `42484305260`.
Reconciliation using freshly fetched install/checkout excerpts produces the
same patch as the retained receipts. The PR and commit-run lookup independently
confirm the merged final head and successful smoke job. The three requested
`gh run view` commands still fail to connect to api.github.com.

Validation with `/opt/hostedtoolcache/Python/3.14.10/x64/bin/python`:

```sh
python -m pytest tests/scripts/test_reconcile_issue_2007.py tests/scripts/test_cross_repo_dev_pins.py tests/test_dependency_version_alignment.py -q -m 'not slow'
```

Exit 0 after formatting: 138 passed, 2 skipped in 3.87 seconds; both skips
require a live sibling TPP checkout. Ruff and `git diff --check` pass. Black
formatted the changed files, then the required whole-tree check exited 0 with
532 files unchanged. Serial CLI verification populated the cache first because
the runner denies Black's worker socket:

```sh
BLACK_CACHE_DIR=/tmp/issue2025-install-serial black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

The proposed ledger patch passes `git apply --check`, but applying it fails
with `Read-only file system`. Shared `git add` likewise fails on
`.git/index.lock`; delivery uses `/tmp/issue2025-install-delivery`, retaining
the matching source and tests here. PR #2026 remains open with draft=false.
No task checkbox is newly completed. Successful owning-repository broad
validation, upstream test publication and ledger application remain incomplete.

Follow-up on consumer base `e1380685715a5804e9e168a2c78d030637505f09`, 2026-11-10:

The reconciliation tool now includes the exact failed owning-repository command,
checked commit, interpreter, timestamp, exit code, outcome and retained log in
task-14's proposed notes. Previously these details were omitted in favor of a
generic historical provisioning failure. `run-reconciliation.json` contains the
new receipt; `ledger-reconciliation.patch` was regenerated and passes
`git apply --check`. The tool keeps task-14 blocked and refuses to use a successful
or malformed command receipt to substantiate that failure. Nine new regression
cases failed before the implementation and pass afterward.

The recorded attempt used Workflows commit
`8c678c19a4f9f60fa5be6a00f08794a9626c87bd`, selected interpreter
`/opt/hostedtoolcache/Python/3.14.10/x64/bin/python`, and exact command:

```sh
PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_RETRIES=0 ./scripts/dev_check.sh
```

Exit **1** while provisioning unavailable isort/docformatter/flake8; no validation
checks ran. `owner-dev-check-current.log` retains the terminal result.

Focused consumer validation:

```sh
python -m pytest tests/scripts/test_reconcile_issue_2007.py tests/scripts/test_cross_repo_dev_pins.py tests/test_dependency_version_alignment.py -q -m 'not slow'
```

Exit **0**, **147 passed, 2 skipped in 4.71 seconds**. Both existing skips require
a sibling TPP checkout. Ruff and `git diff --check` pass. Black formatted the
changed Python files individually; the required whole-tree check uses a writable
cache prepared by per-file CLI checks because worker sockets are denied here.
The following gate exited **0**, with **532 files unchanged**:

```sh
BLACK_CACHE_DIR=/tmp/issue2025-command-black black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

Fresh connected GitHub readback confirms merged #2006, the successful smoke job,
and the immutable retained controller classification. All three requested `gh`
commands still fail to connect. The ledger patch cannot be applied to the
read-only `.agents` mount, and the shared Git index is also read-only. Delivery
uses an isolated consumer checkout, retaining matching edits in this workspace.
No new task is marked complete. Automatic approval review rejected the PR-body
checkbox reconciliation, `needs-human` label and blocker comment with
`MCP tool call requires approval, but approval policy is never`.

Follow-up on consumer base `cc5395a3239d5187ee1c20f790171adb7384cb33`, 2026-11-10:

Advanced the owning resolver acceptance test instead of adding more consumer
receipt-helper cases. Three new cases independently restore the historical
producer Ruff, mypy and pytest mismatches, require pip's exact conflicting
requirements, then restore the successful metadata and resolve again. This
prevents Ruff's first reported conflict from masking the other changed tool
pins. Ten bounded pip invocations now each have a ten-second timeout.

The expanded owner suite passes: **6 passed in 4.32 seconds**. Reintroducing
Ruff 0.17.2 in the successful producer fixture fails the positive resolver test
with `ResolutionImpossible`; restoration passes. The exact commands, immutable
owner base, nine verified source blob hashes, tested source hash and logs are
recorded in `owner-tool-mutations.json`. `workflows-tool-mutations.patch`, applied
after `workflows-regression.patch`, reproduces the exported source, including
the previous type annotation correction and Workflows' required import grouping.

Ruff passes with the owning configuration. The required whole-tree Black check
passes with 532 files unchanged after serial per-file checks populated a writable
cache; worker sockets remain restricted. Existing consumer validation before
these owner-only test edits passed with 147 tests and two sibling-checkout skips.

Fresh connected job logs again establish the editable install inputs and
compatible checkout pair. The requested `gh` log commands still cannot connect.
The reviewed ledger patch cannot be applied to the read-only `.agents` mount;
shared `git add` also fails on `.git/index.lock`. Delivery uses an isolated
consumer clone, retaining matching edits here. Automatic approval review again
rejected checkbox reconciliation, the label and the blocker comment because
approval policy is `never`. No new checkbox was applied. Upstream test
publication and successful documented broad validation remain incomplete.

Follow-up on consumer base `bb70e92d43d65fb2846852c869be75e596cb576c`, 2026-11-10:

The consumer reconciliation CLI now accepts the two requested run-log files
directly. Capture them in an environment with working `gh` access, then run:

```sh
gh run view 42449207754 --repo stranske/trip-planner --log > /tmp/failed.log
gh run view 42484305260 --repo stranske/trip-planner --log > /tmp/successful.log
python scripts/reconcile_issue_2007.py --failed-log /tmp/failed.log --successful-log /tmp/successful.log --sync-core-document docs/evidence/issue-2025/sync-core-classification.md
```

Both files are required together and replace both retained log excerpts. Empty,
swapped or missing files fail without emitting a patch; valid stale excerpts
cannot mask a failed fresh comparison. Tests exercise CLI job/step prefixes,
UTF-8 BOMs, applicable patch output and preservation of all input files.

The three requested `gh run view` commands again failed to connect. Fresh
connected API PR, run-lookup and job receipts confirm the same merged head and
successful smoke. Fresh install/checkout lines from both connected job logs,
passed through the new options, produce the retained ledger patch byte-for-byte.
This verifies those selected lines; it does not claim a successful `gh` invocation.
Applying the patch again failed on the read-only `.agents` mount.

Validation with the selected Python 3.14.10 interpreter:

```sh
python -m pytest tests/scripts/test_reconcile_issue_2007.py tests/scripts/test_cross_repo_dev_pins.py tests/test_dependency_version_alignment.py -q -m 'not slow'
```

Exit 0: **154 passed, 2 skipped in 5.12 seconds**. Both existing skips require
a sibling TPP checkout. No task checkbox is newly complete. The ledger write,
owning documented-command exit-0 result and upstream test publication remain
incomplete. Shared Git metadata is read-only, so commit delivery uses
`/tmp/issue2025-raw-logs-delivery`; matching edits remain in this workspace.

Black formatted both Python files. Serial per-file checks prepared a writable
cache because the runner denies Black's worker socket; the required gate then
exited 0 with **532 files unchanged**:

```sh
BLACK_CACHE_DIR=/tmp/issue2025-raw-logs-black black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

Ruff and `git diff --check` pass. PR #2026 readback is open with draft=false.
