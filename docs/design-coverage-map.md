# Design Coverage Map

This document maps every major design commitment in `trip-planner` to source code, tests, and issue references.
It distinguishes docs-only claims from tested implementations so weekly reviews can assess real delivery status
without re-reading every design doc.

**Last updated:** 2026-05-11
**Test suite baseline:** 524 passed, 1 xfailed (was 3; two resolved by issue #1046 audit — see `tests/planner/MIGRATIONS.md`)  
**Source baseline:** 159 Python modules (~21.5 K LOC), 84 test modules (~18 K LOC), 38 TypeScript/React files

---

## Legend

| Status | Meaning |
|--------|---------|
| ✅ Implemented | Code exists and tests pass |
| 🟡 Partial | Code exists; either seeded/fixture-backed or missing test coverage |
| ❌ Missing | Docs describe it; no implementation yet |
| 🚧 Blocked | Depends on a missing or partial prerequisite |
| 📄 Docs-only | Design or contract document exists; no source file yet |

---

## 1. Domain Contracts

Design ref: [`docs/domain-contracts.md`](domain-contracts.md)

| Contract | Source | Tests | Status |
|----------|--------|-------|--------|
| `Trip` (main planning container) | `trip_planner/contracts/trip.py` | `tests/contracts/test_trip_contracts.py` | ✅ Implemented |
| `Trip.mode` (leisure / business split) | `trip_planner/contracts/trip.py` | `tests/contracts/test_trip_contracts.py` | ✅ Implemented |
| `LeisurePreferenceProfile` | `trip_planner/preferences/schema.py` | `tests/preferences/` (multiple) | ✅ Implemented |
| `BusinessTravelProfile` | `trip_planner/business/schema.py`, `business/profile.py` | `tests/business/test_business_profile.py` | ✅ Implemented |
| `Destination` (normalized place entity) | `trip_planner/contracts/destinations.py` | `tests/contracts/test_destination_contracts.py` | ✅ Implemented |
| `OptionSet` + `Option` | `trip_planner/contracts/options.py` | `tests/contracts/test_option_contracts.py` | ✅ Implemented |
| `ItineraryObjectives` | `trip_planner/contracts/objectives.py` | `tests/contracts/test_objectives_contracts.py` | ✅ Implemented |
| `LodgingOption` | `trip_planner/contracts/lodging.py` | `tests/contracts/` | ✅ Implemented |
| `TransportOption` | `trip_planner/contracts/_option_contracts.py` | `tests/contracts/test_option_contracts.py` | ✅ Implemented |
| `ActivityOption` | `trip_planner/contracts/activities.py` | `tests/contracts/` | ✅ Implemented |
| `InventoryBundle` | `trip_planner/contracts/bundles.py` | `tests/contracts/` | ✅ Implemented |
| `TripPlanProposal` (TPP export) | `trip_planner/business/policy_contracts.py`, `integrations/tpp/contracts.py` | `tests/integrations/test_tpp_contracts.py` | ✅ Implemented |
| Refs-not-inline rule (Trip references artifacts) | `trip_planner/contracts/trip.py` (`artifact_refs`) | `tests/contracts/test_trip_contracts.py` | ✅ Implemented |

All 13 root contracts from `domain-contracts.md` are implemented and tested.

---

## 2. Leisure Preference Engine

Design refs: [`docs/leisure-preference-epic.md`](leisure-preference-epic.md), [`docs/leisure-preference-engine.md`](leisure-preference-engine.md), [`docs/leisure-preference-contract.md`](leisure-preference-contract.md), [`docs/preference-learning-model.md`](preference-learning-model.md)  
Issues: `#506` (epic), `#507`–`#512`

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Leisure preference contracts + package layout (`#507`) | `trip_planner/preferences/schema.py`, `models.py` | `tests/preferences/test_preference_models.py` | ✅ Implemented |
| Evidence model (`#508`) | `trip_planner/preferences/evidence.py`, `evidence_catalog.py` | `tests/preferences/test_evidence.py` | ✅ Implemented |
| Traveler fixture corpus (`#509`) | `trip_planner/preferences/fixture_corpus.py` | `tests/preferences/test_fixture_corpus.py` | ✅ Implemented |
| Preference resolution engine (`#510`) | `trip_planner/preferences/resolution.py` | `tests/preferences/test_resolution.py` | ✅ Implemented |
| Autonomy + revealed-preference updates (`#511`) | `trip_planner/preferences/autonomy.py`, `revealed_preference.py` | `tests/preferences/test_autonomy.py`, `test_revealed_preference.py` | ✅ Implemented |
| Interaction tracking | `trip_planner/preferences/interactions.py` | `tests/preferences/test_interactions.py` | ✅ Implemented |
| Explanation generation | `trip_planner/preferences/explanations.py` | — | 🟡 Partial (no dedicated test) |
| Legacy request adapter | `trip_planner/preferences/legacy_request_adapter.py` | — | 🟡 Partial (no dedicated test) |
| Preference roadmap items (collaborative, in-trip, revealed-preference modes) | `docs/preference-roadmap.md` | — | 📄 Docs-only |

---

## 3. Business Travel Logic

Design refs: [`docs/shared-business-foundation-epic.md`](shared-business-foundation-epic.md), [`docs/business-travel-profile.md`](business-travel-profile.md), [`docs/business-travel-profile-contract.md`](business-travel-profile-contract.md), [`docs/business-objective-derivation-boundary.md`](business-objective-derivation-boundary.md)  
Issues: `#513` (epic), `#514`–`#518`

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Shared trip/option-set/itinerary-objective contracts (`#514`) | `trip_planner/contracts/` | `tests/contracts/` | ✅ Implemented |
| `BusinessTravelProfile` (`#515`) | `trip_planner/business/profile.py`, `schema.py` | `tests/business/test_business_profile.py` | ✅ Implemented |
| Policy-facing proposal + evaluation contracts (`#516`) | `trip_planner/business/policy_contracts.py`, `approval_ready.py` | `tests/business/test_approval_ready.py`, `test_policy_contracts.py` | ✅ Implemented |
| Source/provenance contracts (`#517`) | `trip_planner/sources/schema.py`, `provenance.py` | `tests/sources/` | ✅ Implemented |
| Business planning objectives (`#518`) | `trip_planner/business/objectives.py`, `objective_derivation.py` | `tests/business/test_business_objectives.py`, `test_business_derivation.py` | ✅ Implemented |
| Business scenario simulator | `trip_planner/business/simulator.py` | `tests/business/test_business_simulator.py` | ✅ Implemented |
| Business orchestration boundary | `docs/business-orchestration-boundary.md` | — | 📄 Docs-only |

---

## 4. Itinerary Planning

Design refs: [`docs/itinerary-objective-derivation-boundary.md`](itinerary-objective-derivation-boundary.md), [`docs/itinerary-scenario-assembly-boundary.md`](itinerary-scenario-assembly-boundary.md)

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Itinerary objective derivation | `trip_planner/itinerary/objective_derivation.py` | `tests/itinerary/test_objective_derivation.py` | ✅ Implemented |
| Route feasibility checking | `trip_planner/itinerary/feasibility.py` | `tests/itinerary/test_feasibility.py` | ✅ Implemented |
| Move cost calculation | `trip_planner/itinerary/move_costs.py` | `tests/itinerary/` | ✅ Implemented |
| Scenario generation | `trip_planner/itinerary/scenarios.py` | — | 🟡 Partial (used indirectly) |
| Itinerary search | `trip_planner/itinerary/search.py` | `tests/itinerary/test_itinerary_search.py` | ✅ Implemented |

---

## 5. Normalized Options and Inventory

Design ref: [`docs/normalized-inventory-contracts-epic.md`](normalized-inventory-contracts-epic.md)  
Issues: `#519` (epic), `#520`–`#524`

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Destination/place-context contracts (`#520`) | `trip_planner/contracts/destinations.py` | `tests/contracts/test_destination_contracts.py` | ✅ Implemented |
| `LodgingOption` (`#521`) | `trip_planner/contracts/lodging.py` | `tests/contracts/` | ✅ Implemented |
| `TransportOption` (`#522`) | `trip_planner/contracts/_option_contracts.py` | `tests/contracts/test_option_contracts.py` | ✅ Implemented |
| `ActivityOption` (`#523`) | `trip_planner/contracts/activities.py` | `tests/contracts/` | ✅ Implemented |
| Inventory bundles + mixed option assembly (`#524`) | `trip_planner/contracts/bundles.py`, `options/` | `tests/options/` | ✅ Implemented |

---

## 6. Data Ingestion and Candidate Generation

Design ref: [`docs/source-ingestion-epic.md`](source-ingestion-epic.md)  
Issues: `#525` (epic), `#526`–`#530`

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Source adapter + raw snapshot contracts (`#526`) | `trip_planner/sources/schema.py`, `adapters/base.py`, `snapshots.py` | `tests/sources/` | ✅ Implemented |
| Entity resolution + deduplication (`#527`) | `trip_planner/sources/resolution.py`, `dedup.py` | `tests/sources/` | ✅ Implemented |
| Lodging + transport ingestion (`#528`) | `trip_planner/ingestion/lodging_pipeline.py`, `transport_pipeline.py` | `tests/ingestion/test_lodging_pipeline.py`, `test_transport_pipeline.py` | ✅ Implemented |
| Destination + activity ingestion (`#529`) | `trip_planner/ingestion/destination_pipeline.py`, `activity_pipeline.py` | `tests/ingestion/test_destination_pipeline.py`, `test_activity_pipeline.py` | ✅ Implemented |
| Candidate generation + filtering (`#530`) | `trip_planner/candidates/generation.py`, `models.py` | `tests/candidates/test_generation.py` | ✅ Implemented |

---

## 7. Ranking and Scoring

Design ref: [`docs/ranking-route-search-epic.md`](ranking-route-search-epic.md)

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Leisure ranking | `trip_planner/ranking/leisure.py` | `tests/ranking/` | ✅ Implemented |
| Business ranking | `trip_planner/ranking/business.py` | `tests/ranking/` | ✅ Implemented |
| Ranking explanations | `trip_planner/ranking/explanations.py` | — | 🟡 Partial |
| Source quality model | `docs/source-quality-model.md` | — | 📄 Docs-only |
| Source channel strategy | `docs/source-channel-strategy.md` | — | 📄 Docs-only |

---

## 8. Persistence and Workflow State

Design refs: [`docs/accounts-persistence-workflow-state-epic.md`](accounts-persistence-workflow-state-epic.md), [`docs/persistence-architecture.md`](persistence-architecture.md)  
Issues: `#675` (epic), `#683`–`#686`

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Account registration, login, session restore (`#683`) | `trip_planner/app/routes/auth.py`, `services/auth.py`, `persistence/models/` | `tests/app/test_auth.py` | ✅ Implemented |
| DB-backed trip creation, list, detail (`#684`) | `trip_planner/app/routes/trips.py`, `state/trips.py`, `state/repositories/` | `tests/app/test_trip_routes.py`, `tests/state/test_trips.py` | ✅ Implemented |
| Saved scenario + planning-history persistence (`#685`) | `trip_planner/app/routes/scenario_history.py`, `state/scenarios.py` | `tests/app/`, `tests/state/` | ✅ Implemented |
| Planning-session + activity-log persistence (`#686`) | `trip_planner/app/routes/planner.py`, `services/planner.py`, `persistence/models/planner_memory.py` | `tests/app/test_planner_routes.py`, `tests/app/test_planner_turn_e2e.py` | ✅ Implemented |
| Alembic migrations | `trip_planner/persistence/alembic/` | CI import check | ✅ Implemented |
| Append-only scenario history | `trip_planner/state/scenarios.py` | `tests/state/` | ✅ Implemented |

---

## 9. Application Foundation (Full-Stack Runtime)

Design ref: [`docs/application-foundation-epic.md`](application-foundation-epic.md)  
Issues: `#674` (epic), `#680`–`#682`

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| FastAPI runtime + health endpoint (`#680`) | `trip_planner/app/main.py`, `routes/health.py` | `tests/app/test_health.py` | ✅ Implemented |
| React shell + live health integration (`#680`) | `frontend/src/App.tsx`, `routes/HealthPage.tsx` | `frontend/src/routes/HealthPage.test.tsx` | ✅ Implemented |
| Typed frontend API client (`#681`) | `frontend/src/api/` | `frontend/src/smoke/` | ✅ Implemented |
| Route/data-loading foundation (`#681`) | `frontend/src/router.tsx`, `routes/` | `frontend/src/router.test.ts` | ✅ Implemented |
| Full-stack local dev + CI workflow support (`#682`) | `Makefile`, `ci.yml` | `tests/test_repo_hygiene.py` | ✅ Implemented |

---

## 10. Planner Workspace Vertical Slice

Design ref: [`docs/planner-workspace-vertical-slice-epic.md`](planner-workspace-vertical-slice-epic.md)  
Issues: `#676` (epic), `#687`–`#689`

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Trip entry flow (`#687`) | `frontend/src/routes/NewTripPage.tsx`, `TripsPage.tsx` | `tests/app/test_trip_routes.py`, frontend route tests | ✅ Implemented |
| Planner side panel in workspace (`#688`) | `frontend/src/components/planner/PlannerSidePanelSurface.tsx`, `WorkspacePage.tsx` | `tests/app/test_workspace.py` | ✅ Implemented |
| Planner decisions persisted across reloads (`#689`) | `trip_planner/app/services/planner.py` (memory model), `routes/planner.py` | `tests/app/test_planner_turn_e2e.py` | ✅ Implemented |

---

## 11. Runtime Planning Services

Design ref: [`docs/runtime-planning-services-epic.md`](runtime-planning-services-epic.md)  
Issues: `#677` (epic), `#690`–`#693`

> **Implemented.** Inventory bundle assembly (`#690`), feasibility (`#691`), ranking (`#692`), and route/scenario comparison (`#693`) are now surfaced as inspectable top-level workspace payload keys: `inventory_summary`, `feasibility_summary`, `ranking`, and canonical `route_comparison`. `runtime_scenario_comparison` remains as a compatibility alias for existing clients. The former strict xfail in `test_planner_turn_surfaces_runtime_planning_services_outputs` is now a runtime payload assertion. (Issue #1102, 2026-05-07.)

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Inventory bundle assembly surfaced in workspace (`#690`) | `trip_planner/app/services/inventory.py`, `app/services/workspace.py` (top-level `inventory_summary` key, with assembled `bundles` nested inside) | `tests/app/test_inventory.py` | ✅ Implemented |
| Feasibility + move-cost evaluation in planner outputs (`#691`) | `trip_planner/app/services/feasibility.py`, `app/services/workspace.py` (top-level `feasibility_summary` key) | `tests/app/test_workspace.py` | ✅ Implemented |
| Ranking + scenario-generation services with workspace results (`#692`) | `trip_planner/app/services/scenarios.py`, `app/services/workspace.py` (top-level `ranking` key) | `tests/app/test_workspace.py`, `tests/planner/test_planner_turn_acceptance.py` | ✅ Implemented |
| Route-search + scenario-comparison in workspace (`#693`) | `trip_planner/app/services/workspace.py` (`_build_runtime_scenario_comparison`; surfaced as canonical `route_comparison` plus compatibility alias) | `tests/app/test_workspace.py`, `tests/planner/test_planner_turn_acceptance.py`, `frontend/src/routes/WorkspacePage.test.tsx` | ✅ Implemented |

**Gap:** Arbitrary persisted trips do not yet receive the same normalized inventory and scenario depth as the two seeded examples (`trip-leisure-kyoto-draft`, `trip-business-client-summit`). Tracked in live-runtime-completion epic `#753` (children `#757`–`#759`).

---

## 12. Orchestration and Interactive Planning

Design ref: [`docs/orchestration-interactive-planning-epic.md`](orchestration-interactive-planning-epic.md)  
Issues: `#543` (epic), `#544`–`#548`

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Planner-turn + workflow contracts (`#544`) | `trip_planner/orchestration/models.py`, `actions.py` | `tests/orchestration/test_orchestration_models.py` | ✅ Implemented |
| Leisure orchestration (`#545`) | `trip_planner/orchestration/leisure.py` | `tests/orchestration/test_leisure_flow.py` | ✅ Implemented |
| Feedback loops (`#546`) | `trip_planner/orchestration/feedback.py` | `tests/orchestration/test_feedback.py` | ✅ Implemented |
| In-trip replanning (`#547`) | `trip_planner/orchestration/in_trip.py` | `tests/orchestration/test_in_trip.py` | ✅ Implemented |
| Business orchestration + policy prep (`#548`) | `trip_planner/orchestration/business.py` | `tests/orchestration/test_business_flow.py` | ✅ Implemented |

---

## 13. LangChain Planner Runtime

Design ref: [`docs/langchain-planner-runtime-epic.md`](langchain-planner-runtime-epic.md)

> **Partial.** The planner runtime now has a trip-scoped conversation API, persisted session/checkpoint records, a model-backed runnable, and an explicit app-tool registry/executor. The remaining gap is no longer "no planner tools"; it is that the first-pass registry covers workspace, budget, policy, proposal, decision, feedback, and planning-notebook state, while richer source retrieval, route-provider queries, dynamic model routing, and semantic reorientation remain follow-on work.

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Planner protocol seam (configurable model) | `trip_planner/app/services/planner.py` (`PlannerChatModel`, `ModelBackedPlannerConversationRunnable`) | `tests/app/test_planner_routes.py` | ✅ Implemented |
| Trip-scoped planner session + conversation API | `trip_planner/app/routes/planner.py`, `trip_planner/app/services/planner.py` | `tests/app/test_planner_routes.py`, `tests/app/test_planner_turn_e2e.py` | ✅ Implemented |
| App-tool registry and executor | `trip_planner/app/services/planner_tools.py`, `trip_planner/app/services/planner.py` (`_execute_model_tool_calls`) | `tests/app/test_planner_routes.py` | ✅ Implemented |
| Memory and checkpoint persistence | `trip_planner/persistence/models/planner_memory.py`, `trip_planner/app/services/planner_memory.py` | `tests/app/test_planner_routes.py`, `tests/app/test_planner_turn_e2e.py` | 🟡 Partial (checkpoint and notebook memory; no semantic/vector recall) |
| Planning mode selection (delegated / collaborative / revealed-preference / in-trip) | `frontend/src/components/planner/PlanningModeSelector.tsx`, `trip_planner/app/routes/workspace.py`, `trip_planner/app/services/workspace.py` | `frontend/src/components/planner/PlanningModeSelector.test.tsx`, `frontend/src/routes/WorkspacePage.test.tsx`, `tests/app/test_workspace.py` | ✅ Implemented |
| Dynamic model routing by task complexity | — | — | ❌ Missing |
| Provider-rich planner tools (source retrieval, live routing/maps, source-quality scoring) | `trip_planner/app/services/planner_tools.py` (first-pass app tools only) | partial route/tool tests | 🟡 Partial |

**Gap detail (follow-up issue candidate):** The runtime can execute explicit planner tools and persist their traces, but it still needs a model-routing policy that distinguishes fast conversational turns from deeper synthesis, richer source/map/provider-backed tools, and semantic planner memory that can reorient when a traveler says "I was working on lodging" or "put this in the Oslo file."

---

## 14. Budget and Business Policy Execution

Design ref: [`docs/budget-business-policy-execution-epic.md`](budget-business-policy-execution-epic.md)  
Issues: `#678` (epic), `#694`–`#697`

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Budget editing + actual-spend capture (`#694`) | `trip_planner/app/routes/budget.py`, `services/budget.py`, `state/budget.py` | `tests/app/test_budget_routes.py` | ✅ Implemented |
| Policy constraint sync + approval-readiness display (`#695`) | `trip_planner/app/routes/policy.py`, `services/policy.py` | `tests/app/test_policy.py` | ✅ Implemented |
| Proposal submission + result ingestion (`#696`) | `trip_planner/app/routes/proposal.py`, `integrations/tpp/submission.py`, `results.py` | `tests/app/test_proposal.py`, `tests/integrations/test_submission.py`, `test_results.py` | ✅ Implemented |
| Reoptimization + exception-handling after policy results (`#697`) | `trip_planner/integrations/tpp/reoptimization.py` | `tests/integrations/test_reoptimization.py` | 🟡 Partial (seam implemented; live TPP call deferred) |

---

## 15. Live TPP Execution and Reoptimization

Design ref: [`docs/live-tpp-execution-reoptimization-epic.md`](live-tpp-execution-reoptimization-epic.md)

> **Blocked on live TPP transport.** All contracts and seams exist. The planner-turn → TPP round-trip (permission request → approval evidence → confirmation) is exercisable via `HTTPTPPIntegrationClient.submit_proposal` / `fetch_evaluation_result` (used by `app/services/proposal.py`); the original `test_tpp_approval_flow_round_trip_from_planner_turn` xfail was deleted by the issue #1046 audit (2026-04-30) and recorded in `tests/planner/MIGRATIONS.md`. The CI smoke test (`test_full_product_verification.py`) still auto-skips when `LIVE_TPP` config is absent.

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| TPP client + policy sync contract | `trip_planner/integrations/tpp/client.py`, `policy_sync.py` | `tests/integrations/test_policy_sync.py`, `test_canonical_state_seam.py` | ✅ Implemented |
| Proposal lifecycle + submission | `trip_planner/integrations/tpp/submission.py`, `contracts.py` | `tests/integrations/test_submission.py`, `test_tpp_contracts.py` | ✅ Implemented |
| Result ingestion | `trip_planner/integrations/tpp/results.py` | `tests/integrations/test_results.py` | ✅ Implemented |
| Planner-turn-driven approval round-trip (in-process) | `trip_planner/app/services/proposal.py` (calls `HTTPTPPIntegrationClient.submit_proposal` + `fetch_evaluation_result`) | `tests/integrations/test_submission.py`, `test_results.py`, `test_tpp_cross_repo_smoke.py` | ✅ Implemented |
| Reoptimization seam | `trip_planner/integrations/tpp/reoptimization.py` | `tests/integrations/test_reoptimization.py` | 🟡 Partial (seam only; no live round-trip) |
| Live remote TPP transport | — | `tests/integrations/test_tpp_cross_repo_smoke.py` (contract-shape only) | ❌ Missing |

**Gap detail (follow-up issue candidate):** The remote TPP call path (`integrations/tpp/client.py`) is wired to a real HTTP transport (`HTTPTPPIntegrationClient` dispatches via `urllib.request.urlopen`), but it is not yet exercised end-to-end. `test_tpp_cross_repo_smoke.py` validates the contract shape only; live round-trip coverage requires a running `Travel-Plan-Permission` instance behind the `LIVE_TPP` env config plus transport hardening (timeouts/retries/circuit breaker around the existing `urlopen` call). Tracked as a follow-on integration in `live-tpp-execution-reoptimization-epic.md`.

---

## 16. Google Maps and Frontend Visualization

Design refs: [`docs/google-maps-platform-hardening-epic.md`](google-maps-platform-hardening-epic.md), [`docs/maps-timeline-comparison-epic.md`](maps-timeline-comparison-epic.md)  
Issues: `#679` (epic), `#698`–`#700`

> **Partial.** The map adapter boundary, bounded fallback rendering, Google Maps JavaScript provider path, global/local map-scope controls, workspace timeline rendering, and scenario comparison surfaces now exist. Remaining work is mostly product depth: live provider verification in configured environments, richer regional/local geometry, deeper option-marker detail, and a dedicated source-backed timeline contract beyond the current route-sequence adapter.

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Google Maps JS adapter boundary + fallback rendering | `frontend/src/components/maps/TripMap.tsx`, `frontend/src/components/maps/mapSurface.ts` | `frontend/src/components/maps/mapSurface.test.ts`, `frontend/src/components/maps/TripMap.test.tsx`, `frontend/src/routes/WorkspacePage.test.tsx` | ✅ Implemented |
| Route-context map contract (`docs/contracts/route-context-map-target.md`) | `docs/contracts/route-context-map-target.md`, `frontend/src/components/maps/mapSurface.ts`, `frontend/src/components/maps/TripMap.tsx` | `tests/contracts/test_route_context_map_target.py`, frontend map tests | ✅ Implemented |
| Global/local map scope switching | `frontend/src/components/maps/mapSurface.ts`, `frontend/src/components/maps/TripMap.tsx` | `frontend/src/components/maps/mapSurface.test.ts`, `frontend/src/routes/WorkspacePage.test.tsx` | 🟡 Partial (global/local shipped; richer regional geometry pending) |
| Timeline view for trip structure + day sequencing (`#698`) | `frontend/src/routes/WorkspacePage.tsx` (`buildTimelineStops`, timeline section) | `frontend/src/routes/WorkspacePage.test.tsx` | 🟡 Partial (route-sequence adapter; no provider-rich per-leg timing) |
| Dedicated map surface for route + option context (`#699`) | `frontend/src/components/maps/TripMap.tsx`, `frontend/src/components/maps/mapSurface.ts` | frontend map/workspace tests | ✅ Implemented |
| Saved-scenario + trip comparison views (`#700`) | `frontend/src/components/workspace/ScenarioComparison.tsx`, `components/trips/TripComparison.tsx`, `frontend/src/routes/WorkspacePage.tsx` | `frontend/src/routes/WorkspacePage.test.tsx` | 🟡 Partial (workspace-tested; targeted component tests still thin) |
| Workspace timeline contract | `docs/workspace_timeline_contract.md`, `frontend/src/routes/WorkspacePage.tsx` | `frontend/src/routes/WorkspacePage.test.tsx` | 🟡 Partial |

**Gap detail (follow-up issue candidate):** The shipped timeline and map surfaces are good enough for workspace testing, but they still depend on route-sequence summaries and shaped scenario data rather than provider-rich timing, distance, and local-geometry outputs. The next issue should upgrade the route/timeline/map contract so a traveler can move cleanly between global trip outline, regional comparison, and precise segment review without losing context.

---

## 17. Live Runtime Completion

Design ref: [`docs/live-runtime-completion-epic.md`](live-runtime-completion-epic.md)  
Issues: `#753` (epic), `#757`–`#759`

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Persisted-trip-driven inventory assembly (`#757`) | `trip_planner/app/services/inventory.py` | `tests/app/test_inventory.py` | 🟡 Partial (seeded IDs gate still present) |
| Persisted default workspace bootstrap (`#758`) | `trip_planner/app/services/workspace.py` | `tests/app/test_workspace.py` | 🟡 Partial |
| Runtime ranking + feasibility from persisted inventory (`#759`) | `trip_planner/app/services/scenarios.py` | — | 🟡 Partial (fixture branch present) |

---

## 18. Cross-Cutting: Design Rules and Invariants

From [`docs/product-architecture-brief.md`](product-architecture-brief.md) and [`docs/implementation-plan.md`](implementation-plan.md):

| Rule | Evidence | Status |
|------|---------|--------|
| Contracts before engines before UI (delivery pattern) | Implementation plan §Working Rule | ✅ Followed throughout |
| Separate leisure + business at contract level | `preferences/schema.py` vs `business/schema.py` | ✅ Implemented |
| Audit trail (created_at, updated_at, version on mutable records) | `trip_planner/persistence/models/` | ✅ Implemented |
| Append-only scenario history | `trip_planner/state/scenarios.py` | ✅ Implemented |
| Trip references artifacts (no inlining) | `trip_planner/contracts/trip.py` (`TripArtifactRefs`) | ✅ Implemented |
| Explicit deferred seams (TPP transport, Maps key, provider-rich planner tools) | `tests/app/test_full_product_verification.py` (skip checks) | ✅ Implemented |
| Five bounded modules (preferences, options, itinerary, budget, business_policy_export) | `trip_planner/` subdirectory layout | ✅ Implemented |

---

## Summary: Remaining Follow-Up Claims

These design commitments are still missing, partial, or not yet verified in a live provider environment. Each is a candidate for a follow-up issue:

1. **Dynamic planner model routing** — `product-architecture-brief.md` §4 + `langchain-planner-runtime-epic.md`. Planning mode exists, but runtime model selection does not yet distinguish quick turns from deeper synthesis/planning turns. See §13 above.
2. **Semantic planner memory and reorientation** — planner checkpoints and notebook state exist, but there is no semantic recall/reorientation layer for scattered traveler notes and "I was working on..." context shifts. See §13 above.
3. **Provider-rich planner tools** — `planner_tools.py` exists for first-pass app state actions, but source retrieval, live routing/maps, and source-quality scoring are still not exposed as planner tools. See §13 above.
4. **Live TPP transport verification** — `live-tpp-execution-reoptimization-epic.md`. All seams exist but no live HTTP round-trip is required by the default test matrix. See §15 above.
5. **Source quality model implementation** — `source-quality-model.md` + `source-channel-strategy.md`. Design defined; no engine code.
6. **Provider-rich timeline/map depth** — workspace timeline and map surfaces exist, but still need richer regional/local geometry, per-leg timing, and live provider readiness evidence. See §16 above.
7. **Preference explanation generation tests** — `trip_planner/preferences/explanations.py` exists; no `tests/preferences/test_explanations.py`.

---

## How to Use This Map in Weekly Reviews

1. Check the **planner/runtime acceptance tests** first: `pytest -q tests/planner/test_planner_turn_acceptance.py tests/app/test_planner_routes.py tests/app/test_full_product_verification.py`.
2. The **Docs-only** rows in each section identify items that are design commitments but not yet scheduled work.
3. **Partial** rows identify items where code exists but is seeded/fixture-backed — these are the next implementation lane.
4. The **Summary: Remaining Follow-Up Claims** section lists the highest-priority gaps that should become new issues or verification tasks.
