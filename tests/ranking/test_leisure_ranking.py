import json
from pathlib import Path
from typing import Any, cast

import pytest

from tests.preferences.fixture_corpus import build_profile_from_overrides
from trip_planner.candidates import CandidateSeed, CandidateSet
from trip_planner.contracts import (
    BudgetProtection,
    CountRange,
    DayStructureObjectives,
    DiscoveryStrategy,
    ItineraryObjectives,
    LodgingStrategy,
    MoveDensityTarget,
    QualityFloorProtection,
    RecoveryExpectations,
    TransportStrategy,
)
from trip_planner.itinerary.feasibility import FeasibilityAssessment
from trip_planner.options import (
    ActivityOption,
    BundleCompositionSummary,
    BundleExplanation,
    BundleProvenanceSummary,
    BundleQualityValueFitSummary,
    Destination,
    InventoryBundle,
    LodgingOption,
    TransportOption,
)
from trip_planner.preferences import LeisurePreferenceProfile
from trip_planner.ranking import LeisureRankingEngine

RANKING_FIXTURE_NAMES = (
    "depth_oriented_urban_trip.json",
    "scenic_transit_route.json",
    "discovery_heavy_wanderer_route.json",
    "quality_floor_sensitive_trip.json",
)


def _fixture_path(*parts: str) -> Path:
    return Path("tests/fixtures") / Path(*parts)


def _load_ranking_fixture(name: str) -> dict[str, object]:
    return json.loads(_fixture_path("ranking", "leisure", name).read_text(encoding="utf-8"))


def _result_option_id(result: object) -> str:
    target_option = cast(Any, result).target_option
    assert target_option is not None
    return cast(str, target_option.option_id)


def _load_destination(name: str) -> Destination:
    return Destination.from_dict(
        json.loads(_fixture_path("options", "destinations", name).read_text(encoding="utf-8"))
    )


def _load_lodging(name: str) -> LodgingOption:
    return LodgingOption.from_dict(
        json.loads(_fixture_path("options", "lodging", name).read_text(encoding="utf-8"))
    )


def _load_transport(name: str) -> TransportOption:
    return TransportOption.from_dict(
        json.loads(_fixture_path("options", "transport", name).read_text(encoding="utf-8"))
    )


def _load_activity(name: str) -> ActivityOption:
    return ActivityOption.from_dict(
        json.loads(_fixture_path("options", "activities", name).read_text(encoding="utf-8"))
    )


def _urban_culture_bundle() -> InventoryBundle:
    kyoto = _load_destination("kyoto_city.json")
    gion = _load_destination("gion_neighborhood.json")
    lodging = _load_lodging("central_urban_hotel.json")
    transport = _load_transport("downtown_local_ground.json")
    activity = _load_activity("major_museum.json")

    transport.origin_id = gion.destination_id
    transport.destination_id = kyoto.destination_id
    activity.destination_id = kyoto.destination_id

    return InventoryBundle(
        bundle_id="bundle:urban-culture",
        title="Urban culture base",
        bundle_context="mixed",
        destinations=[gion, kyoto],
        lodging_options=[lodging],
        transport_options=[transport],
        activity_options=[activity],
        composition_summary=BundleCompositionSummary(
            assembly_role="candidate_seed",
            primary_destination_id=kyoto.destination_id,
            component_option_ids=[
                lodging.option_id,
                transport.option_id,
                activity.option_id,
            ],
        ),
        provenance_summary=BundleProvenanceSummary(),
        quality_value_fit=BundleQualityValueFitSummary(
            quality_signal=0.82,
            value_signal=0.7,
            fit_signal=0.84,
        ),
        explanation=BundleExplanation(
            strengths=["Central access to museum-heavy days."],
            tradeoffs=["Some crowd pressure around major sights."],
            evidence=["Museums and walkable density are explicit strengths."],
        ),
        summary="Walkable, museum-forward Kyoto base with direct local movement.",
        tags=["urban", "museum", "iconic"],
    )


def _scenic_wanderer_bundle() -> InventoryBundle:
    kyoto = _load_destination("kyoto_city.json")
    gion = _load_destination("gion_neighborhood.json")
    lodging = _load_lodging("vacation_rental.json")
    transport = _load_transport("scenic_rail.json")
    activity = _load_activity("wandering_district.json")

    transport.origin_id = gion.destination_id
    transport.destination_id = kyoto.destination_id
    activity.destination_id = kyoto.destination_id
    activity.name = "Kyoto backstreet wandering and cafe drift"

    return InventoryBundle(
        bundle_id="bundle:scenic-wanderer",
        title="Scenic wanderer route",
        bundle_context="mixed",
        destinations=[gion, kyoto],
        lodging_options=[lodging],
        transport_options=[transport],
        activity_options=[activity],
        composition_summary=BundleCompositionSummary(
            assembly_role="candidate_seed",
            primary_destination_id=kyoto.destination_id,
            component_option_ids=[
                lodging.option_id,
                transport.option_id,
                activity.option_id,
            ],
        ),
        provenance_summary=BundleProvenanceSummary(),
        quality_value_fit=BundleQualityValueFitSummary(
            quality_signal=0.74,
            value_signal=0.76,
            fit_signal=0.81,
        ),
        explanation=BundleExplanation(
            strengths=["Transit doubles as an experience and the day stays open-ended."],
            tradeoffs=["The scenic leg adds more time than the direct urban option."],
            evidence=["The candidate favors wandering over checklist landmarks."],
        ),
        summary="Rail-led discovery day with open blocks for wandering.",
        tags=["discovery", "rail", "wandering"],
    )


def _quiet_recovery_bundle() -> InventoryBundle:
    kyoto = _load_destination("kyoto_city.json")
    gion = _load_destination("gion_neighborhood.json")
    lodging = _load_lodging("quiet_outer_area_hotel.json")
    transport = _load_transport("downtown_local_ground.json")
    activity = _load_activity("major_museum.json")

    transport.origin_id = gion.destination_id
    transport.destination_id = kyoto.destination_id
    activity.destination_id = kyoto.destination_id

    return InventoryBundle(
        bundle_id="bundle:quiet-recovery",
        title="Quiet recovery-first base",
        bundle_context="mixed",
        destinations=[gion, kyoto],
        lodging_options=[lodging],
        transport_options=[transport],
        activity_options=[activity],
        composition_summary=BundleCompositionSummary(
            assembly_role="candidate_seed",
            primary_destination_id=kyoto.destination_id,
            component_option_ids=[
                lodging.option_id,
                transport.option_id,
                activity.option_id,
            ],
        ),
        provenance_summary=BundleProvenanceSummary(),
        quality_value_fit=BundleQualityValueFitSummary(
            quality_signal=0.86,
            value_signal=0.64,
            fit_signal=0.78,
        ),
        explanation=BundleExplanation(
            strengths=["Quiet sleep quality is protected."],
            tradeoffs=["The outer-neighborhood location reduces spontaneous access."],
            evidence=["Recovery and comfort beat density here."],
        ),
        summary="Comfort-protective Kyoto stay with lower noise and deeper recovery.",
        tags=["quiet", "recovery", "quality-floor"],
    )


def _candidate_set() -> CandidateSet:
    bundles = [
        _urban_culture_bundle(),
        _scenic_wanderer_bundle(),
        _quiet_recovery_bundle(),
    ]
    return CandidateSet(
        candidate_set_id="candidate-set:test:leisure",
        trip_id="trip-test-leisure",
        purpose="profile_learning",
        seeds=[
            CandidateSeed(candidate_id=f"candidate:{bundle.bundle_id}", bundle=bundle)
            for bundle in bundles
        ],
        explanation=["Shared candidate set for leisure ranking tests."],
        source_refs=["src:test-candidate-set"],
    )


def _make_objectives(
    *,
    route_shape: str,
    discovery_style: str,
    protect_open_blocks: bool,
    recovery_priority: float,
    required_quality: list[str],
    transit_is_feature: bool,
) -> ItineraryObjectives:
    return ItineraryObjectives(
        objective_id=f"obj:{route_shape}:{discovery_style}",
        trip_id="trip-test-leisure",
        route_shape=route_shape,
        target_base_count=CountRange(min_value=1, max_value=2),
        move_density=MoveDensityTarget(max_moves=3, cadence_days=3),
        recovery_expectations=RecoveryExpectations(
            buffer_days=1,
            recovery_priority=recovery_priority,
        ),
        day_structure=DayStructureObjectives(
            structure_level="moderate",
            wandering_support_level=0.85 if protect_open_blocks else 0.35,
            reservation_density=0.3 if protect_open_blocks else 0.75,
        ),
        discovery_strategy=DiscoveryStrategy(
            style=discovery_style,
            protect_open_blocks=protect_open_blocks,
        ),
        budget_protection=BudgetProtection(
            protected_categories=["lodging", "food"],
            sensitivity=0.65,
        ),
        quality_floor_protection=QualityFloorProtection(required_categories=required_quality),
        lodging_strategy=LodgingStrategy(
            base_style="single_base",
            arrival_buffer_priority=recovery_priority,
        ),
        transport_strategy=TransportStrategy(
            preferred_modes=["rail"] if transit_is_feature else ["local_ground"],
            transit_is_feature=transit_is_feature,
        ),
        explanations=["Test objectives for deterministic ranking."],
    )


def _profile_from_fixture(name: str) -> LeisurePreferenceProfile:
    fixture = _load_ranking_fixture(name)
    return build_profile_from_overrides(cast(dict[str, Any], fixture["profile_overrides"]))


def _objectives_from_fixture(name: str) -> ItineraryObjectives:
    fixture = _load_ranking_fixture(name)
    objective_payload = cast(dict[str, Any], fixture["objectives"])
    return _make_objectives(
        route_shape=objective_payload["route_shape"],
        discovery_style=objective_payload["discovery_style"],
        protect_open_blocks=objective_payload["protect_open_blocks"],
        recovery_priority=objective_payload["recovery_priority"],
        required_quality=objective_payload["required_quality"],
        transit_is_feature=objective_payload["transit_is_feature"],
    )


def _expected_rank_order(name: str) -> list[str]:
    fixture = _load_ranking_fixture(name)
    return cast(list[str], fixture["expected_rank_order"])


def test_leisure_ranking_fixture_set_is_complete() -> None:
    fixture_dir = _fixture_path("ranking", "leisure")

    assert sorted(path.name for path in fixture_dir.glob("*.json")) == sorted(RANKING_FIXTURE_NAMES)


def test_ranking_fixtures_capture_distinct_traveler_shapes() -> None:
    depth_fixture = _load_ranking_fixture("depth_oriented_urban_trip.json")
    scenic_fixture = _load_ranking_fixture("scenic_transit_route.json")
    discovery_fixture = _load_ranking_fixture("discovery_heavy_wanderer_route.json")
    quality_fixture = _load_ranking_fixture("quality_floor_sensitive_trip.json")

    depth_anchors = cast(
        dict[str, list[dict[str, object]]],
        cast(dict[str, object], depth_fixture["profile_overrides"])["anchors"],
    )
    scenic_anchors = cast(
        dict[str, list[dict[str, object]]],
        cast(dict[str, object], scenic_fixture["profile_overrides"])["anchors"],
    )
    quality_anchors = cast(
        dict[str, list[dict[str, object]]],
        cast(dict[str, object], quality_fixture["profile_overrides"])["anchors"],
    )
    discovery_objectives = cast(dict[str, object], discovery_fixture["objectives"])

    assert depth_anchors["experience_anchors"][0]["type"] == "museum"
    assert depth_anchors["place_anchors"][0]["label"] == "Kyoto"
    assert scenic_anchors["mode_anchors"][0]["type"] == "rail"
    assert discovery_objectives["protect_open_blocks"] is True
    assert quality_anchors["quality_floor_anchors"][0]["label"] == "quiet sleep"
    assert (
        _expected_rank_order("depth_oriented_urban_trip.json")[0]
        == "candidate:bundle:urban-culture"
    )
    assert _expected_rank_order("scenic_transit_route.json")[0] == "candidate:bundle:urban-culture"
    assert (
        _expected_rank_order("quality_floor_sensitive_trip.json")[0]
        == "candidate:bundle:urban-culture"
    )


@pytest.mark.parametrize("fixture_name", RANKING_FIXTURE_NAMES)
def test_fixture_profiles_produce_expected_rank_order(fixture_name: str) -> None:
    engine = LeisureRankingEngine()

    ranked = engine.rank_candidate_set(
        _profile_from_fixture(fixture_name),
        _objectives_from_fixture(fixture_name),
        _candidate_set(),
    )

    assert [_result_option_id(result) for result in ranked.results] == _expected_rank_order(
        fixture_name
    )


def test_depth_oriented_profile_ranks_urban_culture_first() -> None:
    engine = LeisureRankingEngine()
    ranked = engine.rank_candidate_set(
        _profile_from_fixture("depth_oriented_urban_trip.json"),
        _objectives_from_fixture("depth_oriented_urban_trip.json"),
        _candidate_set(),
    )

    assert [_result_option_id(result) for result in ranked.results] == _expected_rank_order(
        "depth_oriented_urban_trip.json"
    )


def test_scenic_discovery_profile_keeps_scenic_bundle_as_best_penalized_option() -> None:
    engine = LeisureRankingEngine()
    ranked = engine.rank_candidate_set(
        _profile_from_fixture("scenic_transit_route.json"),
        _objectives_from_fixture("scenic_transit_route.json"),
        _candidate_set(),
    )

    assert _result_option_id(ranked.results[0]) == "candidate:bundle:urban-culture"
    assert _result_option_id(ranked.results[1]) == "candidate:bundle:scenic-wanderer"
    assert ranked.results[1].score_breakdown.bonuses[0].reason_code == "transit_is_feature"
    assert ranked.results[1].confidence_summary.missing_data_fields == [
        "lodging:lodg-kyoto-machiya-loft:checkin_window"
    ]


def test_ranked_results_emit_breakdowns_and_explanation_records() -> None:
    engine = LeisureRankingEngine()
    ranked = engine.rank_candidate_set(
        _profile_from_fixture("scenic_transit_route.json"),
        _objectives_from_fixture("scenic_transit_route.json"),
        _candidate_set(),
    )

    top_result = ranked.results[0]
    scenic_result = ranked.results[1]
    target_option = top_result.target_option

    assert top_result.score_breakdown.component_contributions
    assert top_result.explanation_records
    assert any(record.record_type == "summary" for record in top_result.explanation_records)
    assert not any(record.record_type == "promotion" for record in top_result.explanation_records)
    assert any(record.record_type == "promotion" for record in scenic_result.explanation_records)
    assert target_option is not None
    assert top_result.explanation_records[0].target_id == target_option.option_id
    assert top_result.explanation_records[0].factor_keys
    assert top_result.explanation_records[0].machine_context
    assert top_result.explanation_records[0].human_summary
    assert target_option.explanation


def test_leisure_ranking_outputs_round_trip_through_canonical_result_contract() -> None:
    engine = LeisureRankingEngine()
    ranked = engine.rank_candidate_set(
        _profile_from_fixture("scenic_transit_route.json"),
        _objectives_from_fixture("scenic_transit_route.json"),
        _candidate_set(),
    )

    payload = ranked.to_dict()
    restored = type(ranked).from_dict(payload)

    assert restored.result_set_id == ranked.result_set_id
    assert restored.explanation == ranked.explanation
    assert [axis.key for axis in restored.comparison_axes] == [
        axis.key for axis in ranked.comparison_axes
    ]
    assert [_result_option_id(result) for result in restored.results] == [
        _result_option_id(result) for result in ranked.results
    ]
    assert restored.results[0].score_breakdown.final_score == ranked.results[0].score
    assert restored.results[0].explanation_records[0].record_type == "summary"


def test_quality_floor_sensitive_profile_penalizes_missing_recovery_data() -> None:
    engine = LeisureRankingEngine()
    ranked = engine.rank_candidate_set(
        _profile_from_fixture("quality_floor_sensitive_trip.json"),
        _objectives_from_fixture("quality_floor_sensitive_trip.json"),
        _candidate_set(),
    )

    assert _result_option_id(ranked.results[0]) == "candidate:bundle:urban-culture"
    assert _result_option_id(ranked.results[1]) == "candidate:bundle:quiet-recovery"
    assert any(
        contribution.contribution_id == "quality_floor_fit"
        and contribution.normalized_signal is not None
        and contribution.normalized_signal > 0.8
        for contribution in ranked.results[1].score_breakdown.component_contributions
    )
    assert ranked.results[1].confidence_summary.missing_data_fields == [
        "lodging:lodg-kyoto-hillside-retreat:checkin_window"
    ]


def test_identical_candidates_reorder_between_depth_and_discovery_profiles() -> None:
    engine = LeisureRankingEngine()
    candidate_set = _candidate_set()

    depth_ranked = engine.rank_candidate_set(
        _profile_from_fixture("depth_oriented_urban_trip.json"),
        _objectives_from_fixture("depth_oriented_urban_trip.json"),
        candidate_set,
    )
    discovery_ranked = engine.rank_candidate_set(
        _profile_from_fixture("discovery_heavy_wanderer_route.json"),
        _objectives_from_fixture("discovery_heavy_wanderer_route.json"),
        candidate_set,
    )

    assert [_result_option_id(result) for result in depth_ranked.results] != [
        _result_option_id(result) for result in discovery_ranked.results
    ]
    assert _result_option_id(depth_ranked.results[0]) == "candidate:bundle:urban-culture"
    assert _result_option_id(discovery_ranked.results[0]) == "candidate:bundle:urban-culture"
    assert _result_option_id(discovery_ranked.results[1]) == "candidate:bundle:scenic-wanderer"


def test_identical_profile_reorders_when_objectives_change() -> None:
    engine = LeisureRankingEngine()
    candidate_set = _candidate_set()
    profile = _profile_from_fixture("depth_oriented_urban_trip.json")

    depth_ranked = engine.rank_candidate_set(
        profile,
        _objectives_from_fixture("depth_oriented_urban_trip.json"),
        candidate_set,
    )
    scenic_ranked = engine.rank_candidate_set(
        profile,
        _objectives_from_fixture("scenic_transit_route.json"),
        candidate_set,
    )

    assert [_result_option_id(result) for result in depth_ranked.results] != [
        _result_option_id(result) for result in scenic_ranked.results
    ]
    assert _result_option_id(depth_ranked.results[0]) == "candidate:bundle:urban-culture"
    assert _result_option_id(scenic_ranked.results[0]) == "candidate:bundle:urban-culture"
    assert _result_option_id(scenic_ranked.results[1]) == "candidate:bundle:scenic-wanderer"


def test_same_candidate_scores_change_with_profile_and_objective_inputs() -> None:
    engine = LeisureRankingEngine()
    candidate_set = _candidate_set()

    depth_ranked = engine.rank_candidate_set(
        _profile_from_fixture("depth_oriented_urban_trip.json"),
        _objectives_from_fixture("depth_oriented_urban_trip.json"),
        candidate_set,
    )
    discovery_ranked = engine.rank_candidate_set(
        _profile_from_fixture("discovery_heavy_wanderer_route.json"),
        _objectives_from_fixture("scenic_transit_route.json"),
        candidate_set,
    )

    def result_by_option_id(ranked_result_set: object, option_id: str) -> object:
        return next(
            item
            for item in cast(Any, ranked_result_set).results
            if _result_option_id(item) == option_id
        )

    depth_result = result_by_option_id(depth_ranked, "candidate:bundle:urban-culture")
    discovery_result = result_by_option_id(discovery_ranked, "candidate:bundle:urban-culture")

    depth_components = {
        contribution.contribution_id: contribution.normalized_signal
        for contribution in cast(Any, depth_result).score_breakdown.component_contributions
    }
    discovery_components = {
        contribution.contribution_id: contribution.normalized_signal
        for contribution in cast(Any, discovery_result).score_breakdown.component_contributions
    }

    assert cast(Any, depth_result).score != cast(Any, discovery_result).score
    assert depth_components["anchor_alignment"] != discovery_components["anchor_alignment"]
    assert depth_components["discovery_fit"] != discovery_components["discovery_fit"]


def test_rank_bundles_reorders_same_inventory_for_different_profiles() -> None:
    engine = LeisureRankingEngine()
    bundles = [seed.bundle for seed in _candidate_set().seeds]

    depth_ranked = engine.rank_bundles(
        _profile_from_fixture("depth_oriented_urban_trip.json"),
        _objectives_from_fixture("depth_oriented_urban_trip.json"),
        bundles,
        trip_id="trip-test-leisure",
        purpose="profile_learning",
    )
    discovery_ranked = engine.rank_bundles(
        _profile_from_fixture("discovery_heavy_wanderer_route.json"),
        _objectives_from_fixture("discovery_heavy_wanderer_route.json"),
        bundles,
        trip_id="trip-test-leisure",
        purpose="profile_learning",
    )

    assert depth_ranked.explanation[0].startswith("Leisure ranking remains downstream")
    assert _result_option_id(depth_ranked.results[0]) == "bundle:urban-culture"
    assert _result_option_id(discovery_ranked.results[0]) == "bundle:urban-culture"
    assert _result_option_id(discovery_ranked.results[1]) == "bundle:scenic-wanderer"
    assert [_result_option_id(result) for result in depth_ranked.results] != [
        _result_option_id(result) for result in discovery_ranked.results
    ]


def test_tension_flags_and_low_confidence_reduce_ranking_confidence() -> None:
    engine = LeisureRankingEngine()
    profile = build_profile_from_overrides(
        {
            "tradeoff_dimensions": {
                "iconic_vs_discovery": {
                    "value": 0.1,
                    "confidence": 0.22,
                    "salience": 0.78,
                },
                "route_coherence_vs_eclectic_contrast": {
                    "value": 0.2,
                    "confidence": 0.3,
                    "salience": 0.72,
                },
            },
            "tension_flags": [
                {
                    "id": "pace-vs-depth",
                    "severity": 0.8,
                    "description": "The traveler wants both recovery space and aggressive sightseeing density.",
                }
            ],
        }
    )
    candidate_set = _candidate_set()
    first_bundle_id = candidate_set.seeds[0].bundle.bundle_id
    assessment = FeasibilityAssessment(
        assessment_id=f"feasibility:{first_bundle_id}",
        bundle_id=first_bundle_id,
        feasible=True,
        recommended_for_ranking=True,
        schedule_protection_required=False,
        confidence_signal=0.64,
        missing_data_fields=["activity:start-window", "lodging:taxes"],
        notes=["Injected test assessment."],
    )

    ranked = engine.rank_candidate_set(
        profile,
        _make_objectives(
            route_shape="hub_and_spoke",
            discovery_style="balanced",
            protect_open_blocks=False,
            recovery_priority=0.7,
            required_quality=["lodging"],
            transit_is_feature=False,
        ),
        candidate_set,
        feasibility_outputs={first_bundle_id: assessment},
    )

    result = next(
        item
        for item in ranked.results
        if _result_option_id(item) == "candidate:bundle:urban-culture"
    )
    assert "tension:pace-vs-depth" in result.confidence_summary.low_confidence_flags
    assert "low_confidence:iconic_vs_discovery" in result.confidence_summary.low_confidence_flags
    assert any(
        penalty.reason_code == "low_confidence_profile"
        for penalty in result.score_breakdown.missing_data_penalties
    )
    assert any(
        penalty.reason_code == "preference_tension" for penalty in result.score_breakdown.penalties
    )
    assert any(record.record_type == "confidence" for record in result.explanation_records)
    assert any(record.record_type == "risk" for record in result.explanation_records)
