from trip_planner.contracts import (
    ProfileRefs,
    TravelerPartySummary,
    Trip,
    TripArtifactRefs,
    TripFrameSummary,
)


def test_trip_serializes_valid_leisure_container() -> None:
    trip = Trip(
        trip_id="trip-leisure-1",
        user_id="user-1",
        mode="leisure",
        status="draft",
        title="Autumn rail trip",
        trip_frame=TripFrameSummary(
            start_date="2026-10-01",
            end_date="2026-10-28",
            duration_days=28,
            primary_regions=["Japan"],
            traveler_party=TravelerPartySummary(kind="pair", traveler_count=2),
        ),
        profile_refs=ProfileRefs(leisure_profile_id="leisure-profile-1"),
        artifacts=TripArtifactRefs(
            objective_id="obj-1",
            option_set_ids=["optset-1", "optset-2"],
            itinerary_state_id="itin-1",
            budget_state_id="budget-1",
        ),
    )

    payload = trip.to_dict()

    assert payload["mode"] == "leisure"
    assert payload["profile_refs"]["leisure_profile_id"] == "leisure-profile-1"
    assert payload["artifacts"]["option_set_ids"] == ["optset-1", "optset-2"]


def test_trip_serializes_valid_business_container() -> None:
    trip = Trip(
        trip_id="trip-business-1",
        user_id="user-2",
        mode="business",
        status="active",
        title="Client meeting trip",
        trip_frame=TripFrameSummary(
            start_date="2026-05-04",
            end_date="2026-05-06",
            duration_days=3,
            primary_regions=["Chicago", "New York"],
            traveler_party=TravelerPartySummary(kind="solo", traveler_count=1),
        ),
        profile_refs=ProfileRefs(business_profile_id="business-profile-1"),
        artifacts=TripArtifactRefs(
            objective_id="obj-business-1",
            option_set_ids=["optset-business-1"],
            itinerary_state_id="itin-business-1",
            budget_state_id="budget-business-1",
            policy_state_id="policy-business-1",
        ),
    )

    payload = trip.to_dict()

    assert payload["mode"] == "business"
    assert payload["profile_refs"]["business_profile_id"] == "business-profile-1"
    assert payload["artifacts"]["policy_state_id"] == "policy-business-1"


def test_trip_rejects_missing_mode_specific_profile_ref() -> None:
    try:
        Trip(
            trip_id="trip-leisure-2",
            user_id="user-3",
            mode="leisure",
            status="draft",
            trip_frame=TripFrameSummary(duration_days=14),
            profile_refs=ProfileRefs(),
        )
    except ValueError as exc:
        assert "leisure_profile_id" in str(exc)
    else:
        raise AssertionError("Leisure trip should require a leisure profile reference")


def test_trip_rejects_duplicate_option_set_refs() -> None:
    try:
        TripArtifactRefs(option_set_ids=["optset-1", "optset-1"])
    except ValueError as exc:
        assert "option_set_ids" in str(exc)
    else:
        raise AssertionError("TripArtifactRefs should reject duplicate option set references")


def test_trip_rejects_policy_state_for_leisure_mode() -> None:
    try:
        Trip(
            trip_id="trip-leisure-3",
            user_id="user-4",
            mode="leisure",
            status="active",
            trip_frame=TripFrameSummary(duration_days=12),
            profile_refs=ProfileRefs(leisure_profile_id="leisure-profile-2"),
            artifacts=TripArtifactRefs(policy_state_id="policy-1"),
        )
    except ValueError as exc:
        assert "policy_state_id" in str(exc)
    else:
        raise AssertionError("Leisure trip should reject business-only policy state references")
