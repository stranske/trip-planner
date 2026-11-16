# Issue #2038: dev-tool pin verification

Check date: 2026-11-16 (UTC). Branch `cursor/issue-2038`.
Outcome: reproduce the `#2037` pin conflict on main, review closed PR `#2039` (`cfe14d89e8a6`), and
confirm the paired pin repair on this branch.

Stop rule: record evidence only; no dependency or workflow edits in this pass unless a gap is found.

## Diagnosis: `#2037` pin conflict on `main`

On `main` (`968b17f4`), planner `pyproject.toml` pins `ruff==0.17.4` and
`.github/workflows/cross-repo-smoke.yml` sets
`TPP_PINNED_REF: 5c9ec6e15ac959023b9fc9cdd1099d70a6073396` (TPP `ruff==0.17.4`).
Sync PR `#2037` bumps planner dev pins to `ruff==0.17.5` without advancing the workflow producer ref,
so cross-repo resolution fails.

| Tool | Planner after `#2037` | TPP at `5c9ec6e` (main workflow) | TPP at `50992156` (repair) |
| --- | --- | --- | --- |
| ruff | 0.17.5 | 0.17.4 | 0.17.5 |
| mypy | 2.4.1 | 2.4.1 | 2.4.1 |
| pytest | 9.2.0 | 9.2.0 | 9.2.0 |

The mypy `2.4.1` vs `2.4.0` and pytest `9.2.0` vs `9.1.1` lines in earlier failure logs come from
synthetic `#2038` downgrade fixtures in `tests/fixtures/issue_2038_dev_pins/trip-planner.toml`, not
from the live pinned TPP checkout at `5c9ec6e`.

## Local reproduction (main-style mismatch)

With planner already at `ruff==0.17.5` on this branch, temporarily restoring only the workflow
producer ref to main's `5c9ec6e…` reproduces the conflict:

```sh
python -m pytest tests/scripts/test_cross_repo_dev_pins.py -q
```

Result: **12 failed, 97 passed, 2 skipped** (Python 3.14.10). Representative pip error:

```text
travel-plan-permission[dev] … depends on ruff==0.17.4
trip-planner[dev] … depends on ruff==0.17.5
ERROR: ResolutionImpossible
```

Restoring `TPP_PINNED_REF: 50992156e4a1f97c1115b6c7af84a219a3b9aae7` yields **112 passed, 2 skipped**.

## Review of closed PR `#2039` (`cfe14d89e8a6`)

Fetched `refs/pull/2039/head` and compared trees.

| Concern / thread theme | What was checked on `#2039` | Disposition on this PR (branch tip) |
| --- | --- | --- |
| Scope creep (`PRODUCT_CONTRACT`, `check_full_product_verification`) | Merge commit `cfe14d89` **dropped** those files relative to parent `aee71a92`; pin repair files match the narrowed diff vs `main` | Same pin-only scope; no product-probe or ledger files on this branch |
| Live vs snapshot TPP guards | `test_live_tpp_checkout_matches_workflow_snapshot`, workflow snapshot under `tests/fixtures/tpp_dev_pins/50992156…` | Present; `TPP_PINNED_REF` and fixture agree on `50992156` |
| Historical `#2038` producer failure | `test_offline_workflow_guard_rejects_original_producer_pins` uses fixture `5c9ec6e…` (`ruff==0.17.4`) vs planner `0.17.5` | Parameterized; stale-ruff case fails when fixture or workflow ref reverted |
| Optional `extra="dev"` marker evaluation | `_requirements` evaluates dev pins with `extra="dev"` only | Implemented in `tests/scripts/test_cross_repo_dev_pins.py` |
| `requires-python` on offline wheels | Snapshots include producer `requires-python`; guards reject drift | Both TPP fixture trees and `#2038` planner fixture carry `>=3.13,<3.15` |
| Deliberate-break / red-green | Prior `#2039` evidence: TPP ref revert → failures | Re-verified below on current head |
| Downstream A1 / A3 (regenerated `#2037`, sync-core) | `#2039` notes: owning sync lane; not satisfied by pin repair alone | Unchanged; out of scope for this source fix |

## Focused verification on current head

Command:

```sh
python -m pytest tests/scripts/test_cross_repo_dev_pins.py -q
```

- Green baseline: **112 passed, 2 skipped** (~15s, keepalive round 5/12, 2026-11-16) including `test_repaired_workflow_pins_agree_across_repo`.
- Keepalive round 5/12 (orchestrator had `tests_skipped`): re-ran green baseline and deliberate-break on `tests/fixtures/issue_2038_dev_pins/trip-planner.toml` `ruff==0.17.4` → **8 failed** in `-k issue-2038`; fixture restored to `0.17.5`.
- `TPP_PINNED_REF` → `5c9ec6e…`: **12 failed** (ruff conflict; re-run 2026-11-16); workflow file restored immediately after.
- `tests/fixtures/issue_2038_dev_pins/trip-planner.toml` `ruff==0.17.4` (repaired `0.17.5` restored after): **8 failed** in `-k issue-2038` (recorded on prior head).
- After restoration: **112 passed** again.

Lint on the changed test module:

```sh
python -m ruff check tests/scripts/test_cross_repo_dev_pins.py
python -m mypy --follow-imports=silent tests/scripts/test_cross_repo_dev_pins.py
```

Both succeed. Full suite:

```sh
make test
```

**3019 passed, 6 skipped** (~4.5m, `-m "not slow"`).

## Pin agreement (repair state)

| Location | ruff pin |
| --- | --- |
| `.github/workflows/autofix-versions.env` | `RUFF_VERSION=0.17.5` |
| `pyproject.toml` | `ruff==0.17.5` |
| `requirements.lock` | `ruff==0.17.5` |
| `.github/workflows/cross-repo-smoke.yml` | `TPP_PINNED_REF: 50992156…` |
| `docs/design-coverage-map.md` | documents `50992156…` |

CI readback on head (GitHub Actions, round 5/12): **Cross-Repo Smoke / cross-repo-full-product** and **Python CI / python 3.14** pass (run `43943342466`); **Gate** pass.

Keepalive round 6 (2026-11-16, commit `5dcd5427`): local PR-head parity before push:

```sh
python -m ruff check --select E4,E7,E9,F --extend-exclude .workflows-lib .
python -m mypy --config-file pyproject.toml --exclude .workflows-lib .
make test
python -m pytest tests/test_ci_python_standard.py tests/scripts/test_cross_repo_smoke_workflow.py tests/scripts/test_cross_repo_dev_pins.py -q -m "not slow"
```

- Ruff (CI select set): pass
- mypy (reusable Python CI args): pass (`493` source files after dropping stale `build/`)
- `make test`: **3023 passed**, 6 skipped (~4m52s)
- Pin/smoke proxy suite: **157 passed**, 2 skipped
- New guard: `test_mypy_matches_reusable_python_ci` encodes the hosted typecheck command beside `test_ruff_check_matches_reusable_python_ci_when_ruff_omitted`

Keepalive round 6/12 (2026-11-16, commit `f0ab9c83`): local acceptance after orchestrator `tests_skipped` (CI green on head):

```sh
python -m pytest tests/scripts/test_cross_repo_dev_pins.py -q
python -m ruff check tests/scripts/test_cross_repo_dev_pins.py
python -m mypy --follow-imports=silent tests/scripts/test_cross_repo_dev_pins.py
```

- Focused pin suite: **112 passed**, 2 skipped (~15s).
- Module ruff/mypy: pass.
- A1 deliberate break (`trip-planner.toml` dev `ruff==0.17.4` temporary): **8 failed** in `-k issue-2038`; fixture restored to `0.17.5`; suite **112 passed** again.
- CI readback on head: **Cross-Repo Smoke / cross-repo-full-product** and **Python CI / python 3.14** pass (workflow runs on `f0ab9c83`, e.g. `43952603169`).

Keepalive round 7/12 (2026-11-16, commit `dec7f89e`): local acceptance after orchestrator `tests_skipped` (CI green on head):

```sh
python -m pytest tests/scripts/test_cross_repo_dev_pins.py -q
python -m ruff check tests/scripts/test_cross_repo_dev_pins.py
python -m mypy --follow-imports=silent tests/scripts/test_cross_repo_dev_pins.py
```

- Focused pin suite: **112 passed**, 2 skipped (~17s).
- Module ruff/mypy: pass.
- A1 deliberate break (`trip-planner.toml` dev `ruff==0.17.4` temporary): **8 failed** in `-k issue-2038`; fixture restored to `0.17.5`; suite **112 passed** again.
- CI readback on head: **Cross-Repo Smoke / cross-repo-full-product** and **Python CI / python 3.14** pass (workflow runs on `dec7f89e`, e.g. `43955967155`).

Keepalive round 8/12 (2026-11-16, parent `920a5f73`): local acceptance after orchestrator `tests_skipped` (CI green on head):

```sh
python -m pytest tests/scripts/test_cross_repo_dev_pins.py -q
python -m ruff check tests/scripts/test_cross_repo_dev_pins.py
python -m mypy --follow-imports=silent tests/scripts/test_cross_repo_dev_pins.py
```

- Focused pin suite: **112 passed**, 2 skipped (~14s).
- Module ruff/mypy: pass.
- A1 deliberate break (`trip-planner.toml` dev `ruff==0.17.4` temporary): **8 failed** in `-k issue-2038`; fixture restored to `0.17.5`; suite **112 passed** again.
- CI readback on head: **Cross-Repo Smoke / cross-repo-full-product** and **Python CI / python 3.14** pass (workflow runs on `920a5f73`, e.g. `43958534552`).

Keepalive round 9/12 (2026-11-16, parent `5cd31b78`): local acceptance after orchestrator `tests_skipped` (CI green on head):

```sh
python -m pytest tests/scripts/test_cross_repo_dev_pins.py -q
python -m ruff check tests/scripts/test_cross_repo_dev_pins.py
python -m mypy --follow-imports=silent tests/scripts/test_cross_repo_dev_pins.py
```

- Focused pin suite: **112 passed**, 2 skipped (~15s).
- Module ruff/mypy: pass.
- A1 deliberate break (`trip-planner.toml` dev `ruff==0.17.4` temporary): **8 failed** in `-k issue-2038`; fixture restored to `0.17.5`; suite **112 passed** again.
- CI readback on head: **Cross-Repo Smoke / cross-repo-full-product** and **Python CI / python 3.14** pass (workflow runs on `5cd31b78`, e.g. `43961295146`).