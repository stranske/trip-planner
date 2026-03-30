import json
from pathlib import Path

from trip_planner.business import (
    BusinessTravelProfile,
    PolicyConstraintSet,
    derive_business_planning_objectives,
)


def _fixture_path(name: str) -> Path:
    return Path("tests/fixtures/business") / name


def _load_profile(name: str) -> BusinessTravelProfile:
    payload = json.loads(_fixture_path(name).read_text(encoding="utf-8"))
    return BusinessTravelProfile.from_dict(payload)


def _load_constraint_set(name: str) -> PolicyConstraintSet:
    payload = json.loads(_fixture_path(name).read_text(encoding="utf-8"))
    return PolicyConstraintSet(**payload["constraint_set"])


def test_conference_profile_derives_compliant_first_objectives() -> None:
    profile = _load_profile("conference_profile.json")
    constraint_set = _load_constraint_set("policy_round_trip_compliant.json")

    objectives = derive_business_planning_objectives(
        profile,
        trip_id="trip-business-conference",
        constraint_set=constraint_set,
    )
    payload = objectives.to_dict()

    assert payload["channel_strategy"]["required_channels"] == ["Concur"]
    assert payload["channel_strategy"]["channel_mode"] == "approved_only"
    assert payload["comparable_requirements"]["required_categories"]["lodging"] == 2
    assert payload["exception_path_posture"]["posture"] == "compliant_first"
    assert "policy_constraint_set:policy-001" in payload["explanations"]


def test_client_meeting_profile_protects_schedule_and_exception_readiness() -> None:
    profile = _load_profile("client_meeting_profile.json")

    objectives = derive_business_planning_objectives(
        profile,
        trip_id="trip-business-client",
    )

    assert objectives.schedule_protection.protection_level == "mission_critical"
    assert objectives.schedule_protection.arrival_buffer_preference == "conservative"
    assert objectives.justification_readiness.maintain_exception_packet is True
    assert objectives.exception_path_posture.posture == "exception_ready"
    assert objectives.cost_control_posture.posture == "policy_first"


def test_site_visit_profile_derives_policy_nearest_exception_posture() -> None:
    profile = _load_profile("site_visit_profile.json")
    constraint_set = _load_constraint_set("policy_round_trip_exception.json")

    objectives = derive_business_planning_objectives(
        profile,
        trip_id="trip-business-site",
        constraint_set=constraint_set,
    )

    assert objectives.exception_path_posture.posture == "policy_nearest"
    assert objectives.exception_path_posture.fallback_mode == "manual_review"
    assert (
        "fatigue_management"
        in objectives.exception_path_posture.allowed_exception_types
    )
    assert (
        objectives.comparable_requirements.additional_comparables_for_exception is True
    )
    assert objectives.comfort_floor_protection.preserve_arrival_readiness is True
    assert "transport" in objectives.comfort_floor_protection.required_categories


def test_distinct_business_fixtures_produce_distinct_objective_bundles() -> None:
    conference = derive_business_planning_objectives(
        _load_profile("conference_profile.json"),
        trip_id="trip-business-a",
        constraint_set=_load_constraint_set("policy_round_trip_compliant.json"),
    )
    client = derive_business_planning_objectives(
        _load_profile("client_meeting_profile.json"),
        trip_id="trip-business-b",
    )
    site_visit = derive_business_planning_objectives(
        _load_profile("site_visit_profile.json"),
        trip_id="trip-business-c",
        constraint_set=_load_constraint_set("policy_round_trip_exception.json"),
    )

    differences = {
        "channels": conference.channel_strategy.required_channels
        != client.channel_strategy.required_channels,
        "schedule": conference.schedule_protection.protection_level
        != client.schedule_protection.protection_level,
        "exception": conference.exception_path_posture.posture
        != site_visit.exception_path_posture.posture,
        "comfort": conference.comfort_floor_protection.required_categories
        != site_visit.comfort_floor_protection.required_categories,
    }

    assert sum(1 for changed in differences.values() if changed) >= 3
