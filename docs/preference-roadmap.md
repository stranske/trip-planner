# Preference Roadmap

This roadmap revises the earlier issue sequence so that **preference evaluation** comes before questionnaires, constraint scoring, and ranking.

## Recommended Issue Order

### 1. Define The Leisure Travel Tradeoff Taxonomy

Goal:

- document the major tradeoffs the planner must understand for serious independent leisure travel over two to six weeks

Acceptance criteria:

- each tradeoff is named, defined, and distinguished from nearby dimensions
- the taxonomy covers route shape, movement, comfort, certainty, budget philosophy, day structure, and fatigue
- first-tier dimensions are explicitly prioritized
- hybrid factors that can act as either anchors or tradeoff dimensions are modeled correctly
- major interaction effects between dimensions are identified
- contradictions and conditional preferences are accounted for

### 2. Define `LeisurePreferenceProfile`

Goal:

- create the canonical schema for the leisure preference model

Acceptance criteria:

- schema includes trip frame, hard constraints, tradeoff vectors, conditional rules, and tension flags
- each field has a clear downstream use
- the model supports confidence and stability values
- the schema can represent when a normally secondary factor has been elevated into anchor-level importance

### 3. Define The Evidence Model

Goal:

- specify what kinds of user input count as strong evidence for each preference dimension

Acceptance criteria:

- the design distinguishes direct statements, tradeoff choices, scenario responses, and resource-allocation choices
- each major dimension has at least two evidence paths
- the evidence model can distinguish general preference from anchor-level priority

### 4. Define Preference Resolution Logic

Goal:

- define how the engine turns mixed evidence into a stable profile

Acceptance criteria:

- rules exist for weighting evidence
- interaction effects can influence the resolved profile
- contradictions are surfaced rather than hidden
- conditional preferences can override global tendencies when relevant
- low-confidence output is represented explicitly

### 5. Design The Leisure Input Flow

Goal:

- design the prompt/question flow after the model exists

Acceptance criteria:

- the flow is based on the tradeoff model, not on generic travel questionnaires
- the flow collects strong evidence efficiently

### 6. Define Constraint Evaluation

Goal:

- separate hard feasibility checks from soft preferences

Acceptance criteria:

- hard constraints are evaluated independently from ranking
- the system can distinguish infeasible plans from merely poor-fit plans

### 7. Map Preference Profiles To Planning Objectives

Goal:

- translate `LeisurePreferenceProfile` into route and itinerary objectives

Acceptance criteria:

- the system can derive target base count, movement density, day elasticity, budget allocation strategy, and comfort targets
- output is explainable and inspectable

### 8. Build The Initial Ranking Algorithm

Goal:

- rank itinerary candidates against derived planning objectives

Acceptance criteria:

- the algorithm is explicitly downstream from preference evaluation
- ranking reasons can be exposed to the user

### 9. Define `BusinessTravelProfile` Separately

Goal:

- design the business-travel preference and policy profile as its own model

Acceptance criteria:

- the business model does not depend on leisure assumptions
- policy fit, justification, and approved channels are first-class concerns

## Immediate Focus

The design is now far enough along to move from schema-only work into learning and contract-definition work:

- define the evidence model and learning loop for leisure preferences
- define contradiction handling and conditional overrides
- define interaction and autonomy controls as part of the preference engine
- lock the core domain contracts needed before itinerary and source work expands
- keep `BusinessTravelProfile` separate while shared infrastructure is still being designed
