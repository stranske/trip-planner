# Product And Architecture Brief

## Product Purpose

`trip-planner` should become a dynamic travel-planning system with two first-class modes:

1. **Recreational travel**
   - Primary users: you and family members
   - Scope: worldwide
   - Goal: design coherent trips that fit traveler preferences, time, cost, travel complexity, and desired experiences
2. **Business travel**
   - Primary users: business travelers
   - Scope: start with the United States
   - Goal: build policy-aware, approval-ready plans with realistic inventory and pricing inputs

## Design Recommendation: Keep `Travel-Plan-Permission` Separate

Business-trip planning should stay in `trip-planner`, while `Travel-Plan-Permission` should remain the policy and approval system.

That boundary is cleaner for three reasons:

- `trip-planner` needs to optimize across traveler intent, inventory, maps, budgets, and itinerary coherence, which is planning logic rather than policy logic.
- `Travel-Plan-Permission` already positions itself as the approval and reimbursement layer and exposes a canonical trip-plan contract plus policy APIs.
- Keeping planning and policy enforcement separate reduces coupling to organization-specific rules and makes the leisure/business planning core reusable.

The integration model should be:

- `trip-planner` produces a versioned `TripPlanProposal`
- `Travel-Plan-Permission` evaluates policy fit, approved vendors, exceptions, and approval requirements
- `trip-planner` can then re-optimize against returned constraints

Relevant local references:

- `Travel-Plan-Permission` README
- `Travel-Plan-Permission/docs/policy-api.md`
- `Travel-Plan-Permission/schemas/trip_plan.min.schema.json`

## Product Capabilities

### 1. Preference Engine

The old repo used fixed scoring across natural, cultural, significance, and experience-bundle factors. That should become part of a broader preference model that captures:

- destination style
- activity intensity
- nature vs. culture balance
- budget sensitivity
- tolerance for transfers and travel complexity
- lodging style
- route density per day
- business constraints, when applicable

### 2. Inventory And Coherence Engine

The planner should ingest and normalize:

- flights
- hotels and other lodging
- rail
- rental cars
- public transit and local ground transport
- points of interest and activities

The system should enforce:

- time-feasible arrival/departure chains
- realistic transfer and check-in windows
- daily activity density limits
- cost ceilings and soft budget preferences
- route continuity and map-aware travel distances

### 3. Budget And Tradeoff System

Budgeting should not just total prices. It should support:

- planned vs. actual cost tracking
- tradeoff analysis
- opportunity cost of higher-comfort or lower-complexity options
- optional cost hiding for experience-first trip design
- business-policy-aware cost reasoning

### 4. Interactive Planning Layer

Use LangChain-based orchestration for:

- guided preference capture
- interactive trip revision
- explanation of tradeoffs
- policy-prep flows for business trips

LangChain should not be the whole architecture. It should sit on top of explicit tools and domain services for:

- search and source retrieval
- itinerary scoring
- budget calculation
- map/routing queries
- policy requirement assembly

### 5. Business-Travel Output

Business mode should:

- identify all data needed by a policy system
- optimize toward policy fit before export
- record vendor choices, comparables, and justification
- produce structured payloads that plug into `Travel-Plan-Permission`

## Recommended Architecture

### Frontend

Build toward a stateful web app with:

- user accounts
- saved trips
- trip comparison views
- itinerary timeline
- interactive maps
- LLM chat side panel
- business-policy readiness summary

### Core Backend Services

Organize the application into five bounded modules:

1. `preferences`
   - traveler profiles
   - trip goals
   - preference elicitation and weighting
2. `options`
   - source adapters
   - canonical flight/lodging/activity/transport records
   - vendor metadata and approval flags
3. `itinerary`
   - route assembly
   - coherence rules
   - scoring and ranking
4. `budget`
   - estimated and actual costs
   - tradeoffs
   - scenario comparison
5. `business_policy_export`
   - policy-ready proposal schema
   - compatibility with `Travel-Plan-Permission`
   - constraint feedback loop

### Supporting Services

- identity and account storage
- trip persistence
- cache for external source data
- map/geocoding/routing service
- audit trail for business plan changes
- LLM orchestration and tool execution layer

## Domain Model

The next design iteration should define explicit schemas for:

- `User`
- `TravelerProfile`
- `Trip`
- `TripMode`
- `PreferenceProfile`
- `Destination`
- `PointOfInterest`
- `TravelSegment`
- `LodgingOption`
- `TransportOption`
- `ActivityOption`
- `ItineraryDay`
- `BudgetPlan`
- `ActualSpendEvent`
- `PolicyConstraintSet`
- `TripPlanProposal`
- `PolicyEvaluationResult`

The most important near-term design decision is to define these contracts before building a larger LLM workflow. Without stable types, conversational updates will become fragile quickly.

## How The Legacy Methodology Fits

The current scoring model in [methodology.md](methodology.md) should be retained, but narrowed to a reusable subsystem:

- legacy natural/cultural/significance scoring becomes one part of leisure preference ranking
- complexity scoring becomes one part of itinerary feasibility and traveler-friction scoring
- route segments remain useful as first-class itinerary objects
- compact vs. extended itinerary generation can evolve into multi-scenario planning

## Delivery Phases

### Phase 1: Foundation

- define canonical schemas
- add user/trip persistence model
- preserve and refactor the existing scoring code into reusable modules
- stand up source-adapter interfaces

### Phase 2: Leisure MVP

- worldwide destination and activity planning
- preference capture
- itinerary ranking
- schematic map support
- budget scenarios

### Phase 3: Business MVP

- US-first
- policy-aware business mode
- approved-source filtering
- structured export to `Travel-Plan-Permission`
- approval-readiness summary

### Phase 4: Advanced Planning

- fuller interactive maps
- route menus inspired by guide-based travel design
- richer local transportation modeling
- actual-spend tracking and post-trip analysis

## Open Design Questions

These remain worth resolving in a later pass:

- whether business mode should support direct booking connections in the first production release or start with priced recommendations plus links
- how much live pricing should be cached vs. refreshed on demand
- which map/provider stack should back routing, transit, and nearby-option discovery
- whether leisure and business should share one UI shell with modes, or one platform with separate entry journeys
