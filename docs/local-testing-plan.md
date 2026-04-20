# Local Testing Plan

This plan is the production-focused verification lane for the planner's highest-value journeys.

Use it when a branch touches auth, trip creation, workspace flows, business policy/proposal state, or any browser-facing behavior that should remain reliable in both local development and a deploy preview.

## Baseline Versus Production-Readiness

`make runtime-check` remains the baseline MVP verification path:

- backend runtime tests
- frontend unit/build checks
- one local full-stack smoke path

That baseline is still required, but it is not the whole production-readiness story. The matrix below adds the planner journeys most likely to regress in real usage, plus a repeatable preview smoke pass.

## Canonical Local Sequence

Run these commands from the repo root after activating `.venv` and installing `frontend/node_modules`:

```bash
make runtime-production-check
```

That command runs:

1. backend auth, trip, workspace, budget, policy, and proposal route tests
2. frontend route tests for sign-up, sign-in, trip listing, trip creation, trip detail, and workspace flows
3. the frontend production build
4. the local full-stack smoke check

If you already know a branch only changed the full-stack smoke path, you may still use:

```bash
make runtime-smoke
```

For full-product readiness evidence, run the separate product-verification lane:

```bash
make full-product-check
```

`make runtime-full-product-check` is an equivalent alias for callers that keep all runtime gates under the same prefix.

That command creates fresh leisure and business trips through the runtime API, opens their workspaces, asserts runtime/source-backed inventory and scenario comparison identifiers, submits one planner turn, persists a business proposal submission, and ingests an evaluation result. It also reports map-provider and live Travel-Plan-Permission readiness explicitly. Missing map or TPP configuration is reported as `SKIPPED` or `BLOCKED` with the exact missing env var or sibling checkout path; it is never reported as live readiness.

## Critical Journeys Covered

### Automated Local Checks

| Journey | Coverage |
| --- | --- |
| Account creation, sign-in, logout, session restore | `tests/app/test_auth.py`, `frontend/src/routes/SignupPage.test.tsx`, `frontend/src/routes/LoginPage.test.tsx` |
| Trip creation, listing, detail reload | `tests/app/test_trip_routes.py`, `frontend/src/routes/TripsPage.test.tsx`, `frontend/src/routes/NewTripPage.test.tsx`, `frontend/src/routes/TripDetailPage.test.tsx` |
| Workspace load, comparison, planner interaction, budget state | `tests/app/test_workspace.py`, `tests/app/test_budget_routes.py`, `frontend/src/routes/WorkspacePage.test.tsx` |
| Business policy import and proposal lifecycle | `tests/app/test_policy.py`, `tests/app/test_proposal.py` |
| Local end-to-end runtime wiring | `scripts/check_full_stack_runtime.sh --smoke-only`, `frontend/src/smoke/runtime.smoke.test.ts` |
| Full-product fresh leisure/business journeys | `scripts/check_full_product_verification.py`, `tests/app/test_full_product_verification.py` |

### Browser-Facing Manual Review

Use a browser for these checks after the automated matrix passes:

1. Sign up with a fresh account, confirm the app routes into `/trips`, then refresh once to confirm session restore.
2. Create one leisure trip from `/trips/new` and confirm the app routes into `/workspace/:tripId`.
3. In the workspace, confirm scenario summaries, comparison content, and any saved-scenario references render without empty-state regressions.
4. If the branch touches business flows, verify the workspace still surfaces policy posture and proposal status without hiding failure details.
5. Exercise one degraded path intentionally:
   - sign out and confirm protected routes redirect or fail cleanly
   - if no Google Maps key is configured, confirm the workspace stays on the textual fallback map surface
   - if no live TPP transport is configured, confirm the UI and docs treat policy/proposal transport as optional or deferred instead of a setup failure

Capture failures with the exact route, the trip id (when present), the request payload or fixture used, and a screenshot when the problem is browser-visible.

## Preview Smoke

Run the preview smoke lane against any deploy preview URL:

```bash
make runtime-preview-smoke TRIP_PLANNER_PREVIEW_URL=https://deploy-preview-123--example.netlify.app
```

Or call the script directly:

```bash
./scripts/check_production_readiness.sh --preview https://deploy-preview-123--example.netlify.app
```

The preview pass reuses the runtime smoke test against the provided origin. It verifies:

- `/api/health` responds from the deployed stack
- sign-up still creates a session cookie
- the workspace API remains reachable from the deployed frontend/backend origin

This preview smoke is intentionally lightweight. It is a guardrail for deploy-preview regressions, not a replacement for the local route and API matrix.

## Optional Live Integration Checks

These are additive checks, not prerequisites for the default local matrix:

- `VITE_GOOGLE_MAPS_BROWSER_API_KEY` for the optional Google Maps JavaScript adapter path
- `VITE_GOOGLE_MAPS_PROVIDER_STATE` for local `ready`, `loading`, or `error` adapter-state checks without live provider access
- `TPP_BASE_URL`, `TPP_ACCESS_TOKEN`, and `TPP_OIDC_PROVIDER` for live Travel-Plan-Permission transport
- `TPP_REPO_PATH` for starting a sibling `Travel-Plan-Permission` checkout when `TPP_BASE_URL` is not already configured; by default the verifier looks for `../Travel-Plan-Permission`

Only run live integration verification when a branch explicitly changes those seams or when you need release confidence on an already configured environment. Their absence should not fail the standard production-readiness lane.

## Failure Reporting Expectations

When a check fails, record:

- the command that failed
- the route or API path that regressed
- the trip id, scenario id, or proposal/policy id involved
- the provider state, missing env var, or sibling repo path if an optional live integration is skipped or blocked
- whether the failure is local-only, preview-only, or both
- any missing optional env var that changed the expected result

That minimum context is enough to reproduce the regression without re-deriving the user journey from scratch.
