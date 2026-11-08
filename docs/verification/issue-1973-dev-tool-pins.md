# Issue #1973: dev-tool pin conflict verification

The existing source fix on PR #2005 head
`590d50cacffa5467d4333934fea80061e03a5d78` passes the hosted cross-repo gate.
The two remaining acceptance criteria still require producer propagation and a
passing full local suite. No workflow files were changed in this round.

## Current verification change

`test_pip_resolves_paired_dev_tool_pins_offline` now invokes pip's actual resolver
with a 30-second timeout, local metadata-only wheels, `--no-index`, `--dry-run`,
and `--ignore-installed`. It reads the planner requirements and the producer
snapshot selected by the workflow. Restoring the original producer tool pins
produces `ResolutionImpossible`; the paired pins resolve to the expected Ruff,
Mypy, and Pytest versions. Both old and current wheel candidates are available,
so the negative case detects incompatible constraints rather than missing files.
This isolates tool-pin resolution; it does not establish a complete installation
or a passing hosted cross-repo gate on a regenerated delivery.

## Verified evidence

- [Original failing job](https://github.com/stranske/trip-planner/actions/runs/41956043710/job/127012076417):
  TPP required `ruff==0.17.2`, while planner required `ruff==0.17.3`;
  pip reported `ResolutionImpossible`.
- [Passing source-fix job](https://github.com/stranske/trip-planner/actions/runs/42455632263/job/128654115780):
  `Cross-Repo Smoke / cross-repo-full-product` succeeded on #2005 head
  `590d50cacffa5467d4333934fea80061e03a5d78`, including the live pin guard,
  joint dependency installation, portal contract, and full-product check.
- PR #1972 remains closed without merging, with head
  `d679b90ac41e91f80fa96f4b43cd05a28f592680`.
- New dev-tool delivery [PR #2006](https://github.com/stranske/trip-planner/pull/2006)
  is open and ready at `4ea6a28d050bbcf2233b725de13ade495f132002`.
  Its [cross-repo job](https://github.com/stranske/trip-planner/actions/runs/42449207902/job/128634653364)
  still fails with the same `ruff==0.17.2` / `ruff==0.17.3` conflict.
  A passing source-fix PR does not establish acceptance on a sync delivery.
- Issue #1973 has no newer sync-core classification comment. Neither the closed
  delivery nor the passing source-fix job proves the live acceptance criterion.

## Local validation

- `python -m pytest tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -q -m 'not slow'`:
  **62 passed, 1 skipped**. The skip requires a live sibling TPP checkout.
- Ruff and `git diff --check` pass.
- The required repository-wide Black command passes: **520 files would be left
  unchanged**. The initial worker-based invocation stalled. All 520 files were
  then checked individually with Black using a temporary cache, followed by
  `BLACK_CACHE_DIR=/tmp/trip-planner-black-1973 BLACK_NUM_WORKERS=1 black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .`.
  No files were excluded beyond the required pattern and configured exclusions.
- `python -m pytest -q -m 'not slow' -x -o faulthandler_timeout=30` again hangs
  during Starlette `TestClient` initialization in `tests/app/test_auth.py`.
  The 30-second stack dump shows the main thread waiting for the AnyIO portal
  and its event-loop thread waiting in `select`. The run was interrupted
  (exit 130); the full suite remains unverified.
- `gh run view 41956043710 --repo stranske/trip-planner` cannot connect to GitHub.
  Hosted evidence above was inspected through the connected GitHub API instead.
- Commit creation is blocked by the read-only Git directory. `git add` failed
  before staging with `Unable to create '.git/index.lock': Read-only file system`.
  The verified test and this evidence note remain uncommitted.

## Task status and follow-up

- [x] Existing source fix verified on PR #2005 using the passing job above.
- [x] Regression tests verified; earlier deliberate-break and restoration remain recorded.
- [ ] Named gate passes on regenerated sync PR #1972 and the full suite passes locally.
- [ ] Next sync-core round classifies #1972 without this finding.

Land the reviewed source fix, regenerate the sync delivery through the owning
Workflows producer, and collect its exact-head named-gate and sync-core evidence.
Run the full local suite in an environment supporting its thread communication.
The attempted blocker comment and `needs-human` label on #2005 were both rejected
by the GitHub approval boundary: `MCP tool call requires approval, but approval
policy is never`. PR #2005 remains open and ready for review.
