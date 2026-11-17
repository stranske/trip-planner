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

Verified on branch `cursor/issue-2043` (2026-11-17):

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

**PR body update (when API token available):** check both acceptance-criteria boxes under
`#### Acceptance criteria` — verification above satisfies them; keepalive does not auto-check
acceptance criteria.