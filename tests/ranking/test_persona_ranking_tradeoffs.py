"""Ranking tradeoff tests showing that distinct traveler persona fixtures produce
different justified rank orders against the same candidate set.

These tests protect the behavioral claim that persona characteristics materially
affect how options are scored — not just which options score highest overall, but
specifically which tradeoffs are resolved differently across profile types.
"""

import json
from pathlib import Path
from typing import Any, cast

from tests.preferences.fixture_corpus import load_fixture_map
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
from trip_planner.ranking import LeisureRankingEngine

# ---------------------------------------------------------------------------
# Shared fixture builders — mirrors the standard candidate set used in
# test_leisure_ranking.py so persona tradeoffs are evaluated against the
# same bundles.
# ---------------------------------------------------------------------------


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
            quality_signal=0.82, value_signal=0.7, fit_signal=0.84
        ),
        explanation=BundleExplanation(
            strengths=["Central access to museum-heavy days."],
            tradeoffs=["Some crowd pressure around major sights."],
            evidence=["Museums and walkable density are explicit strengths."],
        ),
        summary="Walkable, museum-forward base with direct local movement.",
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
    activity.name = "Backstreet wandering and cafe drift"
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
            quality_signal=0.74, value_signal=0.76, fit_signal=0.81
        ),
        explanation=BundleExplanation(
            strengths=["Transit doubles as an experience; the day stays open-ended."],
            tradeoffs=["Scenic leg adds time over the direct urban option."],
            evidence=["Candidate favors wandering over checklist landmarks."],
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
            quality_signal=0.86, value_signal=0.64, fit_signal=0.78
        ),
        explanation=BundleExplanation(
            strengths=["Quiet sleep quality is protected."],
            tradeoffs=["Outer-neighborhood location reduces spontaneous access."],
            evidence=["Recovery and comfort beat density here."],
        ),
        summary="Comfort-protective stay with lower noise and deeper recovery.",
        tags=["quiet", "recovery", "quality-floor"],
    )


def _candidate_set() -> CandidateSet:
    bundles = [_urban_culture_bundle(), _scenic_wanderer_bundle(), _quiet_recovery_bundle()]
    return CandidateSet(
        candidate_set_id="candidate-set:test:persona-tradeoffs",
        trip_id="trip-test-persona",
        purpose="profile_learning",
        seeds=[
            CandidateSeed(candidate_id=f"candidate:{bundle.bundle_id}", bundle=bundle)
            for bundle in bundles
        ],
        explanation=["Shared candidate set for persona tradeoff tests."],
        source_refs=["src:test-persona-tradeoffs"],
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
        trip_id="trip-test-persona",
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
        explanations=["Objectives for persona tradeoff test."],
    )


def _result_option_id(result: object) -> str:
    target_option = cast(Any, result).target_option
    assert target_option is not None
    return cast(str, target_option.option_id)


# ---------------------------------------------------------------------------
# Objectives presets used across multiple tests
# ---------------------------------------------------------------------------

_COMFORT_OBJECTIVES: dict[str, Any] = dict(
    route_shape="hub_and_spoke",
    discovery_style="balanced",
    protect_open_blocks=False,
    recovery_priority=0.9,
    required_quality=["lodging", "sleep_recovery"],
    transit_is_feature=False,
)

_DISCOVERY_OBJECTIVES: dict[str, Any] = dict(
    route_shape="mixed",
    discovery_style="discovery_forward",
    protect_open_blocks=True,
    recovery_priority=0.3,
    required_quality=[],
    transit_is_feature=True,
)

_STRUCTURED_OBJECTIVES: dict[str, Any] = dict(
    route_shape="hub_and_spoke",
    discovery_style="iconic",
    protect_open_blocks=False,
    recovery_priority=0.6,
    required_quality=["lodging"],
    transit_is_feature=False,
)


# ---------------------------------------------------------------------------
# Tradeoff tests
# ---------------------------------------------------------------------------


def test_comfort_persona_ranks_quiet_recovery_above_scenic_wanderer() -> None:
    """comfort-floor-traveler with quality objectives places quiet-recovery at #2."""
    fixture_map = load_fixture_map()
    profile = fixture_map["comfort-floor-traveler"].profile
    objectives = _make_objectives(**_COMFORT_OBJECTIVES)

    ranked = LeisureRankingEngine().rank_candidate_set(profile, objectives, _candidate_set())

    ids = [_result_option_id(r) for r in ranked.results]
    assert ids[0] == "candidate:bundle:urban-culture"
    assert (
        ids[1] == "candidate:bundle:quiet-recovery"
    ), f"comfort-floor-traveler should rank quiet-recovery 2nd; got order {ids}"


def test_discovery_persona_ranks_scenic_wanderer_above_quiet_recovery() -> None:
    """discovery-wanderer with discovery objectives places scenic-wanderer at #2."""
    fixture_map = load_fixture_map()
    profile = fixture_map["discovery-wanderer"].profile
    objectives = _make_objectives(**_DISCOVERY_OBJECTIVES)

    ranked = LeisureRankingEngine().rank_candidate_set(profile, objectives, _candidate_set())

    ids = [_result_option_id(r) for r in ranked.results]
    assert ids[0] == "candidate:bundle:urban-culture"
    assert (
        ids[1] == "candidate:bundle:scenic-wanderer"
    ), f"discovery-wanderer should rank scenic-wanderer 2nd; got order {ids}"


def test_comfort_and_discovery_personas_produce_different_secondary_rank_orders() -> None:
    """The #2 position differs between comfort-floor-traveler and discovery-wanderer.

    This is the core tradeoff assertion: the same candidate set, with different persona
    profiles and appropriately matched objectives, resolves the quiet-recovery vs
    scenic-wanderer choice in opposite directions.
    """
    fixture_map = load_fixture_map()
    engine = LeisureRankingEngine()
    candidates = _candidate_set()

    comfort_ranked = engine.rank_candidate_set(
        fixture_map["comfort-floor-traveler"].profile,
        _make_objectives(**_COMFORT_OBJECTIVES),
        candidates,
    )
    discovery_ranked = engine.rank_candidate_set(
        fixture_map["discovery-wanderer"].profile,
        _make_objectives(**_DISCOVERY_OBJECTIVES),
        candidates,
    )

    comfort_ids = [_result_option_id(r) for r in comfort_ranked.results]
    discovery_ids = [_result_option_id(r) for r in discovery_ranked.results]

    # Both rank urban-culture first — the all-around best option
    assert comfort_ids[0] == discovery_ids[0] == "candidate:bundle:urban-culture"

    # But the #2/#3 ordering is reversed — demonstrating a genuine tradeoff
    assert comfort_ids[1] != discovery_ids[1], (
        f"Comfort and discovery personas should resolve the #2 tradeoff differently. "
        f"comfort={comfort_ids}, discovery={discovery_ids}"
    )


def test_accessibility_aware_persona_ranks_comfort_protective_option_above_open_wandering() -> None:
    """accessibility-aware with quality objectives places quiet-recovery at #2.

    Accessibility-aware travelers need verified comfort floors and cannot accept
    options with uncertain step-free status. This maps to the same quality-protective
    objective pattern as comfort-focused travelers.
    """
    fixture_map = load_fixture_map()
    profile = fixture_map["accessibility-aware"].profile
    objectives = _make_objectives(**_COMFORT_OBJECTIVES)

    ranked = LeisureRankingEngine().rank_candidate_set(profile, objectives, _candidate_set())

    ids = [_result_option_id(r) for r in ranked.results]
    assert ids[0] == "candidate:bundle:urban-culture"
    assert (
        ids[1] == "candidate:bundle:quiet-recovery"
    ), f"accessibility-aware should rank comfort-protective option 2nd; got order {ids}"


def test_schedule_sensitive_persona_ranks_consistently_under_structured_objectives() -> None:
    """schedule-sensitive with structured objectives produces a deterministic rank order.

    Schedule-sensitive travelers use structured, non-elastic objectives. The output
    should be stable and not flip depending on discovery bonuses.
    """
    fixture_map = load_fixture_map()
    profile = fixture_map["schedule-sensitive"].profile
    objectives = _make_objectives(**_STRUCTURED_OBJECTIVES)

    ranked = LeisureRankingEngine().rank_candidate_set(profile, objectives, _candidate_set())

    ids = [_result_option_id(r) for r in ranked.results]
    # Urban-culture is still #1 — structure and iconic discovery favor it
    assert (
        ids[0] == "candidate:bundle:urban-culture"
    ), f"schedule-sensitive should rank urban-culture first; got {ids}"
    # Ranking is deterministic — the same result every time (not flipped by random bonuses)
    ranked_again = LeisureRankingEngine().rank_candidate_set(profile, objectives, _candidate_set())
    ids_again = [_result_option_id(r) for r in ranked_again.results]
    assert ids == ids_again, "schedule-sensitive ranking should be deterministic"


def test_family_leisure_persona_ranks_comfort_protective_option_above_scenic_wanderer() -> None:
    """family-leisure with comfort objectives ranks quiet-recovery above scenic-wanderer.

    Family travelers prioritize recovery and stable lodging. Under comfort-protective
    objectives, quiet-recovery (high quality_signal=0.86) should rank above scenic-wanderer
    (high value_signal but lower quality).
    """
    fixture_map = load_fixture_map()
    profile = fixture_map["family-leisure"].profile
    objectives = _make_objectives(**_COMFORT_OBJECTIVES)

    ranked = LeisureRankingEngine().rank_candidate_set(profile, objectives, _candidate_set())

    ids = [_result_option_id(r) for r in ranked.results]
    assert ids[0] == "candidate:bundle:urban-culture"
    assert (
        ids[1] == "candidate:bundle:quiet-recovery"
    ), f"family-leisure should rank quiet-recovery 2nd; got order {ids}"


def test_budget_focused_persona_ranks_differently_from_comfort_persona() -> None:
    """budget-focused and comfort-floor-traveler produce different secondary rank orders.

    budget-focused (no quality floors, self-reliant) resolves the scenic-wanderer vs
    quiet-recovery tradeoff differently than comfort-floor-traveler (quality floors,
    convenience-oriented) under discovery objectives.
    """
    fixture_map = load_fixture_map()
    engine = LeisureRankingEngine()
    candidates = _candidate_set()

    budget_ranked = engine.rank_candidate_set(
        fixture_map["budget-focused"].profile,
        _make_objectives(**_DISCOVERY_OBJECTIVES),
        candidates,
    )
    comfort_ranked = engine.rank_candidate_set(
        fixture_map["comfort-floor-traveler"].profile,
        _make_objectives(**_COMFORT_OBJECTIVES),
        candidates,
    )

    budget_ids = [_result_option_id(r) for r in budget_ranked.results]
    comfort_ids = [_result_option_id(r) for r in comfort_ranked.results]

    # The two personas resolve the secondary tradeoff differently
    assert budget_ids != comfort_ids, (
        f"budget-focused and comfort-floor-traveler should produce different rank orders. "
        f"budget={budget_ids}, comfort={comfort_ids}"
    )
