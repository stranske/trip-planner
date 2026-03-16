# Preference Learning Model

This document fills in the part still missing from the leisure preference design: how the system learns.

The schema in `leisure-preference-schema.md` defines what the profile looks like. This document defines how evidence should update it over time.

## Purpose

The planner should not infer preferences from one short questionnaire and then freeze them.

For longer leisure travel, the engine should:

1. collect mixed forms of evidence
2. resolve them into a working profile
3. keep track of contradictions and low-confidence areas
4. update the profile when concrete choices reveal stronger preferences

## Learning Loop

The first-pass learning loop should be:

1. capture trip frame and hard constraints
2. identify anchors and quality floors
3. collect evidence on first-tier tradeoffs and hybrid factors
4. resolve a provisional profile
5. generate or select a small number of meaningful option sets
6. learn from reactions to those options
7. update the profile, interaction activations, and tension flags

This is a rolling process, not a one-time inference.

## Evidence Families

The system should distinguish at least six evidence families.

### 1. Direct Statements

Examples:

- "I do not mind moving every few days."
- "I need one quiet week in the middle."
- "I care much more about food than museums."

Use:

- efficient early signal
- useful for anchors, hard constraints, and clearly articulated preferences

Risk:

- people often describe themselves less accurately than they choose

### 2. Forced Tradeoff Choices

Examples:

- choose between a denser route with more highlights and a slower route with fewer moves
- choose between a central smaller hotel and a larger quieter hotel farther out

Use:

- strong signal for salience
- often better than asking abstract questions directly

### 3. Scenario Reactions

Examples:

- reaction to a two-transfer scenic rail day
- reaction to an unscheduled half-day in a historic district
- reaction to a tightly booked museum-heavy city stretch

Use:

- helps distinguish hypothetical tolerance from real comfort
- useful for movement, recovery, structure, discovery, and self-reliance

### 4. Resource Allocation Choices

Examples:

- choosing to spend more on hotel location instead of room size
- choosing a premium rail segment over an extra destination

Use:

- strongest evidence for budget priorities and quality floors

### 5. Revealed Preference From Concrete Options

Examples:

- choosing one of three hotel clusters
- repeatedly preferring coherent scenic routes over cheaper fragmented routes
- favoring lively neighborhoods but selecting quieter lodging within them

Use:

- strongest signal when the system can present real alternatives
- especially useful for comfort, value, route style, food, and lodging judgments

### 6. Revision Signals

Examples:

- "Do more before asking me again."
- "Show me options sooner."
- "This is too busy."
- "I care less about scenery than I thought."

Use:

- updates both the preference profile and the interaction/autonomy settings

## Evidence Strength

Not all evidence should count equally.

The first pass should score evidence strength using:

- `explicitness`: how directly the user expressed the preference
- `specificity`: whether it applies globally or to one segment/type of place
- `tradeoff_reality`: whether the preference was tested against a real cost or sacrifice
- `repeatability`: whether the same signal appears across multiple choices
- `recency`: whether later evidence should slightly outweigh early guesses
- `conflict_penalty`: whether later evidence materially contradicts earlier evidence

Revealed preference and resource-allocation evidence should usually outrank abstract self-description when the two conflict, unless the higher-level preference is anchored or constrained explicitly.

## Preference Resolution Rules

The resolver should compute each first-tier dimension using four layers.

### 1. Direction

Infer the current `value` on the `-1.0` to `1.0` axis.

### 2. Confidence

Estimate how strongly the current directional value is supported.

Low confidence should mean:

- insufficient evidence
- contradictory evidence
- or evidence that is too segment-specific to justify a global position

### 3. Salience

Estimate how costly it would be to ignore this dimension in planning.

High salience does not always mean extreme direction. A traveler can be near the middle on a dimension but care a lot that the plan remains balanced.

### 4. Stability

Estimate how durable the preference is likely to be.

High stability means:

- likely to hold across destinations
- unlikely to be overturned by one concrete option

Lower stability means:

- exploratory preference
- context-specific preference
- or one still being learned

## Conditionality

Conditional preferences should not be forced into one global average.

The engine should infer `conditional_overrides` when:

- a preference is stronger in a specific region or segment type
- a preference matters mostly at one planning stage
- a hybrid factor becomes anchor-like only in certain contexts

Examples:

- food becomes near-anchor-level in specific culinary destinations
- elastic wandering is preferred in historic cities but not on logistics-heavy days
- scenic transit matters greatly on intercity movement days but much less inside major urban bases

## Contradiction Handling

Contradictions should be surfaced, not hidden.

The first-pass system should distinguish:

- `healthy tension`
- `conditional split`
- `true contradiction`

### Healthy Tension

Example:

- wants discovery and route coherence

This is often workable with careful design and should not be treated as failure.

### Conditional Split

Example:

- wants structured museum days in major cities but elastic wandering days elsewhere

This should become a `conditional_override`, not a contradiction.

### True Contradiction

Example:

- wants strong breadth, high recovery protection, many fixed anchors, and very low travel friction in a short trip

This should produce a `tension_flag` and force explicit tradeoff discussion.

## Revealed-Preference Updates

Concrete option choices should be able to change the profile.

But they should not overwrite everything equally.

The update order should be:

1. preserve hard constraints
2. preserve strong anchors unless the user explicitly demotes them
3. update medium-confidence tradeoff inferences readily
4. update high-stability dimensions slowly unless repeated evidence accumulates

Examples:

- one hotel click should not erase a clear quiet-lodging quality floor
- repeated selection of quieter properties in lively districts should strengthen the quiet-recovery signal
- repeated preference for scenic route options should strengthen scenic-transit salience even if the original self-description said efficiency mattered more

## Interaction And Autonomy Learning

The app should learn not only what kind of trip the user wants, but how they want the planner to work.

The interaction model should therefore track:

- `initiative_level`: how much work the system should do before returning
- `checkpoint_frequency`: how often the user wants to be asked to choose
- `example_dependence`: how much the user prefers reacting to concrete options over abstract questions
- `stage_preferences`: different autonomy preferences at initial design, inventory narrowing, daily planning, and in-trip adjustment

This should be a spectrum, not a rigid mode switch.

Examples:

- a user may want high autonomy during initial route design, but more frequent checkpoints once hotel and activity choices begin
- another user may want quick early option menus because their revealed preferences are more reliable than their verbal ones

## Recommended Immediate Deliverables

The next concrete implementation work should now be understood as:

1. formal evidence record types
2. evidence-to-dimension mapping registry
3. resolver weighting rules
4. contradiction and conditionality handling
5. revealed-preference update rules
6. interaction/autonomy state model
