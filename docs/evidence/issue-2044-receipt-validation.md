# Issue #2044 receipt-validator checks

Synthetic local fixtures and in-memory document copies exercise offline
documentation-validator behavior only. README and `docs/design-coverage-map.md`
execution claims remain UNVERIFIED unless a reviewer attaches a checked receipt.

## Receipt contract (summary)

The shared helper `_coverage_claim_errors` validates each bounded proof layer in
the Section 15 JSON registry. VERIFIED claims require a repository-relative JSON
receipt with exact SHAs, scoped environment and command, retained local or shaped
remote locators, and an observed PASS with zero skips. Workflow filenames, remote
configuration URLs and parent-directory paths are rejected without network access.

`_coverage_map_execution_errors` applies the same receipt validator to an entire
document and compares Section 15 table rows (except the historical May row) and
the configured-execution preamble to registry status.

## Deliberate workflow-only failure and restoration

The `workflow-only` parameter supplies `status: VERIFIED` with
`receipt: "workflow.yml"`. DNS and socket entry points are patched to fail on any
network request.

To demonstrate detection, temporarily set the shared `workflow-only` expected
diagnostics to `[]`, run the named test, confirm failure with
`VERIFIED needs a local JSON receipt, not a workflow filename`, restore the
expectation, and rerun until the named test passes.

## Latest local verification (2026-11-17)

Consumer branch `codex/issue-2044` (PR #2047), after merging `origin/main` and
extending Section 15 prose checks to every mapped proof-layer row.

| Command | Observed result |
| --- | --- |
| `python3 -m pytest tests/preferences/test_legacy_request_adapter.py::test_coverage_map_keeps_claims_scoped_to_their_evidence -q` | Exit 0; 106 passed (after workflow-only break → revert on PR #2047) |
| `python3 -m pytest tests/preferences/test_legacy_request_adapter.py -q` | Exit 0; 113 passed |
| `python3 -m pytest tests/test_repo_hygiene.py -q` | Exit 0; 16 passed, 1 skipped |
| `ruff check tests/preferences/test_legacy_request_adapter.py tests/test_repo_hygiene.py` | `test_legacy_request_adapter.py` clean; `test_repo_hygiene.py` reports pre-existing PLW1510 from `main` |
| `black --check --line-length 100 tests/preferences/test_legacy_request_adapter.py tests/test_repo_hygiene.py` | Exit 0; 2 files unchanged |

Repository-wide Black check when required by CI:

```bash
black --check --line-length 100 --exclude '(\.workflows-lib\|node_modules)' .
```

## Verified implementation checklist

- [x] Validate unverified, structured receipt-backed and invalid examples through
  one reusable helper, including workflow-only rejection for every bounded layer.
- [x] Define bounded proof layers and retain explicit UNVERIFIED documentation.
- [x] Distinguish implemented transport, configured checks and observed execution
  in README without promising every main push succeeds.
- [x] Compare Section 15 table prose and preamble to registry status for each
  mapped layer, not only `configured_full_product`.
- [x] Preserve `test_design_coverage_map_references_are_addressable` and
  existing local-path checks.
- [x] Deliberate workflow-only break → revert recorded on PR #2047.