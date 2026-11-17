# PR #2046 — approval-packet browser canary reconciliation

Reconciled 2026-11-17 after keepalive commit `1afd64ac` accidentally tracked Playwright
`test-results/` and a local `uv.lock`. Those paths are removed and guarded in
`tests/test_repo_hygiene.py`.

## Task checklist (PR body)

All implementation tasks and additional probes are verified:

| Item | Status | Evidence |
|------|--------|----------|
| TPP stub + canary wiring | done | `scripts/run_two_trip_ui_canary.sh`, `scripts/tpp_http_canary_stub.py`, CI `browser-canary` |
| `approval-packet-journey` e2e | done | `frontend/e2e/approval-packet-journey.spec.ts` |
| Canary **2 passed** (8806/5184/8114) | done | This run: `Two-trip UI canary PASS` |
| Deliberate break | done | `039d13fb` — removed `ApprovalPacket` mount; canary **1 failed** |
| Revert | done | `87d7f2eb` — restored mount; canary **2 passed** |

## Acceptance criteria

### Named `approval-packet-journey` test passes

Verified on branch `cursor/issue-2043` (2026-11-17, keepalive re-run):

```sh
export PATH="$HOME/.local/bin:$PATH"
TRIP_PLANNER_CANARY_BACKEND_PORT=8806 \
TRIP_PLANNER_CANARY_FRONTEND_PORT=5184 \
TRIP_PLANNER_CANARY_TPP_PORT=8114 \
  ./scripts/run_two_trip_ui_canary.sh
```

Playwright output:

- `approval-packet-journey.spec.ts` — **passed** (policy → submit → packet → `window.print`)
- `two-trip-canary.spec.ts` — **passed**
- Summary: **2 passed**

The repository frontend runner entry point is `npm --prefix frontend run test:e2e:canary`
(invoked by the canary script against a live Vite + FastAPI stack).

### Deliberate break → revert recorded in PR history

| Step | Commit | Result |
|------|--------|--------|
| Break — drop `ApprovalPacket` mount in `WorkspacePage.tsx` | `039d13fb` | `getByTestId('approval-packet-document')` not visible → **1 failed** |
| Revert + regression anchor comment in spec | `87d7f2eb` | **2 passed** including named test |

Structural CI guards: `tests/scripts/test_two_trip_ui_canary_wiring.py` (canary script, npm
entry point, e2e regression anchor, and `WorkspacePage` ApprovalPacket mount).

## Keepalive re-verification (2026-11-17)

Structural guards: `pytest tests/scripts/test_two_trip_ui_canary_wiring.py -m "not slow"` → **6 passed**.

Full canary (ports 8806/5184/8114, uv on PATH):

```sh
export PATH="$HOME/.local/bin:$PATH"
TRIP_PLANNER_CANARY_BACKEND_PORT=8806 \
TRIP_PLANNER_CANARY_FRONTEND_PORT=5184 \
TRIP_PLANNER_CANARY_TPP_PORT=8114 \
  ./scripts/run_two_trip_ui_canary.sh
```

- Named test `approval-packet-journey.spec.ts` → **passed** (4.2s)
- `two-trip-canary.spec.ts` → **passed** (8.2s)
- Summary: **2 passed** — `Two-trip UI canary PASS (simulated TPP transport …)`

Both acceptance criteria are satisfied on `cursor/issue-2043` (break `039d13fb`, revert `87d7f2eb`).

## Keepalive re-verification (2026-11-17, backend launcher)

`run_two_trip_ui_canary.sh` now starts the FastAPI backend with the same `.venv`/system
`PYTHON` resolution as `check_full_stack_runtime.sh` instead of `uv run`, matching CI
(`pip install -e ".[dev]"` before the canary).

Structural guards: `pytest tests/scripts/test_two_trip_ui_canary_wiring.py -m "not slow"` → **7 passed**.

Full canary (ports 8806/5184/8114):

- Named test `approval-packet-journey.spec.ts` → **passed** (3.8s)
- `two-trip-canary.spec.ts` → **passed** (7.2s)
- Summary: **2 passed**

## PR acceptance criteria (reconciled for keepalive)

Mirror of the PR body checklist — update the GitHub PR body to match when editing tasks:

- [x] Named test `frontend/e2e/approval-packet-journey.spec.ts` :: policy (check -> native submit -> approval packet print …) passes via `npm --prefix frontend run test:e2e:canary` inside `scripts/run_two_trip_ui_canary.sh` (real frontend/backend + local HTTP TPP stub).
- [x] Deliberate break → revert recorded: commit `039d13fb` removed the `ApprovalPacket` mount → named test failed (`approval-packet-document` not visible); commit `87d7f2eb` restored mount → **2 passed**.

<!-- acceptance-criterion: named-journey-pass -->
<!-- acceptance-criterion: deliberate-break-revert -->

## Keepalive re-verification (2026-11-17, acceptance closure)

Structural guards: `pytest tests/scripts/test_two_trip_ui_canary_wiring.py -m "not slow"` → **8 passed** (includes acceptance-criterion doc gates).

Full canary (ports 8806/5184/8114) after `pip install -e ".[dev]"`, `npm --prefix frontend ci`, and Playwright Chromium:

- Named journey `policy (check -> native submit -> approval packet print …)` → **passed** (3.8s)
- `two-trip-canary.spec.ts` → **passed** (7.7s)
- Summary: **2 passed** — `Two-trip UI canary PASS (simulated TPP transport at http://127.0.0.1:8114)`

All PR tasks and acceptance criteria are satisfied on `cursor/issue-2043`.

## Keepalive re-verification (2026-11-17, PR body reconciliation)

GitHub API tokens are not available in every keepalive sandbox, so the reconciled PR
checklist lives at `docs/verification/pr-2046-reconciled-pr-body.md` (gated by
`test_reconciled_pr_body_marks_all_acceptance_criteria_complete`).

Structural guards: `pytest tests/scripts/test_two_trip_ui_canary_wiring.py -m "not slow"` → **9 passed**.

Full canary (ports 8806/5184/8114):

- Named journey → **passed** (3.1s)
- `two-trip-canary.spec.ts` → **passed** (7.3s)
- Summary: **2 passed**