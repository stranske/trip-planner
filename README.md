# trip-planner

`trip-planner` is moving from a static itinerary demo toward a broader travel-planning application with two modes:

- recreational trip planning for serious independent leisure travelers
- business trip planning that optimizes against company travel constraints and exports policy-ready plans

The runtime baseline now treats the saved trip record as the durable planning container. New scenario, budget, workspace, and policy work should attach to a persisted trip instead of inventing a parallel root object.
Saved scenarios and trip-level planning history now persist underneath that same trip container, so later comparison and workspace slices should consume those records instead of reintroducing fixture-only storage.

## Key Docs

- [Implementation plan](docs/implementation-plan.md)
- [Application foundation epic plan](docs/application-foundation-epic.md)
- [Accounts, persistence, and workflow state epic plan](docs/accounts-persistence-workflow-state-epic.md)
- [Planner workspace vertical slice epic plan](docs/planner-workspace-vertical-slice-epic.md)
- [Live runtime completion epic plan](docs/live-runtime-completion-epic.md)
- [Live Travel-Plan-Permission execution and reoptimization epic plan](docs/live-tpp-execution-reoptimization-epic.md)
- [LangChain planner runtime epic plan](docs/langchain-planner-runtime-epic.md)
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

Install the backend and frontend dependencies once:

```bash
python -m pip install -e ".[dev]"
npm --prefix frontend install
```

Repo dependency layout:

- Python tooling installs into the active virtualenv from the repo root.
- Application JavaScript dependencies install under `frontend/node_modules`.
- Workflow automation keeps its own vendored helpers under `.github/scripts/node_modules`.
- Do not create or commit a repo-root `node_modules/`; CI and local runtime commands do not depend on it.

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

The verification path covers:

- backend runtime tests for the live FastAPI routes
- frontend unit/build checks
- a smoke test that runs the frontend client against a live backend process
