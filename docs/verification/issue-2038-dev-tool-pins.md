# Issue #2038: dev-tool pin verification

## Outcome and bounded check

Check date: 2026-11-16, local keepalive round 2. The real repository inputs must
co-resolve with the producer selected by `.github/workflows/cross-repo-smoke.yml`.
The command printing this outcome is:

```sh
/opt/anaconda3/bin/python3 -m pytest tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -q -m 'not slow'
```

Result: **86 passed, 2 skipped in 4.16s** on source head
`65c557bedde7f70f229da121fc7d93acbd2588f1`. The two skips require a live TPP
checkout. This round changes only this verification record, leaving those tested
inputs unchanged. Stop rule: two focused repair attempts or 20 minutes; no
implementation repair was needed.

## Source findings

Planner defines its development pins in `pyproject.toml`, with matching entries
in `requirements.lock`; generated pin updates have a single automation writer.
The existing source fix is commit `a99e01e55`. The workflow selects TPP
`50992156e4a1f97c1115b6c7af84a219a3b9aae7`.

| Tool | Planner | Previous TPP `5c9ec6e` | Selected TPP `50992156` |
| --- | --- | --- | --- |
| Ruff | 0.17.5 | 0.17.4 | 0.17.5 |
| mypy | 2.4.1 | 2.4.1 | 2.4.1 |
| pytest | 9.2.0 | 9.2.0 | 9.2.0 |

The selected producer's immutable `pyproject.toml` was read from GitHub again
in this round and confirms these versions. The issue's pytest 9.1.1 and mypy
2.4.0 conflicts are historical negative-test cases. The actual previous producer
already matches pytest and mypy; its Ruff pin causes this delivery's conflict.
No dependency pins were edited in round 2.

## Focused verification

Using the owner-selected fallback `/opt/anaconda3/bin/python3` (Python 3.12.2):

- The command above passed, including the existing `issue-2038-producer` pip
  resolver regression using the actual previous producer snapshot.
- `python -m ruff check tests/scripts/test_cross_repo_dev_pins.py`: passed.
- `python -m mypy --follow-imports=silent tests/scripts/test_cross_repo_dev_pins.py`:
  passed.

This runtime is below the application's Python >=3.13 requirement. These focused
metadata tests passed locally; supported-runtime execution is evidenced separately
by CI, not inferred from the local run.

For A2, only the workflow's TPP ref was temporarily restored to
`5c9ec6e15ac959023b9fc9cdd1099d70a6073396`. No dependency file was edited.
These exact tests failed (exit 1, two failures), naming Ruff 0.17.5 versus 0.17.4
and pip's `ResolutionImpossible`:

```text
tests/scripts/test_cross_repo_dev_pins.py::test_workflow_tpp_pin_resolves_with_planner_dev_pins
tests/scripts/test_cross_repo_dev_pins.py::test_pip_resolves_paired_dev_tool_pins_offline[None-None]
```

The workflow was restored byte-for-byte in a `finally` block. The same command
then passed (exit 0, two passed in 0.63s). `git diff --exit-code` confirmed no
workflow change remained. Session logs:
`/tmp/issue-2038-round2-break.log` and `/tmp/issue-2038-round2-restored.log`.

## CI and remaining acceptance

PR #2039 was read back open and ready (`draft=false`). On head `65c557bed`,
Python 3.14 and cross-repo smoke passed in
[run 43827284404](https://github.com/stranske/trip-planner/actions/runs/43827284404).
This is evidence for this repair PR, not regenerated sync PR #2037.

`gh run view 43820524287 --json headSha,status,conclusion,jobs` still reports
failure on sync PR #2037's original head
`65b25b559ea631d494e3dcfd624fb0126b098bbf`, including Python 3.14 and cross-repo
smoke. The PR readback confirms it has not been regenerated. A1 remains open;
the full suite was not run locally, as round 2 explicitly prohibits it.

A3 remains unverified: no subsequent sync-core classification was established.
The controller/sync owner must regenerate #2037 after source integration, then
read back its Python 3.14 run and the next sync-core classification. No generated
sync PR was edited or workflow dispatched by this round. While that acceptance
is pending, the focused local guard and mutation check remain runnable.

T7 contains only an elided placeholder, so its four unspecified subtasks cannot
be marked complete. T1-T6 and T8 are verified by source readback and focused
checks; A2 is verified by the deliberate-break/revert above. T4 and T6 need no
new pin edits because the required pytest and mypy values are already present.
