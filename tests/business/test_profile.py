import json
from pathlib import Path

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


def _fixture_path(name: str) -> Path:
    fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures" / "business"
    return fixtures_dir / name


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
        tradeoff_dimensions={
            key: TradeoffDimension() for key in TRADEOFF_DIMENSION_KEYS
        },
        hybrid_factors={
            key: HybridFactor(mode="tradeoff") for key in HYBRID_FACTOR_KEYS
        },
    )

    assert business_profile.profile_kind == "business"
    assert leisure_profile.profile_kind == "leisure"
    assert not hasattr(business_profile, "tradeoff_dimensions")
    assert not hasattr(leisure_profile, "policy_constraints")
