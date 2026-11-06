# Issue 1967: cross-repo dev-tool pin pairing (PR #1990)

**Operational outcome:** Cross-Repo Smoke / `cross-repo-full-product` passes on PR head with
compatible TPP pin `b56d92b3`; local deliberate-break reproduces the original
`ResolutionImpossible` class of conflict (mypy/pytest/ruff) against TPP `acc4aed`.
Enhanced: `_requirements` now retains all active Requirement objects per canonical package name;
`find_pin_conflicts` compares every exact-pin/constraint pair bidirectionally; `_exact_pin`
rejects wildcard equality. Added regression fixtures for exact pin + range, compatible/incompatible
wildcard constraints, and multiple requirements per package.

**Check date:** 2026-11-06 (America/Chicago).

**Stop rule:** At most three local pytest matrix runs and one `gh run view`; stop after first
unexpected exit code or 45 minutes.

**Repository interpreter:** CPython 3.12.2 at `/opt/anaconda3/bin/python3` (system interpreter;
repo selects CPython 3.14 via `.python-version`, but 3.14 not available in this environment).

**Branch head under test:** `9d2e68ba7980e23ab5f5e1c5a64691ba9a6cca12` (HEAD of `claude/issue-1967`).
Merge base: `40a71acb828a9175428509a485224cdb8293ec08` (sync with origin/main for merge readiness).

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

**Command:**
```bash
TPP_REPO_PATH=<absolute-checkout> python3 -m pytest tests/scripts/test_cross_repo_dev_pins.py tests/scripts/test_cross_repo_smoke_workflow.py -q
```

**Results:**
```text
# Compatible TPP pin (b56d92b389736c70370aa9134f379ac8cd1f3ad1)
TPP_REPO_PATH=../Travel-Plan-Permission-temp \
  python3 -m pytest tests/scripts/test_cross_repo_dev_pins.py \
  tests/scripts/test_cross_repo_smoke_workflow.py -q
→ 53 passed, exit 0

# Incompatible TPP pin (acc4aeddee5f4ffefbdc73fcb07505cd3d198197)
TPP_REPO_PATH=../Travel-Plan-Permission-temp (checked out to acc4aed) \
  python3 -m pytest tests/scripts/test_cross_repo_dev_pins.py::test_planner_dev_pins_resolve_with_pinned_tpp_checkout -xvs
→ 1 failed (test_planner_dev_pins_resolve_with_pinned_tpp_checkout):
   AssertionError: trip-planner and the pinned TPP revision cannot be installed together:
     mypy: trip-planner 'mypy==2.4.1' vs TPP 'mypy==2.4.0'
     pytest: trip-planner 'pytest==9.2.0' vs TPP 'pytest==9.1.1'
     ruff: trip-planner 'ruff==0.17.3' vs TPP 'ruff==0.17.2'
   exit 1

# Back to compatible TPP pin (b56d92b389736c70370aa9134f379ac8cd1f3ad1)
TPP_REPO_PATH=../Travel-Plan-Permission-temp \
  python3 -m pytest tests/scripts/test_cross_repo_dev_pins.py \
  tests/scripts/test_cross_repo_smoke_workflow.py -q
→ 53 passed, exit 0
```

**New regression tests added (10 new tests):**
- `test_find_pin_conflicts_exact_pin_with_range_in_tpp` - exact pin with compatible range
- `test_find_pin_conflicts_exact_pin_with_incompatible_range_in_tpp` - exact pin with incompatible range
- `test_find_pin_conflicts_exact_pin_in_tpp_with_range_in_planner` - range with compatible exact pin
- `test_find_pin_conflicts_exact_pin_in_tpp_with_incompatible_range_in_planner` - range with incompatible exact pin
- `test_find_pin_conflicts_wildcard_equality_not_treated_as_exact_pin` - wildcard equality rejection
- `test_find_pin_conflicts_compatible_wildcard_constraint` - compatible wildcard constraint
- `test_find_pin_conflicts_incompatible_wildcard_constraint` - incompatible wildcard constraint
- `test_find_pin_conflicts_multiple_requirements_same_package` - multiple requirements, all compatible
- `test_find_pin_conflicts_multiple_requirements_with_conflict` - multiple requirements with one conflict

Raw console capture: `.lane-scratch/acceptance-1967.log` (not committed; scratch dir).

## Sync lineage (#1966 → #1972)

Source fix lands in PR #1990 (pins + `TPP_PINNED_REF` + guard test). Regenerated sync PR
#1972 still fails Cross-Repo Smoke without the TPP pin move; after #1990 merges, #1972 should
be a no-op against `main`. **Next sync-core classification without the pin-conflict finding**
is controller-owned (`maint-68-sync-consumer-repos.yml` / sync-core round on Workflows); it
cannot be completed from this consumer closer run without merge of #1990 and a subsequent
sync-core round on the regenerated PR head.
