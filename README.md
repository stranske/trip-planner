# trip-planner

`trip-planner` is moving from a static itinerary demo toward a broader travel-planning application with two modes:

- recreational trip planning for serious independent leisure travelers
- business trip planning that optimizes against company travel constraints and exports policy-ready plans

## Key Docs

- [Implementation plan](docs/implementation-plan.md)
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

Backend:

```bash
uvicorn trip_planner.app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Validation:

```bash
pytest tests/app/test_health.py
cd frontend && npm test
```
