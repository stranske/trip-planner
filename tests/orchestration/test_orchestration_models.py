import json
from pathlib import Path

import pytest

from trip_planner.orchestration import PlannerTurn


def _fixture_path(name: str) -> Path:
    fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures" / "orchestration" / "turns"
    return fixtures_dir / name


def _load_turn(name: str) -> PlannerTurn:
    payload = json.loads(_fixture_path(name).read_text(encoding="utf-8"))
    return PlannerTurn.from_dict(payload)


def test_leisure_turn_fixture_round_trips() -> None:
    turn = _load_turn("leisure_planning_turn.json")

    payload = turn.to_dict()

    assert payload["workflow_kind"] == "leisure_planning"
    assert payload["workflow_state"]["current_stage"] == "ranking"
    assert payload["outputs"][0]["output_kind"] == "question"
    assert payload["next_step"]["recommended_action_id"] == "action-rank-options"


def test_business_turn_fixture_round_trips() -> None:
    turn = _load_turn("business_planning_turn.json")

    payload = turn.to_dict()

    assert payload["mode"] == "business"
    assert payload["workflow_state"]["workflow_kind"] == "business_planning"
    assert payload["outputs"][0]["output_kind"] == "policy_summary"
    assert payload["transition"]["trigger"] == "policy_constraint"


def test_in_trip_adjustment_fixture_round_trips() -> None:
    turn = _load_turn("in_trip_adjustment_turn.json")

    payload = turn.to_dict()

    assert payload["turn_kind"] == "adjustment_pass"
    assert payload["workflow_state"]["current_stage"] == "replanning"
    assert payload["next_step"]["blocking_decision_ids"] == ["decision-accept-replan"]


def test_planner_turn_rejects_unknown_action_kind() -> None:
    payload = json.loads(_fixture_path("leisure_planning_turn.json").read_text())
    payload["actions"][0]["action_kind"] = "invent_magic"

    with pytest.raises(ValueError, match="action_kind"):
        PlannerTurn.from_dict(payload)


def test_planner_turn_rejects_unknown_next_step_action_reference() -> None:
    payload = json.loads(_fixture_path("business_planning_turn.json").read_text())
    payload["next_step"]["recommended_action_id"] = "missing-action"

    with pytest.raises(ValueError, match="recommended_action_id"):
        PlannerTurn.from_dict(payload)


def test_planner_turn_rejects_overlapping_open_and_completed_actions() -> None:
    payload = json.loads(_fixture_path("in_trip_adjustment_turn.json").read_text())
    payload["workflow_state"]["completed_action_ids"].append("action-replan-options")

    with pytest.raises(ValueError, match="must not overlap"):
        PlannerTurn.from_dict(payload)


def test_planner_turn_rejects_unknown_action_dependencies() -> None:
    payload = json.loads(_fixture_path("leisure_planning_turn.json").read_text())
    payload["actions"][0]["depends_on_action_ids"] = ["missing-action"]

    with pytest.raises(ValueError, match="depends_on_action_ids"):
        PlannerTurn.from_dict(payload)


def test_planner_turn_rejects_inconsistent_open_action_status() -> None:
    payload = json.loads(_fixture_path("leisure_planning_turn.json").read_text())
    payload["actions"][2]["status"] = "completed"

    with pytest.raises(ValueError, match="open_action_ids"):
        PlannerTurn.from_dict(payload)


def test_planner_turn_rejects_unknown_recent_output_references() -> None:
    payload = json.loads(_fixture_path("business_planning_turn.json").read_text())
    payload["workflow_state"]["recent_output_ids"] = ["missing-output"]

    with pytest.raises(ValueError, match="recent_output_ids"):
        PlannerTurn.from_dict(payload)
