import json
from pathlib import Path

import pytest

from trip_planner.contracts import MoneyRange
from trip_planner.itinerary import (
    ItineraryScenario,
    ScenarioSearchResult,
    ScenarioSummary,
    ScenarioTradeoff,
)
from trip_planner.orchestration import (
    LeisureWorkflowContext,
    build_leisure_planner_turn,
)
from trip_planner.ranking import ExplanationRecord
from trip_planner.state import PersistedTripRecord, PlanningSessionState


def _fixture_path(name: str) -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "orchestration"
        / "leisure"
        / name
    )


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _trip_record() -> PersistedTripRecord:
    payload = _load_json(
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "state"
        / "trips"
        / "leisure_draft_trip.json"
    )
    return PersistedTripRecord.from_dict(payload)


def _session_state(name: str) -> PlanningSessionState:
    payload = _load_json(_fixture_path(name))
    return PlanningSessionState.from_dict(payload["session"])


def _scenario_search(trip_id: str = "trip-leisure-kyoto-draft") -> ScenarioSearchResult:
    scenarios = [
        ItineraryScenario(
            scenario_id=f"scenario:{trip_id}:1",
            title="Kyoto base with Uji day trip",
            rank=1,
            bundle_id="bundle:urban-culture",
            source_result_id=f"ranked-result:{trip_id}:1",
            score=0.93,
            scenario_summary=ScenarioSummary(
                headline="Balanced Kyoto culture baseline",
                scenario_kind="primary",
                feasible=True,
                recommended_for_selection=True,
                coherence_passed=True,
                estimated_total=MoneyRange(currency="USD", typical_amount=3400.0),
                total_travel_minutes=265,
                total_transfer_count=4,
                route_sequence=["kyoto", "uji", "kyoto"],
                notes=["baseline"],
            ),
            supporting_option_ids=["option:kyoto-central", "option:uji-daytrip"],
            objective_refs=["objective:kyoto-spring"],
            explanation_records=[
                ExplanationRecord(
                    explanation_id=f"explanation:{trip_id}:1",
                    target_kind="route",
                    target_id=f"scenario:{trip_id}:1",
                    headline="Best overall cultural balance",
                    summary="The baseline scenario preserves depth in Kyoto with one light excursion.",
                    factor_keys=["cultural_depth", "moderate_pace"],
                    machine_context={"planner_mode": "leisure"},
                    human_summary=[
                        "Keeps travel friction moderate while preserving variety."
                    ],
                    source_refs=["ranked-results:kyoto-spring"],
                )
            ],
            unresolved_tradeoffs=[
                ScenarioTradeoff(
                    tradeoff_id=f"tradeoff:{trip_id}:1",
                    code="limited_nightlife",
                    summary="Evening variety is lower than the fallback Osaka-heavy path.",
                    severity="info",
                )
            ],
        ),
        ItineraryScenario(
            scenario_id=f"scenario:{trip_id}:2",
            title="Kyoto plus Osaka fallback",
            rank=2,
            bundle_id="bundle:scenic-wanderer",
            source_result_id=f"ranked-result:{trip_id}:2",
            score=0.88,
            scenario_summary=ScenarioSummary(
                headline="Higher-energy fallback with extra transfers",
                scenario_kind="alternative",
                feasible=True,
                recommended_for_selection=False,
                coherence_passed=True,
                estimated_total=MoneyRange(currency="USD", typical_amount=3250.0),
                total_travel_minutes=360,
                total_transfer_count=7,
                route_sequence=["kyoto", "osaka", "kyoto"],
                notes=["higher movement"],
            ),
            supporting_option_ids=["option:kyoto-central", "option:osaka-daytrip"],
            objective_refs=["objective:kyoto-spring"],
            explanation_records=[
                ExplanationRecord(
                    explanation_id=f"explanation:{trip_id}:2",
                    target_kind="route",
                    target_id=f"scenario:{trip_id}:2",
                    headline="Fallback with broader city coverage",
                    summary="The alternative opens more nightlife at the cost of extra transfers.",
                    factor_keys=["breadth", "transfer_cost"],
                    machine_context={"planner_mode": "leisure"},
                    human_summary=[
                        "Broader exploration, slightly more travel fatigue."
                    ],
                    source_refs=["ranked-results:kyoto-spring"],
                )
            ],
        ),
    ]
    return ScenarioSearchResult(
        search_id="scenario-search:kyoto-spring",
        trip_id=trip_id,
        purpose="final_selection",
        title="Kyoto leisure scenario comparison",
        source_result_set_id="ranked-results:kyoto-spring",
        scenarios=scenarios,
        explanation=[
            "Leisure orchestration should consume ranked scenarios rather than replace ranking."
        ],
        source_refs=["ranked-results:kyoto-spring", "objective:kyoto-spring"],
    )


def _build_turn(name: str):
    return build_leisure_planner_turn(
        LeisureWorkflowContext(
            trip_record=_trip_record(),
            session_state=_session_state(name),
            scenario_search=_scenario_search(),
            generated_at="2026-04-02T15:00:00Z",
        )
    )


def test_delegated_leisure_flow_auto_advances_to_save_ready_checkpoint() -> None:
    turn = _build_turn("delegated_planning_flow.json")

    assert turn.turn_kind == "planning_pass"
    assert turn.workflow_state.current_stage == "decision_checkpoint"
    assert turn.workflow_state.status == "active"
    assert turn.next_step.recommended_action_id == "action-persist-state"
    assert turn.outputs[0].output_kind == "ranked_scenarios"
    assert turn.outputs[1].output_kind == "status_update"
    assert turn.workflow_state.open_action_ids == ["action-persist-state"]
    assert turn.actions[0].payload["activity_log_id"] == "activity-log:kyoto-spring"
    assert turn.actions[1].payload["ask_before_major_change"] is False
    assert turn.actions[3].payload["scenario_count"] == 2
    assert turn.actions[4].payload["source_refs"] == [
        "ranked-results:kyoto-spring",
        "objective:kyoto-spring",
    ]


def test_collaborative_leisure_flow_waits_on_structured_checkpoint() -> None:
    turn = _build_turn("collaborative_iterative_flow.json")

    assert turn.turn_kind == "decision_checkpoint"
    assert turn.workflow_state.status == "waiting_on_user"
    assert turn.next_step.recommended_action_id == "action-request-decision"
    assert turn.next_step.blocking_decision_ids == ["decision:save-baseline"]
    assert turn.outputs[1].output_kind == "decision_request"
    assert "action-request-decision" in turn.workflow_state.open_action_ids
    assert turn.actions[5].payload["decision_ids"] == ["decision:save-baseline"]
    assert turn.actions[6].payload["decision_ids"] == ["decision:save-baseline"]


def test_revised_leisure_flow_returns_to_ranking_after_feedback() -> None:
    turn = _build_turn("revised_after_feedback_flow.json")

    assert turn.turn_kind == "planning_pass"
    assert turn.workflow_state.current_stage == "ranking"
    assert turn.workflow_state.status == "active"
    assert turn.next_step.recommended_action_id == "action-rank-options"
    assert turn.outputs[0].output_kind == "warning"
    assert turn.outputs[1].output_kind == "status_update"
    assert turn.workflow_state.open_action_ids == ["action-rank-options"]
    assert turn.transition.warning_codes == ["feedback_rejected_option_set"]
    assert turn.actions[-1].payload["rejected_option_ids"] == ["option:osaka-daytrip"]


def test_collect_context_omits_missing_activity_log_id() -> None:
    trip = _trip_record()
    session = _session_state("delegated_planning_flow.json")
    session.activity_log_id = None

    turn = build_leisure_planner_turn(
        LeisureWorkflowContext(
            trip_record=trip,
            session_state=session,
            scenario_search=_scenario_search(),
            generated_at="2026-04-02T15:00:00Z",
        )
    )

    assert "activity_log_id" not in turn.actions[0].payload


def test_builder_rejects_trip_and_session_mismatch() -> None:
    trip = _trip_record()
    session = _session_state("delegated_planning_flow.json")
    session.trip_id = "trip-leisure-other"

    with pytest.raises(ValueError, match="session_state.trip_id"):
        build_leisure_planner_turn(
            LeisureWorkflowContext(
                trip_record=trip,
                session_state=session,
                scenario_search=_scenario_search(),
                generated_at="2026-04-02T15:00:00Z",
            )
        )


def test_builder_rejects_non_final_selection_scenario_search() -> None:
    trip = _trip_record()
    session = _session_state("delegated_planning_flow.json")
    scenario_search = _scenario_search()
    scenario_search.purpose = "inventory_narrowing"

    with pytest.raises(ValueError, match="final_selection"):
        build_leisure_planner_turn(
            LeisureWorkflowContext(
                trip_record=trip,
                session_state=session,
                scenario_search=scenario_search,
                generated_at="2026-04-02T15:00:00Z",
            )
        )


@pytest.mark.parametrize("generated_at", ["", "not-a-timestamp"])
def test_builder_rejects_invalid_generated_at(generated_at: str) -> None:
    trip = _trip_record()
    session = _session_state("delegated_planning_flow.json")

    with pytest.raises(ValueError, match="generated_at"):
        build_leisure_planner_turn(
            LeisureWorkflowContext(
                trip_record=trip,
                session_state=session,
                scenario_search=_scenario_search(),
                generated_at=generated_at,
            )
        )
