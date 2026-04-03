import json
from copy import deepcopy
from pathlib import Path

from trip_planner.business.policy_contracts import PolicyConstraintSet
from trip_planner.candidates import CandidateSet, generate_candidate_set
from trip_planner.options import (
    ActivityOption,
    Destination,
    LodgingOption,
    TransportOption,
)


def _fixture_path(name: str) -> Path:
    return Path("tests/fixtures/candidates") / name


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _deep_merge(base: dict, patch: dict) -> dict:
    merged = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _load_entry(entry: dict, parser):
    if "path" in entry:
        payload = _load_json(Path(entry["path"]))
    else:
        payload = deepcopy(entry["payload"])
    if "overrides" in entry:
        payload = _deep_merge(payload, entry["overrides"])
    return parser(payload)


def _load_scenario(name: str) -> dict:
    payload = _load_json(_fixture_path(name))
    return {
        "trip_id": payload["trip_id"],
        "purpose": payload["purpose"],
        "selection_limit": payload["selection_limit"],
        "max_source_freshness_days": payload["max_source_freshness_days"],
        "policy_constraints": (
            PolicyConstraintSet(**payload["policy_constraints"])
            if payload.get("policy_constraints")
            else None
        ),
        "destinations": [
            _load_entry(item, Destination.from_dict) for item in payload["destinations"]
        ],
        "lodging_options": [
            _load_entry(item, LodgingOption.from_dict) for item in payload["lodging_options"]
        ],
        "transport_options": [
            _load_entry(item, TransportOption.from_dict) for item in payload["transport_options"]
        ],
        "activity_options": [
            _load_entry(item, ActivityOption.from_dict) for item in payload["activity_options"]
        ],
    }


def test_leisure_candidate_generation_preserves_explanations_and_freshness_exclusions() -> None:
    scenario = _load_scenario("leisure_route_learning.json")

    candidate_set = generate_candidate_set(**scenario)

    assert isinstance(candidate_set, CandidateSet)
    assert candidate_set.purpose == "profile_learning"
    assert candidate_set.filter_summary.included_bundle_count == 1
    assert candidate_set.filter_summary.freshness_exclusion_count == 1
    assert candidate_set.seeds[0].bundle.destinations[0].destination_id == "dest-city-kyoto"
    assert candidate_set.seeds[0].bundle.activity_options[0].option_id == "activity-major-museum"
    assert any(exclusion.reason_code == "stale_source" for exclusion in candidate_set.exclusions)
    option_set = candidate_set.to_option_set()
    assert option_set.scope == "mixed"
    assert option_set.options[0].explanation


def test_lodging_narrowing_keeps_available_options_and_excludes_sold_out_inventory() -> None:
    scenario = _load_scenario("lodging_narrowing.json")

    candidate_set = generate_candidate_set(**scenario)

    assert candidate_set.purpose == "inventory_narrowing"
    assert candidate_set.filter_summary.included_bundle_count == 1
    assert candidate_set.filter_summary.availability_exclusion_count == 1
    assert candidate_set.seeds[0].bundle.bundle_context == "lodging_only"
    assert len(candidate_set.seeds[0].bundle.lodging_options) == 2
    assert any(
        exclusion.option_id == "lodg-kyoto-machiya-loft" for exclusion in candidate_set.exclusions
    )


def test_business_candidate_generation_filters_policy_violations_and_marks_policy_ready() -> None:
    scenario = _load_scenario("business_initial_candidates.json")

    candidate_set = generate_candidate_set(**scenario)

    assert candidate_set.purpose == "policy_comparison"
    assert candidate_set.filter_summary.policy_exclusion_count == 1
    assert candidate_set.seeds[0].policy_ready is True
    assert candidate_set.seeds[0].bundle.transport_options[0].origin_id == "dest-home-ord"
    assert candidate_set.seeds[0].bundle.lodging_options[0].option_id == (
        "lodg-chicago-lakeshore-conference"
    )
    assert any(
        exclusion.option_id == "transport-car-highland-loop"
        for exclusion in candidate_set.exclusions
    )
    assert candidate_set.to_option_set().comparison_axes[-1].key == "policy_ready"


def test_business_candidate_generation_excludes_non_usd_lodging_for_usd_policy_cap() -> None:
    scenario = _load_scenario("business_initial_candidates.json")

    scenario["lodging_options"][0].cost_summary.nightly.currency = "EUR"
    scenario["lodging_options"][0].cost_summary.nightly.typical_amount = 250.0

    candidate_set = generate_candidate_set(**scenario)

    assert any(
        exclusion.option_id == "lodg-chicago-lakeshore-conference"
        and exclusion.reason_code == "policy_rate_cap"
        for exclusion in candidate_set.exclusions
    )


def test_candidate_generation_validates_limit_and_freshness_inputs() -> None:
    scenario = _load_scenario("leisure_route_learning.json")
    base_kwargs = {
        key: value
        for key, value in scenario.items()
        if key not in {"selection_limit", "max_source_freshness_days"}
    }

    try:
        generate_candidate_set(
            **base_kwargs,
            selection_limit=0,
            max_source_freshness_days=scenario["max_source_freshness_days"],
        )
    except ValueError as exc:
        assert "selection_limit" in str(exc)
    else:
        raise AssertionError("expected selection_limit validation to raise ValueError")

    try:
        generate_candidate_set(
            **base_kwargs,
            selection_limit=scenario["selection_limit"],
            max_source_freshness_days=-1,
        )
    except ValueError as exc:
        assert "max_source_freshness_days" in str(exc)
    else:
        raise AssertionError("expected max_source_freshness_days validation to raise ValueError")
