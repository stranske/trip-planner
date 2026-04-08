# Scenario Ranking Workspace Contract

This contract defines the handoff between runtime ranking inputs, scenario-generation outputs, and later comparison UX.

## Ranking Inputs

- `InventoryBundle` records remain the normalized runtime input surface.
- Leisure ranking consumes resolved leisure profile evidence plus derived `ItineraryObjectives`.
- Business ranking consumes `BusinessTravelProfile`, derived `BusinessPlanningObjectives`, and policy constraint context.
- Feasibility outputs stay attached to bundle ids so ranking and scenario assembly reuse the same travel-friction and blocking signals.

## Scenario Outputs

- Ranking produces ordered bundle recommendations.
- Workspace scenario generation converts those ranked bundle results into `ScenarioSearchResult.scenarios`.
- Each scenario must keep:
  - the source `bundle_id`
  - explicit route sequence
  - score and explanation records
  - unresolved tradeoffs carried forward from feasibility or policy posture
- Workspace planner outputs summarize the ranked set and expose per-rank scenario cards for the side-panel UI.

## Comparison Boundary

- Ranking chooses explainable candidate ordering.
- Scenario generation turns ranked bundles into reusable scenario records.
- Later comparison UX should consume those scenario records directly instead of recomputing ranking scores or collapsing the route explanation into a single opaque recommendation.
