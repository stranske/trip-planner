# Provider Sources: identification, search, and integration

Status: plan, 2026-09-21. Supersedes the brand shortlist in
[`source-channel-strategy.md`](./source-channel-strategy.md), which names desirable
channels but never asked whether any of them can be obtained.

Companion to [`PRODUCT_CONTRACT.md`](./PRODUCT_CONTRACT.md) and to the rule established in
PR #1829: **a price may only come from a source.** That rule is why the product currently
shows no prices. This plan is how prices come back.

---

## 0. The headline, stated plainly

**None of the five named sources can be obtained by this project as it stands.** Not one.
Google Flights, Kayak, Booking.com, Travelocity and the US airline sites are all either
closed to programmatic access entirely, or gated behind a signed commercial contract that
presupposes a travel business this project is not.

That is not a reason to stop. It is a reason to aim one layer down. Those five are
*consumer front-ends*. What we actually want is the **content they display**, and that
content is sold by the layer underneath them — where self-serve access does exist, today,
without a contract.

The plan therefore has two tracks that run at once:

- **Track A — get real prices flowing now**, from the sources that will actually answer a
  request from us, plus the human override that always wins.
- **Track B — record precisely what each named source would require**, so "we want
  Booking.com" becomes a known cost with a known gate rather than an open wish.

---

## 1. Access reality for the five named sources

| Source | Programmatic access | The specific gate | Realistic route to its content |
|---|---|---|---|
| **Google Flights** | **None.** No public API. QPX Express was retired in 2018 and never replaced; Google's Travel APIs are for hotel/flight *advertisers*, not itinerary building. | Google operates its own first-party agent and offers no agent access. | Paid scraping-as-a-service resellers (SerpApi, SearchAPI, HasData) return literal Google Flights results as JSON. See §4, tier 3 — these are **display prices, not quotable fares**. |
| **Kayak** | **None for our purpose.** Metasearch with an affiliate/partner program; no open agent access. | Kayak is itself a metasearch aggregator — it resells others' content and does not license it onward to us. | Skip. Kayak's underlying content is the GDS/NDC layer we can reach directly. |
| **Booking.com** | **Partner-gated.** The Demand API requires Managed Affiliate Partner status, a signed contract, and Account-Manager-enabled Partner Centre access before sandbox *or* production credentials are issued. Partner registration has been reported paused pending revised connectivity terms, and there is a separate written approval requirement for AI-agent use. | A signed commercial contract with a legal entity, plus a business case. Booking's Orders endpoints need a further "Search, Look & Book" approval. | **LiteAPI / RateHawk / Expedia Rapid carry overlapping hotel inventory.** LiteAPI is self-serve today (§4, tier 1). |
| **Travelocity** | **None — the brand has no API.** Travelocity is an Expedia Group retail brand. The programmatic product is Expedia Group B2B / Rapid. | Expedia Rapid is contract-required, partner-gated. An official Expedia MCP server is signalled for late 2026 but is not generally available. | Treat "Travelocity" as "Expedia inventory" and revisit when Expedia's agent surface opens. Not a near-term dependency. |
| **Major US airline sites** (United, American, Delta, Southwest, Alaska, JetBlue) | **Partner-gated per carrier.** NDC Direct Connect requires a corporate distribution or agency relationship — United routes requests through its corporate distribution desk, American through its Direct Connect programme — and IT providers supplying NDC solutions generally need IATA accreditation. | Per-airline commercial agreement, times six. This is the single most expensive item on the page and the least likely to pay off. | **Duffel aggregates 300+ airlines over NDC including the US majors, under one self-serve account, and acts as merchant of record so no IATA/ARC accreditation is needed.** This is the whole reason Duffel exists. See §4, tier 1. |

**Scraping the named sites directly is out of scope and should stay out of scope.**
It violates their terms, breaks without notice, and — most damaging for this product —
produces figures we cannot attribute or stand behind in an approval packet. The entire
point of PR #1829 was that an unattributable number is worse than no number.

### A correction worth knowing about

**Amadeus Self-Service was decommissioned on 2026-07-17.** Registration for new users was
paused in spring 2026 and existing API keys were disabled on that date; only the Enterprise
portal (contract-required) survives.

This matters because Amadeus Self-Service was for years *the* answer to "free flight and
hotel API with self-signup", and a large amount of still-live tutorial content — including
one of the 2026 agent-API roundups consulted while writing this plan — continues to list it
as an available option. Any plan or issue that reaches for `AMADEUS_API_KEY` is working from
stale information. Recorded here so we do not spend a cycle discovering it.

---

## 2. What we actually need from a source

Worth being precise, because it is narrower than "booking" and that narrowness is what
makes the problem tractable.

trip-planner produces **an approval request**, not a reservation. The traveller takes the
packet to their employer; the employer approves; the booking happens elsewhere, usually
through the employer's own managed-travel channel. So the product needs:

1. **A quotable figure** — what this leg would cost, on these dates, for this party.
2. **Attribution** — who said so, captured when.
3. **A staleness bound** — how long that figure can be relied on.
4. **A link back** — so an approver can check it.

It does **not** need: inventory holds, seat maps, payment, ticketing, or PNR servicing.
Dropping those removes most of the accreditation burden and most of the cost, and it is why
a search-only tier is sufficient for the entire near-term roadmap.

> **Design consequence.** A source that can only *search* is fully useful to us. That
> reopens several doors that look closed when read as booking problems.

---

## 3. Selection criteria

A source is a candidate when it satisfies all four:

- **C1 — obtainable.** Self-serve signup, or a gate we can actually pass. Named, not assumed.
- **C2 — real.** Returns live prices for real inventory. **Sandbox data does not qualify**
  (see the trap in §5).
- **C3 — attributable.** Supplies a provider identity, a capture timestamp, and a validity
  window we can print next to the figure.
- **C4 — permitted.** Terms of service allow programmatic access by software acting for a
  traveller. Where terms require explicit AI/agent approval, we have it or we do not use it.

Sources are then ranked by coverage, cost-per-search, and whether the traveller's employer
is likely to accept the figure — a corporate approver trusts a fare from a recognised
distributor more than a scraped screenshot, and that acceptance is the actual product goal.

---

## 4. The source tiers

### Tier 1 — obtainable now, self-serve, no contract

These are the ones to build against. Each is one signup away.

| Source | Covers | Access | Cost | Notes |
|---|---|---|---|---|
| **LiteAPI (Nuitée Connect)** | Hotels — 2–3M properties | **Self-serve sandbox key, no credit card.** | Free sandbox; commission/markup model live | Explicitly built for agents: MCP server, `llms.txt`, OpenAPI, low-token responses. **Best first integration** — lodging is the largest cost line in a business trip and the easiest source to obtain. |
| **Duffel** | Flights — 300+ airlines over NDC, incl. US majors | **Self-serve test token immediately; live mode after account verification + commercial terms.** | ~$3 per confirmed order, 1% of order value on Managed Content, search fee ~$0.005 beyond a 1,500:1 search-to-book ratio | **Merchant of record — removes the IATA/ARC accreditation requirement.** This is the realistic answer to "each major US airline site". ⚠️ Test mode returns synthetic *Duffel Airways* data — see §5. |
| **Amtrak GTFS** | US rail **schedules** | **Public file, no signup.** `content.amtrak.com/content/gtfs/GTFS.zip` | Free | 60 routes, 436 locations (US + Canada, rail and Thruway bus). Schedules and stations only — **no fares, no GTFS-realtime**. See §7. |
| **Travelpayouts** | Flight price *data* (cached) | Self-serve affiliate | Free / commission | Useful as a cross-check and for "is this fare normal", **not** as a quote — cached prices fail C2's spirit even though they are real. Label accordingly. |

### Tier 2 — obtainable with effort, worth it later

- **Expedia Group B2B (Rapid)** — contract-required; carries the Travelocity/Expedia
  inventory; an agent-facing MCP surface is signalled for late 2026. Revisit when it opens.
- **RateHawk / Hotelbeds / WebBeds** — bedbank net rates, partner agreements. Deeper and
  cheaper hotel content than retail APIs; worth it only at volume.
- **Sabre / Travelport** — full GDS, agency relationship required. Both have launched agent
  surfaces. This is where corporate-acceptable fares live, and it is the natural end state
  for a business-travel product — but it is a company-scale commitment, not a sprint.

### Tier 3 — obtainable but constrained, use with an explicit label

- **SerpApi Google Flights** (and SearchAPI, HasData equivalents) — paid per search,
  returns literal Google Flights results including price insights and booking options.
  A US court dismissed Google's DMCA claims against SerpApi in July 2026, which improves
  but does not settle the legal picture; the target site's terms still apply.

  **This is the only honest route to the specific thing that was asked for.** If we use it,
  the figure must be labelled in the UI and in the packet as a *published display price
  observed on Google Flights at <timestamp>*, never as a quote. That distinction is not
  pedantry — an approver who books against it and finds a different price has been misled
  by us.

### Tier 4 — closed. Do not build, do not plan around

Kayak · Booking.com direct · Travelocity direct · airline-site scraping · any community
"Delta MCP" / "Marriott MCP" repository (unsanctioned, ToS-violating, breaks without notice).

Each gets a row in the source registry with `business_approval_status: disallowed` and the
specific reason, so that the next person to ask "why aren't we using Booking.com?" gets an
answer from the code instead of re-running this research.

---

## 5. The sandbox trap — the most important constraint in this plan

Duffel test mode returns offers from a fictional carrier, *Duffel Airways*, with
unrealistic schedules and prices. LiteAPI's sandbox likewise returns non-bookable rates.

**A sandbox quote wired through the current `PriceSource` contract would arrive labelled
`kind="provider"`, attributed to a real company, with a real timestamp — and be entirely
fictional.** That is the exact failure PR #1829 was built to prevent, reintroduced through
the front door and wearing a badge.

Every previous round of this defect survived because the fabricated figure *looked correct
on screen*. A sandbox figure looks more correct than any of them.

**Rule: an adapter running against a sandbox or test credential must not construct a
`SourcedPrice` at all.** It emits an `AdapterIssue` (`stage="availability"`,
`code="sandbox_credential"`) and the leg stays unpriced. No new `SourceKind` is added —
adding a `sandbox` kind would create a third way for a fake number to reach a screen, and
there must not be a third way. Sandbox mode is for exercising request shape, pagination,
error handling and normalisation; it is never for populating a figure.

This is enforced by test, not by discipline: see the test gate in §9.

---

## 6. Integration — the seam already exists

This is the encouraging part. The architecture for provider sources was built; it was
simply never connected to anything. Concretely:

| Component | File | State |
|---|---|---|
| Adapter interface | `trip_planner/sources/adapters/base.py` | **Exists.** `fetch_snapshot(SourceQuery) -> RawSnapshot`, `build_handoff(...) -> NormalizationHandoff` |
| Snapshot contracts | `trip_planner/sources/snapshots.py` | **Exists.** `SourceQuery`, `RawSnapshot`, `RawSourceRecord`, `AdapterIssue` — including `expires_at` and per-issue severity/retriable |
| Source registry model | `trip_planner/sources/models.py` | **Exists.** `SourceRecord` already carries `business_approval_status` |
| Approval vocabulary | `trip_planner/sources/schema.py` | **Exists.** `BUSINESS_APPROVAL_STATUSES = (unknown, approved, preferred, restricted, disallowed)` |
| Live-fetch capability | `trip_planner/sources/schema.py` | **Declared and used by nothing.** `"fetch_live"` appears exactly once in the repo — in the constant that defines it |
| Transport ingestion | `trip_planner/ingestion/transport_pipeline.py` | **Exists**, already accepts `option_kind ∈ {flight, rail, car}` |
| Lodging / activity / destination ingestion | `trip_planner/ingestion/` | **Exists** |
| Entity resolution, dedup, provenance, quality | `trip_planner/sources/` | **Exists** |
| Price + provenance terminus | `trip_planner/pricing/` | **Exists** (PR #1829) |
| **Any adapter that makes a network call** | — | **Does not exist.** The only adapters are a fixture reader and a deep-link capturer. |

So this is not a greenfield build. It is filling one declared, empty socket:
`RawSnapshot` in, real HTTP behind it.

### Two contract gaps to close first

**Gap 1 — `business_approval_status` is decorative.** Nothing reads it. A source marked
`disallowed` can currently produce a price identically to one marked `preferred`. Enforce
it at price construction: a `SourcedPrice` may only be built from a source whose registry
status is `approved` or `preferred`. This is the "way to approve sources" that was asked
for, and most of it is already written.

**Gap 2 — a price has no expiry.** `SourcedPrice` records `captured_at` but nothing else;
`RawSnapshot` already has `expires_at` and it is dropped on the way through. Fares go stale
in hours. An approval packet printing a three-week-old fare as current is a new flavour of
the same untruth. Add `expires_at` to `PriceSource`, carry it from the snapshot, and have
every surface that renders a price render its age beside it.

### Data flow, end to end

```
SourceQuery                  built from the trip (origin, destination, dates, party)
  │
  ▼
<Provider>Adapter.fetch_snapshot()        ← the new code: HTTP, auth, retry, rate limit
  │                                          sandbox credential ⇒ AdapterIssue, no price
  ▼
RawSnapshot(records=[RawSourceRecord], issues=[...], expires_at=...)
  │
  ▼
ingest_transport_snapshot / ingest_lodging_snapshot        ← exists, unchanged
  │   entity resolution · dedup · provenance
  ▼
TransportOption / LodgingOption  with  SourcedPrice(amount, currency, PriceSource)
  │                                       ← registry status checked here
  ▼
candidates → ranking → itinerary → bundles                 ← exists, unchanged
  │
  ▼
workspace view model → Compare / Budget / Policy tabs → approval packet
```

Everything from `ingest_*` rightwards already works. The new code is one adapter per
provider plus the two contract gaps.

---

## 7. Trains

Rail deserves its own treatment because its economics are the opposite of air: **schedules
are freely and openly available, and fares are the hard part** — the reverse of flights,
where a single account gets both.

> *Note: the instruction that opened this workstream was cut off mid-sentence at "do a step
> to address train options, with…". The constraint after "with" has not been applied. This
> section covers rail generally; say what the missing constraint was and it will be folded in.*

### 7a. US rail — schedules now, fares by override

Amtrak publishes **no public API**. It does publish a standard GTFS schedule feed
(`content.amtrak.com/content/gtfs/GTFS.zip`), mirrored by the Mobility Database and
Transitland. Verified against the Mobility Database listing on 2026-09-21: **60 routes,
436 locations across the US and Canada, covering both rail and Amtrak Thruway bus service,
valid 2026-09-20 → 2027-09-20, last fetched 2026-09-21, validation report clean.** No
GTFS-realtime feed is published alongside it, so there is no live delay or disruption data.

What that gets us, with no signup and no cost:

- real station lists and real service patterns
- real departure and arrival times and real journey durations
- correct answers to "is there a train between these two cities at all", which the planner
  currently cannot answer for anywhere on Earth
- rail legs that are genuinely comparable to flight legs on **time**, if not yet on price

What it does not get us: fares. Under the §0 rule the rail leg is therefore **planned and
timed but unpriced** — and that is a legitimate, honest product state, not a failure.
The traveller supplies the fare via the human override, exactly as they would for any
figure they hold and we do not.

This is the cheapest real win available anywhere in this plan: a free static file turns a
mode the product cannot currently plan at all into one it plans correctly.

### 7b. European rail

- **Deutsche Bahn** and **SNCF** publish open developer APIs and GTFS feeds — schedules,
  real-time positions, delays, station metadata. Self-serve.
- **Trainline Partner Solutions** (270+ operators, 45 countries) and **SilverRail** are the
  real fare-and-ticketing layer. Both are partner-gated; SilverRail's documentation is not
  public and rail distribution still leans on legacy SOAP. Sabre and Travelport both resell
  Trainline content, so a future GDS relationship would bring European rail fares along
  with it rather than needing a separate deal.

### 7c. Rail integration

No new pipeline. `ingest_transport_snapshot` already accepts `option_kind="rail"`, and
`TRANSPORT_KINDS` already includes it. A GTFS adapter emits `RawSourceRecord`s of
`payload_type="gtfs_trip"` with `SourceQuery.option_kind="rail"` and no price component;
everything downstream is unchanged.

One genuinely new behaviour is needed: **the comparison surfaces must be able to rank a
priced flight against an unpriced train without either silently winning.** Today's ranking
assumes every option has a cost. A train that beats a flight on time and is simply unknown
on price must be shown as such rather than dropped or defaulted to zero — a defaulted-zero
train would be the cheapest option in every comparison, which is the fabrication defect
inverted.

### 7d. Rental cars

Same gating as hotels and worse coverage self-serve; no tier-1 option. Deferred. Ground
transfers stay unpriced with manual override until a tier-2 supplier relationship exists.

---

## 8. Sequencing, and what each step costs *you*

Ordered so the product is usable at work as early as possible.

### Phase 0 — no signup, no key, no provider (do this first)

The app becomes usable **without a single provider integration**, because the human
override already exists in the backend and has no UI.

1. **Manual price entry in the Budget tab**, wired to the existing
   `trip_planner.pricing.manual_override`. The traveller looks up their own fares — in
   Google Flights, in their corporate booking tool, wherever they normally look — and types
   them in. Attributed to them by name, timestamped, printed in the packet as such.
2. **Every unpriced figure states why it is unpriced and what would price it.** Not "—",
   but "no priced source for this leg · enter a figure, or connect a lodging source".
   *(This is the standing latched-gate rule: report the blocking quantity and the drainable
   quantity in the same place. A surface that goes silent when it cannot price is
   indistinguishable from one that is broken.)*
3. **Enforce `business_approval_status`** at price construction (Gap 1), and seed the
   registry with every source in §4 including the tier-4 rows and their reasons.
4. **Add `expires_at`** to `PriceSource` and render price age everywhere (Gap 2).

**Your time: zero.** No accounts, no keys, no decisions.
**Result: a traveller can plan a trip, enter real figures they already have, and print an
approval packet in which every number is attributed and true.** That is the product,
working, with no provider at all — and it is the answer to "what prevents my using the app
at work right now".

### Phase 1 — hotels live

Sign up for a LiteAPI sandbox key, then a live key. **~10 minutes, no credit card.**
Build `LiteApiLodgingAdapter`. Lodging is the largest line item on a business trip and this
is the least-gated source in the entire landscape.

### Phase 2 — flights live

Duffel. **~10 minutes for a test token; ~30–60 minutes and one business decision for live
mode** (account verification and commercial terms — a real decision about what entity is
transacting, not a dev task, and worth pausing on).

Build `DuffelFlightAdapter` against test mode for shape, then switch. §5 applies with full
force here.

### Phase 3 — trains

Amtrak GTFS adapter. **Your time: zero** — it is a public file.
Then DB/SNCF for Europe if wanted.

### Phase 4 — the Google Flights question, optionally

SerpApi Google Flights as a clearly-labelled comparison source. **Your time: ~10 minutes
plus a paid plan.** Only worth doing if seeing the same figure the traveller sees on Google
matters more than having a figure we can stand behind — they are different goals and this
serves the first.

### Human-involvement budget

Per the standing rule, computed rather than assumed:

| | One-off | Recurring |
|---|---|---|
| Phase 0 | 0 min | 0 |
| Phase 1 | ~10 min (one signup) | 0 |
| Phase 2 | ~10 min + ~45 min live verification | 0 |
| Phase 3 | 0 min | 0 |
| Phase 4 | ~10 min + a paid plan | 0 |
| **Total to a fully-sourced product** | **~75 minutes, one-off** | **~0/week** |

Recurring load is zero by construction: the source registry ships pre-populated in code and
is edited only when a source is added — under four times a year on any realistic path. Key
rotation is annual at most.

**Explicitly ruled out**, because each would fail the budget and create a backlog that
grows with usage:

- a per-trip "approve this source" prompt
- a review queue of unpriced legs awaiting attention
- any approval step that blocks a traveller mid-plan

Source approval is a *standing* property of a source, decided once, enforced automatically.
The human override is always available and never requires anyone's approval but the
traveller's own.

---

## 9. Test gates

Every phase carries a gate that fails when the fabrication defect returns. Each is proven by
deliberate break and revert before the phase may be called done.

1. **Varying-input probe, three axes.** Same trip, changed destination → figures move. Same
   trip, changed party size → figures move. Same trip, changed dates → figures move. The
   third axis is new: it is the one a flat per-night rate passes and a real fare cannot fake.
2. **Sandbox cannot price.** An adapter given a test credential produces zero `SourcedPrice`
   objects and at least one `AdapterIssue` with `code="sandbox_credential"`.
   *Break: let the sandbox path construct a price. The gate must fail.*
3. **No key, no price, and the UI says why.** With no provider configured, every surface
   renders an explicit unpriced state naming what would resolve it. Never a blank, never a
   zero, never a silent omission.
4. **Disallowed source cannot price.** A `SourceRecord` with `business_approval_status` in
   `{unknown, restricted, disallowed}` raises `UnsourcedPriceError` at price construction.
5. **No rate constants.** The existing scan of `trip_planner/app/services/inventory.py` for
   uppercase names containing `COST`/`RATE`/`ALLOWANCE` stays green, extended to every new
   adapter module.
6. **Unpriced options survive ranking.** A rail option with no price is neither dropped from
   comparison nor treated as zero-cost.
7. **Stale prices are visibly stale.** A `SourcedPrice` past its `expires_at` renders with
   its age and does not appear in a packet as a current figure.

Gate 5 is the one that caught a worthless test gate earlier in this work: an assertion on an
internal helper stayed green when the product was reverted to flat constants. **Every gate
above asserts on the served payload or the rendered surface, never on an internal function.**

---

## 10. What this does not solve

Stated so it is not discovered later as a surprise.

- **Corporate acceptability.** A Duffel or LiteAPI figure is real, but an employer's travel
  policy may only recognise fares from its own managed channel. Making the packet acceptable
  to a *specific* employer is a Travel-Plan-Permission concern and a tier-2/3 GDS question,
  not solved here.
- **Booking.** Nothing in this plan books anything. The packet is an approval request; the
  reservation happens elsewhere. Adding booking changes the regulatory picture substantially
  and should be a separate decision.
- **Coverage gaps.** No self-serve source covers every route, every property and every
  operator. The unpriced state is permanent infrastructure, not a temporary scaffold —
  it must be as well-designed as the priced one.
- **Ancillaries.** Bags, seats, resort fees, and taxes vary by fare and are frequently
  excluded from headline figures. An approval packet that understates the true cost is its
  own defect; scope this explicitly when the first adapter lands.

---

## Sources consulted

- Amadeus Self-Service decommissioning — PhocusWire, 2026
- Duffel documentation: test mode, getting started, pricing
- LiteAPI / Nuitée Connect documentation: sandbox key, agentic overview
- Booking.com Partnerships Hub and Demand API developer documentation
- Expedia Group Developer Hub, AI solutions
- United for Business and American Airlines Direct Connect NDC programme pages
- IATA Developer Portal, NDC accreditation
- Amtrak GTFS feed via Mobility Database and Transitland
- Trainline Partner Solutions; SilverRail documentation portal
- SerpApi Google Flights API documentation; reporting on the July 2026 dismissal of
  Google's DMCA claims
- Agent-oriented travel API surveys, 2026 (Levelfare, AltexSoft, Skift, Phocuswire) —
  noting that several still list Amadeus Self-Service as available and are stale on that point
