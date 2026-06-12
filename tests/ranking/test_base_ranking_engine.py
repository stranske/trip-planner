from trip_planner.ranking.base import BaseRankingEngine
from trip_planner.ranking.business import BusinessRankingEngine
from trip_planner.ranking.leisure import LeisureRankingEngine


def test_shared_validators_defined_once() -> None:
    for method_name in (
        "validate_feasibility_outputs",
        "validate_candidate_set",
        "validate_bundles",
    ):
        base_method = getattr(BaseRankingEngine, method_name)
        assert getattr(LeisureRankingEngine, method_name) is base_method
        assert getattr(BusinessRankingEngine, method_name) is base_method


def test_component_weights_stay_distinct() -> None:
    assert round(sum(LeisureRankingEngine.COMPONENT_WEIGHTS.values()), 4) == 0.9
    assert round(sum(BusinessRankingEngine.COMPONENT_WEIGHTS.values()), 4) == 1.0
