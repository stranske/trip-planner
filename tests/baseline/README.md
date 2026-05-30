# Trip-planner app behavior baseline kit

Scenario-driven wiring/sensibility/regression tests built on the shared
**`baseline_kit`** package. Only the app-specific pieces live here.

## Requires

`baseline_kit` (the shared core) must be importable. It lives in
`stranske/Workflows` under `packages/app-baseline-kit`:

```bash
pip install "app-baseline-kit @ git+https://github.com/stranske/Workflows.git#subdirectory=packages/app-baseline-kit"
```

## Target surface

The **deterministic compute** — transport-option evaluation
(`trip_planner.options.TransportOption`), which takes a fixture and produces
scoreable scalars with no DB/network/LLM. (Preference resolution and planner
routing are the natural next surfaces.)

## Layout

```
adapter.py                # fixture -> flat metrics dict  (the only app-specific glue)
catalog.yaml              # fixtures + cross-option orderings + priority metrics
invariants.py             # economic/structural bounds -> baseline_kit.InvariantResult
test_golden.py            # golden master each fixture's metrics
test_directional.py       # cross-option orderings (cheaper, fewer transfers, better fit)
test_invariants.py        # invariants per fixture
test_coverage_manifest.py # metric-dimension coverage -> docs/reports/baseline-coverage.md
```

## Running

```bash
pytest tests/baseline/                       # full suite
pytest tests/baseline/test_golden.py --force-regen   # re-bless after intended change
```

## Calibration notes (first run)

Three invariants were initially too strict for this domain and were fixed (not
trip-planner bugs): optional cost fields (`base_fare`, `taxes_and_fees`) can be
absent (`NaN` = allowed), and structural integrity is **idempotent**
serialization, not byte-equality with the raw fixture.

## Next surfaces

- Preference resolution (`resolve_dimension_evidence`) — directional confidence/
  salience checks.
- Planner routing (`route_planner_turn`) — message → task/effort classification.
