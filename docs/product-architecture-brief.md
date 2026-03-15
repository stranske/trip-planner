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

## Product Capabilities

### 1. Leisure Preference Evaluation

The leisure side should begin with a thoughtful preference-evaluation model, not with a lightweight quiz and not with the ranking layer.

For longer independent trips, the important problem is understanding how a traveler trades off:

- depth vs. breadth
- certainty vs. openness
- comfort vs. immersion
- route ambition vs. fatigue
- iconic priorities vs. curiosity-driven discovery
- spend minimization vs. spending where it matters most

See [leisure-preference-engine.md](leisure-preference-engine.md).

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

Budgeting should support:

- planned vs. actual cost tracking
- tradeoff analysis
- opportunity cost of higher-comfort or lower-complexity options
- category-specific spending preferences
- business-policy-aware cost reasoning

### 4. Interactive Planning Layer

Use LangChain-based orchestration for:

- guided preference capture
- interactive trip revision
- explanation of tradeoffs
- policy-prep flows for business trips

LangChain should sit on top of explicit tools and domain services for:

- source retrieval
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

The business side will likely need a separate profile model and a mostly separate optimization flow.

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
2. `options`
3. `itinerary`
4. `budget`
5. `business_policy_export`

### Domain Model

The next design iteration should define explicit schemas for:

- `User`
- `TravelerProfile`
- `Trip`
- `TripMode`
- `LeisurePreferenceProfile`
- `BusinessTravelProfile`
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

## How The Legacy Methodology Fits

The current scoring model in [methodology.md](methodology.md) should be retained, but narrowed to a reusable subsystem:

- legacy natural/cultural/significance scoring becomes one part of leisure preference ranking
- complexity scoring becomes one part of itinerary feasibility and traveler-friction scoring
- route segments remain useful as first-class itinerary objects
- compact vs. extended itinerary generation can evolve into multi-scenario planning

## Delivery Phases

### Phase 1: Foundation

- define the leisure-travel tradeoff taxonomy
- define canonical preference schemas
- add user/trip persistence model
- preserve and refactor the existing scoring code into reusable modules
- stand up source-adapter interfaces

### Phase 2: Leisure MVP

- implement preference evaluation before itinerary ranking
- worldwide destination and activity planning
- itinerary ranking
- schematic map support
- budget scenarios

### Phase 3: Business MVP

- US-first
- policy-aware business mode
- approved-source filtering
- structured export to `Travel-Plan-Permission`
- approval-readiness summary
