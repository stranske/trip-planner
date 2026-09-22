from __future__ import annotations

from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.app.services.trips import _build_trip_record


def test_whitespace_only_origin_is_normalized_to_none() -> None:
    user = AuthenticatedUser(
        user_id="user-1", email="u@example.com", display_name="User"
    )
    record = _build_trip_record(
        user=user,
        title="Trip",
        summary="",
        mode="business",
        start_date="2026-06-01",
        end_date="2026-06-05",
        duration_days=4,
        primary_regions=["Chicago"],
        traveler_kind="solo",
        traveler_count=1,
        origin="   ",
        traveler_notes="",
    )
    assert record.origin is None
