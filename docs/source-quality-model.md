# Source And Quality Model

This document makes the source strategy more concrete for implementation planning.

The planner should use different source channels for different jobs, and it should not treat raw ratings as equivalent to traveler fit.

## Design Goals

The source layer should support five things:

1. real inventory where possible
2. quality and value estimation
3. curated option discovery
4. business-policy-compatible channel selection
5. revealed-preference learning from concrete option choices

## Source Categories

The first-pass source model should distinguish at least these categories.

### 1. Commercial Inventory Sources

Examples:

- hotel booking sites
- airline and airfare aggregators
- rail and car-rental booking sources
- vacation-rental platforms

Use:

- availability and pricing
- room or fare attributes
- cancellation and booking terms
- booking links

### 2. Rating And Review Sources

Examples:

- hotel review platforms
- restaurant review platforms
- traveler review communities

Use:

- perceived quality
- consistency of experience
- common failure modes
- rough value signals

### 3. Editorial And Guide Sources

Examples:

- strong editorial travel guides
- destination journalism
- route and regional overviews

Use:

- place significance
- neighborhood and route curation
- option-set building
- context beyond rating averages

### 4. Specialist And Non-Commercial Sources

Examples:

- high-quality travel blogs
- enthusiast route guides
- museum, park, and heritage sites
- local cultural calendars

Use:

- deeper or more idiosyncratic discovery
- activity menus
- niche, route-specific, or region-specific fit

### 5. Official And Operational Sources

Examples:

- railway operators
- park systems
- venue calendars
- transit agencies
- tourism boards when useful

Use:

- schedules
- closures
- operating constraints
- official visitor logistics

### 6. Managed-Travel And Policy Sources

Examples:

- business-approved booking channels
- company vendor lists
- policy and reimbursement rules

Use:

- business-travel channel restrictions
- approval readiness
- comparable requirements

## Source Record Shape

Every ingested source should expose a normalized record like:

```json
{
  "source_id": "booking_com_hotel",
  "channel_type": "commercial_inventory|ratings_reviews|editorial|specialist|official|managed_travel",
  "entity_scope": "lodging|transport|restaurant|activity|destination|mixed",
  "freshness": {},
  "commerciality": 0.9,
  "editorial_independence": 0.2,
  "geographic_coverage": "global|regional|local",
  "booking_capability": true,
  "trust_profile": {}
}
```

## Trust Signals

The system should not rely on one scalar trust score only.

Instead, the first pass should track:

- `freshness`
- `coverage_quality`
- `entity_resolution_quality`
- `review_volume`
- `review_consistency`
- `editorial_independence`
- `commercial_bias_risk`
- `operational_reliability`
- `business_approval_status` when relevant

These signals should differ by source category.

## Quality, Value, And Fit

The planner should distinguish three separate outputs.

### Quality

How strong the underlying option appears on its own terms.

Examples:

- hotel quality level
- restaurant reputation
- route scenic quality
- activity significance

### Value

How good the option appears relative to price or effort.

Examples:

- unusually strong hotel for the location and price band
- expensive but defensible splurge
- cheaper option with high friction and weak location fit

### Fit

How well the option matches this traveler and this trip.

Examples:

- a celebrated restaurant may be high quality but low fit for a low-planning-energy trip
- a scenic rail route may be high fit for one traveler and low fit for another

This is the most important distinction. Ratings help with quality. The preference engine drives fit.

## Fusion Logic

The first-pass source fusion process should be:

1. normalize entities across sources
2. filter by feasibility and policy restrictions
3. compute source confidence
4. estimate quality
5. estimate value
6. compute traveler-specific fit
7. surface uncertainty and source disagreement

The app should keep the source provenance visible so later explanations can say why an option was shown.

## Use Of Concrete Option Sets

Some of the most useful learning should happen by presenting a small number of real options.

Examples:

- 3 lodging clusters with different tradeoffs in location, quiet, room quality, and price
- 3 route alternatives trading coherence, scenic value, and move density
- 3 restaurant patterns trading convenience, value, and culinary ambition

This is important because many users reveal real preferences more clearly through choices than through abstract language.

## Source Conflicts

The first-pass model should handle source conflicts explicitly.

Examples:

- strong ratings but weak location fit
- strong editorial praise but low operational reliability
- high consumer usage but poor business approval fit

The planner should not pretend these conflicts are errors. They are often exactly what the user needs help weighing.

## Implementation Priorities

Before heavy ingestion work begins, the repo should lock:

1. source category taxonomy
2. source record schema
3. normalized quality/value/fit outputs
4. provenance requirements
5. business-approval and policy compatibility fields

The current `source-channel-strategy.md` can remain the shortlist of seed channels. This document should be treated as the behavioral model for how those channels are used.
