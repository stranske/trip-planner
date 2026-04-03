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
    assessment = evaluate_bundle_feasibility(_load_bundle("excessive_transfer_burden_route.json"))

    assert assessment.feasible is True
    assert assessment.recommended_for_ranking is True
    assert assessment.total_transfer_count >= 2
    assert assessment.friction_penalty_total > 0.7
    assert any("high_transfer_burden" in move_cost.warnings for move_cost in assessment.move_costs)


def test_unrealistic_same_day_chain_is_blocked() -> None:
    assessment = evaluate_bundle_feasibility(_load_bundle("unrealistic_same_day_chaining.json"))

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
        conflict.code == "tight_schedule_protection" for conflict in assessment.timing_conflicts
    )


def test_missing_activity_window_is_reported_without_hard_block() -> None:
    payload = json.loads(
        _fixture_path("coherent_low_friction_route.json").read_text(encoding="utf-8")
    )
    payload["activity_options"][0]["timing_summary"]["typical_start_window"] = ""

    assessment = evaluate_bundle_feasibility(InventoryBundle.from_dict(payload))

    assert assessment.feasible is True
    assert "activity:activity-kyoto-museum:typical_start_window" in assessment.missing_data_fields


def test_malformed_times_do_not_crash_feasibility_evaluation() -> None:
    payload = json.loads(
        _fixture_path("coherent_low_friction_route.json").read_text(encoding="utf-8")
    )
    payload["transport_options"][0]["timing_summary"]["arrival_local"] = "not-a-timestamp"
    payload["lodging_options"][0]["booking_terms"]["checkin_window"] = "not-a-window"

    assessment = evaluate_bundle_feasibility(InventoryBundle.from_dict(payload))

    assert assessment.feasible is True
    assert assessment.total_travel_minutes == 32
    assert "late_arrival_checkin_conflict" not in assessment.blocking_reasons


def test_candidate_seed_uses_representative_travel_totals() -> None:
    payload = json.loads(
        _fixture_path("coherent_low_friction_route.json").read_text(encoding="utf-8")
    )
    payload["composition_summary"]["assembly_role"] = "candidate_seed"

    alternate_transport = json.loads(json.dumps(payload["transport_options"][0]))
    alternate_transport["option_id"] = "transport-kyoto-osaka-slow"
    alternate_transport["name"] = "Slow regional detour"
    alternate_transport["timing_summary"]["duration_minutes"] = 480
    alternate_transport["timing_summary"]["departure_local"] = "2026-04-10T06:00:00+09:00"
    alternate_transport["timing_summary"]["arrival_local"] = "2026-04-10T14:00:00+09:00"
    alternate_transport["transfer_burden"]["transfer_count"] = 3
    alternate_transport["transfer_burden"]["self_navigation_burden_signal"] = 0.8
    alternate_transport["transfer_burden"]["baggage_complexity_signal"] = 0.7
    alternate_transport["transfer_burden"]["connection_risk_signal"] = 0.65
    alternate_transport["transfer_burden"]["schedule_protection_signal"] = 0.4
    payload["transport_options"].append(alternate_transport)
    payload["composition_summary"]["component_option_ids"] = [
        item["option_id"]
        for item in payload["lodging_options"]
        + payload["transport_options"]
        + payload["activity_options"]
    ]

    assessment = evaluate_bundle_feasibility(InventoryBundle.from_dict(payload))

    assert assessment.total_travel_minutes == 32
    assert assessment.total_transfer_count == 0
    assert any("lowest-friction transport option" in note for note in assessment.notes)
