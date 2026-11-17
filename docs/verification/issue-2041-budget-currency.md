# Issue 2041: budget currency validation

Verified locally on 2026-11-17 against PR #2049, based on
`e088174a6bb18d4381a564b165ddfbcd3c222c15`.

- [x] Validate all trip spend currencies before creating or mutating a plan;
  detect inconsistent spend before aggregation; return 422 for incompatible
  plan updates and 409 for legacy inconsistent reads. The implementation was
  already present in the checked-out commit. Regression coverage now compares
  complete persisted plan, version, spend, trip and planning-session rows, and
  checks mixed USD/EUR spend against proposed USD, EUR and GBP plans.
- [x] Named rejected-update atomicity test passes, including original events,
  totals and version count.
- [x] Deliberate break and restoration verified as described below.
- [x] Entire budget route test file passes: **17 passed**, 31 existing warnings.
- [x] Existing tests retained. Extended
  `test_workspace_budget_spend_event_rejects_currency_drift` to verify a valid
  normalized-currency edit still succeeds, updates totals and creates no plan
  version after a rejected currency edit.

The named command was:

```sh
python3 -m pytest tests/app/test_budget_routes.py::test_plan_currency_change_rejected_when_spend_in_other_currency -q -m "not slow"
```

Removed only the `mismatched_currency` query and its error block from
`upsert_workspace_budget_plan`, retaining the summary guard and transactional
rollback. The named test reread persisted rows directly before checking PUT's
status and failed with:

```text
assert 409 == 422
1 failed, 15 warnings in 0.48s
```

The failure also showed the persisted plan was still USD with one version:
the read-side guard rolled back the attempted update but returned the wrong
status. All five persisted table snapshots remained unchanged. Restored the
service byte for byte in a `finally` block and reran the same named command:

```text
1 passed, 15 warnings in 0.42s
```

The full-file command was
`python3 -m pytest tests/app/test_budget_routes.py -q -m "not slow"`.
Black formatted the changed test file. The required full-repository check,
`black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .`,
passed with **530 files unchanged**. Ruff and `git diff --check` also passed.

The unadapted test command exited before running tests because the sandbox
denies `socket.sendall` on local socket pairs. Successful runs used
`PYTHONPATH=/tmp/budget-currency-validation`, whose temporary `sitecustomize.py`
sends local socket-pair data using permitted `os.write` calls. The existing
socket runtime check passed; no tests or assertions were disabled. Black used
the same temporary adapter, a 10 ms selector wait cap and
`BLACK_NUM_WORKERS=1`. These are local results, not CI results.

Delivery is blocked: `.git` is read-only, so `git add` cannot create
`.git/index.lock`. The GitHub connector also rejected the attempted source
commit because writes require approval while the approval policy is `never`.
PR-body checkbox reconciliation, a blocker comment and the `needs-human` label
were rejected for the same reason. The verified test changes remain uncommitted
in the working tree. PR #2049 was verified open with `draft=false`.

## Follow-up on checked-out commit aa1e8522

- Extended the named rejected-update test to preserve two events in different
  categories, including fractional spending, and assert planned, actual and
  remaining totals before comparing the full response after rejection.
- Added `tests/persistence/test_budget_currency_atomicity.py`, which calls the
  real route function against SQLite without an HTTP transport. It verifies
  HTTPException status 422, no pending ORM changes, no SQL INSERT/UPDATE/DELETE,
  identical plan/version/spend/trip/session rows in a separate session, and
  unchanged aggregate totals and version count. Command:
  `python3 -m pytest tests/persistence/test_budget_currency_atomicity.py -q -m "not slow"`
  — **1 passed**, 14 dependency warnings.
- [ ] The named HTTP acceptance test remains unverified in this follow-up.
  Both the named test and the whole route test file exit unsuccessfully from
  the unchanged runtime prerequisite because socket-pair `sendall` is denied.
  No transport adapters or runtime-check bypasses were used.
- Both changed Python files pass individual Black checks at line length 100.
  Ruff and `git diff --check` pass. The required full-repository Black command
  fails before checking formatting because multiprocessing's forkserver cannot
  bind a local socket (`PermissionError: [Errno 1] Operation not permitted`).
  Per the pre-commit gate, these follow-up changes must remain uncommitted until
  that command passes in a runner permitting the required local operations.

## Follow-up on checked-out commit ab1e6d03

Reviewed `e088174a`, `288091f6`, `aa1e8522`, and `ab1e6d03`. The implementation,
mutation-check evidence, and spend-write regression are already present. The
named HTTP acceptance criterion remains unchecked because this runner cannot
execute its TestClient prerequisite.

Extended the named HTTP regression and the direct-route SQLite regression to
cover one-cent spend as well as ordinary amounts. Any existing spend must block
an incompatible currency change, even for the smallest positive cent amount.
The model rejects zero amounts; zero-valued spend is not a valid HTTP fixture.

- `python3 -m pytest tests/persistence/test_budget_currency_atomicity.py -q -m "not slow"`
  passes: **2 passed**, 14 dependency warnings. Both cases verify 422, no pending
  ORM changes or SQL writes, unchanged persisted rows, totals and version count.
- The named HTTP command and the complete route file both exit unsuccessfully
  because the unchanged runtime prerequisite cannot send a local socket-pair
  wakeup byte (`PermissionError`). No test bypasses or transport adapters used.
- Black formats each changed Python file individually at line length 100. Ruff
  and `git diff --check` pass. The required repository-wide Black check still
  fails before formatting checks because the multiprocessing forkserver cannot
  bind a local socket. No commit was attempted after that failed gate.
- PR-body reconciliation was attempted before continuing. The GitHub connector
  rejected it because writes require approval and the approval policy is `never`.
  The remaining HTTP checkbox must stay unchecked until verified in a runner
  that permits the required socket operations.
