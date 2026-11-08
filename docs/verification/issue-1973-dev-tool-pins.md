# Issue #1973: dev-tool pin conflict verification

The existing source fix on PR #2005 head
`47f4e3b972b2aa5c0f48fe580a36d56ee861b544` passes the hosted cross-repo gate.
The two remaining acceptance criteria still require producer propagation and a
passing full local suite. No workflow files were changed in this round.

## Current verification change

`test_pip_resolves_paired_dev_tool_pins_offline` now resolves both projects through
their `[dev]` extras, matching the dependency path in the failing joint install.
Metadata-only project wheels declare the real planner and producer tool pins as
extra dependencies; pip reads those declarations rather than root tool requirements.
Five cases cover all old producer pins, isolated Ruff/Mypy/Pytest conflicts, and
the paired update. Every conflict must name both project extras and the old and
current tool requirements. The success report must contain both projects and all
three current tools, ensuring the extras actually activate those dependencies.

Pip still runs with a 30-second timeout, `--no-index`, `--dry-run`, and
`--ignore-installed`, with both old and current candidate wheels available.
This isolates tool-pin resolution; it does not establish a complete installation
or a passing gate on a regenerated sync delivery. Restoring the snapshot's old
Ruff pin made the paired-update test fail with `ResolutionImpossible`; after
restoring the snapshot, the focused checks passed again.

## Verified evidence

- [Original failing job](https://github.com/stranske/trip-planner/actions/runs/41956043710/job/127012076417):
  TPP required `ruff==0.17.2`, while planner required `ruff==0.17.3`;
  pip reported `ResolutionImpossible`.
- [Passing source-fix job](https://github.com/stranske/trip-planner/actions/runs/42456539337/job/128656704998):
  `Cross-Repo Smoke / cross-repo-full-product` succeeded on #2005 head
  `47f4e3b972b2aa5c0f48fe580a36d56ee861b544`, including the live pin guard,
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
  **65 passed, 1 skipped**. The skip requires a live sibling TPP checkout.
- Ruff and `git diff --check` pass.
- The required repository-wide Black command passes: **520 files would be left
  unchanged**. The initial worker-based invocation stalled. All 520 files were
  then checked serially with Black's `reformat_one` using identical source
  discovery, configuration, and a temporary cache, followed by
  `BLACK_CACHE_DIR=/tmp/trip-planner-black-1973 BLACK_NUM_WORKERS=1 black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .`.
  No files were excluded beyond the required pattern and configured exclusions.
- `python -m pytest -q -m 'not slow' -x -o faulthandler_timeout=20` again hangs
  during Starlette `TestClient` initialization in `tests/app/test_auth.py`.
  The 20-second stack dump shows the main thread waiting for the AnyIO portal
  and its event-loop thread waiting in `select`. The run was interrupted
  (exit 130); the full suite remains unverified. A standalone asyncio probe
  also failed to deliver a thread-safe callback or wake the loop to stop it,
  independently of the application and its dependencies.
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
Recent commits and PR #2005's body were reconciled: its three checked items
already match the evidence, and both acceptance criteria remain unchecked.
The attempted PR-body evidence update, blocker comment, and `needs-human` label
on #2005 were rejected
by the GitHub approval boundary: `MCP tool call requires approval, but approval
policy is never`. PR #2005 remains open and ready for review.
