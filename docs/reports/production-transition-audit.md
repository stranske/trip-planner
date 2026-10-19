# Production transition proof audit (F53 / issue #1907)

Audited source: `3d4cafc6a` (merged #1926), after native lineage #1915,
SDK selection #1923 and sequential restart #1926. This bounded inventory covers
native proposal lineage and adjacent outbound payload controls, every test in
the two named map modules, and every test in the two named restart modules.
It excludes unrelated proposal/portal behavior and fixture-only integration
adapter tests. A green helper or test name is never treated as production proof.

## Findings and existing owners

1. **F50 / native lineage:** [#1904](https://github.com/stranske/trip-planner/issues/1904),
   delivered by [#1915](https://github.com/stranske/trip-planner/pull/1915).
   `build_workspace_submission_proposal` calls `_submission_source_version` and
   attaches the selected persisted version. `submit_workspace_proposal_for_trip`
   passes that proposal to `save_workspace_proposal_submission`; the latter also
   resolves authoritative lineage before storage. Reoptimization consumes the
   stored version through `ScenarioVersion.from_dict` and the real plan builder.
   The new consumer probe checks the native proposal **before** storage can heal
   a missing builder field, compares it with the workspace saved-version record,
   then independently queries the persisted proposal and persisted plan. Existing
   forged-caller, selected-version, unsupported-label and trip-level controls remain.
   External TPP responses are intentional mocks, not substitutes for this lineage.
2. **F51 / map readiness:** [#1905](https://github.com/stranske/trip-planner/issues/1905),
   delivered by [#1923](https://github.com/stranske/trip-planner/pull/1923).
   The old readiness-prop test still intentionally renders a `simulated-ready`
   group. It proves that branch's rendering only. Four later interaction tests
   omit the override and mount actual `GoogleMapCanvas`; library loading,
   geocoding and SDK classes are mocked at the external boundary. They dispatch
   `gmp-click`, check selected canonical detail/notes, dispose listeners/overlays,
   exercise load/geocode failures and replace overlays on a scenario change.
   `mapSurface` tests are intentionally model-only, including the one whose name
   says "live ... adapter". Their supplied `ready`/error state cannot establish
   actual provider readiness. Live authenticated Google Maps remains **UNKNOWN**.
3. **F52 / shutdown/reopen:** [#1906](https://github.com/stranske/trip-planner/issues/1906),
   delivered by [#1926](https://github.com/stranske/trip-planner/pull/1926).
   Both gates now close A before `clear_inter_app_restart_caches` disposes engine,
   session and migration caches; B is constructed later with fresh authentication.
   The canonical seam compares the full saved proposal and planner state. Its
   two SQL deletion controls exercise actual durable row loss. The adjacent
   proposal-lineage restart also closes A, resets, opens B, logs in and compares
   version/evaluation/plan. These are in-process app restarts against file SQLite,
   not separate-process, PostgreSQL or hosted-service acceptance.

No additional confirmed production defect was found within this inventory.
The explicit unknowns are live external-provider behavior, deployment and
separate-process/database-server restarts. They are returned as limitations,
not new issues or authorization for bundled repairs. The three existing owners
retain original acceptance/verifier disposition separately from their merged code.

## Prevention and disconnection checks

- New native consumer probe fails if builder lineage is disconnected even though
  storage recomputes it, or if persisted lineage/plan loses the expected version.
- The inventory regression requires each named test to exist, covers all tests in
  the five wholly inventoried modules, validates every source anchor, and requires
  one classified row per named test. This protects inventory freshness, not semantics.
- Existing map interaction assertions would fail if SDK click callbacks stop
  selecting canonical details; override/model-only controls are explicitly excluded
  from that proof. Existing SDK mutation receipt: `docs/evidence/issue-1905/`.
- Existing restart ordering/cache and deleted-row controls reject bypassed rebind
  and missing durable data. Existing receipt: `docs/evidence/issue-1906/`.
- Current executed commands, actual temporary production disconnections, restored
  results and hashes are recorded in `docs/evidence/issue-1907/validation.md`.

## Complete bounded test inventory

Each row names its contract and substituted boundary; classifications describe
what is exercised, not a binary judgment that mocks are bad. The JSON companion
is the machine-readable source of these rows. Source/test references are checked
for existence by the inventory regression; exact names avoid drifting line numbers.

| Seam | Test reference | Classification | Producer/consumer and limit |
|---|---|---|---|
| lineage | `tests/app/test_proposal.py::test_workspace_proposal_evaluation_derives_reoptimization_follow_up` | intentional_fixture | Persisted saved version -> native submit builder -> stored proposal -> reoptimization plan. PUT installs a fixture proposal with no lineage; proves the no-lineage refusal, not native generation. |
| lineage | `tests/app/test_proposal.py::test_native_submit_then_reoptimize_without_injected_source_version` | exercised_offline | Persisted saved version -> native submit builder -> stored proposal -> reoptimization plan. TPP result is intercepted; no remote TPP acceptance claim. |
| lineage | `tests/app/test_proposal.py::test_submission_derives_lineage_instead_of_trusting_caller` | exercised_offline | Persisted saved version -> native submit builder -> stored proposal -> reoptimization plan. TPP result is intercepted; no remote TPP acceptance claim. |
| lineage | `tests/app/test_proposal.py::test_reoptimization_uses_the_submitted_version_after_scenario_changes` | exercised_offline | Persisted saved version -> native submit builder -> stored proposal -> reoptimization plan. TPP result is intercepted; no remote TPP acceptance claim. |
| lineage | `tests/app/test_proposal.py::test_native_lineage_prefers_current_saved_scenario_for_shared_itinerary` | exercised_offline | Persisted saved version -> native submit builder -> stored proposal -> reoptimization plan. Writes session selection directly: resolver tie-break control, not public selection-UI proof. |
| lineage | `tests/app/test_proposal.py::test_unsupported_saved_lineage_is_not_advertised_or_reoptimized` | intentional_corruption | Persisted saved version -> native submit builder -> stored proposal -> reoptimization plan. Direct durable-row mutations test unsupported-label refusal; not a legitimate user write path. |
| lineage | `tests/app/test_proposal.py::test_trip_level_reoptimization_returns_no_scenario_lineage` | exercised_offline | Persisted saved version -> native submit builder -> stored proposal -> reoptimization plan. TPP result is intercepted; no remote TPP acceptance claim. |
| lineage | `tests/app/test_proposal.py::test_proposal_state_persists_across_create_app_restart` | exercised_offline | Persisted saved version -> native submit builder -> stored proposal -> reoptimization plan. Sequential app close/reset/reopen, fresh login; not a separate OS process or hosted DB restart. |
| lineage-adjacent | `tests/app/test_proposal_payload_truth.py::test_the_trip_plan_carries_what_tpp_rules_read` | exercised_offline | Real API submission -> intercepted outbound TPP plan. Synthetic external TPP responses; does not prove remote policy service. |
| lineage-adjacent | `tests/app/test_proposal_payload_truth.py::test_an_absent_attestation_is_sent_as_absent_not_as_true` | exercised_offline | Real API submission -> intercepted outbound TPP plan. Synthetic external TPP responses; does not prove remote policy service. |
| lineage-adjacent | `tests/app/test_proposal_payload_truth.py::test_an_unpriced_trip_is_refused_rather_than_sent_as_zero` | exercised_offline | Real API submission -> intercepted outbound TPP plan. Synthetic external TPP responses; does not prove remote policy service. |
| lineage-adjacent | `tests/app/test_proposal_payload_truth.py::test_a_missing_origin_is_sent_as_missing_not_as_a_placeholder` | exercised_offline | Real API submission -> intercepted outbound TPP plan. Synthetic external TPP responses; does not prove remote policy service. |
| lineage-adjacent | `tests/app/test_proposal_payload_truth.py::test_a_trip_the_planner_could_not_map_can_still_go_to_the_policy_check` | exercised_offline | Real API submission -> intercepted outbound TPP plan. Synthetic external TPP responses; does not prove remote policy service. |
| lineage-adjacent | `tests/app/test_proposal_payload_truth.py::test_the_fare_link_is_kept_and_sent_with_the_airfare` | exercised_offline | Real API submission -> intercepted outbound TPP plan. Synthetic external TPP responses; does not prove remote policy service. |
| lineage-adjacent | `tests/app/test_proposal_payload_truth.py::test_a_fare_link_must_be_a_web_address` | exercised_offline | Real API submission -> intercepted outbound TPP plan. Synthetic external TPP responses; does not prove remote policy service. |
| restart | `tests/integrations/test_canonical_state_seam.py::test_canonical_state_seam_persists_planner_turn_and_proposal_lifecycle` | exercised_offline | App A exits -> engine/session/migration caches reset -> app B fresh login and durable reload. In-process app lifecycles and file-backed SQLite; no OS process, PostgreSQL, or hosted deployment claim. |
| restart | `tests/integrations/test_canonical_state_seam.py::test_canonical_state_seam_rejects_missing_durable_rows` | exercised_offline | App A exits -> engine/session/migration caches reset -> app B fresh login and durable reload. Intentional SQL row deletion proves durable-loss sensitivity; not a positive persistence claim. |
| restart | `tests/app/test_planner_turn_e2e.py::test_planner_turn_e2e_persists_across_app_instances` | exercised_offline | App A exits -> engine/session/migration caches reset -> app B fresh login and durable reload. In-process app lifecycles and file-backed SQLite; no OS process, PostgreSQL, or hosted deployment claim. |
| maps | `frontend/src/components/maps/TripMap.test.tsx::switches map scopes without changing the selected route option` | intentional_component | TripMap rendering, scenario/marker controls. Synthetic props/fixture data; not live provider proof. |
| maps | `frontend/src/components/maps/TripMap.test.tsx::keeps provider diagnostics out of the normal traveler map` | intentional_component | TripMap rendering, scenario/marker controls. Synthetic props/fixture data; not live provider proof. |
| maps | `frontend/src/components/maps/TripMap.test.tsx::labels the keyed provider surface as a schematic preview when readiness is unproven` | intentional_component | TripMap rendering, scenario/marker controls. Synthetic props/fixture data; not live provider proof. |
| maps | `frontend/src/components/maps/TripMap.test.tsx::mounts the provider-backed surface when readiness is observed` | intentional_simulation | TripMap rendering, scenario/marker controls. Explicit providerLoadState=ready renders simulated-ready group; it cannot prove observed SDK readiness. |
| maps | `frontend/src/components/maps/TripMap.test.tsx::surfaces linked planning ledger entries as map focus cues` | intentional_component | TripMap rendering, scenario/marker controls. Synthetic props/fixture data; not live provider proof. |
| maps | `frontend/src/components/maps/TripMap.test.tsx::keeps a visible marker selected when refreshed scenario data has a new identity` | intentional_component | TripMap rendering, scenario/marker controls. Synthetic props/fixture data; not live provider proof. |
| maps | `frontend/src/components/maps/TripMap.test.tsx::renders segment timing and confidence in traveler language` | intentional_component | TripMap rendering, scenario/marker controls. Synthetic props/fixture data; not live provider proof. |
| maps | `frontend/src/components/maps/TripMap.test.tsx::selects canonical marker details and linked notes from an SDK click` | exercised_offline | TripMap -> actual GoogleMapCanvas -> mocked SDK libraries/events -> canonical state, failure cleanup, scenario replacement. Only SDK library boundary mocked; no live Google Maps, geocoding, billing or deployment claim. |
| maps | `frontend/src/components/maps/TripMap.test.tsx::retains canonical controls when SDK loading fails` | exercised_offline | TripMap -> actual GoogleMapCanvas -> mocked SDK libraries/events -> canonical state, failure cleanup, scenario replacement. Only SDK library boundary mocked; no live Google Maps, geocoding, billing or deployment claim. |
| maps | `frontend/src/components/maps/TripMap.test.tsx::retains route and option context when geocoding fails and the scenario changes` | exercised_offline | TripMap -> actual GoogleMapCanvas -> mocked SDK libraries/events -> canonical state, failure cleanup, scenario replacement. Only SDK library boundary mocked; no live Google Maps, geocoding, billing or deployment claim. |
| maps | `frontend/src/components/maps/TripMap.test.tsx::replaces SDK overlays on a ready scenario change without losing option controls` | exercised_offline | TripMap -> actual GoogleMapCanvas -> mocked SDK libraries/events -> canonical state, failure cleanup, scenario replacement. Only SDK library boundary mocked; no live Google Maps, geocoding, billing or deployment claim. |
| maps | `frontend/src/components/maps/mapSurface.test.ts::normalizes route stop labels for provider-independent map shaping` | intentional_model | Map surface model and fallback/canonical controls. Synthetic readiness or helper-only shaping; no SDK initialization, readiness or live-service proof. |
| maps | `frontend/src/components/maps/mapSurface.test.ts::selects the live Google Maps JavaScript adapter when a key and route are available` | intentional_model | Map surface model and fallback/canonical controls. Synthetic readiness or helper-only shaping; no SDK initialization, readiness or live-service proof. |
| maps | `frontend/src/components/maps/mapSurface.test.ts::switches between whole-trip and local map scopes without losing the route option` | intentional_model | Map surface model and fallback/canonical controls. Synthetic readiness or helper-only shaping; no SDK initialization, readiness or live-service proof. |
| maps | `frontend/src/components/maps/mapSurface.test.ts::uses provider-rich map view segment details when the runtime payload supplies them` | intentional_model | Map surface model and fallback/canonical controls. Synthetic readiness or helper-only shaping; no SDK initialization, readiness or live-service proof. |
| maps | `frontend/src/components/maps/mapSurface.test.ts::connects directly linked ledger entries to map markers and route segments` | intentional_model | Map surface model and fallback/canonical controls. Synthetic readiness or helper-only shaping; no SDK initialization, readiness or live-service proof. |
| maps | `frontend/src/components/maps/mapSurface.test.ts::omits policy posture from leisure trip route metrics even when the source includes it` | intentional_model | Map surface model and fallback/canonical controls. Synthetic readiness or helper-only shaping; no SDK initialization, readiness or live-service proof. |
| maps | `frontend/src/components/maps/mapSurface.test.ts::retains policy posture in non-leisure route metrics` | intentional_model | Map surface model and fallback/canonical controls. Synthetic readiness or helper-only shaping; no SDK initialization, readiness or live-service proof. |
| maps | `frontend/src/components/maps/mapSurface.test.ts::falls back when Google Maps is not configured` | intentional_model | Map surface model and fallback/canonical controls. Synthetic readiness or helper-only shaping; no SDK initialization, readiness or live-service proof. |
| maps | `frontend/src/components/maps/mapSurface.test.ts::keeps route context visible when the provider reports a load error` | intentional_model | Map surface model and fallback/canonical controls. Synthetic readiness or helper-only shaping; no SDK initialization, readiness or live-service proof. |
| maps | `frontend/src/components/maps/mapSurface.test.ts::keeps route context visible while the provider is still loading` | intentional_model | Map surface model and fallback/canonical controls. Synthetic readiness or helper-only shaping; no SDK initialization, readiness or live-service proof. |
| maps | `frontend/src/components/maps/mapSurface.test.ts::uses sparse route fallback when the active scenario does not include enough route stops` | intentional_model | Map surface model and fallback/canonical controls. Synthetic readiness or helper-only shaping; no SDK initialization, readiness or live-service proof. |
| maps | `frontend/src/components/maps/mapSurface.test.ts::emits lodging, activity, and transport markers from mixed bundle contexts` | intentional_model | Map surface model and fallback/canonical controls. Synthetic readiness or helper-only shaping; no SDK initialization, readiness or live-service proof. |
| maps | `frontend/src/components/maps/mapSurface.test.ts::configured is not observed ready` | intentional_model | Map surface model and fallback/canonical controls. Synthetic readiness or helper-only shaping; no SDK initialization, readiness or live-service proof. |
| maps | `frontend/src/components/maps/mapSurface.test.ts::high confidence requires observed provider` | intentional_model | Map surface model and fallback/canonical controls. Synthetic readiness or helper-only shaping; no SDK initialization, readiness or live-service proof. |
| maps | `frontend/src/components/maps/mapSurface.test.ts::only resolves source-backed stop locations; option schematic coordinates stay unlocated` | intentional_model | Map surface model and fallback/canonical controls. Synthetic readiness or helper-only shaping; no SDK initialization, readiness or live-service proof. |
| lineage | `tests/app/test_proposal.py::test_transition_audit_native_submit_preserves_lineage_at_each_consumer` | exercised_offline | Saved-version API state -> native submission argument at persistence boundary -> independent stored row -> persisted reoptimization plan. Observes original persistence call without replacing its result; external TPP is intercepted. |
