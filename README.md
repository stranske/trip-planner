# trip-planner

`trip-planner` is transitioning from a static itinerary-scoring demo into a broader travel-planning application with two product modes:

- recreational trip planning for individuals and families
- business trip planning that optimizes against company travel constraints and exports policy-ready trip plans

## Current Direction

The target product should handle:

- trip design from traveler preferences
- lodging, airfare, rail, rental-car, and local transport option planning
- day-by-day activity planning with maps and route context
- budget and tradeoff analysis
- interactive LLM-assisted trip refinement
- business-travel planning that can hand structured output to `Travel-Plan-Permission`

## Key Docs

- [Implementation plan](docs/implementation-plan.md)
- [Product and architecture brief](docs/product-architecture-brief.md)
- [Leisure preference contract](docs/leisure-preference-contract.md)
- [Shared planning contracts](docs/shared-planning-contracts.md)
- [Business travel profile contract](docs/business-travel-profile-contract.md)
- [Policy-facing proposal contracts](docs/contracts/trip-plan-proposal.md)
- [Source and provenance contracts](docs/contracts/source-provenance.md)
- [Source channel strategy](docs/source-channel-strategy.md)
- [Legacy itinerary methodology](docs/methodology.md)
- [CI system guide](docs/CI_SYSTEM_GUIDE.md)
- [Legacy static demo archive](archive/legacy-static-demo/README.md)

## Current Repo State

The implementation in this repository is still mostly a script-based generator for static itinerary bundles:

- `scripts/validate_request.py`
- `scripts/generate_itins.py`
- `scripts/build_html.py`

The first canonical application packages now start in:

- `trip_planner/preferences/`
- `trip_planner/contracts/`
- `trip_planner/business/`
- `trip_planner/sources/`

The old script flow is not the default design path for new work. It remains only where a narrow compatibility bridge is still useful, and older static-demo artifacts have been moved under `archive/legacy-static-demo/`.

## Legacy Quick Start

```bash
pip install -r requirements.txt

python scripts/validate_request.py
python scripts/generate_itins.py
python scripts/build_html.py
```
