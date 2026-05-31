import json
from pathlib import Path
from typing import Any, cast

import pytest

from tests.preferences.fixture_corpus import build_profile_from_overrides
from trip_planner.business import (
    BusinessPlanningObjectives,
    BusinessTravelProfile,
    PolicyConstraintSet,
    derive_business_planning_objectives,
)
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
from trip_planner.itinerary import assemble_itinerary_scenarios
from trip_planner.itinerary.feasibility import FeasibilityAssessment
from trip_planner.itinerary.scenarios import ScenarioSearchResult
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
from trip_planner.ranking import (
    BusinessRankingEngine,
    LeisureRankingEngine,
    RankedResultSet,
)


def _fixture_path(*parts: str) -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / Path(*parts)


def _load_json(*parts: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_fixture_path(*parts).read_text(encoding="utf-8")))


def _load_destination(name: str) -> Destination:
    return Destination.from_dict(_load_json("options", "destinations", name))


def _load_lodging(name: str) -> LodgingOption:
    return LodgingOption.from_dict(_load_json("options", "lodging", name))


def _load_transport(name: str) -> TransportOption:
    return TransportOption.from_dict(_load_json("options", "transport", name))


def _load_activity(name: str) -> ActivityOption:
    return ActivityOption.from_dict(_load_json("options", "activities", name))


def _load_business_profile(name: str) -> BusinessTravelProfile:
    return BusinessTravelProfile.from_dict(_load_json("business", name))


def _load_constraint_set(name: str) -> PolicyConstraintSet:
    payload = _load_json("business", name)
    return PolicyConstraintSet(**payload["constraint_set"])


def _build_bundle(
    *,
    bundle_id: str,
    title: str,
    lodging_name: str,
    transport_name: str,
    activity_name: str,
    summary: str,
    strengths: list[str],
    tradeoffs: list[str],
    evidence: list[str],
    tags: list[str],
    quality_signal: float,
    value_signal: float,
    fit_signal: float,
    transport_status: str = "approved",
    business_access_signal: float = 0.0,
) -> InventoryBundle:
    kyoto = _load_destination("kyoto_city.json")
    gion = _load_destination("gion_neighborhood.json")
    lodging = _load_lodging(lodging_name)
    transport = _load_transport(transport_name)
    activity = _load_activity(activity_name)

    transport.origin_id = gion.destination_id
    transport.destination_id = kyoto.destination_id
    transport.policy_summary.business_approval_status = transport_status
    lodging.location_summary.business_access_signal = business_access_signal
    activity.destination_id = kyoto.destination_id

    return InventoryBundle(
        bundle_id=bundle_id,
        title=title,
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
        provenance_summary=BundleProvenanceSummary(
            source_refs=[
                kyoto.source_refs[0].provenance_id,
                gion.source_refs[0].provenance_id,
                lodging.source_refs[0].provenance_id,
                transport.source_refs[0].provenance_id,
                activity.source_refs[0].provenance_id,
            ],
            booking_links=[
                link
                for link in [
                    lodging.booking_links[0] if lodging.booking_links else "",
                    transport.booking_links[0] if transport.booking_links else "",
                    activity.booking_links[0] if activity.booking_links else "",
                ]
                if link
            ],
        ),
        quality_value_fit=BundleQualityValueFitSummary(
            quality_signal=quality_signal,
            value_signal=value_signal,
            fit_signal=fit_signal,
        ),
        explanation=BundleExplanation(
            headline=title,
            strengths=strengths,
            tradeoffs=tradeoffs,
            evidence=evidence,
        ),
        summary=summary,
        tags=tags,
    )


def _leisure_candidate_set() -> CandidateSet:
    bundles = [
        _build_bundle(
            bundle_id="bundle:urban-culture",
            title="Urban culture base",
            lodging_name="central_urban_hotel.json",
            transport_name="downtown_local_ground.json",
            activity_name="major_museum.json",
            summary="Walkable, museum-forward Kyoto base with direct local movement.",
            strengths=["Direct access to dense cultural inventory."],
            tradeoffs=["High-energy core can feel crowded late in the day."],
            evidence=["Museum density and walkability drive the primary route."],
            tags=["urban", "museum", "iconic"],
            quality_signal=0.84,
            value_signal=0.72,
            fit_signal=0.86,
        ),
        _build_bundle(
            bundle_id="bundle:quiet-recovery",
            title="Quiet recovery-first base",
            lodging_name="quiet_outer_area_hotel.json",
            transport_name="downtown_local_ground.json",
            activity_name="major_museum.json",
            summary="Comfort-protective Kyoto stay with lower noise and deeper recovery.",
            strengths=["Sleep quality and recovery windows stay protected."],
            tradeoffs=["Outer-neighborhood location adds more transit overhead."],
            evidence=["Recovery matters more than immediate density for this route."],
            tags=["quiet", "recovery", "quality-floor"],
            quality_signal=0.88,
            value_signal=0.66,
            fit_signal=0.8,
        ),
        _build_bundle(
            bundle_id="bundle:scenic-wanderer",
            title="Scenic wanderer route",
            lodging_name="vacation_rental.json",
            transport_name="scenic_rail.json",
            activity_name="wandering_district.json",
            summary="Rail-led discovery day with open blocks for wandering.",
            strengths=["The route keeps wandering and scenic transit as the core experience."],
            tradeoffs=["The scenic leg is slower than the more direct options."],
            evidence=["Open-ended exploration is preserved as an explicit alternative."],
            tags=["discovery", "rail", "wandering"],
            quality_signal=0.76,
            value_signal=0.78,
            fit_signal=0.82,
        ),
    ]
    return CandidateSet(
        candidate_set_id="candidate-set:itinerary:leisure",
        trip_id="trip-itinerary-leisure",
        purpose="final_selection",
        seeds=[
            CandidateSeed(candidate_id=f"candidate:{bundle.bundle_id}", bundle=bundle)
            for bundle in bundles
        ],
        explanation=["Shared candidate set for itinerary search assembly tests."],
        source_refs=["fixture:itinerary:leisure"],
    )


def _business_candidate_set() -> CandidateSet:
    bundles = [
        _build_bundle(
            bundle_id="bundle:approved-business",
            title="Approved channel primary route",
            lodging_name="central_urban_hotel.json",
            transport_name="downtown_local_ground.json",
            activity_name="major_museum.json",
            summary="Approved-channel itinerary that preserves arrival buffers and central access.",
            strengths=["Channels and schedule protection remain policy aligned."],
            tradeoffs=["Costs run slightly above the leanest alternative."],
            evidence=["Approval-ready route is preserved as the primary scenario."],
            tags=["business", "approved", "primary"],
            quality_signal=0.83,
            value_signal=0.69,
            fit_signal=0.85,
            transport_status="approved",
            business_access_signal=0.9,
        ),
        _build_bundle(
            bundle_id="bundle:exception-business",
            title="Exception-nearest fallback route",
            lodging_name="vacation_rental.json",
            transport_name="scenic_rail.json",
            activity_name="wandering_district.json",
            summary="Fallback route retained when the compliant-first path is not viable.",
            strengths=["Still preserves a coherent trip when strict approval channels fail."],
            tradeoffs=["Needs exception handling and weaker schedule protection."],
            evidence=["Fallback remains explicit instead of disappearing from the route set."],
            tags=["business", "fallback", "exception"],
            quality_signal=0.71,
            value_signal=0.74,
            fit_signal=0.67,
            transport_status="restricted",
            business_access_signal=0.55,
        ),
    ]
    return CandidateSet(
        candidate_set_id="candidate-set:itinerary:business",
        trip_id="trip-itinerary-business",
        purpose="policy_comparison",
        seeds=[
            CandidateSeed(candidate_id=f"candidate:{bundle.bundle_id}", bundle=bundle)
            for bundle in bundles
        ],
        explanation=["Business route alternatives for primary-vs-fallback assembly tests."],
        source_refs=["fixture:itinerary:business"],
    )


def _leisure_objectives() -> ItineraryObjectives:
    return ItineraryObjectives(
        objective_id="obj:itinerary:leisure",
        trip_id="trip-itinerary-leisure",
        route_shape="regional_cluster",
        target_base_count=CountRange(min_value=1, max_value=2),
        move_density=MoveDensityTarget(max_moves=3, cadence_days=3),
        recovery_expectations=RecoveryExpectations(buffer_days=1, recovery_priority=0.62),
        day_structure=DayStructureObjectives(
            structure_level="moderate",
            wandering_support_level=0.75,
            reservation_density=0.4,
        ),
        discovery_strategy=DiscoveryStrategy(style="balanced", protect_open_blocks=True),
        budget_protection=BudgetProtection(
            protected_categories=["lodging", "food"],
            sensitivity=0.55,
        ),
        quality_floor_protection=QualityFloorProtection(required_categories=["lodging"]),
        lodging_strategy=LodgingStrategy(base_style="single_base", arrival_buffer_priority=0.5),
        transport_strategy=TransportStrategy(preferred_modes=["rail", "local_ground"]),
    )


def _business_objectives() -> BusinessPlanningObjectives:
    profile = _load_business_profile("client_meeting_profile.json")
    constraint_set = _load_constraint_set("policy_round_trip_exception.json")
    return derive_business_planning_objectives(
        profile,
        trip_id="trip-itinerary-business",
        constraint_set=constraint_set,
    )


def _run_leisure_ranking(candidate_set: CandidateSet) -> RankedResultSet:
    bundles = [seed.bundle for seed in candidate_set.seeds]
    return LeisureRankingEngine().rank_bundles(
        build_profile_from_overrides({}),
        _leisure_objectives(),
        bundles,
        trip_id=candidate_set.trip_id,
        purpose=candidate_set.purpose,
    )


def _run_business_ranking(candidate_set: CandidateSet) -> RankedResultSet:
    profile = _load_business_profile("client_meeting_profile.json")
    constraint_set = _load_constraint_set("policy_round_trip_exception.json")
    objectives = _business_objectives()
    bundles = [seed.bundle for seed in candidate_set.seeds]
    return BusinessRankingEngine().rank_bundles(
        profile,
        objectives,
        bundles,
        trip_id=candidate_set.trip_id,
        purpose=candidate_set.purpose,
        constraint_set=constraint_set,
    )


def test_assemble_itinerary_scenarios_preserves_leisure_alternatives() -> None:
    fixture = _load_json("itinerary", "scenarios", "leisure_multi_scenario.json")
    candidate_set = _leisure_candidate_set()
    ranked_results = _run_leisure_ranking(candidate_set)
    feasibility = [
        FeasibilityAssessment(
            assessment_id=f"assessment:{seed.bundle.bundle_id}",
            bundle_id=seed.bundle.bundle_id,
            feasible=True,
            recommended_for_ranking=True,
            schedule_protection_required=False,
            total_travel_minutes=50 + index * 15,
            total_transfer_count=index,
            friction_penalty_total=0.05 * index,
        )
        for index, seed in enumerate(candidate_set.seeds)
    ]

    result = assemble_itinerary_scenarios(
        ranked_results,
        candidate_set=candidate_set,
        objectives=_leisure_objectives(),
        feasibility_outputs=feasibility,
        title=cast(str, fixture["title"]),
    )

    assert [scenario.bundle_id for scenario in result.scenarios] == fixture["expected_bundle_order"]
    assert [scenario.scenario_summary.scenario_kind for scenario in result.scenarios] == fixture[
        "expected_kinds"
    ]
    assert all(scenario.scenario_summary.coherence_passed for scenario in result.scenarios)
    assert all(scenario.explanation_records for scenario in result.scenarios)
    assert result.explanation[0] == "objective_mode:leisure"


def test_assemble_itinerary_scenarios_supports_business_primary_and_fallback() -> None:
    fixture = _load_json("itinerary", "scenarios", "business_primary_vs_fallback.json")
    candidate_set = _business_candidate_set()
    ranked_results = _run_business_ranking(candidate_set)
    feasibility = {
        "bundle:approved-business": FeasibilityAssessment(
            assessment_id="assessment:approved-business",
            bundle_id="bundle:approved-business",
            feasible=True,
            recommended_for_ranking=True,
            schedule_protection_required=True,
            total_travel_minutes=55,
            total_transfer_count=1,
            friction_penalty_total=0.08,
        ),
        "bundle:exception-business": FeasibilityAssessment(
            assessment_id="assessment:exception-business",
            bundle_id="bundle:exception-business",
            feasible=True,
            recommended_for_ranking=False,
            schedule_protection_required=True,
            total_travel_minutes=95,
            total_transfer_count=2,
            friction_penalty_total=0.21,
            blocking_reasons=["Manual policy exception review is required before booking."],
        ),
    }

    result = assemble_itinerary_scenarios(
        ranked_results,
        candidate_set=candidate_set,
        objectives=_business_objectives(),
        feasibility_outputs=feasibility,
        title=cast(str, fixture["title"]),
    )

    assert [scenario.bundle_id for scenario in result.scenarios] == fixture["expected_bundle_order"]
    assert [scenario.scenario_summary.scenario_kind for scenario in result.scenarios] == fixture[
        "expected_kinds"
    ]
    fallback_codes = [tradeoff.code for tradeoff in result.scenarios[1].unresolved_tradeoffs]
    for code in fixture["expected_fallback_tradeoff_codes"]:
        assert code in fallback_codes
    assert result.explanation[0] == "objective_mode:business"
    assert result.scenarios[0].scenario_summary.recommended_for_selection is True
    assert result.scenarios[1].scenario_summary.recommended_for_selection is False
    assert (
        result.scenarios[1].unresolved_tradeoffs[0].tradeoff_id
        == "blocking:bundle:exception-business:1"
    )
    assert (
        result.scenarios[1].unresolved_tradeoffs[1].tradeoff_id
        == "ranking:bundle:exception-business:not-recommended"
    )


def test_assemble_itinerary_scenarios_marks_infeasible_results_as_not_coherent() -> None:
    candidate_set = _leisure_candidate_set()
    ranked_results = _run_leisure_ranking(candidate_set)
    lead_bundle = candidate_set.seeds[0].bundle

    result = assemble_itinerary_scenarios(
        ranked_results,
        candidate_set=candidate_set,
        objectives=_leisure_objectives(),
        feasibility_outputs={
            lead_bundle.bundle_id: FeasibilityAssessment(
                assessment_id=f"assessment:{lead_bundle.bundle_id}",
                bundle_id=lead_bundle.bundle_id,
                feasible=False,
                recommended_for_ranking=True,
                schedule_protection_required=False,
                total_travel_minutes=65,
                total_transfer_count=1,
                friction_penalty_total=0.12,
            )
        },
        max_scenarios=1,
    )

    assert result.scenarios[0].scenario_summary.feasible is False
    assert result.scenarios[0].scenario_summary.coherence_passed is False


def test_scenario_search_result_validates_purpose_against_shared_vocab() -> None:
    candidate_set = _leisure_candidate_set()
    ranked_results = _run_leisure_ranking(candidate_set)
    result = assemble_itinerary_scenarios(
        ranked_results,
        candidate_set=candidate_set,
        objectives=_leisure_objectives(),
        max_scenarios=1,
    )

    scenario = result.scenarios[0]
    with pytest.raises(ValueError, match="purpose must be one of"):
        ScenarioSearchResult(
            search_id=result.search_id,
            trip_id=result.trip_id,
            purpose="ad_hoc",
            title=result.title,
            source_result_set_id=result.source_result_set_id,
            scenarios=[scenario],
            explanation=list(result.explanation),
            source_refs=list(result.source_refs),
        )
