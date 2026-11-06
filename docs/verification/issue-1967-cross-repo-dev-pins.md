# Issue 1967: cross-repo dev-tool pin pairing (PR #1990)

PR #1990 delivers the compatible dependency pairing and regression guard. It
references #1967; it does not complete that issue's operational acceptance.

## Delivered scope

- Existing dev-tool updates in `.github/workflows/autofix-versions.env`,
  `pyproject.toml`, and `requirements.lock` are retained unchanged by the salvage.
- `TPP_PINNED_REF` is `b56d92b389736c70370aa9134f379ac8cd1f3ad1`, with
  a targeted pin check before co-installation in `cross-repo-smoke.yml` and the
  corresponding reference in `docs/design-coverage-map.md`.
- `test_cross_repo_dev_pins.py` filters inactive requirements, preserves duplicate
  requirements, compares exact pins against constraints in both directions, and
  rejects wildcard equality as an exact pin, with regression fixtures.

The guard checks shared requirement constraints; it is not a complete dependency
resolver or proof of a live two-app handshake.

## Focused verification

**Outcome 1:** the focused pin and workflow checks pass against the pyproject
from the configured TPP revision. Check date: 2026-11-06 (America/Chicago).
Stop rule for this salvage: two repair attempts or 45 minutes.

Tested implementation commit: `eb985d6f1f1d3260d98b5fde38f6804fa4fa7dbf`.
The salvage changes only this verification document; the tested implementation
and dependency pins remain unchanged.

The repository selects Python 3.14 in `.python-version`. `uv python find 3.14`
resolved `/Users/teacher/.codex/py314/bin/python`, verified as CPython 3.14.3.
Only the two focused modules were run locally, not `make test` or the full suite.

The temporary TPP directory contains only `pyproject.toml` fetched through the
GitHub contents API at `b56d92b389736c70370aa9134f379ac8cd1f3ad1`;
it is not a full TPP checkout.

```bash
TPP_REPO_PATH=/private/tmp/trip-planner-1990-tpp-b56d92b \
  /Users/teacher/.codex/py314/bin/python -m pytest \
  tests/scripts/test_cross_repo_dev_pins.py \
  tests/scripts/test_cross_repo_smoke_workflow.py -q
```

```text
53 passed in 0.58s
exit 0
```

Hosted evidence inspected on 2026-11-06:

```text
gh run view 42227879338 --repo stranske/trip-planner
headSha: eb985d6f1f1d3260d98b5fde38f6804fa4fa7dbf
conclusion: success
Cross-Repo Smoke / cross-repo-full-product: success
```

[Run 42227879338](https://github.com/stranske/trip-planner/actions/runs/42227879338)
predates the salvage documentation commit. It proves that implementation head's
smoke result, not the result of any later head or regenerated sync PR.

## Deferred acceptance: issue #1967 remains open

The following work is outside the salvaged PR and remains tracked by #1967:

- Record dated `make test` output using the repository-selected interpreter and
  identify the tested commit. The salvage explicitly runs only focused tests.
- Record a current-head run of
  `test_planner_dev_pins_resolve_with_pinned_tpp_checkout` using a full TPP
  checkout: pass at `b56d92b389736c70370aa9134f379ac8cd1f3ad1`, fail at
  `acc4aeddee5f4ffefbdc73fcb07505cd3d198197`, then restored pass. Earlier
  unbound local matrix claims have been removed; the focused result above does
  not establish that full sequence.
- Establish actual sync lineage using `gh pr view 1966` and `gh pr view 1972`
  with `--repo stranske/trip-planner`; inspect the associated Evidence run with
  `gh run view <run-id>` and record its exact head and smoke conclusion. No
  regeneration relationship, current failure, or future no-op is asserted here.
- Inspect the next controller-owned Workflows
  `maint-68-sync-consumer-repos.yml` / sync-core round and append its exact
  target-head classification. That controller retains scheduling and writer
  ownership; this salvage does not dispatch or take over a sync round.

Blocking/drainable pair: issue-wide acceptance remains unproven; the completed
pairing and guard can proceed through PR #1990's normal CI/review gates while
the remaining evidence is collected under #1967.
