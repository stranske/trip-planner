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
above. T7 elides two unnamed subtasks; round 6 below recovers their source and
verifies the omitted work.
T8 and A2 are verified by the focused regression run and actual break/revert.

Do not infer A1 or A3 from their checked boxes. Current #2015 is CLOSED, still at
its original failed head, and `gh run view 42542025018` returns failure. No
regenerated #2015 passing run or subsequent sync-core classification was
established by this round. Blocking/drainable pair: downstream acceptance
unverified / retain the source fix and let the owning delivery/controller lane
supply regenerated-delivery and classification evidence. No gate or lease is
created here. Post-push exact-head CI and the seven-minute review floor remain
for the owning keepalive lane; this round does not merge the PR.

## Round 6: recover and verify T7

Check date: 2026-11-08 (America/Chicago), 2026-11-09 UTC.
Outcome: the actual workflow-pinned producer and planner pass the focused
cross-repo dev-pin suite, including the live checkout/snapshot checks.
Command:
`TPP_REPO_PATH=/tmp/issue2017-tpp /opt/anaconda3/bin/python3 -m pytest tests/scripts/test_cross_repo_dev_pins.py -q`.
Stop rule: one evidence pass, at most 15 minutes; no implementation repairs.

The literal T7 text is a formatter elision, not an additional implementation
requirement. Its source is the issue optimizer's
[task-splitting suggestion](https://github.com/stranske/trip-planner/issues/2017#issuecomment-6730036223).
That comment supplies the complete proposed tasks before the issue body split
sentences at commas and truncated the resulting list:

1. Identify the exact mypy, pytest and Ruff version mismatches.
2. Update the source so planner and the pinned TPP revision resolve to compatible
   versions.
3. Run `tests/scripts/test_cross_repo_dev_pins.py` locally and confirm the
   compatibility assertion no longer fires.

The visible T2-T6 cover diagnosis and the start of the compatibility sentence.
Accordingly, T7's omitted remainder is verified as compatibility of the paired
requirements plus the focused local run, rather than inventing two new tasks.
The original issue block also requests only the source fix and regression test;
it supplies no further implementation scope.

Round 6 results on parent head `4323a4a878c1dc247d5d71d2f5e6c594adf3c197`:

- Producer checkout is clean at `5c9ec6e15ac959023b9fc9cdd1099d70a6073396`.
  The live snapshot test verifies this equals the workflow ref and that runtime
  and dev dependency metadata match the reviewed snapshot.
- Focused suite: **39 passed in 2.36s**, zero skips. This exercises the real
  paired requirements and retains the synthetic incompatible-pin regressions.
- No implementation, dependency pin, workflow or regression fixture changed;
  this commit records verification of existing implementation for T7.

T7 is complete under the recovered source-task mapping above. A1 is still not
established: fresh `gh run view 42542025018 --repo stranske/trip-planner --json
conclusion,headSha,status,url` reports `failure`, and #2015 remains closed,
unmerged, at the original head. This round supplies no new A3 evidence.
Blocking/drainable pair: downstream delivery/classification evidence missing /
the owning sync/controller lane can reconcile delivery with the existing source
fix. These gaps do not require another dev-tool pin edit or expansion of T7.

## Keepalive regression follow-up: original producer resolution

Check date: 2026-11-09 UTC. Python 3.14.10, Black 26.10.1, Ruff 0.17.4,
and mypy 2.4.1 match the repository's supported runtime and selected tool pins.

Extended `test_pip_resolves_paired_dev_tool_pins_offline` with the actual
`b56d92b389736c70370aa9134f379ac8cd1f3ad1` producer snapshot from failed run
42542025018. The local wheel index now includes the producer's exact tool
versions as well as planner's and the original regression versions. The new
case requires `ResolutionImpossible` and both Ruff requirements, proving a
version conflict rather than a missing offline wheel. The current paired
producer remains covered by the successful resolution case.

- [x] Verify the original producer conflict and current paired resolution:
  `pytest tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -q -m "not slow"`
  reports **79 passed, 2 skipped**. The skips are the two live-checkout checks;
  no `TPP_REPO_PATH` is configured in this sandbox.
- [x] Verify regression sensitivity: temporarily using planner's requirements
  for the historical producer makes the new case fail because pip succeeds.
  Restoring the test returns the new case to **1 passed**.
- [x] Focused Ruff and mypy checks pass.
- [x] The required repository-wide Black check passes: **529 files would be
  left unchanged**. Files were checked individually first using
  `BLACK_CACHE_DIR=/tmp/issue2017-black-cache`, then the specified check was
  rerun against `.` with that cache and `BLACK_NUM_WORKERS=1` to avoid the
  sandbox's process/socket restrictions.

`pytest -q -m "not slow"` exits unsuccessfully during collection because the
sandbox denies local socketpair I/O required by TestClient. This is not a
full-suite pass. `gh run view 42542025018 --repo stranske/trip-planner --json
conclusion,headSha,status,url` cannot connect to api.github.com here. Connected
GitHub job-log readback confirms the original Ruff conflict; PR readback still
shows #2015 closed, unmerged, at its original head. #2018 is open and ready for
review. A1 and A3 remain unverified; no additional task or acceptance checkbox
is inferred from the elided placeholder.

Commit handoff is blocked: `.git` is mounted read-only, so `git add` fails to
create `.git/index.lock`. The complete changes are saved in
`/tmp/issue-2017-pin-regression.patch`; commit them from a writable checkout.
The requested `needs-human` label could not be applied to #2018 because the
GitHub tool requires approval and this run's approval policy is `never`.
