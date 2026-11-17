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

## Previous delivery blocker

The initial receipt rewrite was committed by automation as `463b4660`. The
follow-up adds precise diagnostic assertions and 14 receipt validation cases;
the follow-up could not be committed in that run because `git add` exited 128:

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

## Skip-count validation follow-up

Observed locally on 2026-11-17, starting from consumer commit
`15ad8d0767a2c4d702c5798146e7c8e9d63cfa57` with this follow-up applied.
That commit contains the previously blocked diagnostic assertions and evidence
record. Reviewed it alongside `463b4660` and `db869e25` before proceeding; the
baseline whole-file run passed all 61 tests. The PR checklist still needed the
verified task reconciliation listed above, including duplicate task entries.

Added five malformed skip-count fixtures: JSON `false`, `0.0`, `"0"`, `null`
and an omitted count. Before the fix, the named test reported **2 failed,
57 passed**: Boolean false and floating-point zero were accepted because Python
compares both equal to integer zero. The shared receipt helper now requires an
integer count of zero, so these malformed observations cannot promote a claim.

Repeated the deliberate workflow-only acceptance expectation by temporarily
setting its expected diagnostics to `[]`. With DNS/socket calls still blocked,
the named test reported **1 failed, 58 passed**, exit 1, specifically:

```text
test_coverage_map_keeps_claims_scoped_to_their_evidence[workflow-only]
AssertionError: assert ['VERIFIED ne...low filename'] == []
Left contains one more item: 'VERIFIED needs a local JSON receipt, not a workflow filename'
```

Restored the rejection expectation, then verified:

| Command | Observed result |
| --- | --- |
| `python3 -m pytest tests/preferences/test_legacy_request_adapter.py::test_coverage_map_keeps_claims_scoped_to_their_evidence -q -m "not slow"` | Exit 0; 59 passed |
| `python3 -m pytest tests/preferences/test_legacy_request_adapter.py -q -m "not slow"` | Exit 0; 66 passed |
| `python3 -m pytest tests/preferences/test_legacy_request_adapter.py tests/test_repo_hygiene.py -q -m "not slow"` | Exit 0; 82 passed, 1 existing skip |
| `ruff check tests/preferences/test_legacy_request_adapter.py` | Exit 0 |
| `git diff --check` | Exit 0 |

Ran Black on the changed Python file, then checked all 530 sources through its
serial `reformat_one` API in CHECK mode with the CLI's source discovery and
configuration. The standard CLI's multiprocessing socket was blocked by the
sandbox. Reusing that freshly populated cache, the required gate passed with
exit 0, **530 files would be left unchanged**:

```bash
BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/black-issue-2044-final black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

Existing addressability and local-path tests are preserved, and all repository
execution claims remain UNVERIFIED. These synthetic fixture results establish
only validator behavior.

### Current delivery blockers

The attempted commit, `test: reject malformed receipt skip counts`, could not
proceed: `git add` exited 128 because `.git/index.lock` is on a read-only file
system. The changed test and this evidence record remain in the working tree
for committing on the existing PR branch from a writable Git environment.

The GitHub connector rejected the verified checklist update, the results/blocker
comment and the additive `needs-human` label with `MCP tool call requires
approval, but approval policy is never`. No PR body, comment or label was changed.
Apply the verified reconciliation above when PR writes are available. A final
read confirmed PR #2047 is open and ready for review (`draft=false`).

## Document promotion regression follow-up

Observed locally on 2026-11-17, starting from consumer commit
`9a1634ac9050bf5dcf9133bd65340c50e3f141b7` with this follow-up applied.
The baseline whole-file run passed 66 tests. The existing helper validated
synthetic receipts, but no case exercised a promoted coverage-map document
through the same registry and prose checks as the repository document.

Extracted those existing checks into `_coverage_map_execution_errors`, which
continues to call the shared `_coverage_claim_errors` receipt validator. Added
five named-test parameters using in-memory copies of the actual coverage map:

- A VERIFIED configured-layer registry entry and matching prose pass with a
  synthetic local receipt containing exact SHAs, scope and observed results.
- The same document fails with only a workflow filename or a missing receipt.
- A VERIFIED registry entry fails if either the table row or the preamble still
  says UNVERIFIED.

The actual README and coverage map retain their UNVERIFIED claims. These tests
establish only the validator's ability to accept a scoped future update.
The existing addressability and local-path checks are preserved.

Repeated the required deliberate break by changing only the `workflow-only`
expected diagnostics to `[]`. The named test reported **1 failed, 63 passed**,
exit 1, specifically:

```text
test_coverage_map_keeps_claims_scoped_to_their_evidence[workflow-only]
AssertionError: assert ['VERIFIED ne...low filename'] == []
Left contains one more item: 'VERIFIED needs a local JSON receipt, not a workflow filename'
```

DNS and socket connection calls remained patched to fail on network requests.
Restored the rejection expectation, then verified:

| Command | Observed result |
| --- | --- |
| `python3 -m pytest tests/preferences/test_legacy_request_adapter.py::test_coverage_map_keeps_claims_scoped_to_their_evidence -q -m "not slow"` | Exit 0; 64 passed |
| `python3 -m pytest tests/preferences/test_legacy_request_adapter.py -q -m "not slow"` | Exit 0; 71 passed |
| `python3 -m pytest tests/preferences/test_legacy_request_adapter.py tests/test_repo_hygiene.py -q -m "not slow"` | Exit 0; 87 passed, 1 existing skip |
| `ruff check tests/preferences/test_legacy_request_adapter.py` | Exit 0 |
| `git diff --check` | Exit 0 |

Ran Black on the changed file. As in the preceding run, the repository-wide
command stalled in the sandbox. Checked all 530 sources through Black's serial
`reformat_one` CHECK API using the CLI's source discovery, project configuration
and inferred Python targets, with no formatting changes needed. Then reran the
required CLI gate using that freshly populated cache:

```bash
BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/black-issue-2044-document black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

Observed exit 0, **530 files would be left unchanged**.

### Delivery status for this follow-up

Attempted `test: exercise receipt-backed documentation promotion` on the existing
PR branch. `git add` exited 128 because `.git/index.lock` is on a read-only
filesystem. The changed Python test and this evidence record remain local.
Commit them from the automation runner's writable Git environment; no branch or
pull request was created.

The GitHub connector rejected the verified PR checklist/results update, the
results/blocker comment and the additive `needs-human` label with
`MCP tool call requires approval, but approval policy is never`. No PR body,
comment or label was changed by this follow-up. The implementation and local
test requirements are verified, including the duplicate entries. Publishing
the failure/revert evidence in the PR and reconciling its checkboxes still
require an environment permitting PR writes. A final read confirmed PR #2047
remains open and ready for review (`draft=false`).

## Workflow-only rejection across proof layers

Observed locally on 2026-11-17 from consumer commit
`e2b68b211386875285c987436d28010fa38dca5b` with this test follow-up applied,
using Linux, CPython 3.14.10 and Black 26.10.1. The baseline file passed
71 tests. Added eight named-test parameters: each proof layer now supplies an
otherwise complete VERIFIED claim with `receipt: "workflow.yml"`. The existing
local workflow file must be rejected even when the claim supplies exact SHAs,
environment and command. All cases use the shared receipt validator, with DNS
and socket connections patched to fail on network requests.

For the deliberate break, temporarily changed the shared `workflow-only`
expected diagnostics to `[]`, leaving the validator unchanged, then ran:

```bash
python3 -m pytest tests/preferences/test_legacy_request_adapter.py::test_coverage_map_keeps_claims_scoped_to_their_evidence -q -m "not slow" --tb=short
```

Observed exit 1: **9 failed, 63 passed**, comprising the original
`[workflow-only]` case and the eight new layer-specific cases. Every failure
reported `VERIFIED needs a local JSON receipt, not a workflow filename` where
the deliberately broken expectation required acceptance. Restored that
expectation in a `finally` block before running the final checks:

| Command | Observed result |
| --- | --- |
| `python3 -m pytest tests/preferences/test_legacy_request_adapter.py::test_coverage_map_keeps_claims_scoped_to_their_evidence -q -m "not slow"` | Exit 0; 72 passed |
| `python3 -m pytest tests/preferences/test_legacy_request_adapter.py -q -m "not slow"` | Exit 0; 79 passed |
| `python3 -m pytest tests/preferences/test_legacy_request_adapter.py tests/test_repo_hygiene.py -q -m "not slow"` | Exit 0; 95 passed, 1 existing skip |
| `ruff check tests/preferences/test_legacy_request_adapter.py` | Exit 0 |
| `git diff --check` | Exit 0 |

Ran Black on the changed Python file. The initial repository-wide CLI stalled;
checked all 530 files through Black's serial `reformat_one` CHECK API, using the
CLI's source discovery, project configuration and inferred Python targets.
Then the required CLI gate passed using the freshly populated cache (exit 0;
**530 files would be left unchanged**):

```bash
BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/black-issue-2044-layer black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

- [x] Validate unverified and receipt-backed examples with one shared helper,
  including workflow-only rejection for every bounded proof layer.
- [x] Verify the named test and full file while preserving addressability and
  local-path checks.

The actual README and coverage-map execution claims remain UNVERIFIED; these
synthetic fixtures establish only offline validator behavior.

Delivery remains blocked for this follow-up: `git add` exited 128 because
`.git/index.lock` is on a read-only filesystem. The attempted commit was
`test: reject workflow-only proof for every receipt layer`; both changed files
remain in the working tree for committing on the existing PR branch.

The GitHub connector rejected the results/blocker comment, the verified
checklist/evidence body update and the additive `needs-human` label with
`MCP tool call requires approval, but approval policy is never`. No PR metadata
was changed. Showing these results in the PR and reconciling its checkboxes
remain blocked on PR write access; the local checks above are complete.

## Current-status declaration regression follow-up

Observed locally on 2026-11-17 from consumer commit
`375b8319b6b437f99f9e2bc006e60064cca32e46` with this repair applied, using
Linux and CPython 3.14.10. The baseline whole-file run passed 79 tests.

The document helper accepted any occurrence of the registry's status on the
relevant prose line. Two new local document fixtures retain a mismatched
UNVERIFIED declaration while adding `Historical examples may be VERIFIED for a
different pair.` on that same line. Before the fix, the named test reported
**2 failed, 72 passed**, exit 1: both mismatched declarations were accepted.
The helper now extracts the current-status declaration and compares it with
the receipt-backed registry status. Both fixtures are rejected with the
expected layer-specific diagnostic; the existing valid promotion still passes.

Repeated the workflow-only deliberate break by temporarily replacing the shared
`workflow-only` expected diagnostics with `[]`, leaving the validator unchanged:

```bash
python3 -m pytest tests/preferences/test_legacy_request_adapter.py::test_coverage_map_keeps_claims_scoped_to_their_evidence -q -m "not slow" --tb=line
```

Observed exit 1, **9 failed, 65 passed**. The original workflow-only case and
all eight layer-specific variants rejected the VERIFIED claim with
`VERIFIED needs a local JSON receipt, not a workflow filename`. DNS and socket
connections remained patched to fail on network requests. Restored the
rejection expectation in a `finally` block, then verified:

| Command | Observed result |
| --- | --- |
| `python3 -m pytest tests/preferences/test_legacy_request_adapter.py::test_coverage_map_keeps_claims_scoped_to_their_evidence -q -m "not slow"` | Exit 0; 74 passed |
| `python3 -m pytest tests/preferences/test_legacy_request_adapter.py -q -m "not slow"` | Exit 0; 81 passed |
| `ruff check tests/preferences/test_legacy_request_adapter.py` | Exit 0 |
| `black --line-length 100 tests/preferences/test_legacy_request_adapter.py` | Exit 0; unchanged |

The initial repository-wide Black CLI stalled and was interrupted. Checked all
530 sources through Black's serial `reformat_one` CHECK API with the CLI's
source discovery, project exclusions and inferred Python targets. All were
unchanged. The required CLI gate then passed using that fresh cache, exit 0,
**530 files would be left unchanged**:

```bash
BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/black-issue-2044-status black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

- [x] Validate unverified, receipt-backed and invalid claims through the shared
  helper, including current-status declarations with misleading later text.
- [x] Verify the named test and whole file, preserving the addressability and
  existing local-path checks.

README and coverage-map execution claims remain UNVERIFIED. These synthetic
fixtures establish only offline documentation-validator behavior.

Delivery for this follow-up is blocked: `git add` exited 128 because
`.git/index.lock` is on a read-only filesystem. The intended commit is
`test: validate declared execution status against receipts`. The changed test
and this evidence record remain local for committing on the checked-out branch
from a writable Git environment.

The GitHub connector rejected the results/blocker comment, the verified
checklist/results body update and the additive `needs-human` label with
`MCP tool call requires approval, but approval policy is never`. No PR metadata
was changed. Publishing the failure/restoration evidence and reconciling the
PR checkboxes still require PR write access. PR #2047 was confirmed open and
ready for review (`draft=false`).

## Existing-file confinement fixtures

Observed locally on 2026-11-17 from consumer commit `4c7b9289` with this
follow-up applied. The baseline whole-file run passed 81 tests. The existing
parent-directory receipt fixture referenced a missing file; it now creates a
real, otherwise valid receipt outside the fixture root. Added escaped symlinks
for receipt, run and artifact files, plus accepted nested local paths. These
cases exercise the same offline validator and preserve the addressability and
existing local-path checks.

Temporarily changed the workflow-only expected diagnostic to an empty list,
leaving the validator and socket/DNS guards unchanged. The named test exited 1:
**9 failed, 69 passed**, each failure reporting
`VERIFIED needs a local JSON receipt, not a workflow filename`. Restored the
rejection expectation in a `finally` block, then verified:

| Command | Observed result |
| --- | --- |
| `python3 -m pytest tests/preferences/test_legacy_request_adapter.py::test_coverage_map_keeps_claims_scoped_to_their_evidence -q -m "not slow"` | Exit 0; 78 passed |
| `python3 -m pytest tests/preferences/test_legacy_request_adapter.py -q -m "not slow"` | Exit 0; 85 passed |
| `ruff check tests/preferences/test_legacy_request_adapter.py` | Exit 0 |
| `black --line-length 100 tests/preferences/test_legacy_request_adapter.py` | Exit 0; unchanged |
| `BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/black-2044-boundaries black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .` | Exit 0; 530 files unchanged |

The initial parallel Black check stalled and was interrupted. Ran Black's CLI
with its batch formatter replaced by serial calls to `reformat_one`, retaining
the CLI's source discovery, configuration, CHECK mode and report. All 530 files
passed; the required unmodified CLI command above then passed with that cache.

Reconciliation of all implemented checklist entries was attempted before this
follow-up. The connector rejected the PR body update, results/blocker comment
and additive `needs-human` label with
`MCP tool call requires approval, but approval policy is never`. No PR metadata
was changed. The receipt fixtures verify validator behavior only; actual
product execution claims remain UNVERIFIED.

The commit attempt `test: exercise retained receipt path confinement` was
blocked at `git add` (exit 128): `.git/index.lock` could not be created on the
read-only filesystem. The changed test and this evidence record remain local;
committing them on the existing branch and publishing the checklist/evidence
require an environment with Git and PR write access.

## Remote locator rejection and task reconciliation

Observed locally on 2026-11-17 from consumer commit
`a57fc4d14b99362022b2a0208b160fafc97d5fd3` with this follow-up applied,
using Linux and CPython 3.14.10. Reviewed the recent commits before continuing;
the baseline named test passed 78 cases and the whole file passed 85 tests.
The implementation and earlier recorded workflow-only failure/restoration
already satisfy the remaining PR checklist entries. Reconciliation of the PR
body was attempted before adding further tests, but the connector rejected it.

Added six synthetic cases to the existing named test, using the same receipt
helper and socket/DNS guards. Both run and artifact fields reject a GitHub
workflow configuration URL, a locator without its numeric ID, and a locator
for the other resource type. Each case asserts its exact diagnostic. Existing
valid remote locators still pass without network requests.

| Command | Observed result |
| --- | --- |
| `python3 -m pytest tests/preferences/test_legacy_request_adapter.py::test_coverage_map_keeps_claims_scoped_to_their_evidence -q -m "not slow"` | Exit 0; 84 passed |
| `python3 -m pytest tests/preferences/test_legacy_request_adapter.py -q -m "not slow"` | Exit 0; 91 passed |
| `ruff check tests/preferences/test_legacy_request_adapter.py` | Exit 0 |
| `black --line-length 100 tests/preferences/test_legacy_request_adapter.py` | Exit 0; unchanged |
| `BLACK_CACHE_DIR=/tmp/black-2044-remote-locators BLACK_NUM_WORKERS=1 black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .` | Exit 0; 530 files unchanged |

The initial repository-wide Black command stalled and was interrupted. Ran
Black's CLI with serial `reformat_one` calls in place of its batch formatter,
preserving source discovery, configuration, CHECK mode and reporting. All 530
files passed; the unmodified required command then passed with that fresh cache.

- [x] Validate unverified, structured receipt-backed and invalid examples through
  the shared helper, including workflow-only evidence and remote locators.
- [x] Keep bounded proof layers and explicit unverified documentation; distinguish
  implemented transport, configured checks and observed execution in README.
- [x] Pass the named test and whole file, preserving addressability/local-path
  checks and the earlier recorded deliberate failure and restoration.

The PR body update, results comment and additive `needs-human` label were all
rejected with `MCP tool call requires approval, but approval policy is never`.
No PR metadata changed. The deliberate failure/restoration evidence above was
retained instead of repeating that completed experiment. These results concern
offline validator behavior only; real execution claims remain UNVERIFIED.

After all checks passed, staging the test and this record failed with exit 128:
Git could not create `.git/index.lock` on the read-only filesystem. The intended
commit is `test: reject remote configuration as receipt evidence`. Changes
remain in the workspace for committing on the existing PR branch from an
environment with a writable Git directory.

## Run/artifact consistency follow-up

Observed locally on 2026-11-17 from consumer commit
`d46789477c09bf870450475c5793f1b6b33d7bf6` with this follow-up applied.
The baseline whole file passed 91 tests. Added three cases to the existing
named test for Actions artifact URLs pointing to a different run, repository
or owner. Before the fix, the named test reported **3 failed, 84 passed**:
each inconsistent pair was accepted. The shared helper now rejects these pairs
with `Receipt artifact must belong to its recorded run`, without fetching URLs.
The receipt contract documents this consistency requirement.

Repeated the required deliberate failure by temporarily making only the
`workflow-only` case expect acceptance. Its VERIFIED claim supplied only an
existing workflow filename as its receipt. With DNS and socket guards active,
the named test exited 1 with **1 failed, 86 passed**, specifically:

```text
test_coverage_map_keeps_claims_scoped_to_their_evidence[workflow-only]
AssertionError: assert ['VERIFIED ne...low filename'] == []
Left contains one more item: 'VERIFIED needs a local JSON receipt, not a workflow filename'
```

Restored that expectation in a `finally` block, formatted the test with Black,
and verified:

| Command | Observed result |
| --- | --- |
| `python3 -m pytest tests/preferences/test_legacy_request_adapter.py::test_coverage_map_keeps_claims_scoped_to_their_evidence -q -m "not slow"` | Exit 0; 87 passed |
| `python3 -m pytest tests/preferences/test_legacy_request_adapter.py -q -m "not slow"` | Exit 0; 94 passed |
| `ruff check tests/preferences/test_legacy_request_adapter.py` | Exit 0 |
| `black --line-length 100 tests/preferences/test_legacy_request_adapter.py` | Exit 0; unchanged |
| `BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/black-2044-run-binding black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .` | Exit 0; 530 files unchanged |

The initial parallel Black check stalled and was interrupted. Black's CLI
source discovery and CHECK-mode reporting were then run with serial
`reformat_one` calls, checking all 530 files. The unmodified required CLI
command above subsequently passed using that fresh cache. Existing
addressability/local-path checks remain intact, and README still distinguishes
implemented transport, configured checks and observed execution. All actual
execution claims remain UNVERIFIED; these results concern the validator only.

Verified checklist reconciliation for this follow-up:

- [x] Validate unverified and structured receipt-backed examples through one
  reusable helper, including missing, mismatched and workflow-only cases.
- [x] Preserve bounded proof layers and explicit UNVERIFIED claims; README
  distinguishes implemented transport, configured checks and observed execution.
- [x] Pass the named test and record workflow-only failure followed by restoration.
- [x] Pass the whole test file and preserve the original addressability/local-path
  checks while deliberately updating the existing execution-evidence test.

Delivery remains blocked: after all checks passed, `git add` exited 128 because
the read-only Git directory prevented creation of `.git/index.lock`. Intended
commit: `test: bind receipt artifacts to their recorded runs`. The three changed
files remain local on `codex/issue-2044`; no branch or PR was created.

Automatic approval review also rejected the PR-body checklist reconciliation,
the evidence/blocker comment and the additive `needs-human` label, each with
`MCP tool call requires approval, but approval policy is never`. No PR metadata
changed. A final read confirmed PR #2047 is open with `draft=false`. Publishing
the evidence/checklist and committing these changes require an environment
with the corresponding write access.
