import pytest

from trip_planner.contracts import MoneyRange
from trip_planner.itinerary.scenarios import (
    SCHEMA_VERSION,
    ItineraryScenario,
    ScenarioSearchResult,
    ScenarioSummary,
    ScenarioTradeoff,
)
from trip_planner.ranking import ExplanationRecord


def _explanation_record(target_id: str = "scenario:primary") -> ExplanationRecord:
    return ExplanationRecord(
        explanation_id=f"explanation:{target_id}",
        record_type="summary",
        target_kind="route",
        target_id=target_id,
        headline="Balanced route",
        summary="This scenario balances walkability, transfer load, and total cost.",
        factor_keys=["walkability", "cost"],
        human_summary=["Keeps the route compact."],
        source_refs=["fixture:itinerary"],
    )


def _scenario_summary(kind: str = "primary") -> ScenarioSummary:
    return ScenarioSummary(
        headline="Compact culture route",
        scenario_kind=kind,
        feasible=True,
        recommended_for_selection=True,
        coherence_passed=True,
        estimated_total=MoneyRange(currency="USD", typical_amount=1840.0),
        total_travel_minutes=85,
        total_transfer_count=2,
        route_sequence=["hotel:central", "activity:museum", "activity:market"],
        notes=["Keeps high-priority activities near the lodging base."],
    )


def _scenario(
    *,
    scenario_id: str = "scenario:primary",
    rank: int = 1,
    scenario_kind: str = "primary",
) -> ItineraryScenario:
    return ItineraryScenario(
        scenario_id=scenario_id,
        title="Compact culture route",
        rank=rank,
        bundle_id="bundle:compact-culture",
        source_result_id="ranked-result:compact-culture",
        score=0.91,
        scenario_summary=_scenario_summary(scenario_kind),
        supporting_option_ids=["hotel:central", "activity:museum"],
        objective_refs=["objective:walkable"],
        explanation_records=[_explanation_record(scenario_id)],
        unresolved_tradeoffs=[
            ScenarioTradeoff(
                tradeoff_id="tradeoff:late-transfer",
                code="late_transfer",
                summary="Evening transfer adds a short delay.",
                severity="info",
                related_ids=["transport:rail"],
                notes=["Acceptable because the hotel remains near the station."],
            )
        ],
        notes=["Recommended as the primary itinerary scenario."],
    )


def test_scenario_tradeoff_to_dict_preserves_contract_shape() -> None:
    tradeoff = ScenarioTradeoff(
        tradeoff_id="tradeoff:cost",
        code="cost_premium",
        summary="Higher quality lodging increases total cost.",
        severity="warning",
        blocking=False,
        related_ids=["lodging:central"],
        notes=["Traveler accepts this premium for lower transfer friction."],
    )

    assert tradeoff.to_dict() == {
        "tradeoff_id": "tradeoff:cost",
        "code": "cost_premium",
        "summary": "Higher quality lodging increases total cost.",
        "severity": "warning",
        "blocking": False,
        "related_ids": ["lodging:central"],
        "notes": ["Traveler accepts this premium for lower transfer friction."],
    }


def test_scenario_summary_to_dict_includes_nested_money_range() -> None:
    payload = _scenario_summary().to_dict()

    assert payload == {
        "headline": "Compact culture route",
        "scenario_kind": "primary",
        "feasible": True,
        "recommended_for_selection": True,
        "coherence_passed": True,
        "estimated_total": {
            "currency": "USD",
            "typical_amount": 1840.0,
            "min_amount": None,
            "max_amount": None,
        },
        "total_travel_minutes": 85,
        "total_transfer_count": 2,
        "route_sequence": ["hotel:central", "activity:museum", "activity:market"],
        "notes": ["Keeps high-priority activities near the lodging base."],
    }


def test_itinerary_scenario_to_dict_serializes_nested_records() -> None:
    payload = _scenario().to_dict()

    assert set(payload) == {
        "scenario_id",
        "title",
        "rank",
        "bundle_id",
        "source_result_id",
        "score",
        "scenario_summary",
        "supporting_option_ids",
        "objective_refs",
        "explanation_records",
        "unresolved_tradeoffs",
        "notes",
    }
    assert payload["scenario_summary"]["scenario_kind"] == "primary"
    assert payload["explanation_records"][0]["target_kind"] == "route"
    assert payload["unresolved_tradeoffs"][0]["severity"] == "info"


def test_scenario_search_result_to_dict_serializes_ranked_scenarios() -> None:
    result = ScenarioSearchResult(
        search_id="scenario-search:kyoto",
        trip_id="trip:kyoto",
        purpose="final_selection",
        title="Kyoto itinerary scenario search",
        source_result_set_id="ranked-result-set:kyoto",
        scenarios=[
            _scenario(),
            _scenario(
                scenario_id="scenario:alternative",
                rank=2,
                scenario_kind="alternative",
            ),
        ],
        explanation=["Primary and alternative scenarios stay route-scoped."],
        source_refs=["fixture:scenario-search"],
    )

    payload = result.to_dict()

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["scope"] == "route"
    assert [item["rank"] for item in payload["scenarios"]] == [1, 2]
    assert payload["scenarios"][1]["scenario_summary"]["scenario_kind"] == "alternative"


@pytest.mark.parametrize("severity", ["minor", "urgent", ""])
def test_tradeoff_rejects_invalid_severity(severity: str) -> None:
    with pytest.raises(ValueError, match="severity must be one of"):
        ScenarioTradeoff(
            tradeoff_id="tradeoff:invalid",
            code="invalid",
            summary="Invalid severity should fail validation.",
            severity=severity,
        )


def test_summary_rejects_invalid_scenario_kind() -> None:
    with pytest.raises(ValueError, match="scenario_kind must be one of"):
        _scenario_summary("bonus")


def test_itinerary_scenario_requires_explanation_records() -> None:
    with pytest.raises(
        ValueError, match="explanation_records must contain at least one"
    ):
        ItineraryScenario(
            scenario_id="scenario:no-explanation",
            title="Missing explanation route",
            rank=1,
            bundle_id="bundle:no-explanation",
            source_result_id="ranked-result:no-explanation",
            score=0.5,
            scenario_summary=_scenario_summary(),
        )


def test_search_result_rejects_duplicate_scenario_ranks() -> None:
    with pytest.raises(ValueError, match="scenarios must use unique ranks"):
        ScenarioSearchResult(
            search_id="scenario-search:duplicate-ranks",
            trip_id="trip:kyoto",
            purpose="final_selection",
            title="Duplicate-rank scenario search",
            source_result_set_id="ranked-result-set:duplicate-ranks",
            scenarios=[
                _scenario(scenario_id="scenario:first", rank=1),
                _scenario(scenario_id="scenario:second", rank=1),
            ],
        )
