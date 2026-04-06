import json
from pathlib import Path

import pytest

from trip_planner.ranking import RankedResultSet


def _fixture_path(name: str) -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures" / "ranking" / "results" / name


def _load_result_set(name: str) -> RankedResultSet:
    payload = json.loads(_fixture_path(name).read_text(encoding="utf-8"))
    return RankedResultSet.from_dict(payload)


def test_leisure_ranking_fixture_round_trips_and_keeps_item_contracts() -> None:
    result_set = _load_result_set("leisure_candidate_result.json")

    assert result_set.purpose == "profile_learning"
    assert result_set.scope == "mixed"
    assert result_set.results[0].result_kind == "item"
    assert result_set.results[0].target_option is not None
    assert result_set.results[0].score_breakdown.final_score == pytest.approx(0.69)
    assert (
        result_set.results[0].explanation_records[0].machine_context["primary_axis"] == "enjoyment"
    )
    assert result_set.to_dict()["results"][0]["target_option"]["option_id"] == (
        "candidate:kyoto-museum-day"
    )


def test_business_ranking_fixture_preserves_missing_data_penalties() -> None:
    result_set = _load_result_set("business_candidate_result.json")

    result = result_set.results[0]
    assert result.result_kind == "item"
    assert result.score_breakdown.missing_data_penalties[0].reason_code == ("missing_tax_estimate")
    assert result.confidence_summary.low_confidence_flags == ["missing_tax_estimate"]
    assert result.unresolved_risks[0].code == "missing_tax_estimate"


def test_route_fixture_supports_route_level_results() -> None:
    result_set = _load_result_set("route_bundle_result.json")

    result = result_set.results[0]
    assert result_set.scope == "route"
    assert result.result_kind == "route"
    assert result.target_bundle_id == "bundle:jp-loop-lite"
    assert result.route_sequence == ["dest-osaka", "dest-kyoto"]
    assert result.explanation_records[0].target_kind == "route"


def test_ranked_result_requires_item_target_option() -> None:
    payload = json.loads(_fixture_path("leisure_candidate_result.json").read_text())
    payload["results"][0]["target_option"] = None

    with pytest.raises(ValueError, match="target_option"):
        RankedResultSet.from_dict(payload)


def test_ranked_result_requires_route_sequence_for_route_results() -> None:
    payload = json.loads(_fixture_path("route_bundle_result.json").read_text())
    payload["results"][0]["route_sequence"] = []

    with pytest.raises(ValueError, match="route_sequence"):
        RankedResultSet.from_dict(payload)


def test_ranked_result_rejects_target_option_for_route_results() -> None:
    payload = json.loads(_fixture_path("route_bundle_result.json").read_text())
    payload["results"][0]["target_option"] = {
        "option_id": "candidate:route-shadow",
        "kind": "activity",
        "label": "Shadow option",
    }

    with pytest.raises(ValueError, match="target_option"):
        RankedResultSet.from_dict(payload)


def test_ranked_result_set_rejects_duplicate_ranks() -> None:
    payload = json.loads(_fixture_path("business_candidate_result.json").read_text())
    duplicate = dict(payload["results"][0])
    duplicate["result_id"] = "ranked:item:backup"
    duplicate["rank"] = 1
    duplicate["score"] = 0.63
    payload["results"].append(duplicate)

    with pytest.raises(ValueError, match="unique ranks"):
        RankedResultSet.from_dict(payload)


def test_score_breakdown_rejects_mismatched_final_score() -> None:
    payload = json.loads(_fixture_path("business_candidate_result.json").read_text())
    payload["results"][0]["score_breakdown"]["final_score"] = 0.61

    with pytest.raises(ValueError, match="final_score"):
        RankedResultSet.from_dict(payload)


def test_risk_flags_validate_known_severities() -> None:
    payload = json.loads(_fixture_path("route_bundle_result.json").read_text())
    payload["results"][0]["unresolved_risks"][0]["severity"] = "urgent"

    with pytest.raises(ValueError, match="severity"):
        RankedResultSet.from_dict(payload)
