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
