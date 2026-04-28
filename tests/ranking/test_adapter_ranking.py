"""Ranking integration tests using adapter-generated inventory.

These tests verify that the ranking engines accept and score inventory generated
by the production PersistedTripSourceInventoryAdapter without any seeded fixture
shortcuts.  All bundles here come from assemble_inventory_bundles_for_trip(), the
same production path used by the planner service entrypoint.
"""

from __future__ import annotations

from trip_planner.app.services.inventory import assemble_inventory_bundles_for_trip
from trip_planner.candidates import CandidateSeed, CandidateSet
from trip_planner.contracts import ItineraryObjectives
from trip_planner.itinerary import assemble_itinerary_scenarios
from trip_planner.options import InventoryBundle
from trip_planner.ranking import LeisureRankingEngine, RankedResultSet

from tests.preferences.fixture_corpus import build_profile_from_overrides

_TRIP_ID = "trip-test-adapter-ranking"
_TRIP_MODE = "leisure"
_REGIONS = ["kyoto"]
_DURATION = 5


def _generate_bundles() -> list[InventoryBundle]:
    return assemble_inventory_bundles_for_trip(
        trip_id=_TRIP_ID,
        trip_mode=_TRIP_MODE,
        primary_regions=_REGIONS,
        duration_days=_DURATION,
    )


def _objectives() -> ItineraryObjectives:
    return ItineraryObjectives(
        objective_id="obj:adapter-ranking:test",
        trip_id=_TRIP_ID,
        route_shape="hub_and_spoke",
    )


def _candidate_set(bundles: list[InventoryBundle]) -> CandidateSet:
    return CandidateSet(
        candidate_set_id="candidate-set:adapter-ranking:test",
        trip_id=_TRIP_ID,
        purpose="profile_learning",
        seeds=[CandidateSeed(candidate_id=bundle.bundle_id, bundle=bundle) for bundle in bundles],
        explanation=["Adapter-generated candidate set for ranking integration tests."],
        source_refs=["src:adapter-ranking-test"],
    )


def _rank_bundles(bundles: list[InventoryBundle]) -> RankedResultSet:
    return LeisureRankingEngine().rank_bundles(
        build_profile_from_overrides({}),
        _objectives(),
        bundles,
        trip_id=_TRIP_ID,
        purpose="profile_learning",
    )


# ---------------------------------------------------------------------------
# Adapter inventory shape — bundles must carry all four option types
# ---------------------------------------------------------------------------


def test_adapter_generated_bundles_include_all_four_option_types() -> None:
    """Adapter must produce bundles with destinations, lodging, transport, and activities."""
    bundle = _generate_bundles()[0]

    assert bundle.destinations, "adapter bundle must include at least one destination"
    assert bundle.lodging_options, "adapter bundle must include lodging options"
    assert bundle.transport_options, "adapter bundle must include transport options"
    assert bundle.activity_options, "adapter bundle must include activity options"


def test_adapter_generated_bundles_have_stable_option_ids() -> None:
    """Adapter-generated option IDs must be scoped to the trip and stable across runs."""
    bundle = _generate_bundles()[0]

    assert bundle.lodging_options[0].option_id == f"lodging:{_TRIP_ID}:primary"
    assert bundle.transport_options[0].option_id == f"transport:{_TRIP_ID}:arrival"
    assert bundle.activity_options[0].option_id == f"activity:{_TRIP_ID}:primary"


def test_adapter_generated_bundles_carry_provenance_source_refs() -> None:
    """Bundle provenance_summary.source_refs must be non-empty and contain runtime refs."""
    bundle = _generate_bundles()[0]
    source_refs = bundle.provenance_summary.source_refs

    assert source_refs, "provenance_summary.source_refs must be non-empty"
    assert all(f"prov:{_TRIP_ID}:runtime" in ref for ref in source_refs)


# ---------------------------------------------------------------------------
# rank_candidate_set — adapter bundles as CandidateSet seeds
# ---------------------------------------------------------------------------


def test_rank_candidate_set_scores_adapter_generated_inventory() -> None:
    """LeisureRankingEngine.rank_candidate_set must score adapter-generated CandidateSet seeds."""
    bundles = _generate_bundles()
    candidate_set = _candidate_set(bundles)
    engine = LeisureRankingEngine()

    ranked = engine.rank_candidate_set(
        build_profile_from_overrides({}),
        _objectives(),
        candidate_set,
    )

    assert ranked.results, "ranking must produce at least one result"
    result = ranked.results[0]
    assert result.rank == 1
    assert result.score > 0.0
    assert result.explanation_records, "result must carry explanation records"
    assert result.score_breakdown.component_contributions, "result must have score components"


def test_rank_candidate_set_result_carries_adapter_provenance() -> None:
    """rank_candidate_set result source_refs must include the adapter-generated bundle provenance."""
    bundles = _generate_bundles()
    candidate_set = _candidate_set(bundles)
    ranked = LeisureRankingEngine().rank_candidate_set(
        build_profile_from_overrides({}),
        _objectives(),
        candidate_set,
    )

    result = ranked.results[0]
    assert result.source_refs, "result must carry non-empty source_refs"
    bundle = bundles[0]
    for ref in bundle.provenance_summary.source_refs:
        assert (
            ref in result.source_refs
        ), f"bundle provenance ref {ref!r} must appear in ranking result source_refs"


# ---------------------------------------------------------------------------
# rank_bundles — adapter bundles passed directly
# ---------------------------------------------------------------------------


def test_rank_bundles_scores_adapter_generated_inventory() -> None:
    """LeisureRankingEngine.rank_bundles must score adapter-generated bundles."""
    bundles = _generate_bundles()
    ranked = _rank_bundles(bundles)

    assert ranked.results, "ranking must produce at least one result"
    result = ranked.results[0]
    assert result.rank == 1
    assert result.score > 0.0
    assert result.target_option is not None
    assert result.target_option.option_id == bundles[0].bundle_id
    assert result.score_breakdown.component_contributions
    assert result.explanation_records


def test_rank_bundles_result_links_back_to_adapter_bundle() -> None:
    """Ranked result's target_option.option_id must equal the adapter-generated bundle_id."""
    bundles = _generate_bundles()
    ranked = _rank_bundles(bundles)

    result = ranked.results[0]
    assert result.target_option is not None
    assert result.target_option.option_id == f"bundle-{_TRIP_ID}-runtime-1-1"


# ---------------------------------------------------------------------------
# Determinism — repeated ranking runs produce identical output
# ---------------------------------------------------------------------------


def test_repeated_adapter_ranking_produces_identical_scores() -> None:
    """Running ranking twice with adapter-generated inventory must produce identical scores."""
    engine = LeisureRankingEngine()
    profile = build_profile_from_overrides({})
    objectives = _objectives()

    ranked_a = engine.rank_bundles(
        profile, objectives, _generate_bundles(), trip_id=_TRIP_ID, purpose="profile_learning"
    )
    ranked_b = engine.rank_bundles(
        profile, objectives, _generate_bundles(), trip_id=_TRIP_ID, purpose="profile_learning"
    )

    assert ranked_a.results[0].score == ranked_b.results[0].score
    assert ranked_a.results[0].target_option is not None
    assert ranked_b.results[0].target_option is not None
    assert (
        ranked_a.results[0].target_option.option_id == ranked_b.results[0].target_option.option_id
    )


def test_repeated_adapter_ranking_produces_identical_provenance_refs() -> None:
    """Source IDs must be identical across two ranking runs with the same adapter data."""
    ranked_a = _rank_bundles(_generate_bundles())
    ranked_b = _rank_bundles(_generate_bundles())

    assert sorted(ranked_a.results[0].source_refs) == sorted(ranked_b.results[0].source_refs)


# ---------------------------------------------------------------------------
# End-to-end — adapter inventory → ranking → itinerary assembly
# ---------------------------------------------------------------------------


def test_itinerary_assembly_from_adapter_ranking_native_output() -> None:
    """assemble_itinerary_scenarios must accept ranking native output from adapter inventory."""
    bundles = _generate_bundles()
    ranked = _rank_bundles(bundles)
    search_result = assemble_itinerary_scenarios(ranked, bundles=bundles, objectives=_objectives())

    assert search_result.scenarios, "itinerary assembly must produce at least one scenario"
    scenario = search_result.scenarios[0]
    assert scenario.bundle_id == bundles[0].bundle_id
    assert scenario.scenario_summary.feasible


def test_itinerary_scenario_source_refs_trace_to_adapter_ranking() -> None:
    """Scenario source_refs must include the ranked result set ID from adapter-based ranking."""
    bundles = _generate_bundles()
    ranked = _rank_bundles(bundles)
    search_result = assemble_itinerary_scenarios(ranked, bundles=bundles, objectives=_objectives())

    assert ranked.result_set_id in search_result.source_refs
    assert search_result.trip_id == _TRIP_ID


def test_no_seeded_fixture_markers_in_adapter_ranking_output() -> None:
    """Ranking output must not contain seeded fixture adapter markers."""
    import json

    bundles = _generate_bundles()
    ranked = _rank_bundles(bundles)
    serialized = json.dumps(ranked.to_dict(), sort_keys=True).lower()

    seeded_markers = ("persistedtripinventoryfixtureadapter", "fixture-normalized-inventory")
    for marker in seeded_markers:
        assert marker not in serialized, (
            f"Seeded fixture marker {marker!r} must not appear in ranking output "
            "for adapter-generated inventory."
        )
