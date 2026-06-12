# Effortless-Travel Roadmap (future plans)

> Status: **vision / future plans.** This document captures the ambitious, multi-month direction for
> trip-planner's leisure side so it is not lost. Near-term, few-weeks-scoped work is tracked as GitHub
> issues and the point-7 epic; the items here are deliberately *deferred* until that foundation lands.
> Detailed design lives in the audit design notes (daily-menu design, traveler-opportunities, and the
> effortless-logistics review).

## North star
Make a great-fit trip **appear to happen without planning work** — across advance planning and the
night-before / day-of. The system absorbs logistics complexity and presents the traveler only with the
few human-judgment moments (taste, trade-offs, the final "yes"). Guiding principles, drawn from how
luxury concierges and the best disruption tools achieve effortlessness:

1. **Anticipate, don't ask** — pre-handle the predictable; keep backups ready.
2. **Surface the solution, not the problem** — on any change, present the already-figured-out alternative.
3. **Prep-then-confirm, not blind autonomy** — do all the heavy lifting; keep a one-tap human "yes"
   (only ~2% of travelers trust fully-autonomous booking today).
4. **Know me once, apply everywhere** — taste/constraints auto-apply to every booking and rebooking.

## What ships near-term (tracked as issues, not here)
The point-7 *engine* and its first products: daily-menu module (deterministic), the commercial↔editorial
source-mix lever + calibration wiring, and a **book-ahead radar v0** (static "must-prebook" flagging from
a curated knowledge base — no live monitoring yet). Plus the code-quality / de-duplication / UX / planner
issues from the audit. See the point-7 epic.

## Deferred tracks (this roadmap)

### 1. The concierge layer — invisible logistics
Turns the planner from an *advisor* into something that *handles things*. Components are drawn from the
external audit design notes for effortless logistics and capacity release:
- **Proactive trip-watcher** — monitors each trip's fragile points (sell-out/lottery deadlines, flight
  disruptions, closures, weather) and surfaces the *solved* alternative, not the problem. Converts the
  reactive `trip_planner/orchestration/in_trip.py` seam into a scheduled monitor.
- **Night-before / day-of ritual** — every evening, a ready, weather/closure/energy-adjusted next-day plan
  the traveler accepts or nudges ("tomorrow is handled").
- **Prep-then-confirm booking** — assemble/hold scarce bookings via provider APIs, apply the taste profile,
  one-tap confirm. Never blind autonomy.
- **Auto-capture / unified itinerary** — import confirmations so the plan reflects reality without data entry.
- **One concierge thread that remembers** — durable cross-session/cross-trip memory; a proactive voice in
  the same thread.
*Why deferred:* requires live external integrations (booking rails, disruption feeds, email import) and
durable monitoring infrastructure — well beyond a few-weeks slice. Honors data-zone rules
(`TRIP_PLANNER_DATA_ZONE`); no real traveler data on synthetic-demo hosts.

### 2. Capacity-release intelligence
Beyond "this is scarce": *how scarcity behaves over time*, per resource, with a backup always paired.
Three archetypes (researched): scheduled returned-inventory release (e.g. Alhambra's midnight re-drop),
operator-allotment release near a cutoff (e.g. scenic-train blocks returned weeks before departure), and
**no-release** (e.g. Inca Trail — must never give false hope). Needs a per-resource knowledge base +
active monitoring (the trip-watcher) + pre-arranged backups. *Why deferred:* depends on the watcher and a
curated, maintained knowledge base + live availability polling.

### 3. Cross-trip taste graph
Persist revealed preferences across *all* a traveler's trips into a durable taste model, so each new trip
starts pre-tuned and the system stops re-asking. Foundation exists in `trip_planner/preferences/`
(`revealed_preference.py`, `resolution.py`); the deferred piece is longitudinal storage + a standing
preference set that booking/rebooking consult automatically. *Why deferred:* cross-trip data model +
privacy/retention design.

### 4. Source ingestion at scale (point-7 P2)
License-clean editorial corpus — Wikidata (CC0 join backbone) + OpenStreetMap/Overpass (POI geometry,
ODbL) + Wikivoyage/Wikipedia (editorial prose, pageview popularity, dwell-time mining). Makes the
non-commercial end of the source-mix slider real. *Why deferred:* multi-source ingestion pipelines +
license/provenance/attribution handling (ODbL share-alike, CC BY-SA, CC0) is a substantial program.

### 5. Feedback bandit (point-7 P4)
`SourceFeedbackBandit` + `SourceFeedbackEvent` folded into `orchestration/feedback.py`, re-weighting
sources from in-session thumbs (LinUCB/Thompson), with the slider as a group prior. Spike-validated
deterministically; production needs the contextual model + online learning. *Why deferred:* online
learning + evaluation harness.

### 6. In-trip day-map + token program (point-7 P5)
A day-scoped, offline-resilient map that updates as the trip progresses (`InTripTriggerEvent` → revised
menu → day map), plus the LangChain token program (digests-not-payloads, server-side menu cache,
prompt-cached preamble). *Why deferred:* depends on the watcher + the deterministic menu + offline sync.

### 7. Experience-deepening, longer-horizon
- **Exploring-together** — fair multi-traveler preference blend + smart split-and-reconverge for groups/families.
- **Trip memory / recap** — generate a keepable recap from the live map + actuals; feed it back to the taste graph.
- **Off-the-circus timing + locals/peers tier**, **follow-your-feet** in-trip nudging, **graceful deviation**
  ripple-replan — full versions (v0s of some land near-term).

## Pointers
- External audit notes, outside this repository: daily-menu design, traveler-opportunities, and
  effortless-logistics/capacity-release review notes from the `audit-tripplanner-tpp` review packet.
- Near-term work: the point-7 epic + linked issues.
