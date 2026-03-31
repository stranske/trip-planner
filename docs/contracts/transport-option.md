# TransportOption Contract

`TransportOption` is the normalized transport boundary for later route assembly, ranking, and policy review work.

It keeps separate the transport surfaces that often get conflated:

- `timing_summary` captures departure, arrival, total duration, and schedule-risk flags like early departures or late arrivals.
- `segments` captures the actual movement chain so flights, rail, ferries, rental cars, and local ground legs can all be represented without flattening away transfers.
- `transfer_burden` captures traveler-friction signals such as transfer count, self-navigation burden, baggage complexity, and connection risk.
- `experience_summary` captures scenic, comfort, privacy, and workability value so transport can be evaluated as part of the trip experience rather than only as logistics.
- `policy_summary` and `booking_terms` capture approved channels, class-of-service expectations, comparable references, and approval posture for business use cases.
- `feasibility` captures availability, accessibility, and operational constraints.

This distinction is intentional. A transport option can be the easiest, cheapest, or best-fit choice without those being the same thing.

## Usage Boundary

Use `TransportOption` when later issues need a stable transport object for:

- route comparison and explanation work that needs normalized movement records
- mixed option bundles that compare transport alongside lodging or activities
- business-trip proposal packaging where a selected transport choice needs policy-ready evidence

Do not overload this contract with live provider APIs, ranking logic, or provider-specific pricing internals. Those belong in adapters or downstream scoring layers, while this contract remains inspectable and mode-agnostic.
