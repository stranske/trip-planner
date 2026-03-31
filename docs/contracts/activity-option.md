# ActivityOption Contract

`ActivityOption` is the normalized boundary for things travelers might actively do, attend, or wander toward once a destination and broader route are known.

It keeps the main activity surfaces separate instead of collapsing them into one score:

- `category` distinguishes structured formats from open-ended exploration so a museum reservation and a wandering district can live in the same model without pretending they behave the same way.
- `timing_summary` captures duration, timing sensitivity, closure risk, crowd pressure, and weather/daylight dependencies that later day-structure work will need.
- `significance_summary` captures anchor-worthiness and destination significance separately from traveler fit.
- `effort_summary` captures physical and sensory load so itinerary pacing can reason about recovery and energy balance.
- `booking_terms` and `cost_summary` keep reservation friction and spending explicit for later assembly and policy-aware use cases.
- `quality_summary`, `value_summary`, and `fit_summary` remain separate so “important,” “worth it,” and “right for this traveler” do not collapse into a single scalar.
- `feasibility` captures seasonal, accessibility, and operational constraints.

## Usage Boundary

Use `ActivityOption` when later issues need a stable activity object for:

- day-structure and itinerary-objective derivation
- mixed option bundles that compare activities alongside transport and lodging
- ranking and explanation work that must distinguish significance, value, and traveler fit

Do not overload this contract with live ticketing integrations, final itinerary sequencing logic, or provider-specific ingestion details. Those belong in later adapter, ranking, and orchestration layers.
