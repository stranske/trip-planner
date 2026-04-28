# Leisure Tradeoff Taxonomy

This document is the canonical reference for the eleven tradeoff dimensions used in the leisure preference model. It defines each dimension's name, description, directionality, and value range. Downstream work — questionnaire design, evidence modeling, and scoring — should derive from this taxonomy rather than invent new dimension names.

The authoritative constants live in `trip_planner/preferences/schema.py`:

- `TRADEOFF_DIMENSION_KEYS` — ordered tuple of the eleven canonical keys
- `POLARITY_MAP` — maps each key to its (-1.0, +1.0) pole labels
- `DIMENSION_DESCRIPTIONS` — maps each key to (description, negative-extreme note, positive-extreme note)

A test in `tests/preferences/test_taxonomy.py` verifies that `POLARITY_MAP` and `DIMENSION_DESCRIPTIONS` stay synchronized with `TRADEOFF_DIMENSION_KEYS`.

---

## Value Range Convention

All tradeoff dimensions share the same numeric representation:

| Value | Meaning |
|-------|---------|
| `-1.0` | Strong preference for the left (negative) pole |
| `-0.5` | Moderate preference for the left pole |
| `0.0` | Balanced, mixed, or not yet resolved |
| `+0.5` | Moderate preference for the right (positive) pole |
| `+1.0` | Strong preference for the right (positive) pole |

Alongside `value`, each `TradeoffDimension` record carries:

- `confidence` [0.0, 1.0] — how well the inferred value is supported by evidence
- `salience` [0.0, 1.0] — how consequential this dimension is when tradeoffs must be made
- `stability` [0.0, 1.0] — how consistently the preference holds across contexts
- `trip_stage_sensitivity` — how strongly the dimension matters at each planning stage

---

## The Eleven Canonical Dimensions

### 1. `movement_vs_friction`

**Description:** How much the traveler enjoys frequent relocation versus preferring fewer, longer stays.

| Pole | Value | Meaning |
|------|-------|---------|
| Movement appetite | `-1.0` | Comfortable with daily or near-daily moves; treats transit as part of the experience. |
| Friction sensitivity | `+1.0` | Values settled bases; dislikes repeated packing and logistical overhead. |

**Questionnaire anchor:** "How often do you want to change location?" (1 = move freely, 5 = prefer staying put)

**Interaction notes:** Interacts strongly with `scenic_transit_vs_destination_time`. A traveler with high movement appetite who also values scenic transit will treat travel days as highlights. A traveler with high movement appetite but high destination-time preference faces a volume-of-moves tension.

---

### 2. `recovery_vs_intensity`

**Description:** Balance between needing deliberate rest periods and sustaining a packed, high-activity pace.

| Pole | Value | Meaning |
|------|-------|---------|
| Recovery need | `-1.0` | Requires built-in slow days; fatigue accumulates quickly without deliberate rest. |
| Sustainable intensity | `+1.0` | Can maintain a full agenda across many consecutive active days. |

**Questionnaire anchor:** "Do you prefer packed days or days with built-in rest?" (1 = need recovery, 5 = can sustain intensity)

**Interaction notes:** Interacts with `breadth_vs_depth`. A traveler with high breadth desire (many places) and high recovery need creates a `breadth_x_recovery` tension: ambition can outrun stamina unless move density is deliberately lowered.

---

### 3. `nature_vs_culture`

**Description:** Whether the traveler is drawn toward natural landscapes and outdoor settings or toward urban cultural immersion.

| Pole | Value | Meaning |
|------|-------|---------|
| Nature | `-1.0` | Landscapes, hiking, wildlife, and open terrain dominate the ideal trip. |
| Culture | `+1.0` | Cities, museums, architecture, food scenes, and human history dominate. |

**Questionnaire anchor:** "Do you prioritize natural landscapes or cultural/urban experiences?" (1 = nature, 5 = culture)

**Legacy mapping:** Directly replaces the old `nature_ratio` field. A `nature_ratio` of 0.8 (strong nature) maps to `nature_vs_culture` ≈ `-0.6`.

**Interaction notes:** Does not carry a strong interaction with most other dimensions on its own; it primarily shapes inventory selection (which stops and activities are scored higher).

---

### 4. `structure_vs_elasticity`

**Description:** Preference for pre-planned, detailed itineraries versus open, improvised days.

| Pole | Value | Meaning |
|------|-------|---------|
| Structured days | `-1.0` | Wants bookings, schedules, and an advance plan for most of the trip. |
| Elastic days | `+1.0` | Prefers loose scaffolding; follows impulse; resists tight hour-by-hour planning. |

**Questionnaire anchor:** "Do you prefer a detailed plan or flexibility to improvise?" (1 = fully planned, 5 = fully flexible)

**Interaction notes:** Interacts with `iconic_vs_discovery`. An elastic traveler who also wants discovery will produce a `structure_x_discovery` pattern: wandering districts and corridors score well; hour-by-hour itineraries score poorly. High `structure_vs_elasticity` with many fixed calendar anchors is internally consistent; high elasticity with many fixed calendar anchors creates tension.

---

### 5. `breadth_vs_depth`

**Description:** Whether the traveler wants to cover many places or linger and go deep in fewer locations.

| Pole | Value | Meaning |
|------|-------|---------|
| Breadth | `-1.0` | Maximizes the number of distinct places, regions, or countries visited. |
| Depth | `+1.0` | Spends multiple days in each stop; prioritizes understanding over coverage. |

**Questionnaire anchor:** "Do you prefer to visit many places or spend more time in fewer places?" (1 = many places, 5 = fewer but deeper)

**Interaction notes:** One of the highest-interaction dimensions. Breadth preference interacts with recovery need (`breadth_x_recovery`), movement patterns, and tension detection. A depth preference interacts with `route_coherence_vs_eclectic_contrast`: depth travelers often prefer coherent route arcs with meaningful immersion per stop.

---

### 6. `self_reliance_vs_convenience`

**Description:** Preference for handling logistics independently versus relying on pre-arranged services and support.

| Pole | Value | Meaning |
|------|-------|---------|
| Logistical self-reliance | `-1.0` | Books independently; navigates on foot or by public transit; avoids package services. |
| Convenience support | `+1.0` | Values pre-arranged transfers, guided access, concierge help, and reduced friction. |

**Questionnaire anchor:** "Do you prefer to handle all logistics yourself or have things pre-arranged?" (1 = fully self-reliant, 5 = prefer pre-arranged)

**Legacy mapping:** Partially replaces `complexity_tolerance`. A low `complexity_tolerance` maps to high convenience support (positive pole). See full legacy mapping table below.

**Interaction notes:** Informs booking strategy (self-booked vs. operator-intermediated), route design (public transit vs. private transfers), and how surprises and gaps in the plan are handled.

---

### 7. `historic_vs_contemporary`

**Description:** Whether the traveler engages primarily with historical heritage or contemporary local life.

| Pole | Value | Meaning |
|------|-------|---------|
| Historic depth | `-1.0` | Ruins, heritage sites, old towns, museums of history, and layered architectural periods. |
| Contemporary life | `+1.0` | Modern neighborhoods, current art, local food culture, and present-day urban texture. |

**Questionnaire anchor:** "Do you prefer historic heritage or engaging with contemporary local culture?" (1 = historic depth, 5 = contemporary life)

**Interaction notes:** Primarily shapes activity and lodging inventory scoring. A historic depth traveler scores old-town neighborhoods and UNESCO sites higher; a contemporary-life traveler scores design hotels, local markets, and current cultural venues higher.

---

### 8. `scenic_transit_vs_destination_time`

**Description:** Whether travel time between places is valued for scenic experience or minimized to protect time at destinations.

| Pole | Value | Meaning |
|------|-------|---------|
| Scenic transit | `-1.0` | Slow trains, coastal ferries, and scenic passes are highlights, not overheads. |
| Destination time | `+1.0` | Favors fastest practical transport to protect time on the ground. |

**Questionnaire anchor:** "Do you enjoy scenic travel days or prefer to get there quickly?" (1 = scenic transit is the point, 5 = minimize travel time)

**Legacy mapping:** Scenic transit preference is a richer successor to `route_passions`. A strong scenic rail passion maps to `scenic_transit_vs_destination_time` ≈ `-0.7` combined with `hybrid_factors.route_modes.preferences.rail` ≈ `0.9`.

**Interaction notes:** The `movement_x_scenic_transit` rule fires when a traveler has high movement appetite and strong scenic transit preference: travel days are experiences, not overheads, so they should be enjoyable rather than merely efficient.

---

### 9. `route_coherence_vs_eclectic_contrast`

**Description:** Whether the route should follow a thematic or geographic thread versus assembling contrasting, varied stops.

| Pole | Value | Meaning |
|------|-------|---------|
| Route coherence | `-1.0` | Logical geographic or thematic progression; aesthetic unity across the trip arc. |
| Eclectic contrast | `+1.0` | Variety is the point — different landscapes, cultures, and moods in deliberate juxtaposition. |

**Questionnaire anchor:** "Do you prefer a coherent themed route or a deliberately varied mix?" (1 = coherent, 5 = eclectic)

**Interaction notes:** Interacts with `breadth_vs_depth` and `structure_vs_elasticity`. A coherent-route depth traveler produces a very different itinerary shape than an eclectic-contrast breadth traveler. High eclectic contrast with many calendar anchors can create logical inconsistency if the anchors are geographically scattered.

---

### 10. `social_energy_vs_solitude`

**Description:** Preference for busy, social environments versus quiet, low-stimulus settings.

| Pole | Value | Meaning |
|------|-------|---------|
| Social energy | `-1.0` | Thrives around crowds, lively neighborhoods, street life, and public social spaces. |
| Solitude | `+1.0` | Seeks quiet lodging, low-traffic routes, and deliberate separation from tourist density. |

**Questionnaire anchor:** "Do you prefer lively social environments or quiet, low-key settings?" (1 = social energy, 5 = solitude)

**Interaction notes:** The `social_energy_x_recovery` rule fires when a traveler likes social energy but also has high recovery need. These are compatible but require deliberate segmentation: lively activity zones during the day with quiet lodging for decompression at night.

---

### 11. `iconic_vs_discovery`

**Description:** Whether the trip prioritizes well-known must-see experiences or off-the-beaten-path finds.

| Pole | Value | Meaning |
|------|-------|---------|
| Iconic certainty | `-1.0` | Validates the trip through canonical highlights; feels incomplete without the major sites. |
| Curious discovery | `+1.0` | The best moments are unexpected; actively avoids crowds; seeks lesser-known places. |

**Questionnaire anchor:** "Do you prioritize iconic must-sees or off-the-beaten-path discoveries?" (1 = iconic, 5 = discovery)

**Interaction notes:** Interacts with `structure_vs_elasticity`. An elastic discovery traveler scores wandering districts and open time higher. An iconic traveler with structured days scores advance-booked major attractions higher.

---

## Hybrid Factors

These four factors can act as anchors, tradeoff dimensions, or both. They are modeled separately from the eleven dimensions because their role is context-dependent.

| Key | Description | Tradeoff Role |
|-----|-------------|---------------|
| `food` | Whether food and dining are background or central to the trip experience. High salience = dining is near-anchor. | `atmosphere` |
| `rest` | Whether sleep quality and lodging comfort are non-negotiable or secondary. High anchor strength = quality is protected. | `rhythm` |
| `music` | Whether live music or sonic atmosphere shapes place choices. High anchor strength = live music is a trip-defining commitment. | `atmosphere` |
| `route_modes` | Preferences for travel modes: rail, boat, road, air, walking. Feeds both scenic-transit dimension and movement planning. | `route_design` |

Hybrid factors use `mode` to declare their current role: `anchor`, `tradeoff`, or `both`.

---

## Legacy Field Mapping

The table below shows how fields from the old `request.json` format map into the canonical taxonomy. All legacy fields are still accepted via `legacy_request_adapter.py` but are not the long-term planning contract.

| Legacy Field | Status | Canonical Target | Notes |
|---|---|---|---|
| `must_see` | Bridged | `hard_constraints.must_include_places` + `anchors.place_anchors` | Strong must-sees elevate to place anchors with high `strength`. |
| `nature_ratio` | Bridged | `tradeoff_dimensions.nature_vs_culture.value` | Maps linearly; `nature_ratio=1.0` → `nature_vs_culture=-1.0`, `nature_ratio=0.0` → `+1.0`. |
| `complexity_tolerance` | Bridged (multi-field) | `movement_vs_friction`, `recovery_vs_intensity`, `self_reliance_vs_convenience` | `low` tolerance → friction-sensitive + recovery-need + convenience-support. See `COMPLEXITY_TOLERANCE_MAP` in `schema.py`. |
| `cost_sensitivity` | Bridged | `budget_model.total_budget_sensitivity` | Direct numeric mapping; higher = more budget-aware. |
| `route_passions` | Bridged | `hybrid_factors.route_modes.preferences` + `scenic_transit_vs_destination_time` | Rail/boat passions → `route_modes.preferences` with high salience; scenic-rail passion also shifts `scenic_transit_vs_destination_time` toward `-1.0`. |

**Deferred fields:** No legacy field is marked deprecated in the current implementation; all are bridged. Fields not listed above (e.g., raw free-text planning notes) are treated as unstructured evidence inputs and are not mapped to a single dimension.

---

## Trip Choice Examples

These examples show how concrete planning choices express tradeoffs. They are intended as calibration references for questionnaire design and scoring.

### Example 1 — The "Slow Train" Traveler

A traveler books a 3-week trip through Switzerland and Austria entirely by rail, spending 4–5 days in each base, with no flights.

| Dimension | Implied Value | Rationale |
|-----------|--------------|-----------|
| `movement_vs_friction` | `-0.2` | Moves, but not frantically — base-hop pattern |
| `scenic_transit_vs_destination_time` | `-0.8` | Rail is a core experience, not overhead |
| `breadth_vs_depth` | `+0.5` | Moderate depth (4–5 days/stop) |
| `self_reliance_vs_convenience` | `-0.5` | Booked rail independently |
| `route_coherence_vs_eclectic_contrast` | `-0.6` | Coherent alpine corridor theme |

### Example 2 — The "Urban Explorer" Traveler

A pair travels to 6 cities in 2 weeks across Spain and Portugal, staying in design hotels, mixing tapas crawls and museums, flying between distant cities.

| Dimension | Implied Value | Rationale |
|-----------|--------------|-----------|
| `movement_vs_friction` | `-0.7` | Comfortable moving every 2–3 days |
| `scenic_transit_vs_destination_time` | `+0.7` | Flew between cities to protect ground time |
| `breadth_vs_depth` | `-0.6` | Coverage over lingering |
| `nature_vs_culture` | `+0.8` | Urban cultural immersion throughout |
| `historic_vs_contemporary` | `+0.4` | Slightly contemporary-leaning (food, design) |

### Example 3 — The "Deep Hiker" Traveler

A solo traveler spends 5 weeks in one mountain region, camping and hiking, with only one city base used for resupply.

| Dimension | Implied Value | Rationale |
|-----------|--------------|-----------|
| `breadth_vs_depth` | `+0.9` | Extreme depth in a single region |
| `nature_vs_culture` | `-0.9` | Nature dominant |
| `movement_vs_friction` | `-0.3` | Within-region movement is acceptable |
| `social_energy_vs_solitude` | `+0.8` | Strong solitude preference |
| `self_reliance_vs_convenience` | `-0.8` | Handles all logistics independently |

### Example 4 — The "Comfort First" Traveler

A couple books a 10-day trip to Italy with a private guide for the first 3 days, pre-booked restaurant reservations, and airport transfers throughout.

| Dimension | Implied Value | Rationale |
|-----------|--------------|-----------|
| `self_reliance_vs_convenience` | `+0.8` | Pre-arranged services throughout |
| `recovery_vs_intensity` | `+0.3` | Pace is comfortable, not packed |
| `iconic_vs_discovery` | `-0.5` | Colosseum, Vatican, etc. are explicit goals |
| `structure_vs_elasticity` | `-0.6` | Advance bookings dominate the plan |
| `historic_vs_contemporary` | `-0.5` | Heritage and history are primary interests |

### Example 5 — The "Eclectic Contrast" Traveler

A solo traveler combines Tokyo, Marrakech, and Reykjavik in a 4-week trip — deliberately choosing maximum contrast.

| Dimension | Implied Value | Rationale |
|-----------|--------------|-----------|
| `route_coherence_vs_eclectic_contrast` | `+0.9` | Contrast is the explicit goal |
| `breadth_vs_depth` | `-0.4` | 1.5–2 weeks per destination |
| `iconic_vs_discovery` | `+0.3` | Favors unexpected corners within each city |
| `structure_vs_elasticity` | `+0.5` | Elastic within each destination |
| `movement_vs_friction` | `-0.4` | Three long-haul flights are acceptable |

---

## Dimension Interaction Summary

The following interactions have named rules in `trip_planner/preferences/interactions.py`. Each rule fires when the listed dimension values exceed their thresholds.

| Rule ID | Dimensions Involved | What It Detects |
|---------|--------------------|----|
| `breadth_x_recovery` | `breadth_vs_depth`, `recovery_vs_intensity` | Wanting many places while needing rest — ambition can outrun stamina. |
| `movement_x_scenic_transit` | `movement_vs_friction`, `scenic_transit_vs_destination_time` | High movement + scenic transit preference → travel days must pay experiential dividends. |
| `structure_x_discovery` | `structure_vs_elasticity`, `iconic_vs_discovery` | Elastic wandering + discovery preference → over-scheduling reduces fit more than under-scheduling. |
| `budget_x_quality_floors` | `budget_model.total_budget_sensitivity`, `anchors.quality_floor_anchors` | Budget pressure alongside explicit quality floors → protect floors before compressing other categories. |
| `social_energy_x_recovery` | `social_energy_vs_solitude`, `recovery_vs_intensity` | Social appetite + recovery need → segment lively activity from quiet lodging. |

---

## Guidance for Future Work

**Questionnaire design:** Each dimension should have at least one direct elicitation question (Likert 1–5) and at least one forced-tradeoff question that reveals the dimension through revealed preference rather than self-report. See `trip_planner/preferences/questionnaire.py` for the current question definitions.

**Evidence modeling:** Direct questionnaire answers yield `confidence = 0.7`. Default (skipped) answers yield `confidence = 0.1`. Forced-choice tradeoff scenarios yield `confidence = 0.8`. See `trip_planner/preferences/normalization.py` and `trip_planner/preferences/evidence.py`.

**Scoring:** Each dimension value influences inventory and itinerary scoring via weighted contributions. See `trip_planner/ranking/leisure.py`. The `salience` field, not `value` alone, determines how much a dimension's contribution is weighted in the final score.

**Adding a new dimension:** Any proposed new dimension must be added to `TRADEOFF_DIMENSION_KEYS`, `POLARITY_MAP`, and `DIMENSION_DESCRIPTIONS` in `schema.py` together, or the taxonomy test will fail. Evaluate whether the new dimension is truly independent or whether it overlaps with an existing one before adding.
