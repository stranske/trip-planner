from tests.ranking.test_business_ranking import (
    _compliant_conference_bundle,
    _objectives_for_scenario,
)
from tests.ranking.test_leisure_ranking import (
    _objectives_from_fixture,
    _profile_from_fixture,
    _urban_culture_bundle,
)
from trip_planner.ranking import BusinessRankingEngine, LeisureRankingEngine


def test_final_score_within_unit_interval() -> None:
    business_profile, business_objectives, constraint_set = _objectives_for_scenario(
        "compliant_conference_trip.json"
    )
    business_result = BusinessRankingEngine().rank_bundles(
        business_profile,
        business_objectives,
        [_compliant_conference_bundle()],
        trip_id="trip-score-bound-business",
        constraint_set=constraint_set,
    ).results[0]

    leisure_result = LeisureRankingEngine().rank_bundles(
        _profile_from_fixture("depth_oriented_urban_trip.json"),
        _objectives_from_fixture("depth_oriented_urban_trip.json"),
        [_urban_culture_bundle()],
        trip_id="trip-score-bound-leisure",
    ).results[0]

    for result in (business_result, leisure_result):
        assert 0.0 <= result.score <= 1.0
        assert 0.0 <= result.score_breakdown.final_score <= 1.0
        assert result.score == result.score_breakdown.final_score
        assert any(
            penalty.reason_code == "score_upper_bound_cap"
            for penalty in result.score_breakdown.penalties
        )
