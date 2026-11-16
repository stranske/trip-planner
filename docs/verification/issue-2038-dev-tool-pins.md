# Issue #2038: dev-tool pin verification

Verified locally on 2026-11-16 using Python 3.14.10, Ruff 0.17.5,
mypy 2.4.1 and Black 26.10.1, on branch `codex/issue-2038`.

The existing source fix is commit `a99e01e5`. The pending test change adds
`issue-2038-producer` to the offline pip resolver regression, using the actual
previous producer snapshot rather than replacing individual dependency strings.

## Source findings

Planner defines its development pins in `pyproject.toml`, with matching entries
in `requirements.lock`. The workflow now selects TPP
`50992156e4a1f97c1115b6c7af84a219a3b9aae7`.

| Tool | Planner | Previous TPP `5c9ec6e` | Selected TPP `50992156` |
| --- | --- | --- | --- |
| Ruff | 0.17.5 | 0.17.4 | 0.17.5 |
| mypy | 2.4.1 | 2.4.1 | 2.4.1 |
| pytest | 9.2.0 | 9.2.0 | 9.2.0 |

Both fixture snapshots' complete runtime and dev dependency lists were compared
with the immutable producer `pyproject.toml` files fetched from GitHub; both
match. No mypy or pytest downgrade is needed. Older synthetic negative-test
inputs in the issue's CI log are distinct from the actual previous producer.

## Verification

- Existing committed baseline: **85 passed, 2 skipped**.
- With the pending resolver regression:
  `pytest tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -q -m 'not slow'`:
  **86 passed, 2 skipped**. The skips require a live TPP checkout.
- `ruff check tests/scripts/test_cross_repo_dev_pins.py`: passed.
- `mypy --follow-imports=silent tests/scripts/test_cross_repo_dev_pins.py`: passed.
- Black formatted the changed file at line length 100. A subsequent
  `black.format_file_in_place(..., write_back=black.WriteBack.CHECK)` check of
  that file reported no formatting change needed.

For the deliberate-break check, the selected producer fixture's Ruff pin was
temporarily changed from 0.17.5 to 0.17.4. These two tests failed with exit 1,
identifying the mismatched Ruff versions and pip's `ResolutionImpossible`:

```text
test_workflow_tpp_pin_resolves_with_planner_dev_pins
test_pip_resolves_paired_dev_tool_pins_offline[None-None]
```

The fixture was restored byte-for-byte in a `finally` block. The same two tests
then passed with exit 0. Logs are in `/tmp/issue-2038-deliberate-break.log` and
`/tmp/issue-2038-restored.log` for this session.

## Remaining blockers

The required whole-repository command
`black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .`
failed because the sandbox denies worker socket creation (`PermissionError`).
The `BLACK_NUM_WORKERS=1` fallback stalled and was interrupted. The full Black
gate has therefore **not passed**; the requested instruction prohibits committing
the pending changes until it succeeds.

`pytest -q -m 'not slow'` exited 1 at the existing TestClient precondition:
local socketpair I/O failed during send wakeup byte with `PermissionError`.
This is an environment failure, not a passing full-suite run. Its log is
`/tmp/issue-2038-suite.log`.

PR-body reconciliation, a blocker comment, and the `needs-human` label were
attempted. GitHub write tools rejected all three because they require approval
while the current approval policy is `never`. The PR checklist remains unchanged.
PR #2039 was verified open and ready for review (`draft=false`). No workflows
were edited in this round, and no branch or pull request was created.

Next step: run the full formatting gate and suite in an environment permitting
local socket operations, commit the pending test change on this branch, and
reconcile the PR checklist. Regenerated sync-PR CI and the next sync-core
classification still require external verification.
