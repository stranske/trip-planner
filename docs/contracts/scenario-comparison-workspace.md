# Scenario Comparison Workspace Contract

Issue `#693` extends the runtime workspace payload with comparison-ready scenario data.

## Runtime Source

- `scenario_search` remains the canonical route-search output.
- `route_comparison` is the canonical derived view over that same result set.
- `runtime_scenario_comparison` is retained as a compatibility alias for existing clients.
- The comparison surface must not invent a separate scenario model or diverge from `scenario_search`.

## Comparison Surface

- `lead_scenario_id` identifies the currently recommended route.
- `comparison_axes` carry reusable comparison dimensions for UI or later APIs.
- Each comparison row keeps:
  - the original `scenario_id`
  - rank, summary, and route sequence
  - score, travel-minute, transfer, and estimated-total metrics
  - deltas versus the lead scenario
  - highlight text suitable for workspace rendering

## UI Boundary

- The trip workspace should render runtime comparison rows before falling back to saved-scenario metadata.
- Saved-scenario history remains valid for persistence and checkpoint history, but runtime comparison uses the live route-search payload.
- Later map and visualization work can reuse `route_comparison.scenarios[*].route_sequence` and metrics without recomputing ranking output on the client.
