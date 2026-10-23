# Design Coverage Map

This document maps every major design commitment in `trip-planner` to source code, tests, and issue references.
It distinguishes docs-only claims from tested implementations so weekly reviews can assess real delivery status
without re-reading every design doc.

**Bounded claim review:** 2026-10-19 at `4f78d2d1a`; [execution receipt](evidence/issue-1908-coverage-map.md).

**Historical May baseline (not rerun):** 2026-05-11
**Historical test suite baseline:** 976 passed, 1 xfailed (issue #1163 added 24 source-quality and explanation-builder tests)
**Historical source baseline:** 161 Python modules (~22 K LOC), 86 test modules (~18.5 K LOC), 38 TypeScript/React files

---

## Legend

| Status | Meaning |
|--------|---------|
| ✅ Implemented | Implementation and cited test paths exist; execution is limited to the dated receipts below, never implied by path existence |
| 🟡 Partial | Code exists; either seeded/fixture-backed or missing test coverage |
| ❌ Missing | Docs describe it; no implementation yet |
| 🚧 Blocked | Depends on a missing or partial prerequisite |
| 📄 Docs-only | Design or contract document exists; no source file yet |

---

## 1. Domain Contracts

Design ref: [`docs/domain-contracts.md`](domain-contracts.md)

| Contract | Source | Tests | Status |
|----------|--------|-------|--------|
| `Trip` (main planning container) | `trip_planner/contracts/trip.py` | `tests/contracts/test_trip.py` | ✅ Implemented |
| `Trip.mode` (leisure / business split) | `trip_planner/contracts/trip.py` | `tests/contracts/test_trip.py` | ✅ Implemented |
| `LeisurePreferenceProfile` | `trip_planner/preferences/schema.py` | `tests/preferences/` (multiple) | ✅ Implemented |
| `BusinessTravelProfile` | `trip_planner/business/schema.py`, `trip_planner/business/profile.py` | `tests/business/test_profile.py` | ✅ Implemented |
| `Destination` (normalized place entity) | `trip_planner/contracts/destinations.py` | `tests/contracts/test_destination_contracts.py` | ✅ Implemented |
| `OptionSet` + `Option` | `trip_planner/contracts/options.py` | `tests/contracts/test_options.py` | ✅ Implemented |
| `ItineraryObjectives` | `trip_planner/contracts/objectives.py` | `tests/contracts/test_objectives.py` | ✅ Implemented |
| `LodgingOption` | `trip_planner/contracts/lodging.py` | `tests/contracts/` | ✅ Implemented |
| `TransportOption` | `trip_planner/contracts/options.py` | `tests/contracts/test_options.py` | ✅ Implemented |
| `ActivityOption` | `trip_planner/contracts/activities.py` | `tests/contracts/` | ✅ Implemented |
| `InventoryBundle` | `trip_planner/contracts/bundles.py` | `tests/contracts/` | ✅ Implemented |
| `TripPlanProposal` (TPP export) | `trip_planner/business/policy_contracts.py`, `trip_planner/integrations/tpp/contracts.py` | `tests/integrations/test_tpp_contracts.py` | ✅ Implemented |
| Refs-not-inline rule (Trip references artifacts) | `trip_planner/contracts/trip.py` (`artifact_refs`) | `tests/contracts/test_trip.py` | ✅ Implemented |

All 13 root contracts retain implementation/test references; only the bounded execution receipt below is a current test-run claim.

---

## 2. Leisure Preference Engine

Design refs: [`docs/leisure-preference-epic.md`](leisure-preference-epic.md), [`docs/leisure-preference-engine.md`](leisure-preference-engine.md), [`docs/leisure-preference-contract.md`](leisure-preference-contract.md), [`docs/preference-learning-model.md`](preference-learning-model.md)  
Issues: `#506` (epic), `#507`–`#512`

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Leisure preference contracts + package layout (`#507`) | `trip_planner/preferences/schema.py`, `trip_planner/preferences/models.py` | `tests/preferences/test_models.py` | ✅ Implemented |
| Evidence model (`#508`) | `trip_planner/preferences/evidence.py`, `trip_planner/preferences/evidence_catalog.py` | `tests/preferences/test_evidence.py` | ✅ Implemented |
| Traveler fixture corpus (`#509`) | `trip_planner/preferences/fixture_corpus.py` | `tests/preferences/test_fixture_corpus.py` | ✅ Implemented |
| Preference resolution engine (`#510`) | `trip_planner/preferences/resolution.py` | `tests/preferences/test_resolution.py` | ✅ Implemented |
| Autonomy + revealed-preference updates (`#511`) | `trip_planner/preferences/autonomy.py`, `trip_planner/preferences/revealed_preference.py` | `tests/preferences/test_autonomy.py`, `tests/preferences/test_revealed_preference.py` | ✅ Implemented |
| Interaction tracking | `trip_planner/preferences/interactions.py` | `tests/preferences/test_interactions.py` | ✅ Implemented |
| Explanation generation | `trip_planner/preferences/explanations.py` | `tests/preferences/test_explanations.py` | ✅ Implemented |
| Legacy request adapter | `trip_planner/preferences/legacy_request_adapter.py` | `tests/preferences/test_legacy_request_adapter.py` | ✅ Implemented; dedicated adapter tests exist and were run in this bounded review |
| Preference roadmap items (collaborative, in-trip, revealed-preference modes) | `docs/preference-roadmap.md` | — | 📄 Docs-only |

---

## 3. Business Travel Logic

Design refs: [`docs/shared-business-foundation-epic.md`](shared-business-foundation-epic.md), [`docs/business-travel-profile.md`](business-travel-profile.md), [`docs/business-travel-profile-contract.md`](business-travel-profile-contract.md), [`docs/business-objective-derivation-boundary.md`](business-objective-derivation-boundary.md)  
Issues: `#513` (epic), `#514`–`#518`

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Shared trip/option-set/itinerary-objective contracts (`#514`) | `trip_planner/contracts/` | `tests/contracts/` | ✅ Implemented |
| `BusinessTravelProfile` (`#515`) | `trip_planner/business/profile.py`, `trip_planner/business/schema.py` | `tests/business/test_profile.py` | ✅ Implemented |
| Policy-facing proposal + evaluation contracts (`#516`) | `trip_planner/business/policy_contracts.py`, `trip_planner/business/approval_ready.py` | `tests/business/test_approval_ready.py`, `tests/business/test_policy_contracts.py` | ✅ Implemented |
| Source/provenance contracts (`#517`) | `trip_planner/sources/schema.py`, `trip_planner/sources/provenance.py` | `tests/sources/` | ✅ Implemented |
| Business planning objectives (`#518`) | `trip_planner/business/objectives.py`, `trip_planner/business/objective_derivation.py` | `tests/business/test_business_objectives.py`, `tests/business/test_business_objective_derivation.py` | ✅ Implemented |
| Business scenario simulator | `trip_planner/business/simulator.py` | `tests/business/test_simulator.py` | ✅ Implemented |
| Business orchestration boundary | `docs/business-orchestration-boundary.md` | — | 📄 Docs-only |

---

## 4. Itinerary Planning

Design refs: [`docs/itinerary-objective-derivation-boundary.md`](itinerary-objective-derivation-boundary.md), [`docs/itinerary-scenario-assembly-boundary.md`](itinerary-scenario-assembly-boundary.md)

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Itinerary objective derivation | `trip_planner/itinerary/objective_derivation.py` | `tests/itinerary/test_objective_derivation.py` | ✅ Implemented |
| Route feasibility checking | `trip_planner/itinerary/feasibility.py` | `tests/itinerary/test_feasibility.py` | ✅ Implemented |
| Move cost calculation | `trip_planner/itinerary/move_costs.py` | `tests/itinerary/` | ✅ Implemented |
| Scenario generation | `trip_planner/itinerary/scenarios.py` | `tests/itinerary/test_scenarios.py` | ✅ Implemented |
| Itinerary search | `trip_planner/itinerary/search.py` | `tests/itinerary/test_search.py` | ✅ Implemented |

---

## 5. Normalized Options and Inventory

Design ref: [`docs/normalized-inventory-contracts-epic.md`](normalized-inventory-contracts-epic.md)  
Issues: `#519` (epic), `#520`–`#524`

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Destination/place-context contracts (`#520`) | `trip_planner/contracts/destinations.py` | `tests/contracts/test_destination_contracts.py` | ✅ Implemented |
| `LodgingOption` (`#521`) | `trip_planner/contracts/lodging.py` | `tests/contracts/` | ✅ Implemented |
| `TransportOption` (`#522`) | `trip_planner/contracts/options.py` | `tests/contracts/test_options.py` | ✅ Implemented |
| `ActivityOption` (`#523`) | `trip_planner/contracts/activities.py` | `tests/contracts/` | ✅ Implemented |
| Inventory bundles + mixed option assembly (`#524`) | `trip_planner/contracts/bundles.py`, `trip_planner/options/` | `tests/options/` | ✅ Implemented |

---

## 6. Data Ingestion and Candidate Generation

Design ref: [`docs/source-ingestion-epic.md`](source-ingestion-epic.md)  
Issues: `#525` (epic), `#526`–`#530`

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Source adapter + raw snapshot contracts (`#526`) | `trip_planner/sources/schema.py`, `trip_planner/sources/adapters/base.py`, `trip_planner/sources/snapshots.py` | `tests/sources/` | ✅ Implemented |
| Entity resolution + deduplication (`#527`) | `trip_planner/sources/resolution.py`, `trip_planner/sources/dedup.py` | `tests/sources/` | ✅ Implemented |
| Lodging + transport ingestion (`#528`) | `trip_planner/ingestion/lodging_pipeline.py`, `trip_planner/ingestion/transport_pipeline.py` | `tests/ingestion/test_lodging_pipeline.py`, `tests/ingestion/test_transport_pipeline.py` | ✅ Implemented |
| Destination + activity ingestion (`#529`) | `trip_planner/ingestion/destination_pipeline.py`, `trip_planner/ingestion/activity_pipeline.py` | `tests/ingestion/test_destination_pipeline.py`, `tests/ingestion/test_activity_pipeline.py` | ✅ Implemented |
| Candidate generation + filtering (`#530`) | `trip_planner/candidates/generation.py`, `trip_planner/candidates/models.py` | `tests/candidates/test_generation.py` | ✅ Implemented |

---

## 7. Ranking and Scoring

Design ref: [`docs/ranking-route-search-epic.md`](ranking-route-search-epic.md)

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Leisure ranking | `trip_planner/ranking/leisure.py` | `tests/ranking/` | ✅ Implemented |
| Business ranking | `trip_planner/ranking/business.py` | `tests/ranking/` | ✅ Implemented |
| Ranking explanations | `trip_planner/ranking/explanations.py` | `tests/ranking/test_source_confidence_explanation.py` | ✅ Implemented |
| Source quality model | `trip_planner/sources/quality.py` + `docs/source-quality-model.md` | `tests/sources/test_source_quality.py` | ✅ Implemented |
| Source channel strategy | `docs/source-channel-strategy.md` | — | 📄 Docs-only |

---

## 8. Persistence and Workflow State

Design refs: [`docs/accounts-persistence-workflow-state-epic.md`](accounts-persistence-workflow-state-epic.md), [`docs/persistence-architecture.md`](persistence-architecture.md)  
Issues: `#675` (epic), `#683`–`#686`

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Account registration, login, session restore (`#683`) | `trip_planner/app/routes/auth.py`, `trip_planner/app/services/auth.py`, `trip_planner/persistence/models/` | `tests/app/test_auth.py` | ✅ Implemented |
| DB-backed trip creation, list, detail (`#684`) | `trip_planner/app/routes/trips.py`, `trip_planner/state/trips.py`, `trip_planner/state/repositories/` | `tests/app/test_trip_routes.py`, `tests/state/test_trips.py` | ✅ Implemented |
| Saved scenario + planning-history persistence (`#685`) | `trip_planner/app/routes/scenario_history.py`, `trip_planner/state/scenarios.py` | `tests/app/`, `tests/state/` | ✅ Implemented |
| Planning-session + activity-log persistence (`#686`) | `trip_planner/app/routes/planner.py`, `trip_planner/app/services/planner.py`, `trip_planner/persistence/models/planner_memory.py` | `tests/app/test_planner_routes.py`, `tests/app/test_planner_turn_e2e.py` | ✅ Implemented |
| Alembic migrations | `trip_planner/persistence/alembic/` | CI import check | ✅ Implemented |
| Append-only scenario history | `trip_planner/state/scenarios.py` | `tests/state/` | ✅ Implemented |

---

## 9. Application Foundation (Full-Stack Runtime)

Design ref: [`docs/application-foundation-epic.md`](application-foundation-epic.md)  
Issues: `#674` (epic), `#680`–`#682`

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| FastAPI runtime + health endpoint (`#680`) | `trip_planner/app/main.py`, `trip_planner/app/routes/health.py` | `tests/app/test_health.py` | ✅ Implemented |
| React shell + live health integration (`#680`) | `frontend/src/App.tsx`, `frontend/src/routes/HealthPage.tsx` | `frontend/src/routes/HealthPage.test.tsx` | ✅ Implemented |
| Typed frontend API client (`#681`) | `frontend/src/api/` | `frontend/src/smoke/` | ✅ Implemented |
| Route/data-loading foundation (`#681`) | `frontend/src/router.tsx`, `frontend/src/routes/` | `frontend/src/router.test.ts` | ✅ Implemented |
| Full-stack local dev + CI workflow support (`#682`) | `Makefile`, `.github/workflows/ci.yml` | `tests/test_repo_hygiene.py` | ✅ Implemented |

---

## 10. Planner Workspace Vertical Slice

Design ref: [`docs/planner-workspace-vertical-slice-epic.md`](planner-workspace-vertical-slice-epic.md)  
Issues: `#676` (epic), `#687`–`#689`

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Trip entry flow (`#687`) | `frontend/src/routes/NewTripPage.tsx`, `frontend/src/routes/TripsPage.tsx` | `tests/app/test_trip_routes.py`, frontend route tests | ✅ Implemented |
| Planner side panel in workspace (`#688`) | `frontend/src/components/planner/PlannerSidePanelSurface.tsx`, `frontend/src/routes/WorkspacePage.tsx` | `tests/app/test_workspace.py` | ✅ Implemented |
| Planner decisions persisted across reloads (`#689`) | `trip_planner/app/services/planner.py` (memory model), `trip_planner/app/routes/planner.py` | `tests/app/test_planner_turn_e2e.py` | ✅ Implemented |

---

## 11. Runtime Planning Services

Design ref: [`docs/runtime-planning-services-epic.md`](runtime-planning-services-epic.md)  
Issues: `#677` (epic), `#690`–`#693`

> **Implemented.** Inventory bundle assembly (`#690`), feasibility (`#691`), ranking (`#692`), and route/scenario comparison (`#693`) are now surfaced as inspectable top-level workspace payload keys: `inventory_summary`, `feasibility_summary`, `ranking`, and canonical `route_comparison`. `runtime_scenario_comparison` remains as a compatibility alias for existing clients. The former strict xfail in `test_planner_turn_surfaces_runtime_planning_services_outputs` is now a runtime payload assertion. (Issue #1102, 2026-05-07.)

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Inventory bundle assembly surfaced in workspace (`#690`) | `trip_planner/app/services/inventory.py`, `trip_planner/app/services/workspace.py` (top-level `inventory_summary` key, with assembled `bundles` nested inside) | `tests/app/test_inventory.py` | ✅ Implemented |
| Feasibility + move-cost evaluation in planner outputs (`#691`) | `trip_planner/app/services/feasibility.py`, `trip_planner/app/services/workspace.py` (top-level `feasibility_summary` key) | `tests/app/test_workspace.py` | ✅ Implemented |
| Ranking + scenario-generation services with workspace results (`#692`) | `trip_planner/app/services/scenarios.py`, `trip_planner/app/services/workspace.py` (top-level `ranking` key) | `tests/app/test_workspace.py`, `tests/planner/test_planner_turn_acceptance.py` | ✅ Implemented |
| Route-search + scenario-comparison in workspace (`#693`) | `trip_planner/app/services/workspace.py` (`_build_runtime_scenario_comparison`; surfaced as canonical `route_comparison` plus compatibility alias) | `tests/app/test_workspace.py`, `tests/planner/test_planner_turn_acceptance.py`, `frontend/src/routes/WorkspacePage.test.tsx` | ✅ Implemented |

**Current persisted-runtime boundary:** `trip_planner/app/services/workspace.py` builds persisted-trip inventory input with `allow_fixture_fallback=False`, then passes that input to `trip_planner/app/services/inventory.py`; the adapter class default remains True for other callers. The non-seeded business/leisure and no-fixture-marker cases in `tests/app/test_workspace.py`, plus persisted-record precedence in `tests/app/test_inventory.py`, exercise the reachable persisted path. Section 17 replaces the old seeded-ID limitation. This does not guarantee provider depth or availability for every arbitrary trip.

---

## 12. Orchestration and Interactive Planning

Design ref: [`docs/orchestration-interactive-planning-epic.md`](orchestration-interactive-planning-epic.md)  
Issues: `#543` (epic), `#544`–`#548`

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Planner-turn + workflow contracts (`#544`) | `trip_planner/orchestration/models.py`, `trip_planner/orchestration/actions.py` | `tests/orchestration/test_orchestration_models.py` | ✅ Implemented |
| Leisure orchestration (`#545`) | `trip_planner/orchestration/leisure.py` | `tests/orchestration/test_leisure_flow.py` | ✅ Implemented |
| Feedback loops (`#546`) | `trip_planner/orchestration/feedback.py` | `tests/orchestration/test_feedback.py` | ✅ Implemented |
| In-trip replanning (`#547`) | `trip_planner/orchestration/in_trip.py` | `tests/orchestration/test_in_trip.py` | ✅ Implemented |
| Business orchestration + policy prep (`#548`) | `trip_planner/orchestration/business.py` | `tests/orchestration/test_business_flow.py` | ✅ Implemented |

---

## 13. LangChain Planner Runtime

Design ref: [`docs/langchain-planner-runtime-epic.md`](langchain-planner-runtime-epic.md)

> **Partial.** The planner runtime now has a trip-scoped conversation API, persisted session/checkpoint records, a model-backed runnable, an explicit app-tool registry/executor, deterministic model-routing by task class and planning mode, provider-rich source/map/route read tools (including executable source-quality scoring for attached inventory source records), and a deterministic cross-category notebook recall layer for session resumption. The remaining gap is live-provider verification.

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Planner protocol seam (configurable model) | `trip_planner/app/services/planner.py` (`PlannerChatModel`, `ModelBackedPlannerConversationRunnable`) | `tests/app/test_planner_routes.py` | ✅ Implemented |
| Trip-scoped planner session + conversation API | `trip_planner/app/routes/planner.py`, `trip_planner/app/services/planner.py` | `tests/app/test_planner_routes.py`, `tests/app/test_planner_turn_e2e.py` | ✅ Implemented |
| App-tool registry and executor | `trip_planner/app/services/planner_tools.py`, `trip_planner/app/services/planner.py` (`_execute_model_tool_calls`) | `tests/app/test_planner_routes.py` | ✅ Implemented |
| Memory and checkpoint persistence | `trip_planner/persistence/models/planner_memory.py`, `trip_planner/app/services/planner_memory.py`, `trip_planner/app/services/planner.py` (`_match_notebook_category`) | `tests/app/test_planner_routes.py`, `tests/app/test_planner_turn_e2e.py` | ✅ Implemented |
| Planning mode selection (delegated / collaborative / revealed-preference / in-trip) | `frontend/src/components/planner/PlanningModeSelector.tsx`, `trip_planner/app/routes/workspace.py`, `trip_planner/app/services/workspace.py` | `frontend/src/components/planner/PlanningModeSelector.test.tsx`, `frontend/src/routes/WorkspacePage.test.tsx`, `tests/app/test_workspace.py` | ✅ Implemented |
| Dynamic model routing by task complexity | `trip_planner/app/services/planner_routing.py`, `trip_planner/app/services/planner.py` (`_planner_turn_metadata`) | `tests/app/test_planner_routing.py`, `tests/app/test_planner_routes.py` | ✅ Implemented |
| Provider-rich planner tools (source retrieval, route/map status, route comparison refresh, source-quality seam) | `trip_planner/app/services/planner_tools.py` | `tests/app/test_planner_routes.py` | ✅ Implemented |
| Semantic notebook recall for session resumption | `trip_planner/app/services/planner_tools.py` (`read_notebook_context`), `trip_planner/app/services/planner.py` (`_implicit_notebook_tool_calls`) | `tests/app/test_planner_routes.py` | ✅ Implemented |

**Gap detail:** The runtime executes explicit planner tools, persists their traces, routes each turn into a task class plus a fast/standard/deep model effort class biased by the selected planning mode, and can inspect provider-rich source/map/route state. `read_source_quality_summary` now scores attached inventory source records from runtime and fixture-backed bundles. Planner memory reorientation uses `_match_notebook_category` to map common traveler vocabulary such as hotels/stays to lodging and flights/trains to route, with clarification for ambiguous later/future-list references. The new `read_notebook_context` tool synthesizes the trip-scoped planning notebook across all categories (≤3 most-recent active items per category) and is invoked deterministically on session-resume phrases ("pick up where we left off", "what were we working on") so the planner can surface active context without the traveler re-stating it. Live-provider verification for configured environments remains tracked separately.

---

## 14. Budget and Business Policy Execution

Design ref: [`docs/budget-business-policy-execution-epic.md`](budget-business-policy-execution-epic.md)  
Issues: `#678` (epic), `#694`–`#697`

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Budget editing + actual-spend capture (`#694`) | `trip_planner/app/routes/budget.py`, `trip_planner/app/services/budget.py`, `trip_planner/state/budget.py` | `tests/app/test_budget_routes.py` | ✅ Implemented |
| Policy constraint sync + approval-readiness display (`#695`) | `trip_planner/app/routes/policy.py`, `trip_planner/app/services/policy.py` | `tests/app/test_policy.py` | ✅ Implemented |
| Proposal submission + result ingestion (`#696`) | `trip_planner/app/routes/proposal.py`, `trip_planner/integrations/tpp/submission.py`, `trip_planner/integrations/tpp/results.py` | `tests/app/test_proposal.py`, `tests/integrations/test_submission.py`, `tests/integrations/test_results.py` | ✅ Implemented |
| Reoptimization + exception-handling after policy results (`#697`) | `trip_planner/integrations/tpp/reoptimization.py`, `trip_planner/app/routes/proposal.py` | `tests/integrations/test_reoptimization.py`, `tests/app/test_proposal.py` | ✅ Implemented |

---

## 15. Live TPP Execution and Reoptimization

Design ref: [`docs/live-tpp-execution-reoptimization-epic.md`](live-tpp-execution-reoptimization-epic.md)

> **Current configured execution: UNVERIFIED.** Historical transport, pinned local two-app contracts and a current full-product gate are separate evidence states.

| Layer | Source / tests | Evidence state |
|---|---|---|
| Historical May live-TPP run | `docs/verification-logs/live-tpp-pass-2026-05-14.log` | Preserved 2026-05-14 `PASS live-tpp` against sibling TPP `ee84f95`; current consumer/producer execution is not established by that old log. |
| Local pinned authenticated two-app handoff | `tests/integration/test_authenticated_two_app_handoff.py`, `tests/integration/test_tpp_portal_contract.py`, `tests/integration/portal_contract_checkout.py` | Real local HTTP/auth/SQLite routes; `.github/workflows/cross-repo-smoke.yml` pins TPP `acc4aeddee5f4ffefbdc73fcb07505cd3d198197`. Configured checks exist; this round did not execute the producer-pinned tests, so no current two-app PASS is claimed. |
| Fixture-envelope lifecycle / reload | `tests/integrations/test_tpp_cross_repo_smoke.py`, `tests/integrations/test_canonical_state_seam.py` | These use Trip Planner app instances and supplied/intercepted policy payloads; they do not prove remote TPP transport. Canonical restart closes A, resets engine/session/migration caches, then opens B against file SQLite. |
| TPP client and policy/result contracts | `trip_planner/integrations/tpp/client.py`, `trip_planner/integrations/tpp/policy_sync.py`, `trip_planner/integrations/tpp/results.py`; `tests/integrations/test_policy_sync.py`, `tests/integrations/test_results.py`, `tests/integrations/test_tpp_transport_httpserver.py` | Implementation and local contract tests are present; path validity alone is not an execution verdict. |
| Native lineage and reoptimization | `trip_planner/app/services/proposal.py`, `trip_planner/integrations/tpp/reoptimization.py`; `tests/app/test_proposal.py` | F50 source #1904 / PR #1915; native producer and persistence/plan consumer evidence is classified in `docs/reports/production-transition-audit.md`. Intercepted external responses are explicit. |
| Current full-product configured TPP transport | `scripts/check_full_product_verification.py`, `.github/workflows/cross-repo-smoke.yml`, `tests/scripts/test_cross_repo_smoke_workflow.py` | 🟡 Partial: current configured execution UNVERIFIED. Required gate: `python scripts/check_full_product_verification.py --live-tpp=required`; retain consumer/producer full SHAs, environment, actual run URL and artifact. Default skips and `--live-tpp off` are not PASS. |

The old remote-path implementation remains available through
`trip_planner/integrations/tpp/client.py`. No new service, deployment, credential
or live-provider run was performed for this docs issue. The current required
configured gate remains a bounded release verification gap; no date or test name
substitutes for its execution receipt.

---

## 16. Google Maps and Frontend Visualization

Design refs: [`docs/google-maps-platform-hardening-epic.md`](google-maps-platform-hardening-epic.md), [`docs/maps-timeline-comparison-epic.md`](maps-timeline-comparison-epic.md)  
Issues: `#679` (epic), `#698`–`#700`

> **Partial.** The map adapter boundary, bounded fallback rendering, Google Maps JavaScript provider path, global/regional/segment map-scope controls, workspace timeline rendering, shared route/segment focus, source-quality summaries, and scenario comparison surfaces now exist. Issue `#1191` adds deterministic route-depth metadata for source-backed markers and per-segment distance-verification state without requiring live Google Maps credentials. Remaining work is mostly release/live-provider confidence, not default local behavior.

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Google Maps JS adapter boundary + fallback rendering | `frontend/src/components/maps/TripMap.tsx`, `frontend/src/components/maps/mapSurface.ts` | `frontend/src/components/maps/mapSurface.test.ts`, `frontend/src/components/maps/TripMap.test.tsx`, `frontend/src/routes/WorkspacePage.test.tsx` | ✅ Implemented |
| Route-context map contract (`docs/contracts/route-context-map-target.md`) | `docs/contracts/route-context-map-target.md`, `frontend/src/components/maps/mapSurface.ts`, `frontend/src/components/maps/TripMap.tsx` | `tests/contracts/test_route_context_map_target.py`, frontend map tests | ✅ Implemented |
| Global/regional/segment map scope switching | `frontend/src/components/maps/mapSurface.ts`, `frontend/src/components/maps/TripMap.tsx` | `frontend/src/components/maps/mapSurface.test.ts`, `frontend/src/components/maps/TripMap.test.tsx`, `frontend/src/routes/WorkspacePage.test.tsx` | ✅ Implemented |
| Timeline view for trip structure + day sequencing (`#698`, `#1365`) | `frontend/src/routes/WorkspacePage.tsx` (`buildTimelineStops`, timeline section, segment focus notes) | `frontend/src/routes/WorkspacePage.test.tsx` | ✅ Implemented |
| Dedicated map surface for route + option context (`#699`, `#1191`) | `frontend/src/components/maps/TripMap.tsx`, `frontend/src/components/maps/mapSurface.ts`, `trip_planner/app/services/workspace.py`, `docs/reports/provider-rich-route-depth.md` | frontend map/workspace tests, `tests/app/test_planner_routes.py`, `tests/app/test_workspace.py` | ✅ Implemented |
| Saved-scenario + trip comparison views (`#700`) | `frontend/src/components/workspace/ScenarioComparison.tsx`, `frontend/src/components/trips/TripComparison.tsx`, `frontend/src/routes/WorkspacePage.tsx` | `frontend/src/components/workspace/ScenarioComparison.test.tsx`, `frontend/src/components/trips/TripComparison.test.tsx`, `frontend/src/routes/WorkspacePage.test.tsx` | ✅ Implemented |
| Traveler-facing workspace polish and hidden diagnostics (`#1164`) | `frontend/src/routes/WorkspacePage.tsx`, `frontend/src/components/workspace/RouteOptionWorkbench.tsx`, `frontend/src/components/maps/TripMap.tsx`, `frontend/src/components/planner/PlanningModeSelector.tsx` | `frontend/src/routes/WorkspacePage.test.tsx`, `frontend/src/components/workspace/RouteOptionWorkbench.test.tsx`, `frontend/src/components/maps/TripMap.test.tsx`, `frontend/src/components/planner/PlanningModeSelector.test.tsx` | ✅ Implemented |
| Workspace timeline contract | `docs/workspace_timeline_contract.md`, `frontend/src/routes/WorkspacePage.tsx` | `frontend/src/routes/WorkspacePage.test.tsx` | ✅ Implemented |

**Gap detail:** The shipped timeline and map surfaces now let a traveler move between whole-trip outline, regional comparison, and precise segment review without losing selected route context, and issue `#1164` keeps raw runtime/provider/debug details behind diagnostics while improving planner reply and route-option presentation. Issue `#1191` resolves the default-runtime depth gap by exposing source-backed marker descriptions, segment source refs, and an explicit `distance_verification_state` through the workspace and planner-tool payloads. Issue `#1365` wires those route geometry segment durations into timeline day-range allocation while preserving equal distribution when segment timing is absent. Live Google Maps distance/geometry verification remains an opt-in release verification concern.

---

## 17. Live Runtime Completion

Design ref: [`docs/live-runtime-completion-epic.md`](live-runtime-completion-epic.md)  
Issues: `#753` (epic), `#757`–`#759`

| Commitment | Source | Tests | Status |
|------------|--------|-------|--------|
| Persisted-trip-driven inventory assembly (`#757`) | `trip_planner/app/services/inventory.py`, `trip_planner/app/services/workspace.py` (`allow_fixture_fallback=False`) | `tests/app/test_inventory.py` | ✅ Implemented persisted-record path; fixture-only callers remain explicit |
| Persisted default workspace bootstrap (`#758`) | `trip_planner/app/services/workspace.py` | `tests/app/test_workspace.py` (non-seeded business/leisure and no-fixture-marker cases) | ✅ Implemented persisted-runtime bootstrap; provider availability is separate |
| Runtime ranking + feasibility from persisted inventory (`#759`) | `trip_planner/app/services/scenarios.py`, `trip_planner/app/services/workspace.py` | `tests/app/test_workspace.py` (persisted-trip runtime-frame cases) | ✅ Reachable persisted inventory path; offline fixture-based assertions do not prove live source depth |

---

## 18. Cross-Cutting: Design Rules and Invariants

From [`docs/product-architecture-brief.md`](product-architecture-brief.md) and [`docs/implementation-plan.md`](implementation-plan.md):

| Rule | Evidence | Status |
|------|---------|--------|
| Contracts before engines before UI (delivery pattern) | Implementation plan §Working Rule | ✅ Followed throughout |
| Separate leisure + business at contract level | `trip_planner/preferences/schema.py` vs `trip_planner/business/schema.py` | ✅ Implemented |
| Audit trail (created_at, updated_at, version on mutable records) | `trip_planner/persistence/models/` | ✅ Implemented |
| Append-only scenario history | `trip_planner/state/scenarios.py` | ✅ Implemented |
| Trip references artifacts (no inlining) | `trip_planner/contracts/trip.py` (`TripArtifactRefs`) | ✅ Implemented |
| Explicit deferred seams (TPP transport, Maps key, provider-rich planner tools) | `tests/app/test_full_product_verification.py` (skip checks) | ✅ Implemented |
| Five bounded modules (preferences, options, itinerary, budget, business_policy_export) | `trip_planner/` subdirectory layout | ✅ Implemented |

---

## Summary: Remaining Follow-Up Claims

These retained gaps describe verification boundaries. This map does not authorize new issues or duplicate the existing implementation owners:

1. **Semantic planner memory and reorientation** — ✅ Addressed by the `read_notebook_context` tool, which synthesizes trip-scoped notebook context across categories and fires on session-resume phrases. Remaining work is deeper embedding-based recall over free-text notes (explicitly out of scope for the deterministic layer). See §13 above.
2. **Provider-rich timeline/map depth** — default workspace and planner-tool payloads now expose source-backed marker detail and per-segment distance-verification state. Remaining work is live provider verification in configured release environments. See §16 above.
---

## How to Use This Map in Weekly Reviews

1. Check the **planner/runtime acceptance tests** first: `pytest -q tests/planner/test_planner_turn_acceptance.py tests/app/test_planner_routes.py tests/app/test_full_product_verification.py`.
2. The **Docs-only** rows in each section identify items that are design commitments but not yet scheduled work.
3. **Partial** rows and preambles name a bounded remaining gap; distinguish configured live-provider verification from missing implementation before selecting work.
4. The **Summary: Remaining Follow-Up Claims** section lists the highest-priority gaps for verification tasks under their existing owners. This scope does not authorize new finding issues or duplicate implementation owners.

Map SDK selection: real-adapter mocked-library interaction/cleanup/failure/scenario coverage in `frontend/src/components/maps/TripMap.test.tsx` (issue #1905). Live provider deployment remains unverified.


## Bounded current evidence and remaining Partial claims (issue #1908)

The [current receipt](evidence/issue-1908-coverage-map.md) records the actual
Python command and result at `4f78d2d1a`. Only that selected set was run here;
the historical 976-test baseline above is preserved and was not repeated.

- **F50 native lineage**: existing source #1904 / PR #1915 and audit #1907 / PR #1927.
  `tests/app/test_proposal.py` observes the native builder before persistence can
  repair missing lineage, then checks the stored proposal and plan. See
  `docs/reports/production-transition-audit.md`; caller-envelope tests prove their
  adapter contract, not the native producer. No new production fix is bundled.
- **F51 maps / section 16 Partial**: source #1905 / PR #1923.
  `frontend/src/components/maps/TripMap.test.tsx` includes actual GoogleMapCanvas
  interaction/lifecycle tests with mocked SDK libraries; supplied readiness props
  and `frontend/src/components/maps/mapSurface.test.ts` are narrower controls.
  Live authenticated provider/deployment behavior remains UNVERIFIED. The
  bounded gap is a configured provider observation, not another map implementation.
- **F52 restart / section 13 Partial**: source #1906 / PR #1926.
  `tests/integrations/test_canonical_state_seam.py` and the adjacent proposal test
  close A, clear caches, open B and freshly authenticate. They prove the scoped
  in-process/file-SQLite transition; OS-process/PostgreSQL/deployment restart and
  live model-provider acceptance remain UNVERIFIED. Planner model/tool tests use
  deterministic test providers, not a live model acceptance run.

`tests/preferences/test_legacy_request_adapter.py` also validates normalized
source/test/doc references in this map, rejects an explicitly nonexistent path,
and accepts document-relative Markdown links. **Path validity is a documentation
check, not behavioral verification.** Each remaining Partial claim above names
its existing source/test reference and bounded execution gap. Scope excludes
runtime changes, epic redesign, new findings issues, and repetition of the
native-lineage/map/restart fixes.
