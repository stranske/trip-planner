# Issue #2017: current-head verification

Check date: 2026-11-08 (America/Chicago).

Outcome: the real workflow-pinned TPP checkout and planner requirements pass
`TPP_REPO_PATH=/tmp/issue2017-tpp /opt/anaconda3/bin/python3 -m pytest tests/scripts/test_cross_repo_dev_pins.py -q`.
Stop rule: two failed repair attempts or 20 minutes. No full suite is run.

## Diagnosis

Read the failed log with `gh run view 42542025018 --repo stranske/trip-planner --log-failed`.
The run belongs to delivery #2015 head `0d62be4352b29c0ee2d3d74bbbbb8cb5a930e36a`.
Its TPP checkout is `b56d92b389736c70370aa9134f379ac8cd1f3ad1`.

| Tool | Planner in failing delivery | Actual pinned TPP | Result |
| --- | --- | --- | --- |
| mypy | 2.4.1 | 2.4.1 | compatible |
| pytest | 9.2.0 | 9.2.0 | compatible |
| ruff | 0.17.4 | 0.17.3 | conflict |

Confirmed producer values with `git show <revision>:pyproject.toml` in the
producer clone. The log also contains synthetic regression failures restoring
mypy 2.4.0, pytest 9.1.1 and Ruff 0.17.2. Those are deliberately incompatible
fixture inputs, not the actual pinned producer's mypy/pytest values. The task
text incorrectly conflates those diagnostics with the live checkout conflict.

## Resolution and focused results

Merged current main, including the existing source fix from #2016. Resolved the
single workflow conflict by retaining main's producer ref
`5c9ec6e15ac959023b9fc9cdd1099d70a6073396`. That checkout matches its reviewed
snapshot and shares mypy 2.4.1, pytest 9.2.0 and Ruff 0.17.4 with planner.
No dependency pins were hand-edited in this round. The merged pyproject,
requirements.lock and autofix-versions.env match main byte-for-byte.

- Focused pytest command above: **39 passed in 2.26s**, no skips.
- `/opt/anaconda3/bin/python3 -m ruff check tests/scripts/test_cross_repo_dev_pins.py`:
  **All checks passed**.
- `/opt/anaconda3/bin/python3 -m mypy --follow-imports=silent tests/scripts/test_cross_repo_dev_pins.py`:
  **Success: no issues found in 1 source file**.
- Deliberately restored only the workflow ref to the original producer and ran
  `test_workflow_tpp_pin_resolves_with_planner_dev_pins`: **1 failed**, naming
  planner Ruff 0.17.4 versus TPP Ruff 0.17.3. Restored the original workflow
  bytes in a finally block and reran: **1 passed**.

The existing parameterized tests also cover isolated mypy, pytest and Ruff
conflicts, all original pins together, and the #2017 Ruff transition.

Runtime limitation: no repository virtual environment exists. The instructed
fallback interpreter is Python 3.12.2, Ruff 0.17.1 and mypy 2.4.0; these focused
results do not claim a supported-runtime full application run or exact-pin lint.
CI must provide supported Python 3.13/3.14 and selected tool-version evidence.

## Remaining evidence

T1-T6 are verified as the source compatibility repair and focused lint/typecheck
above. T7 elides two unnamed subtasks and cannot be certified from its text.
T8 and A2 are verified by the focused regression run and actual break/revert.

Do not infer A1 or A3 from their checked boxes. Current #2015 is CLOSED, still at
its original failed head, and `gh run view 42542025018` returns failure. No
regenerated #2015 passing run or subsequent sync-core classification was
established by this round. Blocking/drainable pair: downstream acceptance
unverified / retain the source fix and let the owning delivery/controller lane
supply regenerated-delivery and classification evidence. No gate or lease is
created here. Post-push exact-head CI and the seven-minute review floor remain
for the owning keepalive lane; this round does not merge the PR.
