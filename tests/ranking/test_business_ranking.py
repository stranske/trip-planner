import json
from pathlib import Path
from typing import Any, cast

import pytest

from trip_planner.business import (
    BusinessPlanningObjectives,
    BusinessTravelProfile,
    PolicyConstraintSet,
    derive_business_planning_objectives,
)
from trip_planner.candidates import CandidateSeed, CandidateSet
from trip_planner.itinerary.feasibility import FeasibilityAssessment
from trip_planner.options import (
    BundleCompositionSummary,
    BundleExplanation,
    BundleProvenanceSummary,
    BundleQualityValueFitSummary,
    Destination,
    InventoryBundle,
    LodgingOption,
    TransportOption,
)
from trip_planner.ranking import BusinessRankingEngine


def _fixture_path(*parts: str) -> Path:
    return Path(__file__).resolve().parents[1].joinpath("fixtures", *parts)


def _load_json(*parts: str) -> dict[str, Any]:
    return json.loads(_fixture_path(*parts).read_text(encoding="utf-8"))


def _load_profile(name: str) -> BusinessTravelProfile:
    return BusinessTravelProfile.from_dict(_load_json("business", name))


def _load_constraint_set(name: str) -> PolicyConstraintSet:
    payload = _load_json("business", name)
    return PolicyConstraintSet(**payload["constraint_set"])


def _load_destination(name: str) -> Destination:
    return Destination.from_dict(_load_json("options", "destinations", name))


def _load_lodging(name: str) -> LodgingOption:
    return LodgingOption.from_dict(_load_json("options", "lodging", name))


def _load_transport(name: str) -> TransportOption:
    return TransportOption.from_dict(_load_json("options", "transport", name))


def _load_scenario(name: str) -> dict[str, Any]:
    return _load_json("ranking", "business", name)


def _result_option_id(result: object) -> str:
    target_option = cast(Any, result).target_option
    assert target_option is not None
    return cast(str, target_option.option_id)


def _conference_destination() -> Destination:
    destination = _load_destination("kyoto_city.json")
    destination.destination_id = "dest-conference"
    destination.name = "Chicago Conference District"
    return destination


def _home_destination() -> Destination:
    destination = _load_destination("kyoto_city.json")
    destination.destination_id = "dest-home"
    destination.name = "Home Base"
    return destination


def _site_destination() -> Destination:
    destination = _load_destination("gion_neighborhood.json")
    destination.destination_id = "dest-site"
    destination.name = "Remote Site Visit District"
    return destination


def _compliant_conference_bundle() -> InventoryBundle:
    home = _home_destination()
    destination = _conference_destination()
    lodging = _load_lodging("conference_hotel.json")
    transport = _load_transport("coastal_flight.json")
    lodging.destination_id = destination.destination_id
    transport.origin_id = "dest-home"
    transport.destination_id = destination.destination_id
    transport.booking_terms.booking_channel = "Concur"
    transport.booking_terms.approved_channels = ["Concur", "managed-travel"]
    transport.policy_summary.business_approval_status = "preferred"
    transport.policy_summary.approved_booking_channel = True
    transport.policy_summary.comparable_reference_ids = ["cmp-flight-1"]
    transport.fit_summary.schedule_fit_signal = 0.92
    transport.transfer_burden.schedule_protection_signal = 0.9
    return InventoryBundle(
        bundle_id="bundle:compliant-conference",
        title="Compliant conference package",
        destinations=[home, destination],
        lodging_options=[lodging],
        transport_options=[transport],
        composition_summary=BundleCompositionSummary(
            assembly_role="business_candidate",
            primary_destination_id=destination.destination_id,
            component_option_ids=[lodging.option_id, transport.option_id],
        ),
        provenance_summary=BundleProvenanceSummary(
            source_refs=[
                lodging.source_refs[0].provenance_id,
                transport.source_refs[0].provenance_id,
            ],
            booking_links=[lodging.booking_links[0], transport.booking_links[0]],
        ),
        quality_value_fit=BundleQualityValueFitSummary(
            quality_signal=0.88,
            value_signal=0.79,
            fit_signal=0.9,
        ),
        explanation=BundleExplanation(
            strengths=["Conference hotel is already business-approved."],
            tradeoffs=["Costs more than fringe properties."],
            evidence=["Comparable packet is easy to assemble."],
        ),
        summary="Managed-travel conference bundle with strong policy posture.",
        tags=["business-approved", "conference", "policy-ready"],
    )


def _cheaper_restricted_bundle() -> InventoryBundle:
    home = _home_destination()
    destination = _conference_destination()
    lodging = _load_lodging("central_urban_hotel.json")
    transport = _load_transport("island_ferry.json")
    lodging.destination_id = destination.destination_id
    lodging.feasibility.business_approval_status = "restricted"
    lodging.value_summary.policy_value_signal = 0.45
    transport.origin_id = "dest-home"
    transport.destination_id = destination.destination_id
    transport.booking_terms.booking_channel = "direct"
    transport.policy_summary.business_approval_status = "restricted"
    transport.policy_summary.approved_booking_channel = False
    transport.fit_summary.schedule_fit_signal = 0.55
    transport.transfer_burden.schedule_protection_signal = 0.44
    return InventoryBundle(
        bundle_id="bundle:restricted-budget",
        title="Restricted budget package",
        destinations=[home, destination],
        lodging_options=[lodging],
        transport_options=[transport],
        composition_summary=BundleCompositionSummary(
            assembly_role="business_candidate",
            primary_destination_id=destination.destination_id,
            component_option_ids=[lodging.option_id, transport.option_id],
        ),
        provenance_summary=BundleProvenanceSummary(
            source_refs=[transport.source_refs[0].provenance_id],
            booking_links=[transport.booking_links[0]],
        ),
        quality_value_fit=BundleQualityValueFitSummary(
            quality_signal=0.63,
            value_signal=0.82,
            fit_signal=0.58,
        ),
        explanation=BundleExplanation(
            strengths=["Lower sticker price."],
            tradeoffs=["Direct booking and weaker approval posture."],
        ),
        summary="Budget-first bundle with weaker policy posture and timing protection.",
        tags=["budget", "restricted"],
    )


def _schedule_protected_bundle() -> InventoryBundle:
    home = _home_destination()
    destination = _conference_destination()
    lodging = _load_lodging("conference_hotel.json")
    transport = _load_transport("coastal_flight.json")
    lodging.destination_id = destination.destination_id
    lodging.location_summary.business_access_signal = 0.95
    transport.origin_id = "dest-home"
    transport.destination_id = destination.destination_id
    transport.booking_terms.booking_channel = "managed-travel"
    transport.policy_summary.business_approval_status = "approved"
    transport.policy_summary.approved_booking_channel = True
    transport.fit_summary.schedule_fit_signal = 0.96
    transport.transfer_burden.schedule_protection_signal = 0.94
    return InventoryBundle(
        bundle_id="bundle:schedule-protected",
        title="Schedule-protected business package",
        destinations=[home, destination],
        lodging_options=[lodging],
        transport_options=[transport],
        composition_summary=BundleCompositionSummary(
            assembly_role="business_candidate",
            primary_destination_id=destination.destination_id,
            component_option_ids=[lodging.option_id, transport.option_id],
        ),
        provenance_summary=BundleProvenanceSummary(
            source_refs=[
                lodging.source_refs[0].provenance_id,
                transport.source_refs[0].provenance_id,
            ],
            booking_links=[lodging.booking_links[0], transport.booking_links[0]],
        ),
        quality_value_fit=BundleQualityValueFitSummary(
            quality_signal=0.86,
            value_signal=0.72,
            fit_signal=0.91,
        ),
        explanation=BundleExplanation(
            strengths=["Buffers client meeting arrival and workspace readiness."],
            tradeoffs=["Costs more than the bargain option."],
            evidence=["Business access and direct timing are explicit."],
        ),
        summary="Mission-critical client bundle with protected arrival timing.",
        tags=["schedule-protected", "client-meeting"],
    )


def _cheap_fragile_bundle() -> InventoryBundle:
    home = _home_destination()
    destination = _conference_destination()
    lodging = _load_lodging("quiet_outer_area_hotel.json")
    transport = _load_transport("regional_rental_car.json")
    lodging.destination_id = destination.destination_id
    lodging.location_summary.business_access_signal = 0.52
    transport.origin_id = "dest-home"
    transport.destination_id = destination.destination_id
    transport.fit_summary.schedule_fit_signal = 0.49
    transport.transfer_burden.schedule_protection_signal = 0.38
    transport.policy_summary.business_approval_status = "approved"
    transport.policy_summary.approved_booking_channel = True
    return InventoryBundle(
        bundle_id="bundle:cheap-fragile",
        title="Cheap but fragile schedule package",
        destinations=[home, destination],
        lodging_options=[lodging],
        transport_options=[transport],
        composition_summary=BundleCompositionSummary(
            assembly_role="business_candidate",
            primary_destination_id=destination.destination_id,
            component_option_ids=[lodging.option_id, transport.option_id],
        ),
        provenance_summary=BundleProvenanceSummary(
            source_refs=[transport.source_refs[0].provenance_id],
        ),
        quality_value_fit=BundleQualityValueFitSummary(
            quality_signal=0.6,
            value_signal=0.84,
            fit_signal=0.54,
        ),
        explanation=BundleExplanation(
            strengths=["Lower cost envelope."],
            tradeoffs=["Arrival risk and weaker business access."],
        ),
        summary="Lower-cost bundle with weaker timing protection for business meetings.",
        tags=["budget", "fragile-schedule"],
    )


def _policy_nearest_exception_bundle() -> InventoryBundle:
    home = _home_destination()
    destination = _site_destination()
    lodging = _load_lodging("conference_hotel.json")
    transport = _load_transport("regional_rental_car.json")
    lodging.destination_id = destination.destination_id
    lodging.feasibility.business_approval_status = "restricted"
    lodging.location_summary.business_access_signal = 0.91
    transport.origin_id = "dest-home"
    transport.destination_id = destination.destination_id
    transport.policy_summary.business_approval_status = "restricted"
    transport.policy_summary.approval_required = True
    transport.fit_summary.schedule_fit_signal = 0.9
    transport.transfer_burden.schedule_protection_signal = 0.86
    transport.booking_terms.comparable_reference_ids = ["cmp-drive-1", "cmp-drive-2"]
    return InventoryBundle(
        bundle_id="bundle:policy-nearest-exception",
        title="Policy-nearest exception package",
        destinations=[home, destination],
        lodging_options=[lodging],
        transport_options=[transport],
        composition_summary=BundleCompositionSummary(
            assembly_role="business_candidate",
            primary_destination_id=destination.destination_id,
            component_option_ids=[lodging.option_id, transport.option_id],
        ),
        provenance_summary=BundleProvenanceSummary(
            source_refs=[
                lodging.source_refs[0].provenance_id,
                transport.source_refs[0].provenance_id,
            ],
            booking_links=[lodging.booking_links[0], transport.booking_links[0]],
        ),
        quality_value_fit=BundleQualityValueFitSummary(
            quality_signal=0.84,
            value_signal=0.69,
            fit_signal=0.89,
        ),
        explanation=BundleExplanation(
            strengths=["Preserves site access and arrival-readiness."],
            tradeoffs=["Needs exception approval and comparables."],
            evidence=["Comparable references already attached for escalation."],
        ),
        summary="Exception-ready bundle that stays close to policy while protecting the site-visit schedule.",
        tags=["exception-path", "policy-nearest"],
    )


def _weak_compliant_bundle() -> InventoryBundle:
    home = _home_destination()
    destination = _site_destination()
    lodging = _load_lodging("central_urban_hotel.json")
    transport = _load_transport("island_ferry.json")
    lodging.destination_id = destination.destination_id
    lodging.location_summary.business_access_signal = 0.41
    lodging.feasibility.business_approval_status = "approved"
    transport.origin_id = "dest-home"
    transport.destination_id = destination.destination_id
    transport.policy_summary.business_approval_status = "approved"
    transport.policy_summary.approved_booking_channel = True
    transport.fit_summary.schedule_fit_signal = 0.43
    transport.transfer_burden.schedule_protection_signal = 0.31
    return InventoryBundle(
        bundle_id="bundle:weak-compliant",
        title="Weak but compliant package",
        destinations=[home, destination],
        lodging_options=[lodging],
        transport_options=[transport],
        composition_summary=BundleCompositionSummary(
            assembly_role="business_candidate",
            primary_destination_id=destination.destination_id,
            component_option_ids=[lodging.option_id, transport.option_id],
        ),
        provenance_summary=BundleProvenanceSummary(
            source_refs=[transport.source_refs[0].provenance_id],
        ),
        quality_value_fit=BundleQualityValueFitSummary(
            quality_signal=0.58,
            value_signal=0.74,
            fit_signal=0.47,
        ),
        explanation=BundleExplanation(
            strengths=["Formally compliant booking path."],
            tradeoffs=["Poor site access and weak timing protection."],
        ),
        summary="Compliant option that struggles to preserve the actual site-visit mission.",
        tags=["compliant", "weak-fit"],
    )


def _candidate_set(*bundles: InventoryBundle) -> CandidateSet:
    return CandidateSet(
        candidate_set_id="candidate-set:test:business",
        trip_id="trip-test-business",
        purpose="final_selection",
        seeds=[
            CandidateSeed(
                candidate_id=f"candidate:{bundle.bundle_id}",
                bundle=bundle,
                supported_purposes=["final_selection"],
                inclusion_reasons=[bundle.summary or bundle.title],
            )
            for bundle in bundles
        ],
        explanation=["Shared candidate set for business ranking tests."],
        source_refs=["src:test-business-candidate-set"],
    )


def _objectives_for_scenario(
    scenario_name: str,
) -> tuple[BusinessTravelProfile, BusinessPlanningObjectives, PolicyConstraintSet | None]:
    scenario = _load_scenario(scenario_name)
    profile = _load_profile(cast(str, scenario["profile_fixture"]))
    constraint_fixture = cast(str | None, scenario["constraint_fixture"])
    constraint_set = _load_constraint_set(constraint_fixture) if constraint_fixture else None
    objectives = derive_business_planning_objectives(
        profile,
        trip_id=f"trip:{scenario_name}",
        constraint_set=constraint_set,
    )
    return profile, objectives, constraint_set


@pytest.mark.parametrize(
    ("scenario_name", "bundles"),
    [
        (
            "compliant_conference_trip.json",
            (_compliant_conference_bundle(), _cheaper_restricted_bundle()),
        ),
        (
            "schedule_sensitive_client_trip.json",
            (_schedule_protected_bundle(), _cheap_fragile_bundle()),
        ),
        (
            "likely_exception_trip.json",
            (_policy_nearest_exception_bundle(), _weak_compliant_bundle()),
        ),
    ],
)
def test_business_ranking_reorders_candidates_by_business_constraints(
    scenario_name: str,
    bundles: tuple[InventoryBundle, InventoryBundle],
) -> None:
    scenario = _load_scenario(scenario_name)
    profile, objectives, constraint_set = _objectives_for_scenario(scenario_name)
    candidate_set = _candidate_set(*bundles)

    results = BusinessRankingEngine().rank_candidate_set(
        profile,
        objectives,
        candidate_set,
        constraint_set=constraint_set,
    )

    assert _result_option_id(results.results[0]) == scenario["expected_top_result_id"]
    assert results.results[0].score > results.results[1].score


def test_business_rank_bundles_rejects_empty_bundle_sequence() -> None:
    profile, objectives, constraint_set = _objectives_for_scenario("compliant_conference_trip.json")

    with pytest.raises(ValueError, match="bundles must contain at least one InventoryBundle"):
        BusinessRankingEngine().rank_bundles(
            profile,
            objectives,
            [],
            trip_id="trip-empty-business",
            constraint_set=constraint_set,
        )


def test_business_ranking_uses_provided_feasibility_outputs() -> None:
    profile, objectives, constraint_set = _objectives_for_scenario(
        "schedule_sensitive_client_trip.json"
    )
    bundles = (_schedule_protected_bundle(), _cheap_fragile_bundle())
    candidate_set = _candidate_set(*bundles)
    fragile = bundles[1]
    assessments = {
        fragile.bundle_id: FeasibilityAssessment(
            assessment_id=f"assessment:{fragile.bundle_id}",
            bundle_id=fragile.bundle_id,
            feasible=False,
            recommended_for_ranking=False,
            schedule_protection_required=True,
            total_travel_minutes=210,
            total_transfer_count=2,
            friction_penalty_total=0.54,
            confidence_signal=0.61,
            blocking_reasons=["schedule_break"],
        )
    }

    results = BusinessRankingEngine().rank_candidate_set(
        profile,
        objectives,
        candidate_set,
        constraint_set=constraint_set,
        feasibility_outputs=assessments,
    )

    low_result = results.results[-1]
    assert _result_option_id(low_result) == "candidate:bundle:cheap-fragile"
    assert any(risk.code == "schedule_break" for risk in low_result.unresolved_risks)
    assert any(
        penalty.reason_code == "feasibility_not_recommended"
        for penalty in low_result.score_breakdown.penalties
    )


def test_business_ranking_exposes_proposal_readiness_records() -> None:
    profile, objectives, constraint_set = _objectives_for_scenario("likely_exception_trip.json")
    bundle = _policy_nearest_exception_bundle()

    result_set = BusinessRankingEngine().rank_bundles(
        profile,
        objectives,
        [bundle],
        trip_id="trip-business-docs",
        constraint_set=constraint_set,
    )

    result = result_set.results[0]
    assert result.explanation_records[0].headline
    assert result.confidence_summary.overall_confidence is not None
    assert "proposal_readiness" in [axis.key for axis in result_set.comparison_axes]
    assert result_set.comparison_axes[2].key == "proposal_readiness"


# ---------------------------------------------------------------------------
# Hard constraint: disallowed inventory cannot be outweighed by preference
# ---------------------------------------------------------------------------


def _disallowed_high_comfort_bundle() -> InventoryBundle:
    """Bundle with disallowed policy status but artificially high schedule/comfort signals."""
    home = _home_destination()
    destination = _conference_destination()
    lodging = _load_lodging("conference_hotel.json")
    transport = _load_transport("coastal_flight.json")
    lodging.destination_id = destination.destination_id
    # Excellent comfort and workspace signals
    lodging.room_summary.workspace_signal = 0.99
    lodging.room_summary.comfort_signal = 0.99
    lodging.location_summary.business_access_signal = 0.99
    # Hard policy block on both components
    lodging.feasibility.business_approval_status = "disallowed"
    transport.origin_id = "dest-home"
    transport.destination_id = destination.destination_id
    transport.policy_summary.business_approval_status = "disallowed"
    transport.policy_summary.approved_booking_channel = False
    # Excellent schedule signals — these must NOT outweigh the hard block
    transport.fit_summary.schedule_fit_signal = 0.99
    transport.transfer_burden.schedule_protection_signal = 0.99
    transport.experience_summary.workability_signal = 0.99
    transport.experience_summary.comfort_signal = 0.99
    return InventoryBundle(
        bundle_id="bundle:disallowed-high-comfort",
        title="Disallowed but high-comfort package",
        destinations=[home, destination],
        lodging_options=[lodging],
        transport_options=[transport],
        composition_summary=BundleCompositionSummary(
            assembly_role="business_candidate",
            primary_destination_id=destination.destination_id,
            component_option_ids=[lodging.option_id, transport.option_id],
        ),
        provenance_summary=BundleProvenanceSummary(
            source_refs=[transport.source_refs[0].provenance_id],
            booking_links=[transport.booking_links[0]],
        ),
        quality_value_fit=BundleQualityValueFitSummary(
            quality_signal=0.99,
            value_signal=0.99,
            fit_signal=0.99,
        ),
        explanation=BundleExplanation(
            strengths=["Excellent comfort, great timing."],
            tradeoffs=["Hard disallowed policy status on all components."],
        ),
        summary="High-comfort bundle explicitly blocked by policy.",
        tags=["disallowed", "high-comfort"],
    )


def _mediocre_compliant_bundle() -> InventoryBundle:
    """Bundle that is fully compliant but only mediocre on schedule/comfort."""
    home = _home_destination()
    destination = _conference_destination()
    lodging = _load_lodging("central_urban_hotel.json")
    transport = _load_transport("regional_rental_car.json")
    lodging.destination_id = destination.destination_id
    lodging.room_summary.workspace_signal = 0.5
    lodging.room_summary.comfort_signal = 0.5
    lodging.location_summary.business_access_signal = 0.55
    lodging.feasibility.business_approval_status = "approved"
    transport.origin_id = "dest-home"
    transport.destination_id = destination.destination_id
    transport.policy_summary.business_approval_status = "approved"
    transport.policy_summary.approved_booking_channel = True
    transport.fit_summary.schedule_fit_signal = 0.55
    transport.transfer_burden.schedule_protection_signal = 0.5
    return InventoryBundle(
        bundle_id="bundle:mediocre-compliant",
        title="Mediocre but compliant package",
        destinations=[home, destination],
        lodging_options=[lodging],
        transport_options=[transport],
        composition_summary=BundleCompositionSummary(
            assembly_role="business_candidate",
            primary_destination_id=destination.destination_id,
            component_option_ids=[lodging.option_id, transport.option_id],
        ),
        provenance_summary=BundleProvenanceSummary(
            source_refs=[transport.source_refs[0].provenance_id],
        ),
        quality_value_fit=BundleQualityValueFitSummary(
            quality_signal=0.55,
            value_signal=0.6,
            fit_signal=0.5,
        ),
        explanation=BundleExplanation(
            strengths=["Fully policy compliant."],
            tradeoffs=["Average comfort and timing."],
        ),
        summary="Compliant package with average attributes.",
        tags=["compliant"],
    )


def test_hard_block_cannot_be_outweighed_by_preference() -> None:
    """Disallowed inventory is capped below the minimum compliant score regardless of other signals."""
    profile, objectives, constraint_set = _objectives_for_scenario("compliant_conference_trip.json")
    engine = BusinessRankingEngine()

    disallowed = _disallowed_high_comfort_bundle()
    compliant = _mediocre_compliant_bundle()

    result_set = engine.rank_bundles(
        profile,
        objectives,
        [disallowed, compliant],
        trip_id="trip-hard-block-test",
        constraint_set=constraint_set,
    )

    disallowed_result = next(
        r
        for r in result_set.results
        if r.target_option and "disallowed" in r.target_option.option_id
    )
    compliant_result = next(
        r
        for r in result_set.results
        if r.target_option and "mediocre-compliant" in r.target_option.option_id
    )

    # Hard block ceiling applied
    assert disallowed_result.score <= engine.HARD_BLOCK_SCORE_CAP

    # Compliant ranks above hard-blocked even though blocked bundle has superior comfort
    assert compliant_result.score > disallowed_result.score
    assert compliant_result.rank < disallowed_result.rank

    # Breakdown carries the hard-block-cap penalty
    assert any(
        p.reason_code == "hard_block_cap" for p in disallowed_result.score_breakdown.penalties
    )

    # Explanation records surface the policy constraint impact
    policy_record = next(
        (r for r in disallowed_result.explanation_records if r.record_type == "penalty"),
        None,
    )
    assert policy_record is not None
    assert policy_record.machine_context.get("hard_blocked") == "true"
    assert "policy_compliance" in policy_record.factor_keys


# ---------------------------------------------------------------------------
# Soft constraint: restricted inventory reduces score by documented penalty
# ---------------------------------------------------------------------------


def _approved_bundle() -> InventoryBundle:
    home = _home_destination()
    destination = _conference_destination()
    lodging = _load_lodging("conference_hotel.json")
    transport = _load_transport("coastal_flight.json")
    lodging.destination_id = destination.destination_id
    lodging.feasibility.business_approval_status = "approved"
    transport.origin_id = "dest-home"
    transport.destination_id = destination.destination_id
    transport.policy_summary.business_approval_status = "approved"
    transport.policy_summary.approved_booking_channel = True
    transport.fit_summary.schedule_fit_signal = 0.75
    transport.transfer_burden.schedule_protection_signal = 0.7
    return InventoryBundle(
        bundle_id="bundle:approved-baseline",
        title="Approved baseline package",
        destinations=[home, destination],
        lodging_options=[lodging],
        transport_options=[transport],
        composition_summary=BundleCompositionSummary(
            assembly_role="business_candidate",
            primary_destination_id=destination.destination_id,
            component_option_ids=[lodging.option_id, transport.option_id],
        ),
        provenance_summary=BundleProvenanceSummary(
            source_refs=[transport.source_refs[0].provenance_id],
        ),
        quality_value_fit=BundleQualityValueFitSummary(
            quality_signal=0.75, value_signal=0.72, fit_signal=0.74
        ),
        explanation=BundleExplanation(strengths=["Approved."]),
        summary="Approved bundle for soft-penalty comparison.",
        tags=["approved"],
    )


def _restricted_bundle() -> InventoryBundle:
    """Same structure as approved bundle but with restricted approval status."""
    home = _home_destination()
    destination = _conference_destination()
    lodging = _load_lodging("conference_hotel.json")
    transport = _load_transport("coastal_flight.json")
    lodging.destination_id = destination.destination_id
    lodging.feasibility.business_approval_status = "restricted"
    transport.origin_id = "dest-home"
    transport.destination_id = destination.destination_id
    transport.policy_summary.business_approval_status = "restricted"
    transport.policy_summary.approved_booking_channel = False
    transport.fit_summary.schedule_fit_signal = 0.75
    transport.transfer_burden.schedule_protection_signal = 0.7
    return InventoryBundle(
        bundle_id="bundle:restricted-baseline",
        title="Restricted baseline package",
        destinations=[home, destination],
        lodging_options=[lodging],
        transport_options=[transport],
        composition_summary=BundleCompositionSummary(
            assembly_role="business_candidate",
            primary_destination_id=destination.destination_id,
            component_option_ids=[lodging.option_id, transport.option_id],
        ),
        provenance_summary=BundleProvenanceSummary(
            source_refs=[transport.source_refs[0].provenance_id],
        ),
        quality_value_fit=BundleQualityValueFitSummary(
            quality_signal=0.75, value_signal=0.72, fit_signal=0.74
        ),
        explanation=BundleExplanation(strengths=["Restricted."], tradeoffs=["Needs exception."]),
        summary="Restricted bundle for soft-penalty comparison.",
        tags=["restricted"],
    )


def test_soft_penalty_restricted_reduces_score() -> None:
    """Restricted inventory scores lower than otherwise-identical approved inventory."""
    profile, objectives, constraint_set = _objectives_for_scenario("compliant_conference_trip.json")
    engine = BusinessRankingEngine()

    approved = _approved_bundle()
    restricted = _restricted_bundle()

    result_set = engine.rank_bundles(
        profile,
        objectives,
        [approved, restricted],
        trip_id="trip-soft-penalty-test",
        constraint_set=constraint_set,
    )

    approved_result = next(
        r
        for r in result_set.results
        if r.target_option and "approved-baseline" in r.target_option.option_id
    )
    restricted_result = next(
        r
        for r in result_set.results
        if r.target_option and "restricted-baseline" in r.target_option.option_id
    )

    # Approved outscores restricted (all else equal)
    assert approved_result.score > restricted_result.score
    assert approved_result.rank < restricted_result.rank

    # Restricted bundle does NOT hit the hard block cap (it's a soft, not hard, constraint)
    assert restricted_result.score > engine.HARD_BLOCK_SCORE_CAP
    assert not any(
        p.reason_code == "hard_block_cap" for p in restricted_result.score_breakdown.penalties
    )


# ---------------------------------------------------------------------------
# Compliant option: no hard-block cap applied
# ---------------------------------------------------------------------------


def test_compliant_option_scores_without_policy_cap() -> None:
    """A fully compliant bundle scores above the hard block cap with no hard-block penalty."""
    profile, objectives, constraint_set = _objectives_for_scenario("compliant_conference_trip.json")
    engine = BusinessRankingEngine()

    compliant = _compliant_conference_bundle()

    result_set = engine.rank_bundles(
        profile,
        objectives,
        [compliant],
        trip_id="trip-compliant-check",
        constraint_set=constraint_set,
    )

    result = result_set.results[0]

    # Score exceeds the hard block ceiling
    assert result.score > engine.HARD_BLOCK_SCORE_CAP

    # No hard-block-cap penalty in the breakdown
    assert not any(p.reason_code == "hard_block_cap" for p in result.score_breakdown.penalties)

    # Explanation records present and structurally valid
    assert result.explanation_records
    assert result.explanation_records[0].record_type == "summary"


# ---------------------------------------------------------------------------
# Tie-breaking: preference signals resolve ties when policy compliance is equal
# ---------------------------------------------------------------------------


def _schedule_heavy_bundle() -> InventoryBundle:
    """Approved bundle with strong schedule protection signals."""
    home = _home_destination()
    destination = _conference_destination()
    lodging = _load_lodging("conference_hotel.json")
    transport = _load_transport("coastal_flight.json")
    lodging.destination_id = destination.destination_id
    lodging.feasibility.business_approval_status = "approved"
    lodging.location_summary.business_access_signal = 0.95
    transport.origin_id = "dest-home"
    transport.destination_id = destination.destination_id
    transport.policy_summary.business_approval_status = "approved"
    transport.policy_summary.approved_booking_channel = True
    # High schedule signals
    transport.fit_summary.schedule_fit_signal = 0.95
    transport.transfer_burden.schedule_protection_signal = 0.93
    # Lower value/cost signals
    transport.experience_summary.workability_signal = 0.55
    return InventoryBundle(
        bundle_id="bundle:schedule-heavy",
        title="Schedule-heavy package",
        destinations=[home, destination],
        lodging_options=[lodging],
        transport_options=[transport],
        composition_summary=BundleCompositionSummary(
            assembly_role="business_candidate",
            primary_destination_id=destination.destination_id,
            component_option_ids=[lodging.option_id, transport.option_id],
        ),
        provenance_summary=BundleProvenanceSummary(
            source_refs=[transport.source_refs[0].provenance_id],
        ),
        quality_value_fit=BundleQualityValueFitSummary(
            quality_signal=0.72, value_signal=0.58, fit_signal=0.72
        ),
        explanation=BundleExplanation(strengths=["Protected schedule."]),
        summary="Approved bundle optimised for schedule protection.",
        tags=["approved", "schedule-first"],
    )


def _cost_heavy_bundle() -> InventoryBundle:
    """Approved bundle with strong value signals but weaker schedule protection."""
    home = _home_destination()
    destination = _conference_destination()
    lodging = _load_lodging("central_urban_hotel.json")
    transport = _load_transport("regional_rental_car.json")
    lodging.destination_id = destination.destination_id
    lodging.feasibility.business_approval_status = "approved"
    lodging.location_summary.business_access_signal = 0.65
    transport.origin_id = "dest-home"
    transport.destination_id = destination.destination_id
    transport.policy_summary.business_approval_status = "approved"
    transport.policy_summary.approved_booking_channel = True
    # Lower schedule signals
    transport.fit_summary.schedule_fit_signal = 0.58
    transport.transfer_burden.schedule_protection_signal = 0.52
    # Higher value signals
    transport.experience_summary.workability_signal = 0.72
    return InventoryBundle(
        bundle_id="bundle:cost-heavy",
        title="Cost-heavy package",
        destinations=[home, destination],
        lodging_options=[lodging],
        transport_options=[transport],
        composition_summary=BundleCompositionSummary(
            assembly_role="business_candidate",
            primary_destination_id=destination.destination_id,
            component_option_ids=[lodging.option_id, transport.option_id],
        ),
        provenance_summary=BundleProvenanceSummary(
            source_refs=[transport.source_refs[0].provenance_id],
        ),
        quality_value_fit=BundleQualityValueFitSummary(
            quality_signal=0.62, value_signal=0.88, fit_signal=0.65
        ),
        explanation=BundleExplanation(strengths=["Lower cost."]),
        summary="Approved bundle optimised for cost posture.",
        tags=["approved", "cost-first"],
    )


def test_preference_signals_break_policy_tie() -> None:
    """When two bundles share equal policy compliance, preference signals determine rank."""
    # Use schedule-sensitive client trip — schedule_protection has highest weight after policy
    profile, objectives, constraint_set = _objectives_for_scenario(
        "schedule_sensitive_client_trip.json"
    )
    engine = BusinessRankingEngine()

    schedule_bundle = _schedule_heavy_bundle()
    cost_bundle = _cost_heavy_bundle()

    result_set = engine.rank_bundles(
        profile,
        objectives,
        [schedule_bundle, cost_bundle],
        trip_id="trip-tiebreak-test",
        constraint_set=constraint_set,
    )

    schedule_result = next(
        r
        for r in result_set.results
        if r.target_option and "schedule-heavy" in r.target_option.option_id
    )
    cost_result = next(
        r
        for r in result_set.results
        if r.target_option and "cost-heavy" in r.target_option.option_id
    )

    # Both are compliant — neither hits the hard block cap
    assert schedule_result.score > engine.HARD_BLOCK_SCORE_CAP
    assert cost_result.score > engine.HARD_BLOCK_SCORE_CAP

    # For a schedule-sensitive mission-critical trip, schedule protection should win
    schedule_contribution = next(
        c
        for c in schedule_result.score_breakdown.component_contributions
        if c.axis_key == "schedule_protection"
    )
    cost_schedule_contribution = next(
        c
        for c in cost_result.score_breakdown.component_contributions
        if c.axis_key == "schedule_protection"
    )
    assert schedule_contribution.weighted_impact > cost_schedule_contribution.weighted_impact
    assert schedule_result.score > cost_result.score
    assert schedule_result.rank < cost_result.rank
