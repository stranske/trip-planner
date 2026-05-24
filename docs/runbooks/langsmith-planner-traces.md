# LangSmith Planner Trace Artifacts

Trip-scoped planner turns emit dashboard-safe `langsmith-fleet/v1` records for
the shared Workflows fleet dashboard contract owned by `stranske/Workflows#2150`.

## Runtime Behavior

- The planner service sets LangSmith project defaults only when
  `LANGSMITH_API_KEY` is present.
- Missing LangSmith credentials never block planner turns; records use
  `status=no_secret` and the normal deterministic fallback/model behavior
  continues.
- Local records are appended to `artifacts/langsmith/langsmith-fleet.ndjson` by
  default. Set `TRIP_PLANNER_LANGSMITH_FLEET_PATH` to redirect the file in tests
  or local debugging.
- Planner response actions persist a `langsmith_fleet` payload with the artifact
  path, local run ID, trace ID, and record count.

## Recorded Fields

Every record includes shared fields such as schema version, repo, surface,
operation, run ID, status, provider, model, and trace ID when available.

The trip-planner domain payload includes bounded metadata only:

- hashed session and trip identifiers
- planning mode, planner action, itinerary phase, and provider/fallback state
- tool-call counts, failed call counts, and mutating call counts
- inventory, budget, and itinerary-coherence status
- context-readiness status and missing context section names

Records must not contain raw traveler messages, full prompts, private trip IDs,
or full itinerary payloads.

## Validation

Focused checks:

```bash
python -m pytest tests/observability/test_langsmith_fleet.py tests/app/test_planner_routes.py -q
python -m ruff check trip_planner/observability/langsmith_fleet.py trip_planner/app/services/planner.py tests/observability/test_langsmith_fleet.py tests/app/test_planner_routes.py
```
