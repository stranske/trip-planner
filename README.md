# trip-planner

`trip-planner` is moving from a static itinerary demo toward a broader travel-planning application with two modes:

- recreational trip planning for serious independent leisure travelers
- business trip planning that optimizes against company travel constraints and exports policy-ready plans

## Key Docs

- [Implementation plan](docs/implementation-plan.md)
- [Product and architecture brief](docs/product-architecture-brief.md)
- [Leisure preference contract](docs/leisure-preference-contract.md)
- [Leisure preference engine](docs/leisure-preference-engine.md)
- [Preference roadmap](docs/preference-roadmap.md)
- [Planning autonomy and revealed preference contracts](docs/contracts/planning-autonomy.md)
- [Shared planning contracts](docs/shared-planning-contracts.md)
- [Business travel profile contract](docs/business-travel-profile-contract.md)
- [Policy-facing proposal contracts](docs/contracts/trip-plan-proposal.md)
- [Source and provenance contracts](docs/contracts/source-provenance.md)
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

The old script flow is not the default design path for new work. It remains only where a narrow compatibility bridge is still useful, and older static-demo artifacts have been moved under `archive/legacy-static-demo/`.
That legacy work is still useful as seed logic for scoring and itinerary generation, but it is no longer the full intended product.

## Legacy Quick Start

```bash
pip install -r requirements.txt

python scripts/validate_request.py
python scripts/generate_itins.py
python scripts/build_html.py
```
