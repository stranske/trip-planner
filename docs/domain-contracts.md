# Core Domain Contracts

This document defines the first real domain contracts needed before the implementation backlog expands further.

The immediate goal is not to finalize every field. The goal is to make sure the repo has stable contract boundaries for planning work.

## Design Principle

The project should distinguish clearly between:

- the `trip`
- the `preference profiles`
- the `option sets`
- the `itinerary objectives`
- the `policy-facing export contract`

If those collapse together, later issues will blur planning, ranking, policy compliance, and UI state.

## 1. Trip

`Trip` is the main planning container.

```json
{
  "trip_id": "trip_123",
  "user_id": "user_456",
  "mode": "leisure|business",
  "status": "draft|active|booked|in_trip|completed|archived",
  "trip_frame": {},
  "traveler_party": {},
  "constraints": {},
  "profile_refs": {
    "leisure": null,
    "business": null
  },
  "objective_ref": null,
  "option_set_refs": [],
  "itinerary_ref": null,
  "budget_ref": null,
  "policy_ref": null
}
```

`Trip` should not inline every resolved planning artifact permanently. It should reference them.

## 2. Trip Mode Split

`Trip.mode` should always be explicit.

- `leisure`
- `business`

The planner can share inventory, itinerary, mapping, and budget infrastructure across modes, but it should not assume that leisure and business preferences are the same kind of object.

## 3. Profile Split

### Leisure

`LeisurePreferenceProfile` is the exploratory, tradeoff-heavy model already being defined in the preference docs.

It is primarily about:

- anchors
- tradeoff dimensions
- conditional preferences
- revealed preference updates
- interaction style

### Business

`BusinessTravelProfile` should be separate from the start.

It is primarily about:

- trip purpose and business justification
- policy constraints
- preferred and approved booking channels
- documentation requirements
- schedule rigidity
- comparables and exception handling

The two profiles may share some nested contract shapes, but they should not be one merged schema.

## 4. Destination

`Destination` should represent a place that can act as a trip anchor, a base, or an activity context.

```json
{
  "destination_id": "dest_123",
  "place_kind": "city|region|neighborhood|landscape|site",
  "name": "Kyoto",
  "summary": "Normalized place entity used upstream from option generation.",
  "parent_refs": [],
  "geo": {
    "latitude": 35.0116,
    "longitude": 135.7681,
    "country_code": "JP",
    "region_code": "JP-26"
  },
  "tags": [],
  "seasonal_signals": [],
  "mobility_profile": {
    "arrival_modes": [],
    "local_modes": [],
    "walkability": null,
    "transit_coverage": null,
    "car_dependency": null
  },
  "experience_signals": [],
  "adjacency_refs": [],
  "region_expansion_refs": [],
  "source_refs": [],
  "operational_notes": []
}
```

Important design point:

`Destination` is not yet an option. It is a normalized place entity that later lodging,
activity, route, and mixed option models can reference without re-normalizing geography,
hierarchy, source provenance, or expansion context.

## 5. Option Set

`OptionSet` is the planner’s unit for presenting alternatives.

It should be able to represent both:

- machine-generated candidate sets
- curated sets shown to the user to learn revealed preferences

```json
{
  "option_set_id": "optset_123",
  "trip_id": "trip_123",
  "purpose": "profile_learning|inventory_narrowing|final_selection",
  "scope": "route|lodging|transport|activity|mixed",
  "options": [],
  "explanation": {},
  "comparison_axes": [],
  "source_refs": []
}
```

`OptionSet` should be first-class because the planner is expected to learn from concrete choices, not only from direct statements.

## 6. Option

Every `OptionSet` should contain explicit `Option` records.

```json
{
  "option_id": "option_123",
  "kind": "route|lodging|flight|rail|car|activity|mixed",
  "label": "Kyoto-first slower cultural route",
  "summary": "",
  "fit_signals": {},
  "cost_summary": {},
  "quality_summary": {},
  "drawbacks": [],
  "booking_links": [],
  "source_refs": []
}
```

## 7. Itinerary Objectives

`ItineraryObjectives` sits between the preference layer and any later ranking/search layer.

```json
{
  "objective_id": "obj_123",
  "trip_id": "trip_123",
  "route_shape": "hub_and_spoke|linear|regional_cluster|mixed",
  "target_base_count": {
    "min": 3,
    "max": 5
  },
  "move_density": {},
  "recovery_expectations": {},
  "day_structure": {},
  "discovery_strategy": {},
  "budget_protection": {},
  "quality_floor_protection": {},
  "lodging_strategy": {},
  "transport_strategy": {},
  "explanations": []
}
```

This contract is important because it keeps the later ranking algorithm from swallowing the preference engine whole.

## 8. Inventory Contracts

At minimum, the first implementation should define distinct normalized contracts for:

- `LodgingOption`
- `TransportOption`
- `ActivityOption`

These contracts do not need complete fields yet, but they do need stable boundaries.

The main point is that all of them should carry:

- normalized identity
- source provenance
- quality and value signals
- cost summary
- feasibility constraints
- booking or reference links

## 9. Policy-Facing Export Contract

The bridge to `Travel-Plan-Permission` should use a stable export object, such as `TripPlanProposal`.

```json
{
  "proposal_id": "proposal_123",
  "trip_id": "trip_123",
  "mode": "business",
  "traveler_context": {},
  "selected_options": {},
  "cost_summary": {},
  "comparables": [],
  "justifications": [],
  "policy_inputs": {},
  "booking_channel_summary": {},
  "approval_notes": []
}
```

This should be rich enough for policy evaluation and approval routing without forcing the planning engine to live inside the policy repo.

## 10. Immediate Contract Priorities

The first implementation wave does not need every domain object equally.

The highest-priority contracts to lock now are:

1. `Trip`
2. `LeisurePreferenceProfile`
3. `BusinessTravelProfile`
4. `OptionSet`
5. `ItineraryObjectives`
6. `TripPlanProposal`

The rest can be refined once the option and itinerary pipelines start taking shape.
