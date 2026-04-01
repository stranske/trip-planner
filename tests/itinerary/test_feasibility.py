import json
from pathlib import Path

from trip_planner.itinerary import evaluate_bundle_feasibility
from trip_planner.options import InventoryBundle


def _fixture_path(name: str) -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures" / "itinerary" / "feasibility" / name


def _load_bundle(name: str) -> InventoryBundle:
    payload = json.loads(_fixture_path(name).read_text(encoding="utf-8"))
    return InventoryBundle.from_dict(payload)


def test_coherent_route_is_feasible_with_low_friction() -> None:
    assessment = evaluate_bundle_feasibility(_load_bundle("coherent_low_friction_route.json"))

    assert assessment.feasible is True
    assert assessment.recommended_for_ranking is True
    assert assessment.total_transfer_count == 0
    assert assessment.friction_penalty_total < 0.35
    assert not assessment.blocking_reasons


def test_excessive_transfer_route_stays_rankable_but_penalized() -> None:
    assessment = evaluate_bundle_feasibility(
        _load_bundle("excessive_transfer_burden_route.json")
    )

    assert assessment.feasible is True
    assert assessment.recommended_for_ranking is True
    assert assessment.total_transfer_count >= 2
    assert assessment.friction_penalty_total > 0.7
    assert any(
        "high_transfer_burden" in move_cost.warnings for move_cost in assessment.move_costs
    )


def test_unrealistic_same_day_chain_is_blocked() -> None:
    assessment = evaluate_bundle_feasibility(
        _load_bundle("unrealistic_same_day_chaining.json")
    )

    assert assessment.feasible is False
    assert assessment.recommended_for_ranking is False
    assert "activity_start_window_missed" in assessment.blocking_reasons
    assert any(conflict.blocking for conflict in assessment.timing_conflicts)


def test_business_schedule_protection_surfaces_warning() -> None:
    assessment = evaluate_bundle_feasibility(
        _load_bundle("business_tight_schedule_protection.json")
    )

    assert assessment.feasible is True
    assert assessment.schedule_protection_required is True
    assert any(
        conflict.code == "tight_schedule_protection"
        for conflict in assessment.timing_conflicts
    )


def test_missing_activity_window_is_reported_without_hard_block() -> None:
    payload = json.loads(
        _fixture_path("coherent_low_friction_route.json").read_text(encoding="utf-8")
    )
    payload["activity_options"][0]["timing_summary"]["typical_start_window"] = ""

    assessment = evaluate_bundle_feasibility(InventoryBundle.from_dict(payload))

    assert assessment.feasible is True
    assert "activity:activity-kyoto-museum:typical_start_window" in assessment.missing_data_fields
