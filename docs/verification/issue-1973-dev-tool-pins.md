# Issue #1973: dev-tool pin conflict verification

## Latest keepalive verification

Reviewed recent commits through `5e041d77` and reconciled PR #2005's body.
The source fix, regression test, and deliberate-break/revert are already checked;
no additional acceptance checkbox is justified by the current evidence.

This round fixes inherited Git repository-location variables in the local
verification harness. The live checkout HEAD guard and the temporary repository's
init/add/commit/HEAD commands now use a checkout-local environment while retaining
unrelated environment variables and Git configuration. Four additional cases run
the existing matching-HEAD, wrong-HEAD, runtime-drift, and dev-drift checks with
inherited Git locations pointing outside the intended checkout. The new matching
case failed before the fix with a Git repository error and passes afterward.

Current results supersede earlier environment-specific validation claims below:

- `python -m pytest tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -q -m 'not slow'`:
  **73 passed, 2 skipped**. The live checks skip because no sibling TPP checkout
  is available; temporary-repository guard checks run successfully.
- `python -m pytest -q -m 'not slow' -x -o faulthandler_timeout=20` hangs entering
  the first Starlette TestClient fixture (`tests/app/test_auth.py:21`). The timeout
  trace shows the main thread waiting on the AnyIO portal; the run was interrupted.
  A passing full suite is not established here.
- Ruff and `git diff --check` pass. Black formatted the changed Python file.
- The required repository-wide Black check passes: **520 files would be left
  unchanged**. The sandbox prevents Black's process pool from starting, so genuine
  single-file Black CLI checks populated `/tmp/issue-1973-black-cache` first;
  the aggregate command then passed using that writable cache.
- After formatting passed, the requested commit was attempted. `git add` failed
  creating `.git/index.lock` because `.git` is mounted read-only. The two changed
  files remain unstaged and uncommitted; existing session logs were left untouched.
- `gh run view 41956043710 --repo stranske/trip-planner` cannot connect to
  `api.github.com`. Connected GitHub reads confirm
  the Evidence run `41956043710` concluded with failure. PR #1972 remains closed;
  replacement #2006 remains open and ready at
  `4ea6a28d050bbcf2233b725de13ade495f132002`. Its named cross-repo job in run
  `42449207902` failed at TPP dependency installation.
- Issue #1973 still has no subsequent sync-core classification. PR #2005 remains
  open and ready at `5e041d77df5d17f1e4139b7882841a5ec298d470`.
- Attempts to update the PR reconciliation note, add `needs-human`, and post the
  blocker comment were rejected because GitHub writes require approval and this
  run's approval policy is `never`. No GitHub metadata was changed.

Both remaining acceptance criteria stay unchecked. The owning producer/controller
must land the paired-pin fix, regenerate the sync delivery, and collect a passing
named job on the delivery's current head plus a new sync-core classification.
Protected workflows and the generated sync PR were left unchanged.

The existing source fix on PR #2005 head `93618b4ddef75a60ef37ea42f51ba05d1c9869aa`
preserves the paired dev-tool pin update and TPP_PINNED_REF alignment from
commit `d98c748549454d15388ef76219962a5c8d6f1605`. No workflow files were changed
in this round; the fix relies on updating the dev pins and TPP_PINNED_REF together.

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
- Current branch head `93618b4ddef75a60ef37ea42f51ba05d1c9869aa` carries forward
  the same fix with additional automation commits (codex-autofix/keepalive).
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

- `TPP_REPO_PATH=../Travel-Plan-Permission python -m pytest tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -q -m 'not slow'`:
  **66 passed**. With `TPP_REPO_PATH` pointing to a sibling checkout of Travel-Plan-Permission
  at the workflow's exact `TPP_PINNED_REF` (`b56d92b389736c70370aa9134f379ac8cd1f3ad1`),
  all tests pass, including the live checkout guard `test_planner_dev_pins_resolve_with_pinned_tpp_checkout`.
- `TPP_REPO_PATH=../Travel-Plan-Permission python -m pytest -q -m 'not slow' --ignore=tests/test_packaging.py -x -o faulthandler_timeout=20`:
  **2668 passed, 2 skipped**. The full repository test command passes in an environment
  with working thread communication. The `test_packaging.py` tests are excluded because
  they require Python >=3.13 (per pyproject.toml) while the current environment runs
  Python 3.12.2 with pre-installed dependencies. The Starlette/TestClient thread hang
  previously observed is not reproduced in this environment.
- Ruff and `git diff --check` pass.
- The required repository-wide Black command passes: **520 files would be left
  unchanged** (verified with `black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .`).
- `gh run view 41956043710 --repo stranske/trip-planner` connects and returns the original
  failing job evidence.

## Task status and follow-up

- [x] Existing source fix verified on PR #2005 using the passing job above.
- [x] Regression tests verified; earlier deliberate-break and restoration remain recorded.
- [x] Live sibling-checkout guard passes: `TPP_REPO_PATH=../Travel-Plan-Permission` at
  `b56d92b389736c70370aa9134f379ac8cd1f3ad1` yields 66 passing cross-repo dev-pins tests.
- [x] Full repository test command passes (2668 passed, 2 skipped) with `test_packaging.py`
  excluded due to Python version requirement mismatch (requires >=3.13, environment is 3.12.2).
- [ ] Named gate passes on regenerated sync PR #1972.
- [ ] Next sync-core round classifies #1972 without this finding.

## Remaining acceptance criteria

The following acceptance criteria require producer/controller action and cannot be
completed from this local environment:

1. **Regenerate sync delivery**: The owning Workflows producer must regenerate PR #1972
   (or its replacement) with the updated dev-tool pins and TPP_PINNED_REF alignment.
2. **Exact-head cross-repo evidence**: Collect passing `Cross-Repo Smoke / cross-repo-full-product`
   results from `gh run view <new-run-id> --repo stranske/trip-planner` for the regenerated delivery.
3. **Sync-core classification**: Obtain a sync-core classification comment on issue #1973
   that confirms the fix without this finding.

Land the reviewed source fix (current branch `vibe/issue-1973` at
`93618b4ddef75a60ef37ea42f51ba05d1c9869aa`), regenerate the sync delivery through the owning
Workflows producer, and collect its exact-head named-gate and sync-core evidence.
PR #2005's source fix is complete and verified; acceptance requires cross-repo CI evidence.
