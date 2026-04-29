# trip-planner

`trip-planner` is moving from a static itinerary demo toward a broader travel-planning application with two modes:

- recreational trip planning for serious independent leisure travelers
- business trip planning that optimizes against company travel constraints and exports policy-ready plans

The runtime baseline now treats the saved trip record as the durable planning container. New scenario, budget, workspace, and policy work should attach to a persisted trip instead of inventing a parallel root object.
Saved scenarios and trip-level planning history now persist underneath that same trip container, so later comparison and workspace slices should consume those records instead of reintroducing fixture-only storage.
The shipped full-stack MVP now includes authenticated trip creation, persisted trip and scenario routes, the workspace shell, planner session APIs, stored policy/proposal state, and a provider-backed map adapter seam with bounded fallback rendering. Live external policy transport remains a follow-on integration, so docs and checks in this repo should describe that gap explicitly instead of implying it already ships.

## Current MVP Surfaces

The current runtime already ships these inspectable application surfaces:

- authenticated sign-up, sign-in, sign-out, and session restore
- persisted trip creation plus saved trip, scenario-history, and workspace routes
- planner session APIs and workspace state hydration for the frontend app shell
- stored proposal and policy posture state that later `Travel-Plan-Permission` work can consume

The current runtime ships a Google Maps JavaScript adapter boundary for the workspace map surface, with CI-safe mocked rendering and fallback states for missing config, provider load errors, and sparse route data. Remote `Travel-Plan-Permission` execution remains an explicit follow-on integration, so local runtime checks and product docs should continue to call that out as deferred.

## Persisted Workspace Runtime Behavior

Workspace reads for saved trips are assembled from the persisted trip runtime context. For arbitrary leisure and business trips, inventory, scenario comparison, budget, source metadata, and provenance should be derived from the saved trip record and database-backed runtime state instead of seeded demo trips or fixture adapter identities.

When a persisted trip is missing a destination, dates, or both, the workspace route still returns a coherent partial response. The inventory summary reports zero runtime bundles and includes `runtime_state.issues` entries with AdapterIssue-style reason codes such as `missing_destination` and `missing_dates`, so callers can distinguish incomplete trip inputs from fixture fallback or hard runtime failure.

## Key Docs

- [Implementation plan](docs/implementation-plan.md)
- [Application foundation epic plan](docs/application-foundation-epic.md)
- [Accounts, persistence, and workflow state epic plan](docs/accounts-persistence-workflow-state-epic.md)
- [Planner workspace vertical slice epic plan](docs/planner-workspace-vertical-slice-epic.md)
- [Live runtime completion epic plan](docs/live-runtime-completion-epic.md)
- [Live Travel-Plan-Permission execution and reoptimization epic plan](docs/live-tpp-execution-reoptimization-epic.md)
- [LangChain planner runtime epic plan](docs/langchain-planner-runtime-epic.md)
- [Google Maps and platform hardening epic plan](docs/google-maps-platform-hardening-epic.md)
- [Runtime planning services epic plan](docs/runtime-planning-services-epic.md)
- [Budget and business policy execution epic plan](docs/budget-business-policy-execution-epic.md)
- [Maps, timeline, and comparison application surfaces epic plan](docs/maps-timeline-comparison-epic.md)
- [Leisure preference epic plan](docs/leisure-preference-epic.md)
- [Shared planning and business foundation epic plan](docs/shared-business-foundation-epic.md)
- [Source ingestion epic plan](docs/source-ingestion-epic.md)
- [Product and architecture brief](docs/product-architecture-brief.md)
- [Leisure preference contract](docs/leisure-preference-contract.md)
- [Leisure preference engine](docs/leisure-preference-engine.md)
- [Leisure preference schema draft](docs/leisure-preference-schema.md)
- [Preference learning model](docs/preference-learning-model.md)
- [Preference roadmap](docs/preference-roadmap.md)
- [Frontend route visualization](docs/frontend-route-visualization.md)
- [Local testing plan](docs/local-testing-plan.md)
- [Planning autonomy and revealed preference contracts](docs/contracts/planning-autonomy.md)
- [Shared planning contracts](docs/shared-planning-contracts.md)
- [Normalized inventory contracts epic](docs/normalized-inventory-contracts-epic.md)
- [Business travel profile contract](docs/business-travel-profile-contract.md)
- [Policy-facing proposal contracts](docs/contracts/trip-plan-proposal.md)
- [Source and provenance contracts](docs/contracts/source-provenance.md)
- [Core domain contracts](docs/domain-contracts.md)
- [Business travel profile](docs/business-travel-profile.md)
- [Planner UI integration](docs/planner-ui-integration.md)
- [Frontend app shell foundation](docs/frontend-app-shell-foundation.md)
- [Frontend entry flows](docs/frontend-entry-flows.md)
- [Frontend trip workspace](docs/frontend-trip-workspace.md)
- [Frontend route loading foundation](docs/frontend-route-loading-foundation.md)
- [Source and quality model](docs/source-quality-model.md)
- [Source channel strategy](docs/source-channel-strategy.md)
- [Legacy itinerary methodology](docs/methodology.md)
- [CI system guide](docs/CI_SYSTEM_GUIDE.md)
- [Design coverage map](docs/design-coverage-map.md)
- [Legacy static demo archive](archive/legacy-static-demo/README.md)

## Current Repo Reality

The codebase still mostly reflects the older script-driven bundle generator:

- `scripts/validate_request.py`
- `scripts/generate_itins.py`
- `scripts/build_html.py`

The first canonical application packages now start in:

- `trip_planner/preferences/`
- `trip_planner/contracts/`
- `trip_planner/business/`
- `trip_planner/sources/`
- `trip_planner/app/`
- `frontend/`

The old script flow is not the default design path for new work. It remains only where a narrow compatibility bridge is still useful, and older static-demo artifacts have been moved under `archive/legacy-static-demo/`.
That legacy work is still useful as seed logic for scoring and itinerary generation, but it is no longer the full intended product.

## Legacy Quick Start

```bash
pip install -r requirements.txt

python scripts/validate_request.py
python scripts/generate_itins.py
python scripts/build_html.py
```

## App Runtime Quick Start

Install all backend and frontend dependencies once from a clean checkout:

```bash
make install
```

This creates `.venv`, installs the Python dev extras into it, and installs `frontend/node_modules`. No manual venv activation is needed before running `make runtime-check` afterward — the script detects `.venv` automatically.

If you prefer to manage the virtualenv yourself:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
npm --prefix frontend ci
```

`make runtime-check` and `make runtime-smoke` require those installs to have completed. If either the backend dev extras or frontend dependencies are missing, the check script exits early with instructions pointing back to `make install`.

Repo dependency layout:

- Python tooling installs into the active `.venv` from the repo root.
- Application JavaScript dependencies install under `frontend/node_modules`.
- Do not create or commit `node_modules/` anywhere in the repo; use `npm ci` to install from the lock file.
- `TRIP_PLANNER_DATABASE_URL` is optional for local work; if unset, the backend falls back to the default SQLite path under the repo.

Run the full stack together from the repo root:

```bash
make runtime-dev
```

That starts the FastAPI runtime on `http://127.0.0.1:8000` and the Vite app on
`http://127.0.0.1:5173` with the frontend proxying `/api` requests to the backend.

Validate the runtime surfaces from the repo root:

```bash
make runtime-check
```

For the production-focused journey matrix, run:

```bash
make runtime-production-check
```

For a full-product verification lane that first runs the backend/frontend runtime smoke layer, then creates fresh leisure and business trips, verifies runtime inventory/scenario/planner/proposal identifiers, and reports optional live map/TPP prerequisites explicitly, run:

```bash
make full-product-check
```

`make runtime-full-product-check` is available as an equivalent runtime-prefixed alias.
Use `python scripts/check_full_product_verification.py --skip-frontend-smoke` only when you need to isolate the product-journey assertions from frontend/runtime smoke prerequisites.

To smoke-check a deploy preview as well, provide the preview origin:

```bash
make runtime-preview-smoke TRIP_PLANNER_PREVIEW_URL=https://deploy-preview-123--example.netlify.app
```

The verification path covers:

- backend runtime tests for the live FastAPI routes
- frontend unit/build checks
- a smoke test that runs the frontend client against a live backend process
- a separate full-product check for fresh leisure and business product journeys

These checks validate the local full-stack MVP that already exists in this repo. They exercise the map adapter and fallback seam with mocked provider state. They do not prove live Google Maps rendering or remote Travel-Plan-Permission transport.
The production-focused testing plan in [docs/local-testing-plan.md](docs/local-testing-plan.md) adds the critical auth, trip, workspace, policy, proposal, and preview-verification journeys on top of that baseline.

## Python Unit Tests

After installing the backend dev extras (`python -m pip install -e ".[dev]"`), run the unit test suite from the repo root:

```bash
make test
```

That runs `pytest` against the `tests/` directory. `testpaths` is set in `pyproject.toml`, so `pytest` alone is equivalent. The full CI test suite also adds type checking and coverage reporting; see `.github/workflows/ci.yml` for those details.

## Optional Live Integration Env Vars

The local MVP does not require live external integrations. `make runtime-check` should pass without the env vars below.

Use these env vars only when you are intentionally exercising an integration seam that already exists in code:

- `VITE_API_BASE_URL`: overrides the frontend API base URL when you are not using the local Vite proxy.
- `VITE_GOOGLE_MAPS_BROWSER_API_KEY`: primary key for enabling the Google Maps JavaScript adapter path in the workspace.
- `VITE_GOOGLE_MAPS_EMBED_API_KEY`: legacy key name still accepted as a compatibility fallback when `VITE_GOOGLE_MAPS_BROWSER_API_KEY` is not set.
- `VITE_GOOGLE_MAPS_PROVIDER_STATE`: optional local/test override for the map adapter load state (`ready`, `loading`, or `error`).
- `TPP_BASE_URL`, `TPP_ACCESS_TOKEN`, `TPP_OIDC_PROVIDER`: enable the live `Travel-Plan-Permission` transport client. If they are unset, the repo should continue to present stored-policy and passive/local TPP seams rather than implying a real remote policy round-trip.
- `TPP_REPO_PATH`: optional sibling checkout path used by `make full-product-check` when it needs to start a local Travel-Plan-Permission service instead of using `TPP_BASE_URL`.

That distinction matters for docs and verification messaging:

- missing local prerequisites such as `.venv` or `frontend/node_modules` are setup failures
- missing live integration env vars are not setup failures for the shipped MVP
- missing Google Maps configuration or a provider load error should preserve route context through the fallback map instead of blanking the workspace
- fallback map behavior is intentionally bounded: route-context overlays, markers, route summaries, and detail panels stay visible, but live provider-only interactions do not
- live remote `Travel-Plan-Permission` execution remains deferred unless you deliberately configure that seam
