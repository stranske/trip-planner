# Issue 1967: cross-repo dev-tool pin pairing (PR #1990)

**Operational outcome:** Cross-Repo Smoke / `cross-repo-full-product` passes on PR head with
compatible TPP pin `b56d92b3`; local deliberate-break reproduces the original
`ResolutionImpossible` class of conflict (mypy/pytest/ruff) against TPP `acc4aed`.

**Check date:** 2026-11-05 (America/Chicago).

**Stop rule:** At most three local pytest matrix runs and one `gh run view`; stop after first
unexpected exit code or 45 minutes.

**Repository interpreter:** CPython 3.14.3 at
`.venv/bin/python` (created from repo `.python-version` via the Dropbox trip-planner 3.14
bootstrap interpreter).

**Branch head under test:** Local pytest matrix on `0a378c76798534805a65544c0ffcb6feddff87f5`.
Closer merge with `origin/main` for merge readiness: `40a71acb828a9175428509a485224cdb8293ec08`.
CI run below bound to the pre-merge fix SHA `0a378c76…` (same tree as the pin/TPP changes).

## CI evidence (Cross-Repo Smoke)

```text
gh run view 42120115243 --repo stranske/trip-planner
headSha: 0a378c76798534805a65544c0ffcb6feddff87f5
conclusion: success
job cross-repo-full-product: success
url: https://github.com/stranske/trip-planner/actions/runs/42120115243
```

## Local acceptance (named tests only)

Documented repository command is `make test` (full `tests/`); per closer lane scope, only the
issue-named pytest modules were executed locally. CI on PR #1990 runs the full suite.

```text
TPP_REPO_PATH=<TPP checkout @ b56d92b389736c70370aa9134f379ac8cd1f3ad1> \
  .venv/bin/python -m pytest tests/scripts/test_cross_repo_dev_pins.py \
  tests/scripts/test_cross_repo_smoke_workflow.py -q
→ 42 passed, exit 0

TPP_REPO_PATH=<TPP checkout @ acc4aeddee5f4ffefbdc73fcb07505cd3d198197> \
  (same pytest command)
→ 1 failed (test_planner_dev_pins_resolve_with_pinned_tpp_checkout):
   mypy 2.4.1 vs 2.4.0, pytest 9.2.0 vs 9.1.1, ruff 0.17.3 vs 0.17.2; exit 1

TPP_REPO_PATH=<TPP checkout @ b56d92b again> (same pytest command)
→ 42 passed, exit 0
```

Raw console capture: `.lane-scratch/acceptance-1967.log` (not committed; scratch dir).

## Sync lineage (#1966 → #1972)

Source fix lands in PR #1990 (pins + `TPP_PINNED_REF` + guard test). Regenerated sync PR
#1972 still fails Cross-Repo Smoke without the TPP pin move; after #1990 merges, #1972 should
be a no-op against `main`. **Next sync-core classification without the pin-conflict finding**
is controller-owned (`maint-68-sync-consumer-repos.yml` / sync-core round on Workflows); it
cannot be completed from this consumer closer run without merge of #1990 and a subsequent
sync-core round on the regenerated PR head.
