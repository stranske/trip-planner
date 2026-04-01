import json
from pathlib import Path

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
from tests.preferences.fixture_corpus import build_profile_from_overrides


def _fixture_path(*parts: str) -> Path:
    return Path("tests/fixtures") / Path(*parts)


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
            component_option_ids=[lodging.option_id, transport.option_id, activity.option_id],
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
            component_option_ids=[lodging.option_id, transport.option_id, activity.option_id],
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
            component_option_ids=[lodging.option_id, transport.option_id, activity.option_id],
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


def _depth_profile() -> LeisurePreferenceProfile:
    return build_profile_from_overrides(
        {
            "hard_constraints": {"budget_ceiling": 1400.0},
            "anchors": {
                "experience_anchors": [
                    {
                        "type": "museum",
                        "label": "museum day",
                        "strength": 0.95,
                        "flexibility": 0.2,
                    }
                ],
                "place_anchors": [
                    {
                        "type": "city",
                        "label": "Kyoto",
                        "strength": 0.8,
                        "flexibility": 0.4,
                    }
                ],
            },
            "tradeoff_dimensions": {
                "iconic_vs_discovery": {"value": 0.75, "confidence": 0.86, "salience": 0.84},
                "breadth_vs_depth": {"value": 0.7, "confidence": 0.8, "salience": 0.75},
                "route_coherence_vs_eclectic_contrast": {
                    "value": 0.65,
                    "confidence": 0.82,
                    "salience": 0.7,
                },
            },
            "budget_model": {
                "total_budget_sensitivity": 0.62,
                "quality_floors": {"lodging": "mid_high"},
            },
        }
    )


def _discovery_profile() -> LeisurePreferenceProfile:
    return build_profile_from_overrides(
        {
            "hard_constraints": {"budget_ceiling": 1500.0},
            "anchors": {
                "experience_anchors": [
                    {
                        "type": "wandering",
                        "label": "wandering district",
                        "strength": 0.95,
                        "flexibility": 0.15,
                    }
                ],
                "mode_anchors": [
                    {
                        "type": "rail",
                        "label": "scenic rail",
                        "strength": 0.9,
                        "flexibility": 0.25,
                    }
                ],
            },
            "tradeoff_dimensions": {
                "iconic_vs_discovery": {"value": -0.85, "confidence": 0.88, "salience": 0.88},
                "structure_vs_elasticity": {"value": -0.7, "confidence": 0.78, "salience": 0.78},
                "scenic_transit_vs_destination_time": {
                    "value": 0.85,
                    "confidence": 0.81,
                    "salience": 0.74,
                },
            },
            "budget_model": {"total_budget_sensitivity": 0.45},
        }
    )


def _quality_floor_profile() -> LeisurePreferenceProfile:
    return build_profile_from_overrides(
        {
            "hard_constraints": {"budget_ceiling": 1700.0},
            "anchors": {
                "quality_floor_anchors": [
                    {
                        "type": "quiet",
                        "label": "quiet sleep",
                        "strength": 0.98,
                        "flexibility": 0.1,
                    }
                ]
            },
            "tradeoff_dimensions": {
                "recovery_vs_intensity": {"value": 0.88, "confidence": 0.83, "salience": 0.9},
                "route_coherence_vs_eclectic_contrast": {
                    "value": 0.6,
                    "confidence": 0.8,
                    "salience": 0.74,
                },
            },
            "budget_model": {
                "total_budget_sensitivity": 0.74,
                "quality_floors": {"lodging": "high", "sleep_recovery": "high"},
            },
        }
    )


def test_depth_oriented_profile_ranks_urban_culture_first() -> None:
    engine = LeisureRankingEngine()
    ranked = engine.rank_candidate_set(
        _depth_profile(),
        _make_objectives(
            route_shape="hub_and_spoke",
            discovery_style="iconic",
            protect_open_blocks=False,
            recovery_priority=0.45,
            required_quality=["lodging"],
            transit_is_feature=False,
        ),
        _candidate_set(),
    )

    assert [result.target_option.option_id for result in ranked.results] == [
        "candidate:bundle:urban-culture",
        "candidate:bundle:quiet-recovery",
        "candidate:bundle:scenic-wanderer",
    ]


def test_scenic_discovery_profile_ranks_scenic_bundle_first() -> None:
    engine = LeisureRankingEngine()
    ranked = engine.rank_candidate_set(
        _discovery_profile(),
        _make_objectives(
            route_shape="mixed",
            discovery_style="discovery_forward",
            protect_open_blocks=True,
            recovery_priority=0.35,
            required_quality=[],
            transit_is_feature=True,
        ),
        _candidate_set(),
    )

    assert ranked.results[0].target_option.option_id == "candidate:bundle:scenic-wanderer"
    assert ranked.results[0].score_breakdown.bonuses[0].reason_code == "transit_is_feature"


def test_quality_floor_sensitive_profile_ranks_recovery_bundle_first() -> None:
    engine = LeisureRankingEngine()
    ranked = engine.rank_candidate_set(
        _quality_floor_profile(),
        _make_objectives(
            route_shape="hub_and_spoke",
            discovery_style="balanced",
            protect_open_blocks=False,
            recovery_priority=0.9,
            required_quality=["lodging", "sleep_recovery"],
            transit_is_feature=False,
        ),
        _candidate_set(),
    )

    assert ranked.results[0].target_option.option_id == "candidate:bundle:quiet-recovery"
    assert any(
        contribution.contribution_id == "quality_floor_fit"
        and contribution.normalized_signal is not None
        and contribution.normalized_signal > 0.8
        for contribution in ranked.results[0].score_breakdown.component_contributions
    )


def test_identical_candidates_reorder_between_depth_and_discovery_profiles() -> None:
    engine = LeisureRankingEngine()
    candidate_set = _candidate_set()

    depth_ranked = engine.rank_candidate_set(
        _depth_profile(),
        _make_objectives(
            route_shape="hub_and_spoke",
            discovery_style="iconic",
            protect_open_blocks=False,
            recovery_priority=0.45,
            required_quality=["lodging"],
            transit_is_feature=False,
        ),
        candidate_set,
    )
    discovery_ranked = engine.rank_candidate_set(
        _discovery_profile(),
        _make_objectives(
            route_shape="mixed",
            discovery_style="discovery_forward",
            protect_open_blocks=True,
            recovery_priority=0.35,
            required_quality=[],
            transit_is_feature=True,
        ),
        candidate_set,
    )

    assert [result.target_option.option_id for result in depth_ranked.results] != [
        result.target_option.option_id for result in discovery_ranked.results
    ]
    assert depth_ranked.results[0].target_option.option_id == "candidate:bundle:urban-culture"
    assert discovery_ranked.results[0].target_option.option_id == "candidate:bundle:scenic-wanderer"


def test_tension_flags_and_low_confidence_reduce_ranking_confidence() -> None:
    engine = LeisureRankingEngine()
    profile = build_profile_from_overrides(
        {
            "tradeoff_dimensions": {
                "iconic_vs_discovery": {"value": 0.1, "confidence": 0.22, "salience": 0.78},
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
        if item.target_option.option_id == "candidate:bundle:urban-culture"
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
