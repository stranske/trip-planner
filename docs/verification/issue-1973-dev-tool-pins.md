# Issue #1973: dev-tool pin conflict verification

The existing source fix on PR #2005 head
`ef4e8afe69bb0acf75592bba1c63b24879bce285` passes the live cross-repo gate.
This round fixes compound and wildcard handling in the consumer-specific pin guard;
it edits no workflow files.

## Current follow-up

The guard only recognized an exact pin when it was the requirement's sole
specifier. It therefore missed `ruff==0.17.2,>=0.17` conflicting with
`ruff>=0.17.3`. It also treated wildcard `ruff==0.17.*` as an exact version,
incorrectly rejecting it alongside `ruff==0.17.3`.

The guard now finds exact pins within compound specifiers and leaves wildcard
validation to the other requirement's exact pin. Eight regression cases check
conflicting and compatible requirements on either project's side. Before the fix,
four failed and four passed; after the fix, all eight pass. Existing repeated
runtime/dev requirement cases still pass.

Recent commits were reviewed before implementation. The source-fix task should be
checked in PR #2005; the reproduction-test and deliberate-break tasks remain checked.
The attempted PR-body reconciliation was rejected by the GitHub approval boundary.
The two remaining acceptance criteria below must remain unchecked.

## Verified evidence

- [Original failing job](https://github.com/stranske/trip-planner/actions/runs/41956043710/job/127012076417):
  TPP `acc4aeddee5f4ffefbdc73fcb07505cd3d198197` required `ruff==0.17.2`,
  while planner required `ruff==0.17.3`; pip reported `ResolutionImpossible`.
- [Latest passing source-fix job](https://github.com/stranske/trip-planner/actions/runs/42450457117/job/128638389433):
  `Cross-Repo Smoke / cross-repo-full-product` succeeded on the pushed head above.
  Python 3.13 and 3.14 test jobs also succeeded in this Gate run. These hosted results
  precede the current uncommitted compound/wildcard guard change.
- [Earlier source-fix logs](https://github.com/stranske/trip-planner/actions/runs/42448858109/job/128633602330):
  `Cross-Repo Smoke / cross-repo-full-product` succeeded. Both the configured
  and resolved TPP SHA were `b56d92b389736c70370aa9134f379ac8cd1f3ad1`.
  The live pin guard passed, joint installation reported `No broken requirements found`,
  portal contract tests passed, and full-product verification passed including live TPP.
  The same Gate run's Python 3.13 and 3.14 test jobs also succeeded.
- Local focused verification:
  `python -m pytest tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -q -m 'not slow'`
  produced **60 passed, 1 skipped**. The skip requires a live sibling TPP checkout.
- The existing workflow test detects an absent guard, missing `TPP_REPO_PATH`, and execution
  after joint installation. These deliberate breaks were made only to in-memory
  workflow copies; the original workflow passed afterward.
- Ruff and Black passed for the changed pin-guard module; `git diff --check` passed.
  The required repository-wide Black command, with `BLACK_NUM_WORKERS=1`,
  timed out after 60 seconds (exit 124). During cancellation it reported
  **520 files would be left unchanged**. This is not a passing formatting gate.

## Task status

- [x] Source fix verified on PR #2005 using the live passing job above.
- [x] Regression test verified, including deliberate break and restoration.
- [ ] Named gate passes on regenerated sync PR #1972 and the full suite passes locally.
- [ ] Next sync-core round classifies #1972 without this finding.

PR #1972 still has head `d679b90ac41e91f80fa96f4b43cd05a28f592680`, but it is now
closed without merging (closed at `2026-11-08T05:33:26Z`). This run has not edited
it by hand. PR #2005 remains open and ready for review.
Land the reviewed source fix, then use the owning Workflows producer to regenerate
the sync delivery and collect its named-gate and sync-core evidence. A passing
source-fix PR does not establish those remaining acceptance criteria.

## Execution limits requiring follow-up

- This round's changes remain uncommitted because the required repository-wide
  Black gate timed out. The task's formatting rule prohibits committing Python
  changes until that command passes.
- GitHub refused the task-checkbox update, blocker comment, and `needs-human` label:
  `MCP tool call requires approval, but approval policy is never`.
- `gh run view 41956043710 --repo stranske/trip-planner` could not connect to GitHub.
  Evidence above was read through the connected GitHub API instead.
- The full local command `python -m pytest -q -m 'not slow' -x
  -o faulthandler_timeout=30` stalled during Starlette `TestClient` initialization
  in `tests/app/test_auth.py`. The 30-second stack dump shows the main thread
  waiting for the AnyIO blocking portal and its event-loop thread waiting in `select`.
  The attempt timed out after 60 seconds (exit 124); the full suite remains unverified.
- Rerun the full suite and normal repository-wide Black command in a validation
  environment that supports their process and thread communication, then commit
  the source changes and reconcile the PR checkboxes. Regenerate #1972 through
  the owning Workflows producer after landing the reviewed source fix.
