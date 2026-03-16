# Planning Autonomy And Revealed Preference Contracts

These contracts define how later chat and orchestration layers should decide:

- how much work the planner should do before returning to the user
- how quickly concrete options should be surfaced
- how option selections and rejections should feed back into the leisure profile without erasing earlier evidence

## Planning Autonomy

`PlanningAutonomyProfile` is intentionally more granular than fixed modes.

It tracks stage-specific preferences for:

- `system_initiative`
- `checkpoint_frequency`
- `option_preview_timing`
- `exploration_depth`
- `explanation_depth`

That lets the planner handle signals like:

- "do more before asking me again"
- "show me options sooner"
- "ask me earlier when you are about to change the route"

without forcing the traveler into a binary delegated-vs-collaborative mode.

`PlannerBehaviorMetadata` is the developer-facing output that later orchestration layers should consume.

It turns the autonomy profile into concrete planning behavior such as:

- whether to ask before the next major change
- how many research passes to attempt before checking back
- how many options to gather before surfacing them
- whether options should be surfaced early
- whether the explanation style should be lean, standard, or detailed

## Revealed Preference Updates

`RevealedPreferenceSignal` represents a concrete reaction to an option or option set.

Examples:

- selected an exploratory neighborhood bundle
- rejected a hotel because arrival logistics looked fragile
- requested more options like a rail-heavy route
- ignored a one-off option without real commitment

The planner should not mutate the resolved profile directly from such reactions.

Instead, `build_revealed_preference_update()` emits new `PreferenceEvidence` plus metadata about:

- protected targets
- blocked overwrites
- transient reactions
- notes for later resolver or orchestration layers

That preserves the evidence history so the resolution engine can decide how much weight the reaction deserves.

## Guardrails

Revealed-preference updates should not silently overwrite:

- hard constraints
- anchors
- stable, high-salience tradeoff dimensions

When a reaction conflicts with a stable preference, the update should emit contradiction-style evidence and record the blocked overwrite instead of silently flipping the profile.

## Later Consumption

Later orchestration and chat layers should use these contracts in this order:

1. read `PlanningAutonomyProfile` for the current trip stage
2. derive `PlannerBehaviorMetadata` for pacing and checkpoint behavior
3. capture option reactions as `RevealedPreferenceSignal`
4. convert those reactions into `PreferenceEvidence` through `RevealedPreferenceUpdate`
5. feed the accumulated evidence back into the resolver rather than overwriting the leisure profile directly
