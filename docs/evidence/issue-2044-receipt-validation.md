# Issue #2044 receipt-validator checks

Observed locally on 2026-11-17, starting from consumer commit
`db869e25f9ea6c47ea2ecac5776de92cb8067b92` with this repair applied.
Environment: Linux sandbox, CPython 3.14.10, pytest, Black 26.10.1.
These results establish documentation-validator behavior only. The synthetic
receipt fixtures do not verify TPP, Maps, a deployment, or a current producer pair.

## Deliberate failure and restoration

The `workflow-only` parameter supplies this claim to `_coverage_claim_errors`:

```json
{"layer": "configured_full_product", "status": "VERIFIED", "receipt": "workflow.yml"}
```

`workflow.yml` exists in the temporary fixture directory and contains only
workflow configuration. Socket connection and DNS entry points are patched to
fail the test on any network request, including for remote receipt locators.

The follow-up expands the named test from 40 to 54 cases. Invalid examples now
assert their exact diagnostics, so an unrelated rejection cannot satisfy the
test. Added cases cover omitted receipt scope fields, an abbreviated producer SHA
and explicitly unverified examples for every proof layer.

Temporarily replaced the `workflow-only` expected diagnostics with an empty list
(expecting the claim to validate), without changing the validator, then ran:

```bash
python3 -m pytest tests/preferences/test_legacy_request_adapter.py::test_coverage_map_keeps_claims_scoped_to_their_evidence -q -m "not slow" --tb=short
```

Observed exit 1, **1 failed, 53 passed**. The failure was the named test's
`[workflow-only]` parameter:

```text
AssertionError: assert ['VERIFIED ne...low filename'] == []
Left contains one more item: 'VERIFIED needs a local JSON receipt, not a workflow filename'
```

Removed the temporary acceptance expectation and reran the named test:

```bash
python3 -m pytest tests/preferences/test_legacy_request_adapter.py::test_coverage_map_keeps_claims_scoped_to_their_evidence -q -m "not slow"
```

Observed exit 0, **54 passed**. The final test expects rejection of the
workflow-only claim and acceptance of scoped structured receipt examples for
each layer. Missing and mismatched receipts, abbreviated SHAs, absent locators,
failed/skipped observations and optional/disabled full-product gates are rejected.

## Whole-file verification

```bash
python3 -m pytest tests/preferences/test_legacy_request_adapter.py -q -m "not slow"
```

Observed exit 0, **61 passed**, including the preserved addressability test,
missing-path rejection and document-relative link checks. Existing dependency
deprecation warnings remain. Ruff checks for the changed Python file also pass.

The required formatting gate passed (exit 0), **530 files would be left unchanged**:

```bash
BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/black-issue-2044-serial black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

The sandbox blocked Black's default multiprocessing socket, and its asynchronous
fallback stalled. All 530 sources discovered with the same configuration were
therefore checked through Black's serial `reformat_one` API in CHECK mode first
(exit 0). The command above then reused that freshly populated Black cache.
No formatting errors were suppressed and no sources were excluded beyond the
configured exclusions and the required command's exclusion expression.

## Verified task reconciliation

- [x] Rewrite and parameterize the existing named test using one reusable helper
  for repository claims and synthetic local receipt fixtures.
- [x] Define bounded proof layers and preserve explicit unverified documentation.
- [x] Distinguish implemented transport, configured checks and observed execution
  in README without promising successful execution on every main push.
- [x] Run the named test, demonstrate workflow-only failure and restoration, and
  pass the whole file while preserving the existing path checks.

## Delivery blocker

The initial receipt rewrite was committed by automation as `463b4660`. The
follow-up adds precise diagnostic assertions and 14 receipt validation cases;
the follow-up remains uncommitted because `git add` exited 128:

```text
fatal: Unable to create '/home/runner/work/trip-planner/trip-planner/.git/index.lock': Read-only file system
```

The attempted commit was `test: assert scoped receipt rejection diagnostics`.
Commit the changed test and this evidence record to the existing PR branch from
an environment with a writable Git directory. No branch or pull request was
created, and the documentation's execution claims remain explicitly unverified.

Updating the PR with the verified checklist and failure/restoration results was
also rejected by the GitHub connector: `MCP tool call requires approval, but
approval policy is never`. Adding the requested `needs-human` label received the
same rejection. Neither the PR body nor its labels were changed by this run.
