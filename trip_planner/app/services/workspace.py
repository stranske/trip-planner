from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from trip_planner.contracts import MoneyRange
from trip_planner.itinerary import (
    ItineraryScenario,
    ScenarioSearchResult,
    ScenarioSummary,
    ScenarioTradeoff,
)
from trip_planner.ranking import ExplanationRecord
from trip_planner.state import (
    PersistedTripRecord,
    PlanningSessionState,
    SavedScenarioRecord,
    ScenarioComparison,
)


@dataclass(frozen=True, slots=True)
class WorkspaceFixture:
    trip_fixture: str
    scenarios_fixture: str
    session_fixture: str
    scenario_search_variant: str


_FIXTURES: dict[str, WorkspaceFixture] = {
    "trip-leisure-kyoto-draft": WorkspaceFixture(
        trip_fixture="leisure_draft_trip.json",
        scenarios_fixture="leisure_baseline_vs_fallback.json",
        session_fixture="active_leisure_session.json",
        scenario_search_variant="leisure",
    ),
    "trip-business-client-summit": WorkspaceFixture(
        trip_fixture="business_active_trip.json",
        scenarios_fixture="business_compliant_vs_exception.json",
        session_fixture="business_review_session.json",
        scenario_search_variant="business",
    ),
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _state_fixture_dir(kind: str) -> Path:
    return _repo_root() / "tests" / "fixtures" / "state" / kind


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_trip_record(name: str) -> PersistedTripRecord:
    return PersistedTripRecord.from_dict(_load_json(_state_fixture_dir("trips") / name))


def _load_saved_scenarios(name: str) -> tuple[list[SavedScenarioRecord], ScenarioComparison | None]:
    payload = _load_json(_state_fixture_dir("scenarios") / name)
    records = [SavedScenarioRecord.from_dict(item) for item in payload["records"]]
    comparison = payload.get("comparison")
    return records, ScenarioComparison.from_dict(comparison) if comparison is not None else None


def _load_session(name: str) -> PlanningSessionState:
    payload = _load_json(_state_fixture_dir("sessions") / name)
    return PlanningSessionState.from_dict(payload["session"])


def _canonicalize_saved_scenario_ids(
    session: PlanningSessionState,
    saved_scenarios: list[SavedScenarioRecord],
) -> None:
    canonical_ids = {record.saved_scenario_id for record in saved_scenarios}

    def normalize(candidate: str | None) -> str | None:
        if candidate is None or candidate in canonical_ids:
            return candidate

        candidate_tokens = set(candidate.split(":")[-1].split("-"))
        matches = [
            record.saved_scenario_id
            for record in saved_scenarios
            if set(record.saved_scenario_id.split(":")[-1].split("-")) == candidate_tokens
        ]
        if len(matches) == 1:
            return matches[0]
        return candidate

    session.current_saved_scenario_id = normalize(session.current_saved_scenario_id)
    for decision in session.pending_decisions:
        decision.related_saved_scenario_id = normalize(decision.related_saved_scenario_id)


def _leisure_search_result(trip_id: str) -> ScenarioSearchResult:
    return ScenarioSearchResult(
        search_id="scenario-search:kyoto-spring",
        trip_id=trip_id,
        purpose="final_selection",
        title="Kyoto leisure scenario comparison",
        source_result_set_id="ranked-results:kyoto-spring",
        scenarios=[
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
                        summary="The baseline preserves depth in Kyoto with one lighter excursion day.",
                        factor_keys=["cultural_depth", "moderate_pace"],
                        machine_context={"planner_mode": "leisure"},
                        human_summary=[
                            "Moderate travel friction with a clear cultural center of gravity."
                        ],
                        source_refs=["ranked-results:kyoto-spring"],
                    )
                ],
                unresolved_tradeoffs=[
                    ScenarioTradeoff(
                        tradeoff_id=f"tradeoff:{trip_id}:1",
                        code="limited_nightlife",
                        summary="Evening variety is lower than the Osaka-heavy fallback.",
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
                        summary="The fallback opens more nightlife at the cost of extra transfers.",
                        factor_keys=["breadth", "transfer_cost"],
                        machine_context={"planner_mode": "leisure"},
                        human_summary=["Broader exploration, slightly more travel fatigue."],
                        source_refs=["ranked-results:kyoto-spring"],
                    )
                ],
            ),
        ],
        explanation=[
            "Workspace timeline derives from the ordered scenario route sequence plus persisted trip dates."
        ],
        source_refs=["ranked-results:kyoto-spring", "objective:kyoto-spring"],
    )


def _business_search_result(trip_id: str) -> ScenarioSearchResult:
    return ScenarioSearchResult(
        search_id="scenario-search:client-summit",
        trip_id=trip_id,
        purpose="final_selection",
        title="Client summit scenario comparison",
        source_result_set_id="ranked-results:client-summit",
        scenarios=[
            ItineraryScenario(
                scenario_id=f"scenario:{trip_id}:1",
                title="Compliant first rail plan",
                rank=1,
                bundle_id="bundle:approved-business",
                source_result_id=f"ranked-result:{trip_id}:1",
                score=0.97,
                scenario_summary=ScenarioSummary(
                    headline="Primary path preserves compliant vendors and arrival buffers",
                    scenario_kind="primary",
                    feasible=True,
                    recommended_for_selection=True,
                    coherence_passed=True,
                    estimated_total=MoneyRange(currency="USD", typical_amount=2280.0),
                    total_travel_minutes=315,
                    total_transfer_count=3,
                    route_sequence=["home", "client-site", "conference-hotel"],
                    notes=["compliant-first"],
                ),
                supporting_option_ids=["option:approved-rail", "option:conference-hotel"],
                objective_refs=["objective:client-summit"],
                explanation_records=[
                    ExplanationRecord(
                        explanation_id=f"explanation:{trip_id}:1",
                        target_kind="route",
                        target_id=f"scenario:{trip_id}:1",
                        headline="Best approval-ready route",
                        summary="Keeps policy-safe vendors and preserves the buffer before the client visit.",
                        factor_keys=["policy_alignment", "schedule_protection"],
                        machine_context={"planner_mode": "business"},
                        human_summary=["Approved route keeps arrival risk low."],
                        source_refs=["ranked-results:client-summit"],
                    )
                ],
            ),
            ItineraryScenario(
                scenario_id=f"scenario:{trip_id}:2",
                title="Exception-nearest direct option",
                rank=2,
                bundle_id="bundle:exception-business",
                source_result_id=f"ranked-result:{trip_id}:2",
                score=0.89,
                scenario_summary=ScenarioSummary(
                    headline="Direct path reduces travel time but requires exception handling",
                    scenario_kind="fallback",
                    feasible=True,
                    recommended_for_selection=False,
                    coherence_passed=True,
                    estimated_total=MoneyRange(currency="USD", typical_amount=2410.0),
                    total_travel_minutes=255,
                    total_transfer_count=2,
                    route_sequence=["home", "client-site", "airport-hotel"],
                    notes=["exception-nearest"],
                ),
                supporting_option_ids=["option:direct-flight", "option:airport-hotel"],
                objective_refs=["objective:client-summit"],
                explanation_records=[
                    ExplanationRecord(
                        explanation_id=f"explanation:{trip_id}:2",
                        target_kind="route",
                        target_id=f"scenario:{trip_id}:2",
                        headline="Faster route with approval debt",
                        summary="Shorter travel time comes with a policy exception path and higher approval burden.",
                        factor_keys=["travel_time", "policy_exception"],
                        machine_context={"planner_mode": "business"},
                        human_summary=["Faster movement, weaker compliance posture."],
                        source_refs=["ranked-results:client-summit"],
                    )
                ],
                unresolved_tradeoffs=[
                    ScenarioTradeoff(
                        tradeoff_id=f"tradeoff:{trip_id}:2a",
                        code="policy_exception_path",
                        summary="Requires exception approval before booking.",
                        severity="critical",
                        blocking=True,
                    )
                ],
            ),
        ],
        explanation=[
            "Business timeline still derives from route order; policy posture is communicated via scenario tradeoffs."
        ],
        source_refs=["ranked-results:client-summit", "objective:client-summit"],
    )


def _build_scenario_search(trip_id: str, variant: str) -> ScenarioSearchResult:
    if variant == "leisure":
        return _leisure_search_result(trip_id)
    if variant == "business":
        return _business_search_result(trip_id)
    raise KeyError(f"Unsupported scenario search variant: {variant}")


def get_workspace_payload(trip_id: str) -> dict[str, Any] | None:
    fixture = _FIXTURES.get(trip_id)
    if fixture is None:
        return None

    trip_record = _load_trip_record(fixture.trip_fixture)
    saved_scenarios, scenario_comparison = _load_saved_scenarios(fixture.scenarios_fixture)
    session = _load_session(fixture.session_fixture)
    _canonicalize_saved_scenario_ids(session, saved_scenarios)
    scenario_search = _build_scenario_search(trip_id, fixture.scenario_search_variant)

    return {
        "trip_record": trip_record.to_dict(),
        "session": session.to_dict(),
        "saved_scenarios": [record.to_dict() for record in saved_scenarios],
        "scenario_comparison": scenario_comparison.to_dict() if scenario_comparison else None,
        "scenario_search": scenario_search.to_dict(),
    }
