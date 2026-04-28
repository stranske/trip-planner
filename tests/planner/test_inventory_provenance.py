"""Tests that planner inventory is generated through adapter interfaces, not fixture injection.

The seeded path (PersistedTripInventoryFixtureAdapter) loads pre-built JSON bundles for
a fixed set of well-known trip IDs.  Any trip ID outside that set routes through
PersistedTripSourceInventoryAdapter, which synthesises inventory from the persisted trip
context at runtime.  These tests pin the runtime path so that:

- Inventory provenance, source IDs, and option IDs are deterministic and verifiable.
- Ranking and itinerary code consumes the adapter-generated bundles without any seeded
  fixture shortcut.
- Tests remain offline and produce the same results on every run.

Task coverage (PR #966):
- Task 1: seeded path traced; runtime path selected for tests.
- Task 2: PersistedTripSourceInventoryAdapter is the fake/local adapter used here.
- Task 3: assemble_inventory_bundles_for_trip feeds bundles through InventoryBundle.from_dict
  (the option contract boundary).
- Task 4: assertions name provenance source_refs and generated option IDs explicitly.

Architecture note on ranking → itinerary wiring:
  LeisureRankingEngine.rank_bundles() emits result_kind="item" results (target_option set,
  target_bundle_id absent).  assemble_itinerary_scenarios() requires result_kind="bundle"
  results (target_bundle_id set).  The itinerary tests here follow the same pattern as
  tests/itinerary/test_search.py: construct a minimal RankedResult(result_kind="bundle")
  from the adapter-generated bundle to feed the itinerary stage.  The ranking tests
  separately assert that rank_bundles() correctly scores adapter-generated inventory.
"""

from __future__ import annotations

from trip_planner.app.services.inventory import (
    PersistedTripSourceInventoryAdapter,
    assemble_inventory_bundles_for_trip,
)
from trip_planner.contracts import ItineraryObjectives
from trip_planner.itinerary import assemble_itinerary_scenarios
from trip_planner.options import InventoryBundle
from trip_planner.ranking import (
    ExplanationRecord,
    LeisureRankingEngine,
    RankedResult,
    RankedResultSet,
    ScoreBreakdown,
    ScoreConfidenceSummary,
)
from trip_planner.sources import SourceQuery

from tests.preferences.fixture_corpus import build_profile_from_overrides

_TRIP_ID = "trip-test-provenance-kyoto"
_TRIP_MODE = "leisure"
_REGIONS = ["kyoto"]
_DURATION = 5


def _objectives() -> ItineraryObjectives:
    return ItineraryObjectives(
        objective_id="obj:test:provenance",
        trip_id=_TRIP_ID,
        route_shape="hub_and_spoke",
    )


def _generate_bundles() -> list[InventoryBundle]:
    return assemble_inventory_bundles_for_trip(
        trip_id=_TRIP_ID,
        trip_mode=_TRIP_MODE,
        primary_regions=_REGIONS,
        duration_days=_DURATION,
    )


# ---------------------------------------------------------------------------
# Task 2 — PersistedTripSourceInventoryAdapter as the local adapter
# ---------------------------------------------------------------------------


def test_source_adapter_fetch_returns_complete_snapshot() -> None:
    """Direct adapter fetch should return a complete snapshot with one runtime record."""
    adapter = PersistedTripSourceInventoryAdapter(
        trip_id=_TRIP_ID,
        trip_mode=_TRIP_MODE,
        primary_regions=_REGIONS,
        duration_days=_DURATION,
    )
    query = SourceQuery(
        query_id=f"inventory-query:{_TRIP_ID}",
        entity_scope="mixed",
        option_kind="mixed",
        destination="kyoto",
    )
    snapshot = adapter.fetch_snapshot(query)

    assert snapshot.adapter_id == "persisted-trip-source-inventory"
    assert snapshot.source_id == "persisted-trip-runtime-source"
    assert snapshot.snapshot_status == "complete"
    assert len(snapshot.records) == 1
    assert snapshot.records[0].payload_type == "runtime_bundle_seed"
    assert not snapshot.issues


def test_source_adapter_handoff_ready_with_provenance() -> None:
    """Adapter handoff must be ready and include exactly one provenance reference."""
    adapter = PersistedTripSourceInventoryAdapter(
        trip_id=_TRIP_ID,
        trip_mode=_TRIP_MODE,
        primary_regions=_REGIONS,
        duration_days=_DURATION,
    )
    query = SourceQuery(
        query_id=f"inventory-query:{_TRIP_ID}",
        entity_scope="mixed",
        option_kind="mixed",
        destination="kyoto",
    )
    snapshot = adapter.fetch_snapshot(query)
    handoff = adapter.build_handoff(snapshot)

    assert handoff.status == "ready"
    assert len(handoff.provenance_refs) == 1
    assert handoff.provenance_refs[0].contribution_kind == "inventory"
    assert handoff.provenance_refs[0].source_id == "persisted-trip-runtime-source"


def test_source_adapter_emits_no_issues_when_regions_and_duration_provided() -> None:
    """Adapter must produce zero issues when primary regions and duration are present."""
    adapter = PersistedTripSourceInventoryAdapter(
        trip_id=_TRIP_ID,
        trip_mode=_TRIP_MODE,
        primary_regions=_REGIONS,
        duration_days=_DURATION,
    )
    query = SourceQuery(
        query_id=f"inventory-query:{_TRIP_ID}",
        entity_scope="mixed",
        option_kind="mixed",
        destination="kyoto",
    )
    snapshot = adapter.fetch_snapshot(query)
    assert snapshot.issues == []


# ---------------------------------------------------------------------------
# Task 3 — normalized bundles through option contracts
# ---------------------------------------------------------------------------


def test_adapter_snapshot_bundle_payloads_deserialise_via_option_contract() -> None:
    """Bundle payloads in the snapshot must be accepted by InventoryBundle.from_dict."""
    adapter = PersistedTripSourceInventoryAdapter(
        trip_id=_TRIP_ID,
        trip_mode=_TRIP_MODE,
        primary_regions=_REGIONS,
        duration_days=_DURATION,
    )
    query = SourceQuery(
        query_id=f"inventory-query:{_TRIP_ID}",
        entity_scope="mixed",
        option_kind="mixed",
        destination="kyoto",
    )
    snapshot = adapter.fetch_snapshot(query)
    bundle_payloads = snapshot.records[0].payload.get("bundle_payloads")

    assert isinstance(bundle_payloads, list) and len(bundle_payloads) == 1
    bundle = InventoryBundle.from_dict(bundle_payloads[0])
    assert bundle.bundle_id == f"bundle-{_TRIP_ID}-runtime-1-1"


def test_assemble_inventory_produces_one_bundle_via_source_adapter() -> None:
    """assemble_inventory_bundles_for_trip must route through the source adapter for non-seeded IDs."""
    bundles = _generate_bundles()
    assert len(bundles) == 1
    assert bundles[0].bundle_id == f"bundle-{_TRIP_ID}-runtime-1-1"


def test_generated_bundles_contain_all_four_option_domains() -> None:
    """Generated bundles must include destinations, lodging, transport, and activities."""
    bundle = _generate_bundles()[0]

    assert bundle.destinations, "bundle must have at least one destination"
    assert bundle.lodging_options, "bundle must have at least one lodging option"
    assert bundle.transport_options, "bundle must have at least one transport option"
    assert bundle.activity_options, "bundle must have at least one activity option"


# ---------------------------------------------------------------------------
# Task 4 — provenance and generated option IDs
# ---------------------------------------------------------------------------


def test_generated_bundle_has_deterministic_option_ids() -> None:
    """Option IDs must be scoped to the trip ID and stable across runs."""
    bundle = _generate_bundles()[0]

    assert bundle.lodging_options[0].option_id == f"lodging:{_TRIP_ID}:primary"
    assert bundle.transport_options[0].option_id == f"transport:{_TRIP_ID}:arrival"
    assert bundle.activity_options[0].option_id == f"activity:{_TRIP_ID}:primary"


def test_generated_bundle_has_provenance_source_refs() -> None:
    """Bundle-level provenance must include runtime source refs derived from the trip ID."""
    bundle = _generate_bundles()[0]
    source_refs = bundle.provenance_summary.source_refs

    assert source_refs, "provenance_summary.source_refs must be non-empty"
    assert all(f"prov:{_TRIP_ID}:runtime" in ref for ref in source_refs)
    assert any(ref.endswith(":lodging") for ref in source_refs)
    assert any(ref.endswith(":transport") for ref in source_refs)
    assert any(ref.endswith(":activity") for ref in source_refs)


def test_generated_lodging_option_has_provenance_reference() -> None:
    """Each lodging option must carry a ProvenanceReference linking back to the runtime adapter."""
    lodging = _generate_bundles()[0].lodging_options[0]

    assert lodging.source_refs, "lodging.source_refs must be non-empty"
    ref = lodging.source_refs[0]
    assert ref.provenance_id == f"prov:{_TRIP_ID}:runtime:lodging"
    assert ref.contribution_kind == "inventory"
    assert ref.source_id == "persisted-trip-runtime-source"


def test_generated_transport_option_has_provenance_reference() -> None:
    """Each transport option must carry a ProvenanceReference linking back to the runtime adapter."""
    transport = _generate_bundles()[0].transport_options[0]

    assert transport.source_refs, "transport.source_refs must be non-empty"
    ref = transport.source_refs[0]
    assert ref.provenance_id == f"prov:{_TRIP_ID}:runtime:transport"
    assert ref.contribution_kind == "inventory"
    assert ref.source_id == "persisted-trip-runtime-source"
    assert ref.source_id, "transport source_id must be non-empty"


def test_generated_activity_option_has_provenance_reference() -> None:
    """Each activity option must carry a ProvenanceReference linking back to the runtime adapter."""
    activity = _generate_bundles()[0].activity_options[0]

    assert activity.source_refs, "activity.source_refs must be non-empty"
    ref = activity.source_refs[0]
    assert ref.provenance_id == f"prov:{_TRIP_ID}:runtime:activity"
    assert ref.contribution_kind == "inventory"
    assert ref.source_id == "persisted-trip-runtime-source"
    assert ref.source_id, "activity source_id must be non-empty"


def test_generated_destination_has_source_ref_with_stable_source_id() -> None:
    """Each destination must carry a DestinationSourceRef with a non-empty stable source_id."""
    bundle = _generate_bundles()[0]

    for destination in bundle.destinations:
        assert destination.source_refs, f"{destination.name} source_refs must be non-empty"
        ref = destination.source_refs[0]
        assert ref.source_id == "persisted-trip-runtime-source"
        assert ref.source_id, f"{destination.name} source_ref source_id must be non-empty"
        assert ref.provenance_id, f"{destination.name} source_ref provenance_id must be non-empty"


# ---------------------------------------------------------------------------
# Acceptance criteria — ranking and itinerary consume generated inventory
# ---------------------------------------------------------------------------


def _bundle_ranked_result(
    bundle: InventoryBundle,
    *,
    rank: int,
    score: float,
) -> RankedResult:
    """Build a bundle-kind RankedResult from adapter-generated inventory.

    rank_bundles() emits result_kind="item" results; assemble_itinerary_scenarios()
    requires result_kind="bundle" results with target_bundle_id.  This helper bridges
    the gap following the same pattern as tests/itinerary/test_search.py.
    """
    return RankedResult(
        result_id=f"test-result:{bundle.bundle_id}:{rank}",
        result_kind="bundle",
        rank=rank,
        score=score,
        target_bundle_id=bundle.bundle_id,
        supporting_option_ids=bundle.option_ids,
        supporting_destination_ids=bundle.destination_ids,
        route_sequence=bundle.destination_ids,
        score_breakdown=ScoreBreakdown(baseline_score=score, final_score=score),
        confidence_summary=ScoreConfidenceSummary(overall_confidence=0.8),
        explanation_records=[
            ExplanationRecord(
                explanation_id=f"test:{bundle.bundle_id}",
                record_type="summary",
                target_kind="bundle",
                target_id=bundle.bundle_id,
                headline="Adapter-generated inventory test result",
                summary="Test result built from source-adapter-generated bundle.",
                factor_keys=["adapter_provenance"],
                machine_context={"bundle_id": bundle.bundle_id},
                human_summary=["Bundle generated by PersistedTripSourceInventoryAdapter."],
                source_refs=list(bundle.provenance_summary.source_refs),
            )
        ],
        source_refs=list(bundle.provenance_summary.source_refs),
    )


def _bundle_ranked_result_set(
    bundles: list[InventoryBundle],
    *,
    trip_id: str,
) -> RankedResultSet:
    """Build a RankedResultSet from adapter-generated bundles."""
    results = [
        _bundle_ranked_result(b, rank=i + 1, score=0.8 - i * 0.05) for i, b in enumerate(bundles)
    ]
    return RankedResultSet(
        result_set_id=f"test-ranked-results:{trip_id}:adapter-generated",
        trip_id=trip_id,
        purpose="profile_learning",
        scope="mixed",
        title="Adapter-generated inventory test result set",
        results=results,
        explanation=["Test ranked result set built from source-adapter-generated bundles."],
        source_refs=[f"adapter:{trip_id}:runtime"],
    )


def test_ranking_consumes_adapter_generated_inventory() -> None:
    """LeisureRankingEngine.rank_bundles must accept and score adapter-generated bundles."""
    bundles = _generate_bundles()
    engine = LeisureRankingEngine()
    ranked = engine.rank_bundles(
        build_profile_from_overrides({}),
        _objectives(),
        bundles,
        trip_id=_TRIP_ID,
        purpose="profile_learning",
    )

    assert len(ranked.results) == 1
    result = ranked.results[0]
    # rank_bundles produces result_kind="item"; bundle identity is in target_option and notes
    assert result.rank == 1
    assert result.score > 0.0
    assert result.target_option is not None
    assert result.target_option.option_id == bundles[0].bundle_id
    assert f"bundle_id={bundles[0].bundle_id}" in result.notes
    assert result.explanation_records
    assert result.score_breakdown.component_contributions


def test_itinerary_assembled_end_to_end_from_generated_inventory() -> None:
    """assemble_itinerary_scenarios must produce a feasible scenario from adapter-generated inventory."""
    bundles = _generate_bundles()
    ranked = _bundle_ranked_result_set(bundles, trip_id=_TRIP_ID)
    search_result = assemble_itinerary_scenarios(ranked, bundles=bundles, objectives=_objectives())

    assert len(search_result.scenarios) == 1
    scenario = search_result.scenarios[0]
    assert scenario.bundle_id == bundles[0].bundle_id
    assert scenario.scenario_summary.feasible
    assert scenario.supporting_option_ids


def test_scenario_source_refs_trace_back_to_generated_inventory() -> None:
    """Scenario's source_refs must include the ranked result set ID from the adapter path."""
    bundles = _generate_bundles()
    ranked = _bundle_ranked_result_set(bundles, trip_id=_TRIP_ID)
    search_result = assemble_itinerary_scenarios(ranked, bundles=bundles, objectives=_objectives())

    assert ranked.result_set_id in search_result.source_refs
    assert search_result.trip_id == _TRIP_ID


# ---------------------------------------------------------------------------
# Stable source ID determinism — repeated runs must produce identical IDs
# ---------------------------------------------------------------------------


def test_stable_source_id_is_identical_across_repeated_runs() -> None:
    """Running the generation pipeline twice must yield identical source IDs for all option types.

    This verifies acceptance criterion: repeated execution with the same repository
    data produces identical source IDs for inventory records with matching primary keys.
    """
    bundles_first = _generate_bundles()
    bundles_second = _generate_bundles()

    assert len(bundles_first) == len(bundles_second)
    bundle_a = bundles_first[0]
    bundle_b = bundles_second[0]

    # Lodging source IDs are identical across runs
    assert bundle_a.lodging_options[0].source_refs[0].source_id == (
        bundle_b.lodging_options[0].source_refs[0].source_id
    )
    # Transport source IDs are identical across runs
    assert bundle_a.transport_options[0].source_refs[0].source_id == (
        bundle_b.transport_options[0].source_refs[0].source_id
    )
    # Activity source IDs are identical across runs
    assert bundle_a.activity_options[0].source_refs[0].source_id == (
        bundle_b.activity_options[0].source_refs[0].source_id
    )
    # Provenance IDs are also identical (full determinism check)
    assert bundle_a.lodging_options[0].source_refs[0].provenance_id == (
        bundle_b.lodging_options[0].source_refs[0].provenance_id
    )
    assert bundle_a.transport_options[0].source_refs[0].provenance_id == (
        bundle_b.transport_options[0].source_refs[0].provenance_id
    )
    assert bundle_a.activity_options[0].source_refs[0].provenance_id == (
        bundle_b.activity_options[0].source_refs[0].provenance_id
    )
    # Destination source IDs are identical across runs
    for dest_a, dest_b in zip(bundle_a.destinations, bundle_b.destinations):
        assert dest_a.source_refs[0].source_id == dest_b.source_refs[0].source_id


def test_stable_source_adapter_exposes_stable_source_id_property() -> None:
    """PersistedTripSourceInventoryAdapter must expose stable_source_id matching the source record."""
    adapter = PersistedTripSourceInventoryAdapter(
        trip_id=_TRIP_ID,
        trip_mode=_TRIP_MODE,
        primary_regions=_REGIONS,
        duration_days=_DURATION,
    )
    assert adapter.stable_source_id == "persisted-trip-runtime-source"
    assert adapter.stable_source_id == adapter.source_record.source_id
