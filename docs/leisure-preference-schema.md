# Leisure Preference Schema Draft

This document converts the current taxonomy into an initial implementation-shaped schema for a `LeisurePreferenceProfile`.

The goal is not to freeze the final data model yet. The goal is to get the taxonomy into a form that can drive:

- elicitation design
- persistence
- interaction rules
- later itinerary-objective mapping

## Design Notes

This schema is intentionally built from the signals already present in the repo:

- `must_see`
- `nature_ratio`
- `complexity_tolerance`
- `cost_sensitivity`
- `route_passions`

Those old fields should map into richer structures rather than disappear.

## Schema Outline

```json
{
  "schema_version": "0.1.0",
  "profile_kind": "leisure",
  "trip_frame": {},
  "hard_constraints": {},
  "anchors": {},
  "budget_model": {},
  "tradeoff_dimensions": {},
  "hybrid_factors": {},
  "conditional_overrides": [],
  "interaction_rules": [],
  "tension_flags": [],
  "evidence_summary": {}
}
```

## 1. Trip Frame

```json
{
  "duration_days": 35,
  "traveler_party": "solo|pair|family|friends",
  "season_window": ["September", "October"],
  "trip_stage": "first_visit|repeat_visit|mixed",
  "regions_in_scope": [],
  "special_themes": []
}
```

This gives context before any tradeoff is interpreted.

## 2. Hard Constraints

```json
{
  "date_window": {
    "start": "2025-09-01",
    "end": "2025-10-15"
  },
  "duration_bounds": {
    "min_days": 28,
    "max_days": 42
  },
  "budget_ceiling": null,
  "must_include_places": [],
  "must_protect_experiences": [],
  "mobility_constraints": [],
  "lodging_constraints": [],
  "visa_border_constraints": []
}
```

## 3. Anchors

```json
{
  "place_anchors": [],
  "experience_anchors": [],
  "mode_anchors": [],
  "rhythm_anchors": [],
  "calendar_anchors": [],
  "quality_floor_anchors": [],
  "regional_adjacency_preferences": []
}
```

### Anchor Record

Each anchor should use a common structure:

```json
{
  "type": "place|experience|mode|rhythm|calendar|quality_floor|regional_adjacency",
  "label": "Jungfrau Region",
  "strength": 0.9,
  "flexibility": 0.2,
  "notes": "Can be replaced only by a clearly better alpine base"
}
```

## 4. Budget Model

The schema needs both overall budget sensitivity and category behavior.

```json
{
  "total_budget_sensitivity": 0.6,
  "spending_priorities": {
    "lodging_location": 0.8,
    "lodging_quality": 0.4,
    "food_quality": 0.7,
    "scenic_transit": 0.9,
    "activity_access": 0.6,
    "flexibility": 0.5
  },
  "quality_floors": {
    "lodging": null,
    "food": null,
    "transport": null
  },
  "splurge_policy": {
    "allowed": true,
    "style": "few_peak_experiences|distributed_quality|rarely_splurge"
  }
}
```

## 5. Tradeoff Dimensions

Each first-tier dimension should use a shared structure.

### Dimension Record

```json
{
  "value": 0.35,
  "confidence": 0.8,
  "salience": 0.9,
  "stability": 0.7,
  "trip_stage_sensitivity": {
    "initial_design": 0.9,
    "inventory_selection": 0.7,
    "daily_activity_design": 0.5,
    "in_trip_adjustment": 0.4
  },
  "scope": "global|segment_specific|conditional",
  "notes": ""
}
```

Interpretation:

- `value` runs from `-1.0` to `1.0`
- negative means left pole
- positive means right pole
- `salience` captures importance, separate from direction

Use the metadata like this:

- `value`: where the traveler sits between the two poles
- `confidence`: how well supported that inferred value is by evidence
- `salience`: how consequential this dimension is when tradeoffs must be made
- `stability`: how likely the preference is to remain consistent across destinations, segments, and later reflection
- `trip_stage_sensitivity`: how strongly the dimension matters at different planning stages

Examples:

- a traveler may show high `salience` but moderate `stability` on `food` if food matters a lot, but only in certain cities
- `structure_vs_elasticity` may have high `trip_stage_sensitivity.initial_design` and lower `trip_stage_sensitivity.in_trip_adjustment` if the traveler likes early scaffolding but loosens up once in place
- `scenic_transit_vs_destination_time` may be low-salience for most of the trip but highly salient during route selection

`trip_stage_sensitivity` should complement, not replace, `salience` and `stability`:

- `salience` answers "how much does this matter when a decision must be made?"
- `stability` answers "how persistently true is this preference?"
- `trip_stage_sensitivity` answers "when in the planning lifecycle does this preference matter most?"

### Dimension Evidence Record

Each dimension inference can be traced to one or more normalized evidence records. The implementation contract is `DimensionEvidenceRecord` in `trip_planner.preferences.evidence`.

```json
{
  "dimension": "movement_vs_friction",
  "signal_type": "explicit_answer|revealed_behavior|default_assumption",
  "value": -0.74,
  "source": "user_message|structured_input|option_menu|scenario_prompt|planner_inference_review|trip_revision|imported_trip_notes",
  "confidence": 0.86,
  "observed_at": "2026-04-24T10:30:00Z",
  "provenance": {
    "source_id": "choice-775",
    "channel": "option-comparison",
    "captured_by": "planner-turn-3"
  },
  "evidence_type": "direct_statement|hard_constraint_declaration|anchor_declaration|forced_tradeoff_choice|scenario_reaction|option_selection|option_rejection|trip_revision"
}
```

Confidence starts from the signal family, then is adjusted by dimension context:

- `explicit_answer`: direct user statements and structured answers, useful for declared intent.
- `revealed_behavior`: option choices, rejections, scenario reactions, and trip revisions; this is the strongest signal when behavior conflicts with stated intent.
- `default_assumption`: planner inference or imported context; this is low confidence and should become stale quickly unless confirmed.

Every first-tier dimension has a confidence-guidance entry in `DIMENSION_CONFIDENCE_GUIDANCE`. Examples:

- `movement_vs_friction`: prefer revealed routing or relocation choices over stated appetite when they conflict.
- `structure_vs_elasticity`: structured-input preferences start strong and decay when later trip revisions loosen the plan.
- `social_energy_vs_solitude`: lodging and neighborhood selections can confirm stated social-energy preference.

`DIMENSION_EVIDENCE_SOURCE_GUIDANCE` enumerates the primary source channels and stale/conflict rule for each first-tier dimension:

| Dimension | Primary source channels | Confidence and freshness rule |
|---|---|---|
| `movement_vs_friction` | `option_menu`, `scenario_prompt`, `trip_revision` | Prefer recent relocation, routing, and packing-friction choices over generic movement appetite statements; older routing choices become stale after later base-cadence revisions. |
| `recovery_vs_intensity` | `user_message`, `structured_input`, `trip_revision` | Raise confidence when fatigue notes, rest-day edits, and rejected packed plans agree; early stamina assumptions become stale after later fatigue or recovery edits. |
| `nature_vs_culture` | `user_message`, `option_menu`, `imported_trip_notes` | Treat direct destination interests as strong, but require repeated behavior before overriding stated nature or culture priorities; prior-trip notes become stale after conflicting current stops. |
| `structure_vs_elasticity` | `structured_input`, `trip_revision`, `scenario_prompt` | Structured-input answers start strong and decay when later revisions loosen or tighten the itinerary; initial planning-form answers become stale after later in-trip revision behavior. |
| `breadth_vs_depth` | `option_menu`, `trip_revision`, `user_message` | Chosen stay lengths and rejected fast routes outrank abstract statements; early coverage goals become stale after actual stay changes. |
| `self_reliance_vs_convenience` | `option_menu`, `structured_input`, `scenario_prompt` | Transfer, guide, booking-support, and self-navigation choices are highest confidence; assumptions become stale after conflicting support-seeking or self-service behavior. |
| `historic_vs_contemporary` | `option_menu`, `imported_trip_notes`, `user_message` | Keep confidence moderate until attraction choices repeatedly favor one pole across multiple cities; prior-trip interests become stale when current attraction choices diverge. |
| `scenic_transit_vs_destination_time` | `option_menu`, `scenario_prompt`, `trip_revision` | Revealed transport choices outrank generic travel-style answers; the signal becomes stale after later revisions trade scenery for time, or vice versa. |
| `route_coherence_vs_eclectic_contrast` | `scenario_prompt`, `option_menu`, `structured_input` | Increase confidence when scenario reactions and selected route bundles agree on route shape; initial route answers become stale after bundle selections introduce a new pattern. |
| `social_energy_vs_solitude` | `option_menu`, `user_message`, `trip_revision` | Lodging, neighborhood, and crowd-exposure choices confirm stated social energy; declarations become stale after conflicting lodging or neighborhood choices. |
| `iconic_vs_discovery` | `user_message`, `option_menu`, `imported_trip_notes` | Must-see declarations are strong explicit evidence, while off-list substitutions are strong revealed evidence; imported must-see lists become stale after the traveler drops or replaces the anchor. |

Fixture coverage lives in `tests/fixtures/preferences/evidence_records.json` and validates explicit, revealed, default, stale, and conflicting evidence cases.

### First-Tier Dimension Keys

```json
{
  "movement_vs_friction": {},
  "recovery_vs_intensity": {},
  "nature_vs_culture": {},
  "structure_vs_elasticity": {},
  "breadth_vs_depth": {},
  "self_reliance_vs_convenience": {},
  "historic_vs_contemporary": {},
  "scenic_transit_vs_destination_time": {},
  "route_coherence_vs_eclectic_contrast": {},
  "social_energy_vs_solitude": {},
  "iconic_vs_discovery": {}
}
```

### Dimension Polarity Map

The first pass should keep one consistent convention:

- `-1.0` means strong preference for the left pole
- `0.0` means balanced, mixed, or unresolved
- `1.0` means strong preference for the right pole

| Dimension Key | -1.0 | 1.0 |
|---|---|---|
| `movement_vs_friction` | movement appetite | friction sensitivity |
| `recovery_vs_intensity` | sustainable intensity | recovery need |
| `nature_vs_culture` | nature | culture |
| `structure_vs_elasticity` | structured days | elastic days |
| `breadth_vs_depth` | breadth | depth |
| `self_reliance_vs_convenience` | logistical self-reliance | convenience support |
| `historic_vs_contemporary` | historic depth | contemporary life |
| `scenic_transit_vs_destination_time` | scenic transit | destination time |
| `route_coherence_vs_eclectic_contrast` | route coherence | eclectic contrast |
| `social_energy_vs_solitude` | social energy | solitude |
| `iconic_vs_discovery` | iconic certainty | curious discovery |

This polarity map matters because interaction rules should be written against stable directional semantics rather than ad hoc labels.

## 6. Hybrid Factors

Some factors can be anchors, tradeoff dimensions, or both.

```json
{
  "food": {},
  "rest": {},
  "music": {},
  "route_modes": {}
}
```

### Hybrid Factor Record

```json
{
  "mode": "anchor|tradeoff|both",
  "salience": 0.7,
  "anchor_strength": 0.2,
  "tradeoff_role": "cost|rhythm|atmosphere|route_design|none",
  "notes": ""
}
```

### Route Modes Hybrid Record

```json
{
  "mode": "both",
  "salience": 0.8,
  "preferences": {
    "rail": 0.9,
    "boat": 0.4,
    "road": 0.1
  },
  "anchor_strength": 0.6,
  "tradeoff_role": "route_design"
}
```

This is the richer successor to the repo’s current `route_passions`.

## 7. Conditional Overrides

Some preferences are real but only under specific conditions.

Examples:

- scenic rail matters strongly in alpine regions, but not in dense business cities
- food quality becomes near-anchor-level in Italy or Japan, but is secondary elsewhere
- elastic wandering is preferred in historic neighborhoods, but not on airport-transfer days

These should not be forced into one global dimension value.

### Conditional Override Record

```json
{
  "id": "food_priority_in_primary_food_regions",
  "when": {
    "region_tags": ["food_primary"],
    "trip_stage": ["inventory_selection", "daily_activity_design"]
  },
  "effect": {
    "dimension_adjustments": [],
    "hybrid_factor_adjustments": [],
    "anchor_promotions": []
  },
  "confidence": 0.7,
  "notes": ""
}
```

This layer should be used for:

- region-specific intensification
- trip-stage-specific behavior
- segment-specific behavior
- conditional promotion of a hybrid factor into anchor-like status

## 8. Interaction Rules

These rules are not optional add-ons. They are part of the profile.

### Rule Record

```json
{
  "id": "breadth_x_recovery",
  "dimensions": ["breadth_vs_depth", "recovery_vs_intensity"],
  "activation": {
    "all": [
      {
        "dimension": "breadth_vs_depth",
        "operator": ">=",
        "value": 0.5,
        "use": "value"
      },
      {
        "dimension": "recovery_vs_intensity",
        "operator": ">=",
        "value": 0.5,
        "use": "value"
      }
    ]
  },
  "effect": {
    "planning_biases": [],
    "warnings": [],
    "explanation": ""
  },
  "strength": 0.9,
  "priority": 0.8
}
```

### Rule Semantics

Each interaction rule should have four jobs:

1. detect a meaningful combination of preferences
2. modify downstream itinerary objectives
3. generate human-readable explanation text
4. surface unresolved tensions when the combination is hard to satisfy cleanly

The initial implementation should treat each rule as:

```json
{
  "id": "rule_name",
  "dimensions": [],
  "activation": {
    "all": [],
    "any": [],
    "salience_floor": 0.5
  },
  "effect": {
    "planning_biases": [],
    "warnings": [],
    "explanation": ""
  },
  "strength": 0.8,
  "priority": 0.7
}
```

Recommended semantics:

- `activation.all` means every listed condition must hold
- `activation.any` means at least one listed condition must hold
- `salience_floor` means rules should fire only when the involved dimensions matter enough to the traveler
- `strength` measures how strongly the rule should influence downstream objectives
- `priority` helps decide which rule wins if two rules push in different directions

### Planning Bias Types

The first implementation can keep the rule outputs compact by emitting only a few bias categories:

- `route_shape`
- `move_density`
- `recovery_blocks`
- `booking_style`
- `budget_protection`
- `lodging_strategy`
- `day_structure`
- `discovery_strategy`
- `social_exposure`

Those are enough to shape itinerary generation without locking the final ranking algorithm too early.

### Version 1 Interaction Rules

#### 1. Breadth x Recovery

```json
{
  "id": "breadth_x_recovery",
  "dimensions": ["breadth_vs_depth", "recovery_vs_intensity"],
  "activation": {
    "all": [
      {
        "dimension": "breadth_vs_depth",
        "operator": "<=",
        "value": -0.4,
        "use": "value"
      },
      {
        "dimension": "recovery_vs_intensity",
        "operator": ">=",
        "value": 0.4,
        "use": "value"
      }
    ],
    "salience_floor": 0.6
  },
  "effect": {
    "planning_biases": [
      "allow regional variety but lower move density",
      "prefer day trips or short loops over repeated full relocations",
      "insert deliberate recovery blocks after high-friction segments"
    ],
    "warnings": [
      "ambition can outrun stamina if destination count grows too fast"
    ],
    "explanation": "This traveler wants contrast and coverage, but not at a pace that compounds fatigue."
  },
  "strength": 0.95,
  "priority": 0.9
}
```

#### 2. Movement x Scenic Transit

```json
{
  "id": "movement_x_scenic_transit",
  "dimensions": ["movement_vs_friction", "scenic_transit_vs_destination_time"],
  "activation": {
    "all": [
      {
        "dimension": "movement_vs_friction",
        "operator": ">=",
        "value": 0.4,
        "use": "value"
      },
      {
        "dimension": "scenic_transit_vs_destination_time",
        "operator": "<=",
        "value": -0.4,
        "use": "value"
      }
    ],
    "salience_floor": 0.6
  },
  "effect": {
    "planning_biases": [
      "treat transit as part of the experience only when scenic payoff is high",
      "avoid operationally ugly transfers with low experiential return",
      "prefer clean, memorable movement days over merely efficient but stressful ones"
    ],
    "warnings": [
      "long travel days need experiential justification"
    ],
    "explanation": "Travel time is acceptable when the route itself feels rewarding, not when it is just friction."
  },
  "strength": 0.9,
  "priority": 0.85
}
```

#### 3. Structure x Discovery

```json
{
  "id": "structure_x_discovery",
  "dimensions": ["structure_vs_elasticity", "iconic_vs_discovery"],
  "activation": {
    "all": [
      {
        "dimension": "structure_vs_elasticity",
        "operator": ">=",
        "value": 0.4,
        "use": "value"
      },
      {
        "dimension": "iconic_vs_discovery",
        "operator": ">=",
        "value": 0.4,
        "use": "value"
      }
    ],
    "salience_floor": 0.6
  },
  "effect": {
    "planning_biases": [
      "recommend wandering districts, corridors, and landscapes",
      "use optional nearby targets instead of dense hour-by-hour plans",
      "keep a few anchor experiences but preserve room for drift and local discovery"
    ],
    "warnings": [
      "over-scheduling will reduce fit more than under-scheduling"
    ],
    "explanation": "The traveler wants discovery through movement and attention, not through a fully choreographed plan."
  },
  "strength": 0.9,
  "priority": 0.85
}
```

#### 4. Budget x Quality Floors

```json
{
  "id": "budget_x_quality_floors",
  "dimensions": ["budget_model.total_budget_sensitivity", "anchors.quality_floor_anchors"],
  "activation": {
    "all": [
      {
        "dimension": "budget_model.total_budget_sensitivity",
        "operator": ">=",
        "value": 0.5,
        "use": "value"
      },
      {
        "dimension": "anchors.quality_floor_anchors",
        "operator": "not_empty",
        "use": "presence"
      }
    ]
  },
  "effect": {
    "planning_biases": [
      "protect quality-floor categories first",
      "compress lower-priority categories before eroding non-negotiables",
      "favor route simplification if it preserves core quality floors"
    ],
    "warnings": [
      "budget pressure can silently undermine stated quality floors unless the system defends them explicitly"
    ],
    "explanation": "This traveler is budget-aware, but only after the plan protects categories that materially affect trip quality."
  },
  "strength": 0.95,
  "priority": 0.95
}
```

#### 5. Social Energy x Recovery

```json
{
  "id": "social_energy_x_recovery",
  "dimensions": ["social_energy_vs_solitude", "recovery_vs_intensity"],
  "activation": {
    "all": [
      {
        "dimension": "social_energy_vs_solitude",
        "operator": "<=",
        "value": -0.4,
        "use": "value"
      },
      {
        "dimension": "recovery_vs_intensity",
        "operator": ">=",
        "value": 0.4,
        "use": "value"
      }
    ],
    "salience_floor": 0.5
  },
  "effect": {
    "planning_biases": [
      "separate lively public atmosphere from private decompression requirements",
      "favor quiet lodging even when activity zones are energetic",
      "insert low-stimulus intervals between socially dense stretches"
    ],
    "warnings": [
      "social appetite does not eliminate the need for quiet recovery"
    ],
    "explanation": "The traveler likes public energy, but still needs strong recovery protection to sustain the trip."
  },
  "strength": 0.85,
  "priority": 0.8
}
```

## 9. Interaction Precedence And Conflict Handling

The preference engine should resolve profile logic in this order:

1. hard feasibility constraints
2. anchor protection
3. quality-floor protection
4. interaction rules
5. single-dimension preferences

This order is important because travelers usually experience disappointment from violating anchors and quality floors more sharply than from missing a moderate directional preference.

When rules conflict, the engine should:

- keep both active if they can be satisfied by segmentation
- prefer the higher-priority rule if they directly collide
- emit a `tension_flag` if no clean resolution exists

Example:

- a traveler may want elastic discovery and strong route coherence
- that is not a contradiction by itself
- but it becomes tense if the route also has many fixed calendar anchors and high breadth pressure

## 10. Tension Flags

Tension flags should record unresolved conflicts rather than flatten them away.

```json
[
  {
    "id": "deep_trip_too_many_destinations",
    "severity": 0.8,
    "description": "Wants depth but also too many places for trip length"
  }
]
```

Suggested tension sources for version 1:

- anchor overload for trip length
- depth preference combined with excessive destination count
- recovery need combined with high move ambition
- strong quality floors under budget compression
- elastic discovery goals combined with too many fixed-booking commitments

## 11. Evidence Summary

This layer connects future elicitation design to the resolved profile.

```json
{
  "sources": {
    "direct_statements": [],
    "tradeoff_choices": [],
    "scenario_reactions": [],
    "resource_allocations": []
  },
  "confidence_notes": []
}
```

## Mapping From The Old Repo

The current repo inputs can map into this schema like this:

- `must_see` -> `hard_constraints.must_include_places` plus possible `anchors.place_anchors`
- `nature_ratio` -> `tradeoff_dimensions.nature_vs_culture.value`
- `complexity_tolerance` -> evidence feeding:
  - `movement_vs_friction`
  - `recovery_vs_intensity`
  - `self_reliance_vs_convenience`
- `cost_sensitivity` -> `budget_model.total_budget_sensitivity`
- `route_passions` -> `hybrid_factors.route_modes`

## Immediate Next Implementation Step

The next natural step is to define:

- the evidence model for each dimension and hybrid factor
- how evidence weights produce `value`, `confidence`, `salience`, and `stability`
- how conditional overrides are inferred and updated
- how interaction-rule outputs map into itinerary objectives and later ranking logic
