# Issue #1973: dev-tool pin conflict verification

The existing source fix on PR #2005 head
`d436c2dc876cbf1f39d299e2ca97630ee3a5a6c9` passes the live cross-repo gate.
This round adds a consumer-specific workflow regression test; it edits no workflow files.

## Verified evidence

- [Original failing job](https://github.com/stranske/trip-planner/actions/runs/41956043710/job/127012076417):
  TPP `acc4aeddee5f4ffefbdc73fcb07505cd3d198197` required `ruff==0.17.2`,
  while planner required `ruff==0.17.3`; pip reported `ResolutionImpossible`.
- [Passing source-fix job](https://github.com/stranske/trip-planner/actions/runs/42448858109/job/128633602330):
  `Cross-Repo Smoke / cross-repo-full-product` succeeded. Both the configured
  and resolved TPP SHA were `b56d92b389736c70370aa9134f379ac8cd1f3ad1`.
  The live pin guard passed, joint installation reported `No broken requirements found`,
  portal contract tests passed, and full-product verification passed including live TPP.
  The same Gate run's Python 3.13 and 3.14 test jobs also succeeded.
- Local focused verification:
  `python -m pytest tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -q -m 'not slow'`
  produced **48 passed, 1 skipped**. The skip requires a live sibling TPP checkout.
- The new test detects an absent guard, missing `TPP_REPO_PATH`, and execution
  after joint installation. These deliberate breaks were made only to in-memory
  workflow copies; the original workflow passed afterward.
- Ruff passed for both focused test modules. Black formatted and checked the changed file.
  A sequential Black library runner using the same CLI arguments and source selection
  also passed: **520 files would be left unchanged**. Only pool scheduling was replaced;
  Black's parsing, comparison, and exit status were preserved.

## Task status

- [x] Source fix verified on PR #2005 using the live passing job above.
- [x] Regression test verified, including deliberate break and restoration.
- [ ] Named gate passes on regenerated sync PR #1972 and the full suite passes locally.
- [ ] Next sync-core round classifies #1972 without this finding.

PR #1972 still has head `d679b90ac41e91f80fa96f4b43cd05a28f592680`.
It has not been edited by hand. PRs #1972 and #2005 were both open and ready for review.
Land the reviewed source fix, then use the owning Workflows producer to regenerate
the sync delivery and collect its named-gate and sync-core evidence. A passing
source-fix PR does not establish those remaining acceptance criteria.

## Execution limits requiring follow-up

- `git add` failed because `.git/index.lock` cannot be created on the read-only
  filesystem. This round's changes remain uncommitted.
- GitHub refused the task-checkbox update, blocker comment, and `needs-human` label:
  `MCP tool call requires approval, but approval policy is never`.
- `gh run view 41956043710 --repo stranske/trip-planner` could not connect to GitHub.
  Evidence above was read through the connected GitHub API instead.
- The full local command `python -m pytest -q -m 'not slow' -x` timed out after
  60 seconds during Starlette `TestClient` initialization in `tests/app/test_auth.py`.
- The required repository-wide Black command failed in multiprocessing setup
  because socket binding is forbidden. Single-worker scheduling also stalled;
  the normal command must be rerun in an unrestricted validation environment.
