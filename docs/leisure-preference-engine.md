# Leisure Preference Engine

## Purpose

This document defines the design target for the **leisure-travel preference evaluation algorithm**.

It is not centered on a short travel quiz. The main goal is to understand how a serious independent traveler thinks through the real tradeoffs involved in planning a two- to six-week trip. Only after that model exists should the system decide what questions, prompts, or ranking inputs are needed.

## Design Principle

For leisure travel, the application should evaluate preferences in this order:

1. understand the trip frame
2. identify hard constraints and non-negotiables
3. infer the traveler's real tradeoff structure
4. detect where preferences are conditional, unstable, or contradictory
5. derive a structured preference profile
6. translate that profile into itinerary objectives and ranking weights

The ranking algorithm is downstream from this process, not a substitute for it.

## What The Existing Repo Suggests

The initial repo work already hints at a few important preference signals:

- `must_see`
- `nature_ratio`
- `complexity_tolerance`
- `cost_sensitivity`
- `route_passions` for train, boat, and road travel

Those should not be kept in their current form, but they are useful evidence about the intended direction:

- some places or experiences act as anchors
- travel mode itself can be part of the desired experience
- travel complexity matters
- spending has both an absolute ceiling and a category-allocation side
- nature vs. culture is meaningful, but it is only one tradeoff among many

The early Europe-specific segment generation should be interpreted narrowly: it looks like an attempt to expand from an initial inventory into nearby or contiguous regions. That behavior should be retained as **regional adjacency expansion**, not as a Europe-only design.

## Anchor Logic

The system should not treat anchors as only “must-see places.”

There are several kinds of anchors that can shape a trip:

### 1. Place Anchors

- cities
- regions
- landscapes
- heritage sites
- neighborhoods

### 2. Experience Anchors

- a major hike
- a music festival or opera run
- beach/rest time
- food exploration
- museum depth
- hot springs
- wildlife viewing

### 3. Mode Anchors

These are already visible in the repo’s `route_passions`.

- scenic rail
- ferry or boat travel
- road-trip corridors
- long-distance bus tolerance or aversion

For some travelers, the movement mode is part of the reward, not just a means to an end.

Mode preferences should therefore be modeled in two places:

- as anchors when rail, boat, road, or another movement style is a primary trip-shaping desire
- as tradeoff dimensions when they mainly express tolerance, taste, or route preference

### 4. Rhythm Anchors

- a slow week in the middle of the trip
- recovery blocks after transit-heavy sections
- city intensity followed by countryside decompression

### 5. Calendar Anchors

- seasonal windows
- concerts
- festivals
- migration or bloom periods
- weather-dependent activity windows

### 6. Quality-Floor Anchors

Some travelers have minimum standards that effectively anchor the plan.

Examples:

- never stay below a certain lodging comfort level
- always stay centrally in cities
- always have private space for recovery
- always preserve high-quality food access

### 7. Regional-Adjacency Anchors

This appears to be the real idea behind the earlier Europe-specific generation logic.

If a traveler anchors on one or two places, the system should be able to ask:

- what contiguous regions are natural extensions?
- what nearby landscapes or cities deepen the trip instead of diluting it?
- what additions preserve route coherence?

This should work worldwide, not just in Europe.

## Hybrid Factors: Anchor Or Tradeoff

Some preferences should not be forced into only one layer.

### Food

For many travelers, food is:

- a secondary planning factor
- a spending-allocation issue
- part of daily quality rather than the main purpose of the trip

For others, especially serious food travelers, it can become:

- a primary experience anchor
- a geographic organizer
- a strong constraint on rhythm, budget, and route choice

So food should exist:

- as an anchor when it is trip-defining
- as a tradeoff dimension around cost, time allocation, and planning energy for most travelers

### Relaxation And Rest

Relaxation/rest can sometimes be an anchor, but it will more often function as a tradeoff dimension.

Usually it affects:

- pace
- recovery scheduling
- day density
- lodging location and style
- willingness to sacrifice coverage for rhythm

So the engine should treat rest primarily as part of tradeoff logic, while still allowing specific rest-focused anchors such as beach weeks, spa intervals, or decompression stays.

### Music

Music will often matter less as a general tradeoff dimension than as a specific anchor:

- a concert run
- a festival
- a destination with a strong live-music culture

But when it is not an anchor, it can still show up as part of:

- historic depth vs. contemporary life
- sensory richness vs. calm restoration
- nightlife/social energy preferences

### Route Passions

The original repo’s `route_passions` field is useful because it points to a real hybrid factor.

For most travelers, rail/boat/road preferences will function mainly as tradeoff inputs:

- scenic transit vs. destination time
- convenience vs. independence
- route coherence vs. variety

For a smaller but important group, they become true anchors:

- a rail-centered trip
- a ferry-stitched coastal route
- a road-trip corridor as the trip’s core identity

## The Core Leisure Tradeoffs

The list below is intentionally broader than the old repo’s nature/culture slider.

Based on the current discussion, the following are the **first-tier leisure tradeoffs**, roughly in descending importance:

1. movement appetite vs. friction sensitivity
2. recovery need vs. sustainable intensity
3. nature vs. culture
4. structured days vs. elastic days
5. breadth vs. depth
6. logistical self-reliance vs. convenience support
7. historic depth vs. contemporary life
8. scenic transit vs. destination time
9. route coherence vs. eclectic contrast
10. social energy vs. solitude
11. iconic certainty vs. curious discovery

Other dimensions remain useful, but these should drive the first core version of the leisure preference model.

### 1. Breadth vs. Depth

- breadth-oriented travelers want contrast and coverage
- depth-oriented travelers want fewer places and more local absorption

This affects base count, movement density, and the value of day trips vs. overnight moves.

### 2. Movement Appetite vs. Friction Sensitivity

This captures whether the traveler enjoys onward motion or mainly tolerates it when necessary.

It should reflect:

- transfer tolerance
- airport/rail complexity tolerance
- packing and unpacking tolerance
- willingness to sacrifice time-in-place for route ambition

### 3. Certainty vs. Openness

This captures how much structure the traveler wants to carry.

- some want fixed anchors and advance bookings
- others want partial structure and room to adjust to weather, mood, or discovery

### 4. Comfort vs. Immersion

This is not the same as budget.

The model should separate:

- comfort need
- friction tolerance
- desire for immersion
- what categories are worth spending on

### 5. Iconic Certainty vs. Curious Discovery

This captures whether the traveler will regret missing canonical places more than they dislike tourist pressure, or whether they would rather pursue strong-fit but lower-profile options.

### 6. Structured Days vs. Elastic Days

Some travelers want shaped days with clear objectives. Others want one anchor and a lot of room for drifting.

This should include:

- comfort with wandering without a precise objective
- desire for loose neighborhood exploration
- preference for “things to wander toward” rather than tightly scheduled activities
- preference for districts, promenades, landscapes, or market areas that reward unstructured time

### 7. Urban Density vs. Landscape Exposure

The deeper question is what kind of attention the traveler wants to sustain for weeks:

- dense city immersion
- scenic movement
- small-town rhythm
- alternating urban and natural energy cycles

### 8. Peak Experience Maximization vs. Trip Rhythm Quality

- peak-maximizers accept uneven days if the highlights are strong
- rhythm-oriented travelers care more about cumulative coherence and recovery

### 9. Budget Minimization vs. Budget Intentionality

The engine should capture where the traveler wants to save and where they want to spend, not just whether they are “budget” or “luxury.”

### 10. Social Energy vs. Solitude

This affects:

- neighborhood choice
- lodging choice
- crowd tolerance
- need for reflective time

### 11. Recovery Need vs. Sustainable Intensity

Many plans fail because they are attractive in isolation but exhausting in sequence.

The model should estimate:

- how often the traveler needs low-intensity days
- how strongly late arrivals and early starts damage the trip
- what kind of recovery they prefer

Recovery should be treated as both:

- physical recovery
- cognitive and sensory recovery

For many long trips, cognitive/sensory fatigue matters just as much as physical fatigue.

### 12. Logistical Self-Reliance vs. Convenience Support

This should capture whether the traveler prefers to handle complexity personally or to spend, simplify, and structure the trip to reduce operational burden.

It should reflect:

- confidence with local transit systems
- comfort with ambiguity
- willingness to solve problems in motion
- appetite for independent travel operations

### 13. Nature vs. Culture

This should remain in the model, but not as the sole or dominant axis.

The useful version of this dimension is broader than “outdoors vs. museums.” It is closer to:

- landscape exposure
- built-environment immersion
- ecological experience
- artistic, historical, and civic experience

On the culture side, the model should explicitly cover both:

- historic depth
- contemporary life

### 14. Scenic Transit vs. Destination Time

Some travelers love route experience:

- mountain railways
- coastal ferries
- scenic drives

Others mainly value being in the place once they arrive.

### 15. Route Coherence vs. Eclectic Contrast

Some trips feel best when they unfold through neighboring or culturally connected places. Others gain energy from radical contrast.

This affects:

- whether to expand contiguously from anchors
- whether to tolerate long leaps for variety
- whether the trip should feel like one story or several chapters

### 16. Familiarity vs. Novelty

Some travelers want repeated competence and comfort; others actively want strangeness, challenge, and unfamiliar patterns.

This can affect:

- cuisine
- accommodation style
- transport systems
- language environments
- everyday convenience

### 17. Historic Depth vs. Contemporary Life

Two travelers can both be “culture-oriented” while wanting very different things:

- one may want monuments, churches, ruins, and museums
- another may care more about contemporary neighborhoods, design, music, markets, and present-day urban life

This is not separate from the nature/culture dimension; it refines the culture side of that broader axis.

### 18. Sensory Richness vs. Calm Restoration

For some trips, the traveler wants:

- nightlife
- live music
- dense street energy
- strong food and social stimulation

For others, the traveler wants:

- quiet
- rhythm
- low sensory load
- contemplative space

This seems especially important in light of your note that relaxation, music, or another priority can rival or outrank “must see.”

### 19. Food Seriousness vs. Incidental Dining

Food can be:

- a major organizing principle
- an important but secondary pleasure
- mostly functional

This affects geography, schedule, spending, and recovery.

### 20. Shared Synchronization vs. Personal Autonomy

This matters more for pairs, families, or friend groups than for solo travel, but it is still a major long-trip factor.

The planner needs to know whether the trip should optimize for:

- tight coordination
- partial independence
- modular plans with optional divergence

## Interaction Effects

These dimensions should not be evaluated in isolation. The preference model needs to represent meaningful interaction effects.

### High-Priority Interaction Clusters

#### 1. Pace Cluster

- movement appetite vs. friction sensitivity
- recovery need vs. sustainable intensity
- breadth vs. depth
- structured days vs. elastic days

This cluster largely determines whether a trip feels exhilarating or depleting.

#### 2. Route Logic Cluster

- scenic transit vs. destination time
- route coherence vs. eclectic contrast
- logistical self-reliance vs. convenience support
- movement appetite vs. friction sensitivity

This cluster determines what kinds of routes are satisfying, not just feasible.

#### 3. Experience Attention Cluster

- nature vs. culture
- historic depth vs. contemporary life
- iconic certainty vs. curious discovery
- structured days vs. elastic days

This cluster shapes what the traveler actually wants to notice and spend time on.

#### 4. Energy And Atmosphere Cluster

- social energy vs. solitude
- recovery need vs. sustainable intensity
- sensory richness vs. calm restoration
- structured days vs. elastic days

This cluster often explains why two superficially similar itineraries feel completely different.

#### 5. Spend And Quality Cluster

- total budget sensitivity
- category-level spending priorities
- food seriousness vs. incidental dining
- comfort vs. immersion
- quality-floor anchors

This cluster determines not just what the traveler can afford, but what they believe is worth paying for.

### Important Pairwise Effects

Some pairings should be modeled explicitly.

#### Breadth x Recovery

High breadth with high recovery need is a common source of planning error.

The system should detect when the traveler likes variety in theory but enjoys it only if the route includes recovery blocks or slower transitions.

#### Movement x Scenic Transit

A traveler may dislike friction but still accept long movement days when the transit itself is rewarding.

This is one reason route modes cannot be treated as only a separate preference field.

#### Structure x Discovery

Travelers who prefer elastic days can still want strong discovery support.

For them, the planner should not over-schedule. It should instead provide:

- high-quality wandering zones
- directional prompts
- optional nearby anchors
- neighborhoods or landscapes likely to reward loose exploration

#### Nature/Culture x Historic/Contemporary

The old nature/culture axis is too coarse unless it can interact with the historic/contemporary split.

Examples:

- a culture-first traveler may be highly historic
- another culture-first traveler may be strongly contemporary
- a nature-first traveler may still want modern city intervals for energy reset

#### Social Energy x Recovery

Some travelers want lively places but need quieter lodging or decompression breaks.

The model should distinguish:

- desired public atmosphere
- desired private recovery environment

#### Budget x Quality Floors

Some travelers are budget-sensitive overall but still have non-negotiable floors for:

- location
- private room quality
- food quality
- transit simplicity

This should not be treated as inconsistency. It is often the core of their spending philosophy.

## Design Implication

The preference engine should therefore avoid a model where each dimension is just an independent slider.

It should support:

- first-order dimensions
- hybrid anchor/tradeoff factors
- interaction rules
- contradiction detection
- segment-specific overrides

## The Output Model

The algorithm should output a `LeisurePreferenceProfile` with five categories.

### A. Trip Frame

- duration
- traveler composition
- season
- special-purpose themes

### B. Hard Constraints

- time window
- budget ceiling
- must-include destinations
- must-protect experiences
- mobility or lodging requirements
- visa or border constraints

### C. Tradeoff Vectors

Each major dimension should store:

- direction
- strength
- confidence
- stability

First-tier dimensions should also support:

- salience
- whether the dimension is acting globally or only in certain trip segments
- whether it has been elevated to anchor-like importance for this traveler

### D. Conditional Rules

Examples:

- “I accept difficult travel if the destination is exceptional.”
- “I want more structure in cities than in countryside segments.”
- “I pay more for location, not for amenities.”
- “Music or rest can outrank landmark coverage.”
- “I want one or two high-quality experiences even on a moderate budget.”
- “Food is usually secondary, except in certain cities where it becomes a primary goal.”
- “Rail is preferred in general, but only when it adds scenic value rather than logistical burden.”

### E. Tension Flags

Examples:

- wanting a deep trip and too many destinations
- wanting spontaneity in peak season
- wanting high comfort with very low spend
- wanting ambitious days with low fatigue tolerance

## How To Infer Preferences

The system should prefer these signal types over shallow self-ratings:

### 1. Tradeoff Choices

Force meaningful compromise between alternatives.

### 2. Resource Allocation Choices

Ask where time, money, and energy should be spent if everything cannot be optimized.

This is especially important for:

- total budget sensitivity
- category-level spending philosophy
- quality floors
- deliberate splurges
- destination time vs. scenic transit time

### 3. Scenario Reactions

Use realistic planning scenarios:

- a long transfer day for a high-reward destination
- a weather disruption that makes flexibility valuable
- a crowded iconic site vs. a quieter but better-fit alternative

## Input Design Should Follow The Model

Only after the tradeoff model is defined should the app design its question flow.

That flow may still become compact, but it should be based on the above structure rather than on generic travel-site questionnaires.

In practice, the input design should probably distinguish:

- total budget sensitivity
- category-level spending priorities
- quality floors
- exceptional splurge logic

Those are not interchangeable.

It should also distinguish:

- a factor that is generally important
- a factor that is only situationally important
- a factor that is actually an anchor for this traveler

## Business Travel Should Be Mostly Separate

Business travel should not be treated as a small variant of leisure planning.

It is shaped much more by:

- policy fit
- schedule certainty
- approved channels
- documentation and comparables
- reimbursement defensibility

So the business side should have:

- a separate `BusinessTravelProfile`
- its own elicitation and optimization flow
- policy-aware objective functions from the start

## What Comes After Preference Evaluation

Once `LeisurePreferenceProfile` exists, the next layers should be:

1. constraint evaluation
2. option generation
3. itinerary objective mapping
4. ranking
5. explanation

## Explanation and Provenance Integration

### Design

`resolve_dimension_evidence` produces three provenance fields per dimension:

- `explanation_code` — a short machine-readable tag indicating how evidence resolved:
  `default_seed`, `explicit_override`, `behavioral_inference`, `conflict_override`,
  `conflict_low_confidence`
- `explanation_text` — a human-readable sentence describing the resolution outcome
- `contributing_evidence_ids` — the top-5 evidence IDs by weight that drove the result

### Integration Approach: Augment

`_apply_dimension_resolution` retains its own value-update logic (it uses the seed direction
and accumulated positive/weakening support rather than `resolve_dimension_evidence`'s
precedence-score approach).  After processing each dimension's evidence it calls
`resolve_dimension_evidence` a second time — solely to obtain the provenance fields — and
writes them onto `DimensionResolutionExplanation`.

This means `DimensionResolutionExplanation` carries:
- the existing influence list, tension references, and interaction rule IDs
- the new `explanation_code`, `explanation_text`, and `contributing_evidence_ids`

### Consumer: `_build_explanations` in `objective_derivation.py`

The itinerary-objective derivation layer already builds a structured explanation list from
`ResolvedLeisureProfile`.  Each tradeoff-dimension line is augmented with the evidence code:

```
movement_vs_friction: value=0.40, confidence=0.52, salience=0.45, evidence_code=explicit_override
```

This gives the downstream ranking and UI layers a stable, auditable signal about how
confident the resolver was for each dimension and why.

### Fields on `DimensionEvidenceResolution`

`DimensionEvidenceResolution` exposes only fields that are consumed by callers:

| Field | Consumer |
|-------|----------|
| `final_value` | tests and direct callers of `resolve_dimension_evidence` |
| `confidence` | tests; factored from `explicit_support` and `contradiction_support` internally |
| `explanation_code` | `_apply_dimension_resolution` → `DimensionResolutionExplanation` |
| `explanation_text` | `_apply_dimension_resolution` → `DimensionResolutionExplanation` |
| `contributing_evidence_ids` | `_apply_dimension_resolution` → `DimensionResolutionExplanation` |
| `recent_behavior_support` | `test_dimension_resolution_stale_behavior_is_discounted` |
| `older_behavior_support` | `test_dimension_resolution_stale_behavior_is_discounted` |

Intermediate scalars (`explicit_support`, `contradiction_support`, `salience_boost`,
`stability_bonus`, `stage_boosts`) were dropped from the dataclass; they remain local
variables inside `resolve_dimension_evidence` and their effect is already captured in
`confidence` and the explanation fields.
