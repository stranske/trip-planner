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

Run `make install` once from a clean checkout to create `.venv` and install all deps, then run these commands from the repo root:

```bash
.venv/bin/black --check .
```

Black's local config is centralized in `pyproject.toml` with `line-length = 100`, matching the remote automation. Older local commands that passed `--line-length 100` explicitly are equivalent, but the flag should no longer be needed from a correctly synced checkout and refreshed `.venv`.

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

When live TPP auto-start is enabled with `TPP_REPO_PATH`, the verifier runs the sibling service with that repo's own Python environment. Resolution order is `<TPP_REPO_PATH>/.venv/bin/python`, then `uv run --directory <TPP_REPO_PATH> python` when `uv.lock` is present and `uv` is installed, then a fail-fast setup error. If startup does not reach `/readyz`, the verifier includes the resolved command plus the last 50 lines of captured TPP stdout and stderr so missing dependency errors are visible in CI logs. Setting `TPP_BASE_URL` skips auto-start and trusts the externally managed service as before; the regression suite asserts that this path never resolves or launches a local TPP interpreter.

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

## Live TPP Verification Setup

The `live-tpp` check inside `make full-product-check` has three modes selected via `--live-tpp`:

- `auto` (default): runs when configured, otherwise reports `SKIPPED` with a remediation hint.
- `off`: never runs; reports `SKIPPED` regardless of configuration.
- `required`: runs and fails the verifier when configuration is missing or invalid.

The verifier supports two configured transport modes. Pick exactly one per run; `TPP_BASE_URL` takes precedence and the sibling-checkout path is never resolved when it is set.

### Sibling-checkout mode (`TPP_REPO_PATH`)

Use this when you have a local `Travel-Plan-Permission` checkout and want the verifier to start and stop the HTTP service for you.

```bash
export TPP_REPO_PATH=../Travel-Plan-Permission        # or any absolute checkout path
export TPP_ACCESS_TOKEN=local-dev-token
export TPP_OIDC_PROVIDER=google
make full-product-check
```

The verifier resolves the interpreter for the sibling service in this order:

1. `<TPP_REPO_PATH>/.venv/bin/python` if that file exists
2. `uv run --directory <TPP_REPO_PATH> python` when `uv.lock` is present and `uv` is installed
3. fail-fast with an actionable setup error otherwise

It binds the service to `http://127.0.0.1:<free-port>` (default `8765` when free), waits up to twenty seconds for `/readyz`, then runs the live policy/proposal/evaluation round-trip against that service. The service is terminated automatically on exit.

When the sibling service does not become ready, the verifier reports `live-tpp` `FAIL` and includes:

- the resolved interpreter command and the full launch command
- the working directory and current `Popen` return code
- the last fifty lines of captured TPP `stdout` and `stderr`

Use that context to fix the sibling environment (missing dependencies, wrong Python version, port collisions) before re-running.

### External-service mode (`TPP_BASE_URL`)

Use this when a `Travel-Plan-Permission` service is already running (for example in CI or a remote sandbox).

```bash
export TPP_BASE_URL=https://tpp.preview.example.com
export TPP_ACCESS_TOKEN=live-token
export TPP_OIDC_PROVIDER=google
make full-product-check
```

In this mode the verifier never resolves a sibling interpreter, never starts a subprocess, and trusts the externally managed service. A regression test (`tests/app/test_full_product_verification.py::test_started_tpp_service_with_base_url_does_not_attempt_sibling_resolution`) keeps that contract honest.

### Interpreting the `live-tpp` result

| Status | Meaning | Typical remediation |
|--------|---------|---------------------|
| `PASS` | live round-trip completed: policy sync, proposal submission, status poll, evaluation ingest | none |
| `READY` | configuration is valid; live round-trip will run | none (transitional state surfaced by `tpp_prerequisite_status`) |
| `SKIPPED` (`mode: off`) | `--live-tpp off` was requested | rerun with `--live-tpp auto` (or `required`) after exporting the env vars below |
| `SKIPPED` (`missing_env: TPP_BASE_URL or TPP_REPO_PATH`) | no transport target configured | set either `TPP_BASE_URL` or `TPP_REPO_PATH` |
| `BLOCKED` (`missing_env`) | transport target set but `TPP_ACCESS_TOKEN` / `TPP_OIDC_PROVIDER` missing | export the missing env vars for the configured transport target |
| `BLOCKED` (`invalid_path_detail.kind = missing`) | `TPP_REPO_PATH` does not exist | point it at a real sibling checkout or unset it and use `TPP_BASE_URL` |
| `BLOCKED` (`invalid_path_detail.kind = not-a-directory`) | `TPP_REPO_PATH` exists but is a file | unset it or set it to the checkout directory |
| `FAIL` | sibling service failed to reach `/readyz`, or the live round-trip surfaced a non-success status | inspect the embedded `command`, `stdout_tail`, and `stderr_tail` in the failure details |

Every non-`PASS` `live-tpp` result with actionable next steps includes a `remediation` field in its details payload, surfaced on stderr alongside the JSON detail blob.

## Failure Reporting Expectations

When a check fails, record:

- the command that failed
- the route or API path that regressed
- the trip id, scenario id, or proposal/policy id involved
- the provider state, missing env var, or sibling repo path if an optional live integration is skipped or blocked
- whether the failure is local-only, preview-only, or both
- any missing optional env var that changed the expected result

That minimum context is enough to reproduce the regression without re-deriving the user journey from scratch.
