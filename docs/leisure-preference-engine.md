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

## The Core Leisure Tradeoffs

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

### 12. Logistical Self-Reliance

This should capture:

- confidence with local transit systems
- comfort with ambiguity
- willingness to solve problems in motion
- appetite for independent travel operations

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
- mobility or lodging requirements
- visa or border constraints

### C. Tradeoff Vectors

Each major dimension should store:

- direction
- strength
- confidence
- stability

### D. Conditional Rules

Examples:

- “I accept difficult travel if the destination is exceptional.”
- “I want more structure in cities than in countryside segments.”
- “I pay more for location, not for amenities.”

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

### 3. Scenario Reactions

Use realistic planning scenarios:

- a long transfer day for a high-reward destination
- a weather disruption that makes flexibility valuable
- a crowded iconic site vs. a quieter but better-fit alternative

## Input Design Should Follow The Model

Only after the tradeoff model is defined should the app design its question flow.

That flow may still become compact, but it should be based on the above structure rather than on generic travel-site questionnaires.

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
