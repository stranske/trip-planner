# Leisure Preference Contract

The canonical leisure preference contract now lives in `trip_planner/preferences/`.

This package is the source of truth for the first implementation pass of the leisure profile model.

## Canonical Modules

- `trip_planner/preferences/models.py`
  - canonical dataclass contracts for `LeisurePreferenceProfile` and its main nested records
- `trip_planner/preferences/schema.py`
  - first-tier dimension keys, hybrid-factor keys, polarity map, and other schema constants
- `trip_planner/preferences/evidence.py`
  - evidence records for direct statements, tradeoff choices, scenario reactions, concrete option choices, and revisions
- `trip_planner/preferences/evidence_catalog.py`
  - allowed evidence pathways and strength levels for tradeoffs, hybrid factors, and anchors
- `trip_planner/preferences/legacy_request_adapter.py`
  - narrow compatibility adapter from the repo's older `request.json` shape into the canonical contract
- `tests/fixtures/preferences/leisure_traveler_corpus.json`
  - regression corpus of leisure archetypes and tension cases used to validate future resolver work
- `tests/preferences/fixture_corpus.py`
  - reusable loader that instantiates fixture profiles and evidence records from the corpus

## What This Replaces

Historically, the repo's preference surface lived mostly in ad hoc request fields:

- `must_see`
- `nature_ratio`
- `complexity_tolerance`
- `cost_sensitivity`
- `route_passions`

Those fields are still supported as legacy inputs, but only as a compatibility bridge. They should not be treated as the long-term planning contract.

## Current Guidance

- new leisure planning logic should target `LeisurePreferenceProfile`
- legacy script flows may continue to read `request.json`, but any translation into newer planning systems should go through `legacy_request_adapter.py`
- future evidence, ranking, and orchestration work should build on these canonical contracts instead of inventing new preference shapes
- evidence about anchors should be modeled separately from normal tradeoff evidence, because anchors express trip-defining commitments rather than mere directional preference
- when a legacy artifact is useful only as history, it should live under `archive/legacy-static-demo/` rather than remain in the active docs path
