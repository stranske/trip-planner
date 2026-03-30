import json
from pathlib import Path

import pytest

from trip_planner.business import BusinessTravelProfile, CostControls, TravelerContext
from trip_planner.preferences.models import (
    BudgetModel,
    HardConstraints,
    HybridFactor,
    LeisurePreferenceProfile,
    TradeoffDimension,
    TripFrame,
)
from trip_planner.preferences.schema import HYBRID_FACTOR_KEYS, TRADEOFF_DIMENSION_KEYS

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "business"


def _fixture_path(name: str) -> Path:
    return FIXTURES_DIR / name


def _load_fixture(name: str) -> BusinessTravelProfile:
    payload = json.loads(_fixture_path(name).read_text(encoding="utf-8"))
    return BusinessTravelProfile.from_dict(payload)


def test_business_profile_loads_conference_fixture() -> None:
    profile = _load_fixture("conference_profile.json")

    payload = profile.to_dict()

    assert payload["profile_kind"] == "business"
    assert payload["traveler_context"]["home_airport"] == "ORD"
    assert payload["trip_purpose"]["purpose_type"] == "conference"
    assert payload["vendor_constraints"]["comparison_requirements"]["lodging"] == 2


def test_business_profile_loads_client_meeting_fixture() -> None:
    profile = _load_fixture("client_meeting_profile.json")

    assert profile.schedule_requirements.meeting_protection_priority == 0.98
    assert profile.approval_targets.needs_exception_preclearance is True
    assert "Navan" in profile.policy_constraints.required_booking_channels


def test_business_profile_loads_site_visit_fixture() -> None:
    profile = _load_fixture("site_visit_profile.json")

    assert profile.trip_purpose.purpose_type == "site_visit"
    assert profile.vendor_constraints.comparison_requirements["car_rental"] == 2
    assert profile.exception_strategy.fallback_mode == "manual_review"


def test_business_profile_fixture_path_is_cwd_independent(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    fixture_path = _fixture_path("conference_profile.json")

    assert fixture_path == FIXTURES_DIR / "conference_profile.json"
    assert fixture_path.is_file()


def test_business_profile_fixture_loader_from_nested_cwd(monkeypatch, tmp_path: Path) -> None:
    nested_cwd = tmp_path / "nested" / "cwd"
    nested_cwd.mkdir(parents=True)
    monkeypatch.chdir(nested_cwd)

    profile = _load_fixture("conference_profile.json")

    assert profile.traveler_context.home_airport == "ORD"
    assert profile.trip_purpose.purpose_type == "conference"


def test_business_profile_rejects_invalid_traveler_context() -> None:
    try:
        TravelerContext(
            employee_type="volunteer",
            traveler_experience="frequent",
            home_airport="ORD",
        )
    except ValueError as exc:
        assert "employee_type" in str(exc)
    else:
        raise AssertionError("TravelerContext should reject unsupported employee types")


def test_business_profile_rejects_invalid_cost_controls() -> None:
    try:
        CostControls(policy_compliance_priority=1.2)
    except ValueError as exc:
        assert "policy_compliance_priority" in str(exc)
    else:
        raise AssertionError("CostControls should reject values outside 0.0..1.0")


def test_business_and_leisure_profiles_remain_separate_contracts() -> None:
    business_profile = _load_fixture("conference_profile.json")
    leisure_profile = LeisurePreferenceProfile(
        trip_frame=TripFrame(duration_days=7),
        hard_constraints=HardConstraints(),
        budget_model=BudgetModel(),
        tradeoff_dimensions={key: TradeoffDimension() for key in TRADEOFF_DIMENSION_KEYS},
        hybrid_factors={key: HybridFactor(mode="tradeoff") for key in HYBRID_FACTOR_KEYS},
    )

    assert business_profile.profile_kind == "business"
    assert leisure_profile.profile_kind == "leisure"
    assert not hasattr(business_profile, "tradeoff_dimensions")
    assert not hasattr(leisure_profile, "policy_constraints")


@pytest.mark.parametrize(
    ("fixture_name", "expected_airport"),
    [
        ("conference_profile.json", "ORD"),
        ("client_meeting_profile.json", "DFW"),
        ("site_visit_profile.json", "MSP"),
    ],
)
def test_business_profile_fixture_loader_is_cwd_independent(
    monkeypatch, tmp_path: Path, fixture_name: str, expected_airport: str
) -> None:
    monkeypatch.chdir(tmp_path)

    profile = _load_fixture(fixture_name)

    assert profile.traveler_context.home_airport == expected_airport
