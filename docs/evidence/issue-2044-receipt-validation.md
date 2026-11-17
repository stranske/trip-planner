# Issue #2044 receipt-validator checks

Observed locally on 2026-11-17, starting from consumer commit
`6c77b32d20e209487bf04da929fca6de2d160d7d` with this repair applied.
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

Temporarily added `workflow-only` to the set of examples expected to validate,
without changing the validator, then ran:

```bash
python3 -m pytest tests/preferences/test_legacy_request_adapter.py::test_coverage_map_keeps_claims_scoped_to_their_evidence -q -m "not slow" --tb=short
```

Observed exit 1, **1 failed, 39 passed**. The failure was the named test's
`[workflow-only]` parameter:

```text
AssertionError: ['VERIFIED needs a local JSON receipt, not a workflow filename']
```

Removed the temporary acceptance expectation and reran the named test:

```bash
python3 -m pytest tests/preferences/test_legacy_request_adapter.py::test_coverage_map_keeps_claims_scoped_to_their_evidence -q -m "not slow"
```

Observed exit 0, **40 passed**. The final test expects rejection of the
workflow-only claim and acceptance of scoped structured receipt examples for
each layer. Missing and mismatched receipts, abbreviated SHAs, absent locators,
failed/skipped observations and optional/disabled full-product gates are rejected.

## Whole-file verification

```bash
python3 -m pytest tests/preferences/test_legacy_request_adapter.py -q -m "not slow"
```

Observed exit 0, **47 passed**, including the preserved addressability test,
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

The local `git add`/`git commit` attempt was rejected because `.git` is mounted
read-only. The GitHub connector also rejected the tree-creation action because
it requires approval while this run's approval policy is `never`. Consequently
this repair is present in the workspace but is not committed, and the PR's
checkboxes have not been changed. Commit these four validated files to the
existing PR branch and include this failure/restoration record in the PR.
