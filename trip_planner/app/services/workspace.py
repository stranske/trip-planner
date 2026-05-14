from __future__ import annotations

import hashlib
import json
import secrets
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.app.services.budget import (
    build_fixture_budget_payload,
    load_budget_payload_for_workspace,
)
from trip_planner.app.services.feasibility import (
    build_feasibility_planner_outputs,
    build_feasibility_summary_payload,
)
from trip_planner.app.services.inventory import (
    _build_inventory_assembly_input,
    assemble_inventory_bundles_for_trip,
    build_inventory_summary_payload,
)
from trip_planner.app.services.planner_memory import build_planner_memory_payload
from trip_planner.app.services.policy import get_workspace_policy_payload
from trip_planner.app.services.proposal import get_workspace_proposal_payload
from trip_planner.app.services.planner_runtime_config import get_planner_runtime_config
from trip_planner.app.services.scenarios import (
    build_scenario_ranking_payload,
    build_scenario_ranking_outputs,
    build_workspace_scenario_search,
)
from trip_planner.contracts.trip import Trip
from trip_planner.contracts import MoneyRange
from trip_planner.itinerary import (
    ItineraryScenario,
    ScenarioSearchResult,
    ScenarioSummary,
    ScenarioTradeoff,
)
from trip_planner.options import InventoryBundle
from trip_planner.persistence.models.activity import (
    PersistedActivityLogEvent,
    PersistedPlannerAction,
)
from trip_planner.persistence.models.planning_ledger import PersistedPlanningLedgerEntry
from trip_planner.persistence.models.planning_notebook import (
    PersistedPlanningNotebookItem,
)
from trip_planner.persistence.models.scenario import (
    PersistedSavedScenario,
)
from trip_planner.persistence.models.session import PersistedPlanningSessionState
from trip_planner.persistence.models.trip import PersistedTrip
from trip_planner.ranking import ExplanationRecord
from trip_planner.state import (
    ActivityLogEvent,
    OptionPresentationRecord,
    PendingDecision,
    PLANNING_MODES,
    PersistedTripRecord,
    PersistedTripArtifactRefs,
    PlanningSessionState,
    SavedScenarioRecord,
    ScenarioComparison,
    TripLifecycle,
)


@dataclass(frozen=True, slots=True)
class WorkspaceFixture:
    trip_fixture: str
    scenarios_fixture: str
    session_fixture: str
    scenario_search_variant: str


WORKSPACE_ACTIVITY_LOG_LIMIT = 50
PLANNING_LEDGER_LIMIT = 100
PLANNING_LEDGER_ITEM_TYPES: tuple[str, ...] = (
    "option_considered",
    "option_rejected",
    "decision",
    "assumption",
    "open_question",
    "constraint",
    "source_reference",
)
PLANNING_LEDGER_STATUSES: tuple[str, ...] = (
    "active",
    "completed",
    "rejected",
    "superseded",
    "deferred",
)
PLANNING_NOTEBOOK_LIMIT = 200
PLANNING_NOTEBOOK_CATEGORIES: tuple[str, ...] = (
    "route",
    "lodging",
    "activities",
    "budget",
    "documents",
    "policy",
    "other",
)
PLANNING_NOTEBOOK_STATUSES: tuple[str, ...] = ("active", "completed", "archived")
PLANNING_NOTEBOOK_PRIORITIES: tuple[str, ...] = ("low", "normal", "high")
PLANNING_NOTEBOOK_SOURCES: tuple[str, ...] = ("user", "planner")
ROUTE_OPTION_STATES: tuple[str, ...] = (
    "active",
    "baseline",
    "fallback",
    "rejected",
    "needs_research",
)
ROUTE_OPTION_ACTIONS: tuple[str, ...] = (
    "make_baseline",
    "keep",
    "reject",
    "reopen",
    "revise",
)
_BOOTSTRAP_SCENARIO_SCORE_BY_LABEL = {
    "baseline": 0.82,
    "fallback": 0.68,
}


class WorkspaceTripNotFoundError(ValueError):
    """Raised when a workspace trip does not exist for the authenticated user."""


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


def _load_saved_scenarios(
    name: str,
) -> tuple[list[SavedScenarioRecord], ScenarioComparison | None]:
    payload = _load_json(_state_fixture_dir("scenarios") / name)
    records = [SavedScenarioRecord.from_dict(item) for item in payload["records"]]
    comparison = payload.get("comparison")
    return records, (ScenarioComparison.from_dict(comparison) if comparison is not None else None)


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
                supporting_option_ids=[
                    "option:approved-rail",
                    "option:conference-hotel",
                ],
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
            "Business timeline still derives from route order; approval posture is communicated via scenario tradeoffs."
        ],
        source_refs=["ranked-results:client-summit", "objective:client-summit"],
    )


def _build_scenario_search(
    *,
    trip_id: str,
    trip_mode: str,
    bundles: list[Any],
    trip_title: str | None = None,
    primary_regions: tuple[str, ...] = (),
    duration_days: int | None = None,
    traveler_party_kind: str | None = None,
) -> ScenarioSearchResult:
    return build_workspace_scenario_search(
        trip_id=trip_id,
        trip_mode=trip_mode,
        bundles=bundles,
        trip_title=trip_title,
        primary_regions=primary_regions,
        duration_days=duration_days,
        traveler_party_kind=traveler_party_kind,
    )


def _generated_route_sequence(route_sequence: list[str], *, variant: str) -> list[str]:
    clean_sequence = [stop for stop in route_sequence if stop]
    if not clean_sequence:
        clean_sequence = ["first-base", "comparison-stop"]
    if variant == "reverse":
        return (
            list(reversed(clean_sequence))
            if len(clean_sequence) > 1
            else [
                clean_sequence[0],
                "nearby-base",
            ]
        )
    if len(clean_sequence) == 1:
        return [clean_sequence[0], "nearby-base", clean_sequence[0]]
    return [*clean_sequence, clean_sequence[0]]


def _adjust_estimated_total(
    estimated_total: dict[str, Any] | None,
    *,
    delta: float,
) -> dict[str, Any] | None:
    if not isinstance(estimated_total, dict):
        return estimated_total
    typical_amount = estimated_total.get("typical_amount")
    if typical_amount is None:
        return estimated_total
    adjusted = dict(estimated_total)
    adjusted["typical_amount"] = round(max(0.0, float(typical_amount) + delta), 2)
    return adjusted


def _route_option_variant(
    *,
    base_scenario: dict[str, Any],
    trip_id: str,
    variant: str,
    rank: int,
    title: str,
    headline: str,
    tradeoff_summary: str,
    score_delta: float,
    travel_minutes_delta: int,
    transfer_delta: int,
    estimated_total_delta: float,
    scenario_kind: str,
) -> dict[str, Any]:
    generated = deepcopy(base_scenario)
    base_summary = dict(base_scenario.get("scenario_summary") or {})
    base_route = list(base_summary.get("route_sequence") or [])
    generated_id = f"scenario:{trip_id}:route-option:{variant}"
    generated["scenario_id"] = generated_id
    generated["title"] = title
    generated["rank"] = rank
    generated["source_result_id"] = (
        f"{base_scenario.get('source_result_id', generated_id)}:{variant}"
    )
    generated["score"] = round(
        max(0.05, min(0.98, float(base_scenario.get("score", 0.5)) + score_delta)), 2
    )
    generated["scenario_summary"] = {
        **base_summary,
        "headline": headline,
        "scenario_kind": scenario_kind,
        "recommended_for_selection": False,
        "estimated_total": _adjust_estimated_total(
            base_summary.get("estimated_total"),
            delta=estimated_total_delta,
        ),
        "total_travel_minutes": max(
            0,
            int(base_summary.get("total_travel_minutes") or 0) + travel_minutes_delta,
        ),
        "total_transfer_count": max(
            0,
            int(base_summary.get("total_transfer_count") or 0) + transfer_delta,
        ),
        "route_sequence": _generated_route_sequence(base_route, variant=variant),
        "notes": [
            *list(base_summary.get("notes") or []),
            "generated_route_option",
        ],
    }
    generated["unresolved_tradeoffs"] = [
        *list(base_scenario.get("unresolved_tradeoffs") or []),
        {
            "tradeoff_id": f"tradeoff:{trip_id}:route-option:{variant}",
            "code": f"generated_{variant}_route",
            "summary": tradeoff_summary,
            "severity": "warning",
            "blocking": False,
            "related_ids": [str(base_scenario.get("scenario_id") or "")],
            "notes": ["Generated as a rough comparison route until deeper planner research runs."],
        },
    ]
    generated["notes"] = [
        *list(base_scenario.get("notes") or []),
        "Generated as a rough route option from the current workspace route shape.",
    ]
    return generated


def _ensure_route_option_search_depth(
    record: PersistedTrip,
    scenario_search: dict[str, Any],
) -> dict[str, Any]:
    scenarios = list(scenario_search.get("scenarios") or [])
    if len(scenarios) >= 3 or not scenarios:
        return scenario_search

    expanded = dict(scenario_search)
    expanded_scenarios = [deepcopy(scenario) for scenario in scenarios]
    base_scenario = scenarios[0]
    next_rank = len(expanded_scenarios) + 1
    if len(expanded_scenarios) < 3:
        expanded_scenarios.append(
            _route_option_variant(
                base_scenario=base_scenario,
                trip_id=record.trip_id,
                variant="reverse",
                rank=next_rank,
                title="Reverse-order route option",
                headline="Same anchors in a different order to test pacing and arrival flow.",
                tradeoff_summary=(
                    "Reversing the order may improve arrival rhythm, but the planner still "
                    "needs to validate local transfer timing."
                ),
                score_delta=-0.08,
                travel_minutes_delta=45,
                transfer_delta=1,
                estimated_total_delta=120.0,
                scenario_kind="alternative",
            )
        )
        next_rank += 1
    if len(expanded_scenarios) < 3:
        expanded_scenarios.append(
            _route_option_variant(
                base_scenario=base_scenario,
                trip_id=record.trip_id,
                variant="loop",
                rank=next_rank,
                title="Loop route option",
                headline="Return through the starting anchor to preserve a fallback exit path.",
                tradeoff_summary=(
                    "The loop keeps a recovery path open but adds movement that may not be "
                    "worth it for the final plan."
                ),
                score_delta=-0.14,
                travel_minutes_delta=90,
                transfer_delta=2,
                estimated_total_delta=240.0,
                scenario_kind="fallback",
            )
        )

    expanded["scenarios"] = expanded_scenarios[:4]
    expanded["explanation"] = [
        *list(expanded.get("explanation") or []),
        "Route option workbench generated rough alternatives so the traveler can compare more than one path.",
    ]
    expanded["source_refs"] = list(
        dict.fromkeys(
            [
                *list(expanded.get("source_refs") or []),
                f"route-options:{record.trip_id}",
            ]
        )
    )
    return expanded


def _build_runtime_scenario_search_for_trip(
    *,
    record: PersistedTrip,
    inventory_bundles: list[Any],
    saved_scenarios: list[dict[str, Any]],
    inventory_status: str = "ready",
) -> dict[str, Any]:
    if inventory_status != "ready":
        if saved_scenarios:
            return _build_saved_scenario_runtime_search(
                record,
                saved_scenarios=saved_scenarios,
            )
        return _empty_workspace_scenario_search()

    if inventory_bundles:
        return _ensure_route_option_search_depth(
            record,
            _build_scenario_search(
                trip_id=record.trip_id,
                trip_mode=record.mode,
                bundles=inventory_bundles,
                trip_title=record.title,
                primary_regions=tuple(record.primary_regions),
                duration_days=record.duration_days,
                traveler_party_kind=record.traveler_party_kind,
            ).to_dict(),
        )

    if saved_scenarios:
        return _build_saved_scenario_runtime_search(
            record,
            saved_scenarios=saved_scenarios,
        )
    return _empty_workspace_scenario_search()


def _comparison_status_label(scenario: dict[str, Any]) -> str:
    summary = scenario["scenario_summary"]
    if not summary["feasible"]:
        return "blocked"
    if summary["scenario_kind"] == "fallback":
        return "fallback"
    if summary["recommended_for_selection"]:
        return "recommended"
    return "alternative"


def _estimated_total_delta(
    scenario: dict[str, Any],
    lead: dict[str, Any],
) -> float | None:
    scenario_total = scenario["scenario_summary"].get("estimated_total")
    lead_total = lead["scenario_summary"].get("estimated_total")
    if (
        scenario_total is None
        or lead_total is None
        or scenario_total.get("currency") != lead_total.get("currency")
    ):
        return None
    scenario_amount = scenario_total.get("typical_amount")
    lead_amount = lead_total.get("typical_amount")
    if scenario_amount is None or lead_amount is None:
        return None
    return round(float(scenario_amount) - float(lead_amount), 2)


def _comparison_highlights(
    *,
    scenario: dict[str, Any],
    lead: dict[str, Any],
) -> list[str]:
    summary = scenario["scenario_summary"]
    route_sequence = " -> ".join(summary.get("route_sequence") or []) or "route sequence pending"
    highlights = [
        f"Route: {route_sequence}.",
        f"Travel {summary['total_travel_minutes']} minutes with {summary['total_transfer_count']} transfer(s).",
    ]
    if scenario["scenario_id"] == lead["scenario_id"]:
        highlights.append("Lead scenario for the current workspace comparison set.")
    else:
        score_delta = round(float(scenario["score"]) - float(lead["score"]), 2)
        travel_delta = (
            summary["total_travel_minutes"] - lead["scenario_summary"]["total_travel_minutes"]
        )
        transfers_delta = (
            summary["total_transfer_count"] - lead["scenario_summary"]["total_transfer_count"]
        )
        delta_parts = [f"Score {score_delta:+.2f} versus the lead scenario."]
        if travel_delta:
            delta_parts.append(f"Travel time {travel_delta:+d} minutes versus lead.")
        if transfers_delta:
            delta_parts.append(f"Transfers {transfers_delta:+d} versus lead.")
        estimated_total_delta = _estimated_total_delta(scenario, lead)
        if estimated_total_delta is not None:
            delta_parts.append(f"Estimated total {estimated_total_delta:+.2f} versus lead.")
        highlights.append(" ".join(delta_parts))
    highlights.extend(
        tradeoff["summary"] for tradeoff in scenario.get("unresolved_tradeoffs", [])[:2]
    )
    return highlights


def _latest_presentation_for_option_set(
    session: dict[str, Any] | None,
    option_set_id: str,
) -> dict[str, Any] | None:
    if session is None:
        return None
    presentations = session.get("recent_option_presentations", [])
    if not isinstance(presentations, list):
        return None
    for presentation in reversed(presentations):
        if isinstance(presentation, dict) and presentation.get("option_set_id") == option_set_id:
            return presentation
    return None


def _note_option_ids(notes: list[Any], prefix: str) -> set[str]:
    marker = f"{prefix}:"
    return {
        note.split(":", 1)[1]
        for note in notes
        if isinstance(note, str) and note.startswith(marker) and note.split(":", 1)[1]
    }


def _session_route_option_state(
    session: dict[str, Any] | None,
    option_set_id: str,
) -> tuple[set[str], str | None, set[str], set[str]]:
    presentation = _latest_presentation_for_option_set(session, option_set_id)
    if presentation is None:
        return set(), None, set(), set()

    rejected_option_ids = {
        item for item in presentation.get("rejected_option_ids", []) if isinstance(item, str)
    }
    selected_option_id = presentation.get("selected_option_id")
    if not isinstance(selected_option_id, str) or selected_option_id == "":
        selected_option_id = None
    notes = list(presentation.get("notes") or [])
    return (
        rejected_option_ids,
        selected_option_id,
        _note_option_ids(notes, "fallback"),
        _note_option_ids(notes, "needs_research"),
    )


def _route_option_state(
    *,
    scenario_id: str,
    status: str,
    lead_scenario_id: str,
    rejected_option_ids: set[str],
    selected_option_id: str | None,
    fallback_option_ids: set[str],
    needs_research_option_ids: set[str],
) -> str:
    if scenario_id in rejected_option_ids:
        return "rejected"
    if status == "blocked":
        return "needs_research"
    if scenario_id == selected_option_id or (
        selected_option_id is None and scenario_id == lead_scenario_id
    ):
        return "baseline"
    if scenario_id in needs_research_option_ids:
        return "needs_research"
    if scenario_id in fallback_option_ids or status == "fallback":
        return "fallback"
    return "active"


def _route_option_purpose(*, state: str, status: str, scenario: dict[str, Any]) -> str:
    title = scenario.get("title") or "This route"
    if state == "baseline":
        return f"Use {title} as the route everything else is compared against."
    if state == "fallback":
        return f"Keep {title} available as a backup or later comparison lane."
    if state == "rejected":
        return f"Keep {title} in history so the reason for rejecting it is not lost."
    if state == "needs_research":
        return f"Send {title} back for a focused revision before treating it as settled."
    if status == "recommended":
        return f"Compare {title} as a strong candidate before making it the baseline."
    return f"Compare {title} as an active alternative while the route is still taking shape."


def _route_option_confidence(*, scenario: dict[str, Any], state: str) -> float:
    try:
        confidence = float(scenario.get("score", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    summary = scenario.get("scenario_summary") or {}
    if not summary.get("feasible", True):
        confidence = min(confidence, 0.35)
    if state == "needs_research":
        confidence = min(confidence, 0.55)
    if state == "rejected":
        confidence = min(confidence, 0.4)
    for tradeoff in scenario.get("unresolved_tradeoffs", []):
        if tradeoff.get("severity") == "critical" or tradeoff.get("blocking"):
            confidence = min(confidence, 0.58)
    return round(max(0.05, min(confidence, 0.98)), 2)


def _route_option_unresolved_questions(*, scenario: dict[str, Any], state: str) -> list[str]:
    summary = scenario.get("scenario_summary") or {}
    questions: list[str] = []
    if not summary.get("route_sequence"):
        questions.append("Which stops should anchor this route?")
    if summary.get("estimated_total") is None:
        questions.append("What rough cost range should this route assume?")
    for tradeoff in scenario.get("unresolved_tradeoffs", [])[:2]:
        tradeoff_summary = tradeoff.get("summary")
        if isinstance(tradeoff_summary, str) and tradeoff_summary:
            questions.append(f"Can this tradeoff work for the trip: {tradeoff_summary}")
    if state == "needs_research":
        questions.append("What should the planner change before comparing this route again?")
    return questions[:3]


def _route_option_available_actions(state: str) -> list[dict[str, str]]:
    if state not in ROUTE_OPTION_STATES:
        raise ValueError(f"state must be one of {', '.join(ROUTE_OPTION_STATES)}")
    if state == "rejected":
        return [
            {
                "action_type": "reopen",
                "label": "Reopen",
                "description": "Move this route back into the active comparison set.",
            }
        ]

    actions: list[dict[str, str]] = []
    if state not in {"baseline", "needs_research"}:
        actions.append(
            {
                "action_type": "make_baseline",
                "label": "Make baseline",
                "description": "Use this route as the main plan while keeping alternatives visible.",
            }
        )
    if state != "fallback":
        actions.append(
            {
                "action_type": "keep",
                "label": "Keep for later",
                "description": "Preserve this route as a backup option without making it the main plan.",
            }
        )
    actions.extend(
        [
            {
                "action_type": "reject",
                "label": "Reject",
                "description": "Move this route to history so it stops competing with active options.",
            },
            {
                "action_type": "revise",
                "label": "Revise",
                "description": "Ask the planner to improve this route before the next checkpoint.",
            },
        ]
    )
    return actions


def _humanize_route_stop(stop: str) -> str:
    return (
        stop.replace("dest-city-", "")
        .replace("dest-", "")
        .replace("city-", "")
        .replace("_", " ")
        .replace("-", " ")
        .strip()
        .title()
    )


def _map_coordinate_for_route_index(index: int, route_length: int) -> dict[str, float]:
    if route_length <= 1:
        return {"x": 0.5, "y": 0.5}

    progress = index / (route_length - 1)
    wave = -1 if index % 2 == 0 else 1
    return {
        "x": round(0.12 + progress * 0.76, 4),
        "y": round(0.52 + wave * 0.18, 4),
    }


def _build_runtime_map_place_markers(
    route_sequence: list[str],
    *,
    source_refs: list[str],
) -> list[dict[str, Any]]:
    stop_count = len([stop for stop in route_sequence if stop])
    return [
        {
            "id": f"route-stop:{index + 1}",
            "source_id": stop,
            "label": _humanize_route_stop(stop),
            "description": (
                f"Route stop {index + 1} of {stop_count}, sourced from the ranked scenario "
                "route sequence."
            ),
            "source_refs": list(source_refs),
            "route_index": index,
            **_map_coordinate_for_route_index(index, len(route_sequence)),
        }
        for index, stop in enumerate(route_sequence)
        if stop
    ]


def _build_runtime_map_route_geometry(
    place_markers: list[dict[str, Any]],
    *,
    route_warning: str | None,
    total_travel_minutes: int,
    feasible: bool,
    source_refs: list[str],
    total_distance_km: float | None = None,
) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    segment_count = max(1, len(place_markers) - 1)
    per_segment_minutes = max(0, round(total_travel_minutes / segment_count))
    per_segment_distance_km = (
        round(total_distance_km / segment_count, 1)
        if total_distance_km is not None and total_distance_km > 0
        else None
    )
    distance_available = per_segment_distance_km is not None
    for index, marker in enumerate(place_markers[:-1]):
        next_marker = place_markers[index + 1]
        segments.append(
            {
                "id": f"route-segment:{index + 1}",
                "from_marker_id": marker["id"],
                "to_marker_id": next_marker["id"],
                "from_label": marker["label"],
                "to_label": next_marker["label"],
                "x1": marker["x"],
                "y1": marker["y"],
                "x2": next_marker["x"],
                "y2": next_marker["y"],
                "warning": route_warning if index == 0 else None,
                "duration_minutes": per_segment_minutes,
                "distance_km": per_segment_distance_km,
                "confidence": "medium" if feasible else "low",
                "provider_distance_available": distance_available,
                "distance_verification_state": (
                    "scenario_distance_available"
                    if distance_available
                    else "duration_estimate_only"
                ),
                "distance_source": "scenario_summary" if distance_available else None,
                "source_refs": list(source_refs),
                "unavailable_reason": (
                    None
                    if distance_available
                    else "Provider distance is not available; duration is estimated from ranked scenario timing."
                ),
            }
        )
    return segments


def _build_runtime_map_view_payload(
    *,
    scenario: dict[str, Any],
    summary: dict[str, Any],
    route_sequence: list[str],
) -> dict[str, Any]:
    confidence_level = "high" if summary.get("feasible", False) else "medium"
    route_warning = None if summary.get("feasible", False) else "Scenario feasibility needs review."
    source_refs = [
        ref
        for ref in [
            scenario.get("source_result_id"),
            *list(scenario.get("objective_refs") or []),
        ]
        if ref
    ]
    place_markers = _build_runtime_map_place_markers(route_sequence, source_refs=source_refs)
    rough_route_geometry = _build_runtime_map_route_geometry(
        place_markers,
        route_warning=route_warning,
        total_travel_minutes=int(summary.get("total_travel_minutes") or 0),
        total_distance_km=summary.get("total_distance_km"),
        feasible=bool(summary.get("feasible", False)),
        source_refs=source_refs,
    )
    return {
        "active_scope": "regional",
        "active_route_option_id": scenario["scenario_id"],
        "selected_segment_id": rough_route_geometry[0]["id"] if rough_route_geometry else None,
        "place_markers": place_markers,
        "rough_route_geometry": rough_route_geometry,
        "confidence": {
            "level": confidence_level,
            "summary": (
                "This route outline is drawn from ranked scenario data."
                if confidence_level == "high"
                else "This route outline is approximate while feasibility is still settling."
            ),
        },
    }


def _build_runtime_map_diagnostics_payload(
    *,
    scenario: dict[str, Any],
    summary: dict[str, Any],
    route_sequence: list[str],
) -> dict[str, Any]:
    has_route = len(route_sequence) > 1
    return {
        "provider": {
            "kind": "fallback",
            "status": "sparse-route" if not has_route else "fallback",
            "details": "Route geometry is synthesized from scenario route_sequence.",
        },
        "route_state": "ready" if has_route else "sparse",
        "route_warning": None if summary.get("feasible", False) else "scenario_not_feasible",
        "source_result_id": scenario["source_result_id"],
        "objective_refs": list(scenario.get("objective_refs") or []),
    }


def _build_runtime_scenario_comparison(
    *,
    trip_id: str,
    trip_title: str,
    scenario_search: dict[str, Any],
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scenarios = list(scenario_search.get("scenarios", []))
    option_set_id = _bootstrap_option_set_id(trip_id)
    (
        rejected_option_ids,
        selected_option_id,
        fallback_option_ids,
        needs_research_option_ids,
    ) = _session_route_option_state(session, option_set_id)
    comparison_axes = [
        {"key": "score", "label": "Planner score", "direction": "higher_better"},
        {
            "key": "travel_minutes",
            "label": "Travel minutes",
            "direction": "lower_better",
        },
        {"key": "transfers", "label": "Transfers", "direction": "lower_better"},
        {
            "key": "estimated_total",
            "label": "Estimated total",
            "direction": "lower_better",
        },
    ]
    if not scenarios:
        return {
            "trip_id": trip_id,
            "title": "Workspace scenario comparison",
            "summary": (
                f"{trip_title} does not have runtime scenario comparison data yet. "
                "Run ranking and route assembly before rendering comparison views."
            ),
            "comparison_axes": comparison_axes,
            "lead_scenario_id": None,
            "scenarios": [],
            "source_refs": list(scenario_search.get("source_refs") or []),
        }

    scenario_ids = {scenario["scenario_id"] for scenario in scenarios}
    if selected_option_id not in scenario_ids or selected_option_id in rejected_option_ids:
        selected_option_id = None
    lead = (
        next(
            (
                scenario
                for scenario in scenarios
                if selected_option_id is not None and scenario["scenario_id"] == selected_option_id
            ),
            None,
        )
        or scenarios[0]
    )
    rows = []
    for scenario in scenarios:
        summary = scenario["scenario_summary"]
        estimated_total = summary.get("estimated_total")
        status = _comparison_status_label(scenario)
        state = _route_option_state(
            scenario_id=scenario["scenario_id"],
            status=status,
            lead_scenario_id=lead["scenario_id"],
            rejected_option_ids=rejected_option_ids,
            selected_option_id=selected_option_id,
            fallback_option_ids=fallback_option_ids,
            needs_research_option_ids=needs_research_option_ids,
        )
        unresolved_questions = _route_option_unresolved_questions(
            scenario=scenario,
            state=state,
        )
        available_actions = _route_option_available_actions(state)
        rows.append(
            {
                "scenario_id": scenario["scenario_id"],
                "route_option_id": scenario["scenario_id"],
                "title": scenario["title"],
                "rank": scenario["rank"],
                "status": status,
                "state": state,
                "purpose": _route_option_purpose(
                    state=state,
                    status=status,
                    scenario=scenario,
                ),
                "confidence": _route_option_confidence(scenario=scenario, state=state),
                "unresolved_questions": unresolved_questions,
                "available_actions": available_actions,
                "open_question": unresolved_questions[0] if unresolved_questions else None,
                "available_action": available_actions[0] if available_actions else None,
                "summary": summary["headline"],
                "comparison_note": (
                    "Lead route for the current workspace comparison set."
                    if scenario["scenario_id"] == lead["scenario_id"]
                    else "Alternative route preserved for direct scenario comparison."
                ),
                "option_count": max(
                    1,
                    len(scenario.get("supporting_option_ids") or []),
                ),
                "checkpoint_id": None,
                "budget_variant_id": None,
                "route_sequence": list(summary.get("route_sequence") or []),
                "route_summary": " -> ".join(summary.get("route_sequence") or [])
                or "route pending",
                "recommended_for_selection": summary["recommended_for_selection"],
                "feasible": summary["feasible"],
                "metrics": {
                    "score": scenario["score"],
                    "travel_minutes": summary["total_travel_minutes"],
                    "transfers": summary["total_transfer_count"],
                    "estimated_total": estimated_total,
                },
                "delta": {
                    "score_delta": round(float(scenario["score"]) - float(lead["score"]), 2),
                    "travel_minutes_delta": (
                        summary["total_travel_minutes"]
                        - lead["scenario_summary"]["total_travel_minutes"]
                    ),
                    "transfers_delta": (
                        summary["total_transfer_count"]
                        - lead["scenario_summary"]["total_transfer_count"]
                    ),
                    "estimated_total_delta": _estimated_total_delta(scenario, lead),
                },
                "highlights": _comparison_highlights(scenario=scenario, lead=lead),
                "source_result_id": scenario["source_result_id"],
                "objective_refs": list(scenario.get("objective_refs") or []),
                "map_view": _build_runtime_map_view_payload(
                    scenario=scenario,
                    summary=summary,
                    route_sequence=list(summary.get("route_sequence") or []),
                ),
                "map_diagnostics": _build_runtime_map_diagnostics_payload(
                    scenario=scenario,
                    summary=summary,
                    route_sequence=list(summary.get("route_sequence") or []),
                ),
            }
        )

    return {
        "trip_id": trip_id,
        "title": scenario_search.get("title") or "Workspace scenario comparison",
        "summary": (
            f"{len(rows)} runtime scenario(s) are available for side-by-side comparison in {trip_title}."
        ),
        "comparison_axes": comparison_axes,
        "lead_scenario_id": lead["scenario_id"],
        "scenarios": rows,
        "source_refs": list(scenario_search.get("source_refs") or []),
    }


def _build_workspace_inventory_inputs(
    record: PersistedTrip,
) -> tuple[list[InventoryBundle], dict[str, Any]]:
    assembly_input = _build_inventory_assembly_input(
        persisted_trip=record,
        trip_id=record.trip_id,
        trip_mode=record.mode,
        start_date=record.start_date,
        end_date=record.end_date,
        trip_status=record.status,
        primary_regions=record.primary_regions,
        duration_days=record.duration_days,
        trip_title=record.title,
        trip_summary=record.summary,
        traveler_party_kind=record.traveler_party_kind,
        traveler_count=record.traveler_count,
    )
    bundles = assemble_inventory_bundles_for_trip(assembly_input=assembly_input)
    return bundles, build_inventory_summary_payload(
        bundles,
        assembly_input=assembly_input,
    )


def _isoformat(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _owner_profile_id(record: PersistedTrip) -> str:
    if record.mode == "business" and record.business_profile_id:
        return record.business_profile_id
    if record.leisure_profile_id:
        return record.leisure_profile_id
    return f"profile:{record.trip_id}:{record.mode}"


def _serialize_persisted_trip_record(record: PersistedTrip) -> dict[str, Any]:
    trip = Trip.from_dict(
        {
            "trip_id": record.trip_id,
            "user_id": record.user_id,
            "title": record.title,
            "summary": record.summary,
            "mode": record.mode,
            "status": record.status,
            "trip_frame": {
                "start_date": record.start_date,
                "end_date": record.end_date,
                "duration_days": record.duration_days,
                "primary_regions": list(record.primary_regions),
                "traveler_party": {
                    "kind": record.traveler_party_kind,
                    "traveler_count": record.traveler_count,
                    "notes": record.traveler_notes,
                },
            },
            "profile_refs": record.profile_refs_payload(),
            "artifacts": record.artifacts_payload(),
        }
    )
    return PersistedTripRecord(
        trip=trip,
        owner_profile_id=_owner_profile_id(record),
        lifecycle=TripLifecycle(
            created_at=_isoformat(record.created_at),
            updated_at=_isoformat(record.updated_at),
        ),
        artifact_refs=PersistedTripArtifactRefs(
            objective_id=record.objective_id,
            option_set_ids=list(record.option_set_ids),
            itinerary_state_id=record.itinerary_state_id,
            budget_state_id=record.budget_state_id,
            policy_state_id=record.policy_state_id,
            session_state_id=f"session:{record.trip_id}",
            notes=["Workspace shell opened from persisted trip creation."],
        ),
        notes=["Minimal persisted workspace payload until scenario state exists."],
    ).to_dict()


def _default_workspace_decisions(trip_id: str) -> list[PendingDecision]:
    return [
        PendingDecision(
            decision_id=f"decision:{trip_id}:bootstrap-direction",
            title="Set the first planner direction",
            prompt="Should the workspace keep the current trip frame narrow, or compare another planner-backed option first?",
            created_at=_isoformat(datetime.now(UTC)),
            choices=[
                "Keep the current direction.",
                "Compare another planner-backed option first.",
            ],
            blocking=True,
            related_option_set_id=f"option-set:{trip_id}:workspace-bootstrap",
            notes=["Workspace bootstrap decision seeded for persisted planner interaction."],
        )
    ]


def _default_workspace_presentation(trip_id: str, shown_at: str) -> OptionPresentationRecord:
    return OptionPresentationRecord(
        presentation_id=f"presentation:{trip_id}:workspace-bootstrap",
        option_set_id=f"option-set:{trip_id}:workspace-bootstrap",
        shown_at=shown_at,
        surface_kind="scenario_comparison",
        surfaced_option_ids=[
            f"bootstrap:{trip_id}:keep-frame",
            f"bootstrap:{trip_id}:broaden-frame",
        ],
        highlighted_option_id=f"bootstrap:{trip_id}:keep-frame",
        summary="Workspace bootstrap options are ready for the first persisted planner action.",
        notes=["Initial workspace planner presentation."],
    )


def _default_workspace_session(record: PersistedTrip) -> PlanningSessionState:
    timestamp = _isoformat(record.updated_at)
    return PlanningSessionState(
        session_state_id=f"session:{record.trip_id}",
        trip_id=record.trip_id,
        user_id=record.user_id,
        owner_profile_id=_owner_profile_id(record),
        mode=record.mode,
        started_at=_isoformat(record.created_at),
        updated_at=timestamp,
        recent_option_presentations=[_default_workspace_presentation(record.trip_id, timestamp)],
        pending_decisions=_default_workspace_decisions(record.trip_id),
        activity_log_id=f"activity-log:{record.trip_id}",
        active_budget_plan_id=record.budget_state_id,
        notes=["Workspace opened before any saved scenarios or planner turns existed."],
    )


def _serialize_session_record(record: PersistedPlanningSessionState) -> dict[str, Any]:
    return PlanningSessionState.from_dict(
        {
            "session_state_id": record.session_state_id,
            "trip_id": record.trip_id,
            "user_id": record.user_id,
            "owner_profile_id": record.owner_profile_id,
            "mode": record.mode,
            "started_at": record.started_at,
            "updated_at": record.last_updated_at,
            "interaction_state": dict(record.interaction_state),
            "recent_option_presentations": list(record.recent_option_presentations),
            "pending_decisions": list(record.pending_decisions),
            "status": record.status,
            "selected_planning_mode": record.selected_planning_mode,
            "current_checkpoint_id": record.current_checkpoint_id,
            "current_saved_scenario_id": record.current_saved_scenario_id,
            "active_budget_plan_id": record.active_budget_plan_id,
            "activity_log_id": record.activity_log_id,
            "schema_version": record.schema_version,
            "tags": list(record.tags),
            "notes": list(record.notes),
        }
    ).to_dict()


def _bootstrap_saved_scenario_id(*, trip_id: str, label: str) -> str:
    token = hashlib.sha1(f"{trip_id}:{label}".encode("utf-8")).hexdigest()[:10]
    return f"saved-scenario:{label}-{token}"


def _bootstrap_option_set_id(trip_id: str) -> str:
    return f"option-set:{trip_id}:workspace-panel"


def _bootstrap_scope_label(record: PersistedTrip) -> str:
    primary_regions = [region for region in record.primary_regions if region]
    if primary_regions:
        return ", ".join(primary_regions[:2])
    return record.title


def _bootstrap_version_title(record: PersistedTrip, *, label: str) -> str:
    scope_label = _bootstrap_scope_label(record)
    if label == "baseline":
        return f"{scope_label} baseline"
    return f"{scope_label} fallback"


def _bootstrap_version_summary(record: PersistedTrip, *, label: str) -> str:
    scope_label = _bootstrap_scope_label(record)
    if label == "baseline":
        return (
            f"Capture the current persisted trip frame for {scope_label} so the workspace "
            "has a stable first saved scenario to refine."
        )
    return (
        f"Keep an explicit fallback scaffold for {scope_label} before deeper ranking and "
        "route search are available."
    )


def _bootstrap_artifact_refs(
    record: PersistedTrip,
    *,
    session_state_id: str,
) -> dict[str, Any]:
    refs: dict[str, Any] = {
        "session_state_id": session_state_id,
        "scenario_search_id": f"scenario-search:{record.trip_id}:workspace-bootstrap",
        "itinerary_scenario_id": f"scenario:{record.trip_id}:workspace-bootstrap",
        "option_set_ids": [_bootstrap_option_set_id(record.trip_id)],
        "notes": ["Persisted workspace bootstrap scaffold."],
    }
    if record.objective_id:
        refs["objective_id"] = record.objective_id
    if record.budget_state_id:
        refs["budget_state_id"] = record.budget_state_id
    if record.policy_state_id:
        refs["policy_state_id"] = record.policy_state_id
    if record.leisure_profile_id:
        refs["leisure_profile_id"] = record.leisure_profile_id
    if record.business_profile_id:
        refs["business_profile_id"] = record.business_profile_id
    return refs


def _bootstrap_saved_scenario_records(
    record: PersistedTrip,
    *,
    session_state_id: str,
    created_at: str,
) -> tuple[SavedScenarioRecord, SavedScenarioRecord]:
    baseline_id = _bootstrap_saved_scenario_id(trip_id=record.trip_id, label="baseline")
    fallback_id = _bootstrap_saved_scenario_id(trip_id=record.trip_id, label="fallback")
    artifact_refs = _bootstrap_artifact_refs(record, session_state_id=session_state_id)
    baseline_version_id = f"{baseline_id}-v1"
    fallback_version_id = f"{fallback_id}-v1"

    baseline = SavedScenarioRecord.from_dict(
        {
            "saved_scenario_id": baseline_id,
            "trip_id": record.trip_id,
            "current_version_id": baseline_version_id,
            "versions": [
                {
                    "version_id": baseline_version_id,
                    "saved_scenario_id": baseline_id,
                    "trip_id": record.trip_id,
                    "title": _bootstrap_version_title(record, label="baseline"),
                    "label": "baseline",
                    "created_at": created_at,
                    "snapshot_refs": artifact_refs,
                    "created_by": "workspace-bootstrap",
                    "scope": "mixed",
                    "summary": _bootstrap_version_summary(record, label="baseline"),
                    "tags": ["workspace-bootstrap", record.mode],
                    "notes": ["Generated during persisted workspace bootstrap."],
                }
            ],
            "comparisons": [
                {
                    "comparison_id": f"comparison:{record.trip_id}:workspace-bootstrap",
                    "trip_id": record.trip_id,
                    "baseline_scenario_id": baseline_id,
                    "candidate_scenario_id": fallback_id,
                    "compared_at": created_at,
                    "outcome": "preferred",
                    "summary": (
                        "The baseline preserves the current trip frame while the fallback "
                        "keeps a broader comparison lane available."
                    ),
                    "focus_areas": ["scope", "comparison-readiness"],
                    "notes": ["Bootstrap comparison scaffold for persisted workspace rendering."],
                }
            ],
            "tags": ["workspace-bootstrap", "preferred"],
            "notes": ["Created automatically during the first persisted workspace bootstrap."],
        }
    )
    fallback = SavedScenarioRecord.from_dict(
        {
            "saved_scenario_id": fallback_id,
            "trip_id": record.trip_id,
            "current_version_id": fallback_version_id,
            "versions": [
                {
                    "version_id": fallback_version_id,
                    "saved_scenario_id": fallback_id,
                    "trip_id": record.trip_id,
                    "title": _bootstrap_version_title(record, label="fallback"),
                    "label": "fallback",
                    "created_at": created_at,
                    "snapshot_refs": artifact_refs,
                    "created_by": "workspace-bootstrap",
                    "scope": "mixed",
                    "summary": _bootstrap_version_summary(record, label="fallback"),
                    "tags": ["workspace-bootstrap", record.mode],
                    "notes": ["Generated during persisted workspace bootstrap."],
                }
            ],
            "comparisons": [],
            "tags": ["workspace-bootstrap", "fallback"],
            "notes": ["Created automatically during the first persisted workspace bootstrap."],
        }
    )
    return baseline, fallback


def _saved_scenario_priority(saved_scenario: dict[str, Any]) -> tuple[int, str]:
    version = saved_scenario["versions"][0]
    label = version.get("label", "")
    priority = {
        "baseline": 0,
        "preferred": 1,
        "compliant_first": 2,
        "fallback": 3,
        "exception_nearest": 4,
        "in_trip_revision": 5,
    }.get(label, 9)
    return priority, version.get("title", saved_scenario["saved_scenario_id"])


def _ordered_saved_scenarios(
    saved_scenarios: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return sorted(saved_scenarios, key=_saved_scenario_priority)


def _bootstrap_route_sequence(record: PersistedTrip, *, label: str) -> list[str]:
    primary_regions = [region for region in record.primary_regions if region]
    if not primary_regions:
        primary_regions = [record.title]
    if label == "fallback":
        return [*primary_regions, "comparison-pass"]
    return primary_regions


def _bootstrap_scenario_metrics(
    record: PersistedTrip,
    *,
    label: str,
) -> tuple[float, int, int, dict[str, Any]]:
    duration_days = max(record.duration_days or 1, 1)
    base_minutes = 90 if record.mode == "leisure" else 120
    base_cost = 180.0 if record.mode == "leisure" else 320.0
    if label == "fallback":
        travel_minutes = duration_days * (base_minutes + 45)
        transfers = 2
        estimated_total = base_cost * duration_days + 120.0
    else:
        travel_minutes = duration_days * base_minutes
        transfers = 1
        estimated_total = base_cost * duration_days
    return (
        _BOOTSTRAP_SCENARIO_SCORE_BY_LABEL.get(label, 0.6),
        travel_minutes,
        transfers,
        {"currency": "USD", "typical_amount": round(estimated_total, 2)},
    )


def _build_saved_scenario_runtime_search(
    record: PersistedTrip,
    *,
    saved_scenarios: list[dict[str, Any]],
) -> dict[str, Any]:
    ordered = _ordered_saved_scenarios(saved_scenarios)
    scenario_rows: list[dict[str, Any]] = []
    source_refs = [f"session:{record.trip_id}"]
    for index, saved_scenario in enumerate(ordered, start=1):
        version = saved_scenario["versions"][0]
        label = version["label"]
        score, travel_minutes, transfers, estimated_total = _bootstrap_scenario_metrics(
            record,
            label=label,
        )
        route_sequence = _bootstrap_route_sequence(record, label=label)
        source_refs.extend(
            ref
            for ref in (
                version["snapshot_refs"].get("scenario_search_id"),
                version["snapshot_refs"].get("session_state_id"),
            )
            if ref
        )
        scenario_rows.append(
            {
                "scenario_id": saved_scenario["saved_scenario_id"],
                "title": version["title"],
                "rank": index,
                "bundle_id": None,
                "source_result_id": version["version_id"],
                "score": score,
                "scenario_summary": {
                    "headline": version["summary"],
                    "scenario_kind": "fallback" if label == "fallback" else "primary",
                    "feasible": True,
                    "recommended_for_selection": label != "fallback",
                    "coherence_passed": True,
                    "estimated_total": estimated_total,
                    "total_travel_minutes": travel_minutes,
                    "total_transfer_count": transfers,
                    "route_sequence": route_sequence,
                    "notes": list(version.get("notes") or []),
                },
                "supporting_option_ids": list(version["snapshot_refs"].get("option_set_ids") or []),
                "objective_refs": [
                    ref for ref in [version["snapshot_refs"].get("objective_id")] if ref is not None
                ],
                "unresolved_tradeoffs": (
                    [
                        {
                            "tradeoff_id": f"tradeoff:{record.trip_id}:workspace-bootstrap",
                            "code": "broader_scope",
                            "summary": "Fallback stays available until live ranking can compare a broader planning pass.",
                            "severity": "info",
                        }
                    ]
                    if label == "fallback"
                    else []
                ),
            }
        )

    return {
        "search_id": f"scenario-search:{record.trip_id}:workspace-bootstrap",
        "trip_id": record.trip_id,
        "purpose": "workspace_bootstrap",
        "title": "Persisted workspace bootstrap comparison",
        "source_result_set_id": f"workspace-bootstrap:{record.trip_id}",
        "scenarios": scenario_rows,
        "explanation": [
            "Saved scenarios are bootstrapped from the persisted trip record until deeper planner ranking is available.",
            "The workspace comparison surface can render immediately without falling back to seeded trip fixtures.",
        ],
        "source_refs": list(dict.fromkeys(source_refs)),
    }


def _serialize_activity_record(record: PersistedActivityLogEvent) -> dict[str, Any]:
    return ActivityLogEvent.from_dict(
        {
            "activity_event_id": record.activity_event_id,
            "trip_id": record.trip_id,
            "session_state_id": record.session_state_id,
            "occurred_at": record.occurred_at,
            "event_kind": record.event_kind,
            "summary": record.summary,
            "actor": record.actor,
            "related_decision_id": record.related_decision_id,
            "related_option_set_id": record.related_option_set_id,
            "saved_scenario_id": record.saved_scenario_id,
            "budget_plan_id": record.budget_plan_id,
            "scenario_budget_id": record.scenario_budget_id,
            "checkpoint_id": record.checkpoint_id,
            "metadata": dict(record.metadata_payload),
            "tags": list(record.tags),
            "notes": list(record.notes),
        }
    ).to_dict()


def _session_feedback_state(
    session: dict[str, Any],
    option_set_id: str,
) -> tuple[set[str], str | None, set[str]]:
    rejected_option_ids: set[str] = set()
    selected_option_id: str | None = None
    fallback_option_ids: set[str] = set()

    for presentation in reversed(session.get("recent_option_presentations", [])):
        if presentation.get("option_set_id") != option_set_id:
            continue
        rejected_option_ids.update(presentation.get("rejected_option_ids", []))
        if selected_option_id is None:
            selected_option_id = presentation.get("selected_option_id")
        for note in presentation.get("notes", []):
            if note.startswith("fallback:"):
                fallback_option_ids.add(note.split(":", 1)[1])
        break

    return rejected_option_ids, selected_option_id, fallback_option_ids


def _workspace_activity_outputs(
    trip_id: str,
    activity_log: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for entry in activity_log[:2]:
        outputs.append(
            {
                "output_id": f"output:{trip_id}:activity:{entry['activity_event_id']}",
                "title": entry["event_kind"].replace("_", " ").title(),
                "body": entry["summary"],
                "tags": ["activity", entry["event_kind"]],
            }
        )
    return outputs


def _serialize_ledger_entry(record: PersistedPlanningLedgerEntry) -> dict[str, Any]:
    return {
        "ledger_entry_id": record.ledger_entry_id,
        "trip_id": record.trip_id,
        "session_state_id": record.session_state_id,
        "item_type": record.item_type,
        "status": record.status,
        "category": record.category,
        "summary": record.summary,
        "detail": record.detail,
        "source_message_ids": list(record.source_message_ids or []),
        "source_refs": list(record.source_refs or []),
        "related_option_id": record.related_option_id,
        "related_decision_id": record.related_decision_id,
        "supersedes_entry_id": record.supersedes_entry_id,
        "metadata": dict(record.metadata_payload or {}),
        "created_at": _isoformat(record.created_at),
        "updated_at": _isoformat(record.updated_at),
    }


def _planning_ledger_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    active = [entry for entry in entries if entry["status"] == "active"]
    return {
        "active_decisions": [entry for entry in active if entry["item_type"] == "decision"],
        "open_questions": [entry for entry in active if entry["item_type"] == "open_question"],
        "active_options": [entry for entry in active if entry["item_type"] == "option_considered"],
        "rejected_options": [entry for entry in entries if entry["item_type"] == "option_rejected"],
        "constraints": [entry for entry in active if entry["item_type"] == "constraint"],
        "assumptions": [entry for entry in active if entry["item_type"] == "assumption"],
        "source_references": [
            entry for entry in active if entry["item_type"] == "source_reference"
        ],
    }


def _planning_ledger_state(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {"entries": entries, "summary": _planning_ledger_summary(entries)}


def _serialize_notebook_item(record: PersistedPlanningNotebookItem) -> dict[str, Any]:
    return {
        "notebook_item_id": record.notebook_item_id,
        "trip_id": record.trip_id,
        "session_state_id": record.session_state_id,
        "title": record.title,
        "note": record.note or "",
        "category": record.category,
        "status": record.status,
        "priority": record.priority,
        "source": record.source,
        "linked_ledger_entry_id": record.linked_ledger_entry_id,
        "source_message_ids": list(record.source_message_ids or []),
        "tags": list(record.tags or []),
        "metadata": dict(record.metadata_payload or {}),
        "completed_at": _isoformat(record.completed_at) if record.completed_at else None,
        "created_at": _isoformat(record.created_at),
        "updated_at": _isoformat(record.updated_at),
    }


def _planning_notebook_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    active = [item for item in items if item["status"] == "active"]
    completed = [item for item in items if item["status"] == "completed"]
    archived = [item for item in items if item["status"] == "archived"]
    by_category: dict[str, list[dict[str, Any]]] = {
        category: [] for category in PLANNING_NOTEBOOK_CATEGORIES
    }
    for item in active:
        by_category.setdefault(item["category"], []).append(item)
    return {
        "active_items": active,
        "completed_items": completed,
        "archived_items": archived,
        "by_category": by_category,
    }


def _planning_notebook_state(
    items: list[dict[str, Any]],
    *,
    focus_category: str | None = None,
    focus_item_id: str | None = None,
) -> dict[str, Any]:
    return {
        "items": items,
        "summary": _planning_notebook_summary(items),
        "focus": {
            "category": focus_category,
            "notebook_item_id": focus_item_id,
        },
    }


def _ledger_category_for_type(item_type: str) -> str:
    if item_type in {"option_considered", "option_rejected"}:
        return "route_options"
    if item_type == "open_question":
        return "questions"
    if item_type == "source_reference":
        return "sources"
    return item_type


def _add_planning_ledger_entry(
    db_session: Session,
    *,
    trip_id: str,
    session_state_id: str,
    item_type: str,
    summary: str,
    status: str = "active",
    category: str | None = None,
    detail: str = "",
    source_message_ids: list[str] | None = None,
    source_refs: list[str] | None = None,
    related_option_id: str | None = None,
    related_decision_id: str | None = None,
    supersedes_entry_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> PersistedPlanningLedgerEntry:
    if item_type not in PLANNING_LEDGER_ITEM_TYPES:
        raise ValueError(f"item_type must be one of {', '.join(PLANNING_LEDGER_ITEM_TYPES)}")
    if status not in PLANNING_LEDGER_STATUSES:
        raise ValueError(f"status must be one of {', '.join(PLANNING_LEDGER_STATUSES)}")
    now = datetime.now(UTC)
    entry = PersistedPlanningLedgerEntry(
        ledger_entry_id=f"ledger:{secrets.token_hex(16)}",
        trip_id=trip_id,
        session_state_id=session_state_id,
        item_type=item_type,
        status=status,
        category=category or _ledger_category_for_type(item_type),
        summary=summary[:280],
        detail=detail,
        source_message_ids=list(source_message_ids or []),
        source_refs=list(source_refs or []),
        related_option_id=related_option_id,
        related_decision_id=related_decision_id,
        supersedes_entry_id=supersedes_entry_id,
        metadata_payload=dict(metadata or {}),
        created_at=now,
        updated_at=now,
    )
    db_session.add(entry)
    return entry


def _validate_planning_ledger_supersedes_target(
    db_session: Session,
    *,
    trip_id: str,
    ledger_entry_id: str,
    supersedes_entry_id: str,
) -> None:
    if not supersedes_entry_id.strip():
        raise ValueError("supersedes_entry_id must reference an existing ledger entry.")
    if supersedes_entry_id == ledger_entry_id:
        raise ValueError("supersedes_entry_id cannot reference the same ledger entry.")

    seen: set[str] = {ledger_entry_id}
    current_id: str | None = supersedes_entry_id
    while current_id:
        if current_id in seen:
            raise ValueError("supersedes_entry_id cannot create a cycle.")
        seen.add(current_id)
        current = db_session.scalar(
            select(PersistedPlanningLedgerEntry)
            .where(PersistedPlanningLedgerEntry.trip_id == trip_id)
            .where(PersistedPlanningLedgerEntry.ledger_entry_id == current_id)
        )
        if current is None:
            raise ValueError("supersedes_entry_id must reference an existing ledger entry.")
        current_id = current.supersedes_entry_id


def _build_persisted_trip_workspace(
    record: PersistedTrip,
    *,
    session: dict[str, Any] | None = None,
    saved_scenarios: list[dict[str, Any]] | None = None,
    activity_log: list[dict[str, Any]] | None = None,
    planning_ledger: dict[str, Any] | None = None,
    planning_notebook: dict[str, Any] | None = None,
    planner_memory: dict[str, Any] | None = None,
    budget_state: dict[str, Any] | None = None,
    policy_context: dict[str, Any] | None = None,
    proposal_context: dict[str, Any] | None = None,
    inventory_bundles: list[InventoryBundle] | None = None,
    inventory_summary: dict[str, Any] | None = None,
    scenario_search: dict[str, Any] | None = None,
    feasibility_summary: dict[str, Any] | None = None,
    include_debug: bool = True,
) -> dict[str, Any]:
    resolved_session = session or _default_workspace_session(record).to_dict()
    trip_record = _serialize_persisted_trip_record(record)
    resolved_activity_log = activity_log or []
    resolved_budget_state = budget_state or {
        "budget_plan": None,
        "versions": [],
        "spend_events": [],
        "summary": {
            "currency": "USD",
            "has_budget_plan": False,
            "current_scenario_budget_id": None,
            "current_scenario_title": None,
            "planned_total": 0.0,
            "actual_total": 0.0,
            "remaining_total": 0.0,
            "spend_event_count": 0,
            "version_count": 0,
            "suggested_categories": [],
            "category_summaries": [],
        },
    }
    ordered_saved_scenarios = _ordered_saved_scenarios(saved_scenarios or [])
    inventory_assembly_input = _build_inventory_assembly_input(
        persisted_trip=record,
        trip_id=record.trip_id,
        trip_mode=record.mode,
        start_date=record.start_date,
        end_date=record.end_date,
        trip_status=record.status,
        primary_regions=record.primary_regions,
        duration_days=record.duration_days,
        trip_title=record.title,
        trip_summary=record.summary,
        traveler_party_kind=record.traveler_party_kind,
        traveler_count=record.traveler_count,
        allow_fixture_fallback=False,
    )
    resolved_inventory_bundles = (
        inventory_bundles
        if inventory_bundles is not None
        else assemble_inventory_bundles_for_trip(
            assembly_input=inventory_assembly_input,
        )
    )
    resolved_inventory_summary = inventory_summary or build_inventory_summary_payload(
        resolved_inventory_bundles,
        assembly_input=inventory_assembly_input,
    )
    inventory_status = str(
        (resolved_inventory_summary.get("runtime_state") or {}).get("status") or "empty"
    )
    resolved_scenario_search = scenario_search or (
        _build_runtime_scenario_search_for_trip(
            record=record,
            inventory_bundles=resolved_inventory_bundles,
            saved_scenarios=ordered_saved_scenarios,
            inventory_status=inventory_status,
        )
    )
    resolved_feasibility_summary = feasibility_summary or build_feasibility_summary_payload(
        resolved_inventory_bundles
    )
    runtime_scenario_comparison = _build_runtime_scenario_comparison(
        trip_id=record.trip_id,
        trip_title=trip_record["trip"]["title"],
        scenario_search=resolved_scenario_search,
        session=resolved_session,
    )
    ranking = build_scenario_ranking_payload(
        trip_id=record.trip_id,
        scenario_search=resolved_scenario_search,
    )
    runtime_state = _build_workspace_runtime_state(
        inventory_summary=resolved_inventory_summary,
        runtime_scenario_comparison=runtime_scenario_comparison,
    )

    raw_policy_state = (policy_context or {}).get("policy_state")
    raw_proposal_state = (proposal_context or {}).get("proposal_state")
    planner_panel_state = _build_planner_panel_state(
        trip=trip_record["trip"],
        scenario_search=resolved_scenario_search,
        session=resolved_session,
        saved_scenarios=ordered_saved_scenarios,
        activity_log=resolved_activity_log,
        feasibility_summary=resolved_feasibility_summary,
        policy_context=policy_context,
        proposal_context=proposal_context,
    )

    payload: dict[str, Any] = {
        "trip_record": trip_record,
        "session": resolved_session,
        "saved_scenarios": ordered_saved_scenarios,
        "scenario_comparison": (
            ordered_saved_scenarios[0]["comparisons"][0]
            if ordered_saved_scenarios and ordered_saved_scenarios[0].get("comparisons")
            else None
        ),
        "scenario_search": resolved_scenario_search,
        "ranking": ranking,
        "route_comparison": runtime_scenario_comparison,
        "runtime_scenario_comparison": runtime_scenario_comparison,
        "activity_log": resolved_activity_log,
        "planning_ledger": planning_ledger or _planning_ledger_state([]),
        "planning_notebook": planning_notebook or _planning_notebook_state([]),
        "planner_memory": planner_memory
        or {
            "current_checkpoint_id": resolved_session.get("current_checkpoint_id"),
            "checkpoints": [],
            "artifacts": [],
        },
        "planner_panel_state": planner_panel_state,
        "runtime_state": runtime_state,
        "feasibility_summary": resolved_feasibility_summary,
        "inventory_summary": resolved_inventory_summary,
        "budget_state": resolved_budget_state,
        "policy_state": raw_policy_state,
        "proposal_state": raw_proposal_state,
    }
    if not include_debug:
        payload["trip_record"] = _public_workspace_trip_record(trip_record)
        payload["policy_state"] = _public_workspace_policy_state(raw_policy_state)
        payload["proposal_state"] = _public_workspace_proposal_state(raw_proposal_state)
        payload["planner_panel_state"] = _public_workspace_planner_panel_state(planner_panel_state)
        payload = _strip_raw_workspace_diagnostic_keys(payload)
    payload["view_model"] = _build_workspace_view_model(
        payload,
        trip_mode=record.mode,
        include_debug=include_debug,
    )
    return payload


def _empty_workspace_scenario_search() -> dict[str, Any]:
    return {
        "title": "Trip setup workspace",
        "scenarios": [],
        "explanation": [
            "This workspace was opened from a newly created persisted trip.",
            "Scenario search and comparisons will appear after planning begins.",
        ],
        "source_refs": [],
    }


_TRIP_MODE_LABELS: dict[str, str] = {
    "leisure": "Leisure trip",
    "business": "Business trip",
}

# Raw workspace payload keys that must NEVER appear in user-facing view-model
# copy. They are mirrored under WorkspaceDebugState.sections so an explicit
# debug/advanced affordance can still surface them.
_DEBUG_PAYLOAD_KEYS: tuple[str, ...] = (
    "runtime_state",
    "inventory_summary",
    "scenario_search",
    "ranking",
    "route_comparison",
    "runtime_scenario_comparison",
    "feasibility_summary",
    "planner_panel_state",
    "policy_state",
    "proposal_state",
    "trip_record",
    "session",
    "saved_scenarios",
    "activity_log",
    "planner_memory",
)


def _public_workspace_policy_state(policy_state: Any) -> dict[str, Any] | None:
    if not isinstance(policy_state, dict) or not policy_state:
        return None

    constraint_set = deepcopy(policy_state.get("constraint_set") or {})
    if isinstance(constraint_set, dict):
        for key in ("policy_id", "organization_id", "policy_version"):
            constraint_set.pop(key, None)
    else:
        constraint_set = {}

    organization_context = deepcopy(policy_state.get("organization_context") or {})
    if isinstance(organization_context, dict):
        organization_context.pop("organization_id", None)
    else:
        organization_context = {}

    public_state: dict[str, Any] = {}
    if constraint_set:
        public_state["constraint_set"] = constraint_set
    if organization_context:
        public_state["organization_context"] = organization_context
    notes = policy_state.get("notes")
    if isinstance(notes, list) and notes:
        public_state["notes"] = list(notes)
    tags = policy_state.get("tags")
    if isinstance(tags, list) and tags:
        public_state["tags"] = list(tags)
    return public_state or None


def _public_workspace_trip_record(trip_record: dict[str, Any]) -> dict[str, Any]:
    public_record = deepcopy(trip_record)
    trip = public_record.get("trip")
    if isinstance(trip, dict):
        artifacts = trip.get("artifacts")
        if isinstance(artifacts, dict):
            artifacts.pop("policy_state_id", None)
    artifact_refs = public_record.get("artifact_refs")
    if isinstance(artifact_refs, dict):
        artifact_refs.pop("policy_state_id", None)
    return public_record


def _strip_raw_workspace_diagnostic_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_raw_workspace_diagnostic_keys(item)
            for key, item in value.items()
            if key not in {"policy_state_id", "proposal_state_id"}
        }
    if isinstance(value, list):
        return [_strip_raw_workspace_diagnostic_keys(item) for item in value]
    return value


def _public_workspace_follow_up(follow_up: Any) -> dict[str, Any] | None:
    if not isinstance(follow_up, dict) or not follow_up:
        return None
    public_keys = {
        "status",
        "path",
        "title",
        "summary",
        "recommended_action",
        "recommended_label",
        "alternatives",
        "guidance",
        "notes",
        "selected_alternative",
        "requested_exception",
    }
    return {key: deepcopy(value) for key, value in follow_up.items() if key in public_keys}


def _public_workspace_proposal_state(proposal_state: Any) -> dict[str, Any] | None:
    if not isinstance(proposal_state, dict) or not proposal_state:
        return None

    proposal = proposal_state.get("proposal") if isinstance(proposal_state, dict) else {}
    proposal = proposal if isinstance(proposal, dict) else {}
    public_proposal: dict[str, Any] = {}
    approval_notes = proposal.get("approval_notes")
    if isinstance(approval_notes, list) and approval_notes:
        public_proposal["approval_notes"] = list(approval_notes)
    comparables = proposal.get("comparables")
    if isinstance(comparables, list) and comparables:
        public_proposal["comparables"] = deepcopy(comparables)

    summary = proposal_state.get("summary")
    summary = summary if isinstance(summary, dict) else {}
    public_summary_keys = {
        "submission_summary",
        "approval_ready",
        "comparable_count",
        "highlights",
        "follow_up_status",
        "follow_up_title",
        "follow_up_summary",
    }
    public_summary = {
        key: deepcopy(value)
        for key, value in summary.items()
        if key in public_summary_keys and value is not None
    }

    return {
        "proposal": public_proposal,
        "evaluation": {"evaluation_result": None},
        "summary": public_summary,
        "follow_up": _public_workspace_follow_up(proposal_state.get("follow_up")),
    }


def _public_workspace_planner_panel_state(
    planner_panel_state: dict[str, Any],
) -> dict[str, Any]:
    public_state = deepcopy(planner_panel_state)
    trip = public_state.get("trip")
    if isinstance(trip, dict):
        artifacts = trip.get("artifacts")
        if isinstance(artifacts, dict):
            artifacts.pop("policy_state_id", None)
    proposal = public_state.get("proposal")
    if isinstance(proposal, dict):
        for key in (
            "proposal_id",
            "trip_id",
            "proposal_version",
            "scenario_id",
            "constraint_set_id",
        ):
            proposal.pop(key, None)
        for option in proposal.get("selected_options") or []:
            if isinstance(option, dict):
                option.pop("option_id", None)
                option.pop("justification_refs", None)
        public_state["proposal"] = proposal or None
    policy_evaluation = public_state.get("policy_evaluation")
    if isinstance(policy_evaluation, dict):
        public_state["policy_evaluation"] = {
            key: deepcopy(value)
            for key, value in policy_evaluation.items()
            if key in {"notes", "recommendation", "summary"}
        } or None
    return public_state


def _workspace_policy_state_is_active(
    *,
    policy_state: Any,
    proposal_state: Any,
) -> bool:
    if isinstance(policy_state, dict) and policy_state:
        return True
    if not isinstance(proposal_state, dict) or not proposal_state:
        return False

    summary = proposal_state.get("summary") or {}
    summary = summary if isinstance(summary, dict) else {}
    if proposal_state.get("execution_id"):
        return True
    if summary.get("approval_ready"):
        return True
    if summary.get("evaluation_result_status") or summary.get("follow_up_status"):
        return True
    submission_status = str(
        summary.get("submission_status") or proposal_state.get("submission_status") or ""
    ).lower()
    evaluation_status = str(
        summary.get("evaluation_transport_status") or proposal_state.get("evaluation_status") or ""
    ).lower()
    return submission_status not in {"", "pending"} or evaluation_status not in {
        "",
        "pending",
    }


def _workspace_approval_status(
    proposal_state: dict[str, Any],
) -> tuple[str, str, list[str]]:
    proposal_summary = proposal_state.get("summary") or {}
    proposal_summary = proposal_summary if isinstance(proposal_summary, dict) else {}
    approval_ready = bool(proposal_summary.get("approval_ready"))
    follow_up_status = str(proposal_summary.get("follow_up_status") or "").lower()
    evaluation_status = str(
        proposal_summary.get("evaluation_result_status")
        or proposal_summary.get("submission_status")
        or ""
    ).lower()

    if approval_ready:
        return "approved", "Your trip is ready for approval.", []
    if evaluation_status in {"in_review", "pending", "submitted"}:
        return "in_review", "Your trip approval is in review.", []
    if evaluation_status in {"failed", "rejected", "needs_attention"} or follow_up_status in {
        "exception_required",
        "reoptimization_required",
        "remediation_required",
    }:
        blockers = [
            str(item)
            for item in (proposal_summary.get("highlights") or [])
            if isinstance(item, str)
        ]
        return "needs_attention", "Approval needs your attention.", blockers
    if proposal_state:
        return "not_ready", "Approval is not ready yet.", []
    return "not_applicable", "Approval is not required yet.", []


def _policy_presentation_for_workspace(
    *,
    active_policy_state: bool,
    proposal_state: Any,
) -> dict[str, Any]:
    if not active_policy_state:
        return {
            "active_policy_state": False,
            "posture_label": "Not applicable",
            "approval_status_label": "Not applicable",
            "next_step_label": "No policy action needed",
            "summary": "Policy approval is not part of this workspace yet.",
        }

    proposal_state = proposal_state if isinstance(proposal_state, dict) else {}
    if not proposal_state:
        return {
            "active_policy_state": True,
            "posture_label": "Approval not started",
            "approval_status_label": "Approval not started",
            "next_step_label": "Build approval packet",
            "summary": "No approval packet has been submitted yet.",
        }

    approval_status, headline, blockers = _workspace_approval_status(proposal_state)
    summary = proposal_state.get("summary") or {}
    summary = summary if isinstance(summary, dict) else {}
    follow_up_status = str(summary.get("follow_up_status") or "").lower()

    if approval_status == "approved":
        posture_label = "Ready for approval"
        next_step_label = "Prepare approval packet"
    elif follow_up_status == "exception_required":
        posture_label = "Needs exception"
        next_step_label = "Review exception request"
    elif approval_status == "needs_attention":
        posture_label = "Needs follow-up"
        next_step_label = "Resolve policy follow-up"
    elif approval_status == "in_review":
        posture_label = "Waiting for policy review"
        next_step_label = "Wait for policy review"
    elif approval_status == "not_ready":
        posture_label = "Not ready for approval"
        next_step_label = "Complete approval packet"
    else:
        posture_label = "Policy state available"
        next_step_label = "Review policy details"

    return {
        "active_policy_state": True,
        "posture_label": posture_label,
        "approval_status_label": posture_label,
        "next_step_label": next_step_label,
        "summary": " ".join([headline, *blockers[:1]]).strip(),
    }


def _build_workspace_view_model(
    payload: dict[str, Any],
    *,
    trip_mode: str | None = None,
    include_debug: bool = True,
) -> dict[str, Any]:
    """Map a workspace payload dict into the typed product view model.

    The mapper deliberately keeps user-facing strings free of raw runtime,
    provider, fallback, policy/proposal id, and trip-scoped object id
    language. Raw payloads are mirrored under ``debug_state.sections`` so the
    frontend can render them only behind an explicit debug affordance.
    """

    trip_record = payload.get("trip_record") or {}
    trip_block = trip_record.get("trip") if isinstance(trip_record, dict) else {}
    trip_block = trip_block if isinstance(trip_block, dict) else {}

    resolved_mode = str(trip_mode or trip_block.get("mode") or "leisure")
    if resolved_mode not in _TRIP_MODE_LABELS:
        resolved_mode = "leisure"
    mode_label = _TRIP_MODE_LABELS[resolved_mode]

    runtime_state = payload.get("runtime_state") or {}
    runtime_state = runtime_state if isinstance(runtime_state, dict) else {}
    status = str(runtime_state.get("status") or "empty")
    if status not in {"ready", "partial", "empty"}:
        status = "empty"

    trip_title = str(trip_block.get("title") or "Trip workspace")

    saved_scenarios = payload.get("saved_scenarios") or []
    saved_scenarios = saved_scenarios if isinstance(saved_scenarios, list) else []
    feasibility_summary = payload.get("feasibility_summary") or {}
    feasibility_summary = feasibility_summary if isinstance(feasibility_summary, dict) else {}

    decided: list[str] = []
    if saved_scenarios:
        decided.append(f"{len(saved_scenarios)} saved scenario draft(s)")
    inventory_summary = payload.get("inventory_summary") or {}
    inventory_summary = inventory_summary if isinstance(inventory_summary, dict) else {}
    bundle_count = int(inventory_summary.get("bundle_count") or 0)
    if bundle_count:
        decided.append(f"{bundle_count} inventory bundle(s) assembled")

    uncertain: list[str] = []
    attention_count = int(feasibility_summary.get("attention_bundle_count") or 0)
    if attention_count:
        uncertain.append(f"{attention_count} bundle(s) need attention")
    if status == "empty":
        uncertain.append("Trip context is not complete yet.")
    elif status == "partial":
        uncertain.append("Scenario comparison is not yet ready.")

    if status == "ready":
        headline = "Your trip plan is ready to review."
        next_step_title = "Review and pick a scenario"
        next_step_summary = "Compare the saved scenarios and choose one to keep planning around."
        next_step_action = "Open scenario comparison"
        next_step_target = "scenario-comparison"
        blocked = False
    elif status == "partial":
        headline = "Your trip plan is partially assembled."
        next_step_title = "Continue planning"
        next_step_summary = (
            "Inventory is in place; resolve the open uncertainties to unlock"
            " scenario comparison."
        )
        next_step_action = "Continue planning"
        next_step_target = "planner"
        blocked = False
    else:
        headline = "Trip planning hasn't started yet."
        next_step_title = "Start planning"
        next_step_summary = "Add the missing trip context to start assembling scenarios."
        next_step_action = "Open trip setup"
        next_step_target = "trip-setup"
        blocked = True

    user_summary = {
        "trip_title": trip_title,
        "trip_mode": resolved_mode,
        "mode_label": mode_label,
        "status": status,
        "headline": headline,
        "decided": decided,
        "uncertain": uncertain,
    }

    next_step = {
        "title": next_step_title,
        "summary": next_step_summary,
        "action_label": next_step_action,
        "action_target": next_step_target,
        "blocked": blocked,
    }

    policy_state = payload.get("policy_state")
    proposal_state_value = payload.get("proposal_state")
    active_policy_state = _workspace_policy_state_is_active(
        policy_state=policy_state,
        proposal_state=proposal_state_value,
    )
    show_policy_panels = resolved_mode == "business" or active_policy_state
    panel_visibility = {
        "show_budget_panel": True,
        "show_policy_posture": show_policy_panels,
        "show_proposal_panel": show_policy_panels,
        "show_approval_readiness_panel": show_policy_panels,
    }
    policy_presentation = _policy_presentation_for_workspace(
        active_policy_state=show_policy_panels,
        proposal_state=proposal_state_value,
    )

    business_summary: dict[str, Any] | None = None
    if resolved_mode == "business":
        proposal_state = payload.get("proposal_state") or {}
        proposal_state = proposal_state if isinstance(proposal_state, dict) else {}
        approval_status, approval_headline, blockers = _workspace_approval_status(proposal_state)

        business_summary = {
            "approval_status": approval_status,
            "headline": approval_headline,
            "blockers": blockers,
        }

    debug_sections: dict[str, dict[str, Any]] = {}
    for key in _DEBUG_PAYLOAD_KEYS:
        if not include_debug and key in {"policy_state", "proposal_state"}:
            continue
        raw_value = payload.get(key)
        if raw_value is None:
            continue
        debug_sections[key] = {
            "title": key.replace("_", " ").title(),
            "payload": raw_value,
        }

    return {
        "user_summary": user_summary,
        "next_step": next_step,
        "panel_visibility": panel_visibility,
        "policy_presentation": policy_presentation,
        "business_summary": business_summary,
        "debug_state": {"sections": debug_sections},
    }


def _build_workspace_runtime_state(
    *,
    inventory_summary: dict[str, Any],
    runtime_scenario_comparison: dict[str, Any],
) -> dict[str, str]:
    inventory_runtime_state = dict(inventory_summary.get("runtime_state") or {})
    runtime_scenarios = list(runtime_scenario_comparison.get("scenarios") or [])
    inventory_status = str(inventory_runtime_state.get("status") or "")

    if inventory_status == "ready" and runtime_scenarios:
        return {
            "status": "ready",
            "title": "Workspace runtime is ready",
            "summary": "Inventory, scenario ranking, and comparison surfaces are ready for review.",
        }
    if inventory_status in {"partial", "empty"}:
        return {
            "status": inventory_status,
            "title": str(
                inventory_runtime_state.get("title")
                or (
                    "Workspace runtime is partially assembled"
                    if inventory_status == "partial"
                    else "Workspace runtime is still empty"
                )
            ),
            "summary": str(
                inventory_runtime_state.get("summary")
                or (
                    "Inventory bundles are available, but scenario comparison is not ready yet."
                    if inventory_status == "partial"
                    else "Trip context is not complete enough for runtime workspace assembly yet."
                )
            ),
        }
    if inventory_summary.get("bundle_count", 0) > 0 or runtime_scenarios:
        return {
            "status": "partial",
            "title": "Workspace runtime is partially assembled",
            "summary": "Inventory bundles are available, but scenario comparison is not ready yet.",
        }
    return {
        "status": str(inventory_runtime_state.get("status") or "empty"),
        "title": str(inventory_runtime_state.get("title") or "Workspace runtime is still empty"),
        "summary": str(
            inventory_runtime_state.get("summary")
            or "Trip context is not complete enough for runtime workspace assembly yet."
        ),
    }


def _build_runtime_scenario_comparison_payload(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
) -> dict[str, Any] | None:
    fixture = _FIXTURES.get(trip_id)
    if fixture is not None:
        _db_record = db_session.scalar(
            select(PersistedTrip)
            .where(PersistedTrip.trip_id == trip_id)
            .where(PersistedTrip.user_id == user.user_id)
        )
        if _db_record is not None:
            fixture = None
    if fixture is not None:
        trip_record = _load_trip_record(fixture.trip_fixture)
        session = _load_session(fixture.session_fixture)
        inventory_bundles = assemble_inventory_bundles_for_trip(
            trip_id=trip_id,
            trip_mode=trip_record.trip.mode,
        )
        scenario_search = _build_scenario_search(
            trip_id=trip_id,
            trip_mode=trip_record.trip.mode,
            bundles=inventory_bundles,
            trip_title=trip_record.trip.title,
            primary_regions=tuple(trip_record.trip.trip_frame.primary_regions),
            duration_days=trip_record.trip.trip_frame.duration_days,
            traveler_party_kind=trip_record.trip.trip_frame.traveler_party.kind,
        )
        return _build_runtime_scenario_comparison(
            trip_id=trip_id,
            trip_title=trip_record.trip.title,
            scenario_search=scenario_search.to_dict(),
            session=session.to_dict(),
        )

    try:
        record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    except WorkspaceTripNotFoundError:
        return None

    session_record = _get_or_create_workspace_session_record(db_session, record=record)
    persisted_saved_scenarios_records = list(
        db_session.scalars(
            select(PersistedSavedScenario)
            .where(PersistedSavedScenario.trip_id == trip_id)
            .order_by(PersistedSavedScenario.updated_at.desc())
        ).all()
    )
    if not persisted_saved_scenarios_records:
        persisted_saved_scenarios_records = _create_bootstrap_saved_scenarios(
            db_session,
            record=record,
            session_record=session_record,
        )
        db_session.commit()
    persisted_saved_scenarios = [
        {
            "saved_scenario_id": scenario.saved_scenario_id,
            "trip_id": scenario.trip_id,
            "current_version_id": scenario.current_version_id,
            "versions": list(scenario.versions),
            "comparisons": list(scenario.comparisons),
            "tags": list(scenario.tags),
            "notes": list(scenario.notes),
        }
        for scenario in persisted_saved_scenarios_records
    ]
    persisted_inventory_bundles, inventory_summary = _build_workspace_inventory_inputs(record)
    inventory_status = str((inventory_summary.get("runtime_state") or {}).get("status") or "empty")
    return _build_runtime_scenario_comparison(
        trip_id=trip_id,
        trip_title=record.title,
        scenario_search=_build_runtime_scenario_search_for_trip(
            record=record,
            inventory_bundles=persisted_inventory_bundles,
            saved_scenarios=persisted_saved_scenarios,
            inventory_status=inventory_status,
        ),
        session=_serialize_session_record(session_record),
    )


def _create_bootstrap_saved_scenarios(
    db_session: Session,
    *,
    record: PersistedTrip,
    session_record: PersistedPlanningSessionState,
) -> list[PersistedSavedScenario]:
    created_at = _isoformat(datetime.now(UTC))
    baseline, fallback = _bootstrap_saved_scenario_records(
        record,
        session_state_id=session_record.session_state_id,
        created_at=created_at,
    )
    persisted_records = [
        PersistedSavedScenario(
            saved_scenario_id=scenario.saved_scenario_id,
            trip_id=scenario.trip_id,
            current_version_id=scenario.current_version_id,
            versions=[item.to_dict() for item in scenario.versions],
            comparisons=[item.to_dict() for item in scenario.comparisons],
            tags=list(scenario.tags),
            notes=list(scenario.notes),
        )
        for scenario in (baseline, fallback)
    ]
    try:
        with db_session.begin_nested():
            for persisted in persisted_records:
                db_session.add(persisted)
            if _bootstrap_option_set_id(record.trip_id) not in record.option_set_ids:
                record.option_set_ids = [
                    *record.option_set_ids,
                    _bootstrap_option_set_id(record.trip_id),
                ]
            record.updated_at = datetime.now(UTC)
            db_session.flush()
    except IntegrityError:
        existing = db_session.scalars(
            select(PersistedSavedScenario)
            .where(PersistedSavedScenario.trip_id == record.trip_id)
            .order_by(PersistedSavedScenario.updated_at.desc())
        ).all()
        if existing:
            return list(existing)
        raise
    return persisted_records


def _sync_workspace_session_record(
    session_record: PersistedPlanningSessionState,
    *,
    record: PersistedTrip,
    saved_scenarios: list[PersistedSavedScenario],
    runtime_option_ids: list[str] | None = None,
) -> bool:
    ordered_ids = [
        scenario["saved_scenario_id"]
        for scenario in _ordered_saved_scenarios(
            [
                {
                    "saved_scenario_id": item.saved_scenario_id,
                    "versions": list(item.versions),
                }
                for item in saved_scenarios
            ]
        )
    ]
    if not ordered_ids:
        return False

    updated = False
    if session_record.current_saved_scenario_id is None:
        session_record.current_saved_scenario_id = ordered_ids[0]
        updated = True

    option_set_id = _bootstrap_option_set_id(record.trip_id)
    surfaced_option_ids = list(runtime_option_ids or ordered_ids)
    presentation = (
        session_record.recent_option_presentations[0]
        if session_record.recent_option_presentations
        else None
    )
    if (
        presentation is None
        or presentation.get("option_set_id") != option_set_id
        or presentation.get("surfaced_option_ids") != surfaced_option_ids
        or presentation.get("highlighted_option_id") not in surfaced_option_ids
    ):
        session_record.recent_option_presentations = [
            OptionPresentationRecord(
                presentation_id=f"presentation:{record.trip_id}:workspace-panel",
                option_set_id=option_set_id,
                shown_at=session_record.last_updated_at,
                surface_kind="scenario_comparison",
                surfaced_option_ids=surfaced_option_ids,
                highlighted_option_id=surfaced_option_ids[0],
                summary=(
                    "Runtime workspace scenarios are ready for comparison."
                    if runtime_option_ids
                    else "Persisted workspace bootstrap scenarios are ready for comparison."
                ),
                notes=["Initial workspace planner presentation."],
            ).to_dict()
        ]
        updated = True

    if session_record.pending_decisions:
        decision = dict(session_record.pending_decisions[0])
        if (
            decision.get("related_option_set_id") != option_set_id
            or decision.get("related_saved_scenario_id") is None
        ):
            decision["related_saved_scenario_id"] = ordered_ids[0]
            decision["related_option_set_id"] = option_set_id
            session_record.pending_decisions = [
                decision,
                *session_record.pending_decisions[1:],
            ]
            updated = True

    if updated:
        session_record.last_updated_at = _isoformat(datetime.now(UTC))
        notes = list(session_record.notes)
        if "workspace-bootstrap:scenario-scaffold" not in notes:
            notes.append("workspace-bootstrap:scenario-scaffold")
        session_record.notes = notes
    return updated


def _transport_error_code(error_record: dict[str, Any]) -> str | None:
    code = error_record.get("code")
    if isinstance(code, str) and code:
        return code
    details = error_record.get("details")
    if isinstance(details, dict):
        details_code = details.get("error_code")
        if isinstance(details_code, str) and details_code:
            return details_code
    return None


def _build_planner_panel_state(
    *,
    trip: dict[str, Any],
    scenario_search: dict[str, Any],
    session: dict[str, Any],
    saved_scenarios: list[dict[str, Any]],
    activity_log: list[dict[str, Any]],
    feasibility_summary: dict[str, Any],
    policy_context: dict[str, Any] | None = None,
    proposal_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scenarios = list(scenario_search.get("scenarios", []))
    primary_regions = list(trip["trip_frame"].get("primary_regions") or [])
    region_summary = ", ".join(primary_regions[:2]) if primary_regions else "the current trip frame"

    if scenarios:
        option_set = {
            "option_set_id": f"option-set:{trip['trip_id']}:workspace-panel",
            "trip_id": trip["trip_id"],
            "purpose": "workspace_review",
            "scope": "scenario_selection",
            "title": scenario_search.get("title") or "Workspace planner scenarios",
            "comparison_axes": [
                {
                    "key": "score",
                    "label": "Planner score",
                    "direction": "higher_better",
                },
                {
                    "key": "travel_minutes",
                    "label": "Travel minutes",
                    "direction": "lower_better",
                },
                {"key": "transfers", "label": "Transfers", "direction": "lower_better"},
            ],
            "explanation": list(scenario_search.get("explanation") or [])
            or [
                "This panel mirrors the current workspace scenarios through the app runtime.",
            ],
            "options": [
                {
                    "option_id": scenario["scenario_id"],
                    "kind": "scenario",
                    "label": scenario["title"],
                    "summary": scenario["scenario_summary"]["headline"],
                    "drawbacks": [
                        tradeoff["summary"] for tradeoff in scenario.get("unresolved_tradeoffs", [])
                    ]
                    or ["No explicit unresolved tradeoffs were recorded for this scenario yet."],
                    "explanation": [
                        f"Rank #{scenario['rank']} with score {scenario['score']:.2f}.",
                        f"Route sequence: {' -> '.join(scenario['scenario_summary'].get('route_sequence', [])) or 'not surfaced yet'}.",
                    ],
                }
                for scenario in scenarios[:3]
            ],
        }
        outputs = [
            {
                "output_id": f"output:{trip['trip_id']}:workspace-summary",
                "title": "Workspace scenario feed",
                "body": f"The workspace now renders planner-side-panel content for {trip['title']} using trip-scoped API data.",
                "tags": ["workspace", "planner-panel"],
            },
            {
                "output_id": f"output:{trip['trip_id']}:scenario-count",
                "title": "Scenario coverage",
                "body": f"{len(scenarios)} scenario option(s) are currently available for {region_summary}.",
                "tags": ["scenarios", trip["mode"]],
            },
        ]
    else:
        option_set = {
            "option_set_id": f"option-set:{trip['trip_id']}:workspace-bootstrap",
            "trip_id": trip["trip_id"],
            "purpose": "workspace_bootstrap",
            "scope": "trip_setup",
            "title": "Planner workspace bootstrap",
            "comparison_axes": [
                {
                    "key": "scope",
                    "label": "Planning scope",
                    "direction": "higher_better",
                },
                {
                    "key": "specificity",
                    "label": "Trip specificity",
                    "direction": "higher_better",
                },
            ],
            "explanation": [
                "This starter panel is seeded from the persisted trip record until ranked planner scenarios exist.",
                "Later planner issues can replace these bootstrap options with live orchestration outputs.",
            ],
            "options": [
                {
                    "option_id": f"bootstrap:{trip['trip_id']}:keep-frame",
                    "kind": "trip_setup",
                    "label": "Keep the current trip frame narrow",
                    "summary": f"Use {region_summary} as the first planner pass boundary.",
                    "drawbacks": [
                        "You may need another pass if the trip should span more regions."
                    ],
                    "explanation": [
                        "Best when the user wants to start from one durable trip container and iterate later.",
                    ],
                },
                {
                    "option_id": f"bootstrap:{trip['trip_id']}:broaden-frame",
                    "kind": "trip_setup",
                    "label": "Broaden the first planner pass",
                    "summary": "Expand regions, dates, or traveler notes before the first ranked scenario run.",
                    "drawbacks": ["A broader scope can delay the first saved scenario comparison."],
                    "explanation": [
                        "Best when the trip shell is real but still intentionally under-specified.",
                    ],
                },
            ],
        }
        outputs = [
            {
                "output_id": f"output:{trip['trip_id']}:bootstrap-ready",
                "title": "Workspace bootstrap is ready",
                "body": f"{trip['title']} has enough persisted trip context to mount the planner surface inside the app.",
                "tags": ["bootstrap", "workspace"],
            },
            {
                "output_id": f"output:{trip['trip_id']}:bootstrap-scenarios",
                "title": "Saved scenario scaffold is ready",
                "body": (
                    f"{len(saved_scenarios)} persisted saved scenario(s) are available for the first "
                    "workspace comparison pass."
                    if saved_scenarios
                    else "Saved scenario scaffolding will appear once the persisted workspace path initializes it."
                ),
                "tags": ["bootstrap", "saved-scenarios"],
            },
            {
                "output_id": f"output:{trip['trip_id']}:next-pass",
                "title": "Next planning pass",
                "body": "Scenario search, ranking, and persistence issues can now build on a real workspace-mounted planner panel.",
                "tags": ["handoff", trip["mode"]],
            },
        ]

    rejected_option_ids, selected_option_id, fallback_option_ids = _session_feedback_state(
        session,
        option_set["option_set_id"],
    )
    option_set["options"] = [
        {
            **option,
            "label": (
                f"{option['label']} (saved direction)"
                if option["option_id"] == selected_option_id
                else (
                    f"{option['label']} (fallback)"
                    if option["option_id"] in fallback_option_ids
                    else option["label"]
                )
            ),
            "explanation": (
                ["You already chose this direction in the workspace."] + option["explanation"]
                if option["option_id"] == selected_option_id
                else (
                    ["This option was kept as an explicit fallback for later comparison."]
                    + option["explanation"]
                    if option["option_id"] in fallback_option_ids
                    else option["explanation"]
                )
            ),
        }
        for option in option_set["options"]
        if option["option_id"] not in rejected_option_ids
    ] or option_set["options"]

    mapped_decisions = [
        {
            "decision_id": decision["decision_id"],
            "title": decision["title"],
            "prompt": decision["prompt"],
            "choices": (
                list(decision["choices"])
                if isinstance(decision.get("choices"), (list, tuple)) and decision["choices"]
                else [
                    "Keep the current direction.",
                    "Compare another planner-backed option first.",
                ]
            ),
        }
        for decision in session.get("pending_decisions", [])
    ]

    outputs = (
        _workspace_activity_outputs(trip["trip_id"], activity_log)
        + build_feasibility_planner_outputs(
            trip_id=trip["trip_id"],
            feasibility_summary=feasibility_summary,
        )
        + build_scenario_ranking_outputs(
            trip_id=trip["trip_id"],
            scenario_search=scenario_search,
        )
        + outputs
    )

    next_step_actions = [
        {
            "action_id": f"action:{trip['trip_id']}:review-outputs",
            "action_kind": "review_outputs",
            "label": "Review planner outputs",
            "description": "Read the trip-scoped planner summary before saving or revising the workspace direction.",
            "emphasis": "secondary",
            "target_section": "outputs",
        },
        {
            "action_id": f"action:{trip['trip_id']}:compare-options",
            "action_kind": "compare_options",
            "label": "Compare planner options",
            "description": "Inspect the mounted planner options without leaving the workspace route.",
            "emphasis": "primary",
            "target_section": "options",
        },
    ]
    if mapped_decisions:
        next_step_actions.insert(
            0,
            {
                "action_id": f"action:{trip['trip_id']}:answer-decision",
                "action_kind": "answer_decision",
                "label": "Answer the current planner decision",
                "description": "Resolve the active planner question before the next planning checkpoint.",
                "emphasis": "primary",
                "target_section": "decisions",
            },
        )

    proposal_state = (
        dict(proposal_context["proposal_state"])
        if proposal_context is not None and proposal_context.get("proposal_state") is not None
        else None
    )
    if proposal_state is not None:
        policy_evaluation = (
            dict(proposal_state["evaluation"].get("evaluation_result"))
            if proposal_state.get("evaluation") is not None
            and proposal_state["evaluation"].get("evaluation_result") is not None
            else None
        )
        proposal = (
            dict(proposal_state["proposal"]) if proposal_state.get("proposal") is not None else None
        )
    else:
        policy_evaluation = (
            dict(policy_context["policy_evaluation"])
            if policy_context is not None and policy_context.get("policy_evaluation") is not None
            else None
        )
        proposal = (
            dict(policy_context["proposal"])
            if policy_context is not None and policy_context.get("proposal") is not None
            else None
        )
    if policy_evaluation is not None:
        outputs.append(
            {
                "output_id": f"output:{trip['trip_id']}:policy-ready",
                "title": "Approval readiness loaded",
                "body": "The workspace is using saved approval inputs instead of placeholder readiness state.",
                "tags": ["policy", "workspace", trip["mode"]],
                "status": (
                    "positive"
                    if policy_evaluation["status"] == "compliant"
                    else (
                        "critical" if policy_evaluation["status"] == "non_compliant" else "caution"
                    )
                ),
                "highlights": list(policy_evaluation.get("notes") or [])[:3],
            }
        )
        next_step_actions.insert(
            0,
            {
                "action_id": f"action:{trip['trip_id']}:review-policy",
                "action_kind": "prepare_approval",
                "label": "Review approval readiness",
                "description": "Inspect saved approval constraints and readiness before moving to submission work.",
                "emphasis": "primary",
                "target_section": "approval",
            },
        )
    policy_summary = (
        dict(policy_context.get("summary") or {}) if isinstance(policy_context, dict) else {}
    )
    policy_transport_error = (
        dict(policy_summary.get("transport_error") or {})
        if isinstance(policy_summary.get("transport_error"), dict)
        else {}
    )
    policy_error_code = policy_transport_error.get("error_code")
    if policy_summary.get("status") == "stored_policy_fallback" and policy_error_code in {
        "breaker_open",
        "timeout",
    }:
        if policy_error_code == "breaker_open":
            notice_title = "Approval service is temporarily unavailable"
            notice_body = (
                "The workspace is using the latest saved approval information while the live "
                "service recovers."
            )
        else:
            notice_title = "Approval service request timed out"
            notice_body = (
                "The workspace is using the latest saved approval information while the live "
                "service recovers."
            )
        outputs.append(
            {
                "output_id": f"output:{trip['trip_id']}:policy-transport-fallback",
                "title": notice_title,
                "body": notice_body,
                "tags": ["policy", "transport", "stored-policy", trip["mode"]],
                "status": "caution",
                "highlights": [
                    "Saved approval information is still available.",
                    "Retry the live approval refresh later.",
                ],
            }
        )
    if proposal_state is not None:
        summary = dict(proposal_state.get("summary") or {})
        follow_up = dict(proposal_state.get("follow_up") or {})
        outputs.append(
            {
                "output_id": f"output:{trip['trip_id']}:proposal-lifecycle",
                "title": "Approval packet loaded",
                "body": "The workspace now carries saved approval packet and review state.",
                "tags": ["proposal", "approval", trip["mode"]],
                "status": (
                    "positive"
                    if summary.get("approval_ready")
                    else ("caution" if summary.get("evaluation_transport_status") else "neutral")
                ),
                "highlights": list(summary.get("highlights") or [])[:3],
            }
        )
        submission_error = summary.get("submission_error")
        evaluation_error = summary.get("evaluation_error")
        transport_error = (
            submission_error
            if isinstance(submission_error, dict)
            else evaluation_error if isinstance(evaluation_error, dict) else None
        )
        if isinstance(transport_error, dict):
            error_code = _transport_error_code(transport_error)
            if error_code in {"breaker_open", "timeout"}:
                if error_code == "breaker_open":
                    notice_title = "Approval service is temporarily unavailable"
                    notice_body = (
                        "The workspace is using the latest saved approval information while the "
                        "live service recovers."
                    )
                else:
                    notice_title = "Approval service request timed out"
                    notice_body = (
                        "The workspace is using the latest saved approval information while the "
                        "live service recovers."
                    )
                outputs.append(
                    {
                        "output_id": f"output:{trip['trip_id']}:proposal-transport-fallback",
                        "title": notice_title,
                        "body": notice_body,
                        "tags": [
                            "proposal",
                            "transport",
                            "stored-policy",
                            trip["mode"],
                        ],
                        "status": "caution",
                        "highlights": [
                            "Saved approval information is still available.",
                            "Retry the live approval refresh later.",
                        ],
                    }
                )
        if follow_up:
            outputs.append(
                {
                    "output_id": f"output:{trip['trip_id']}:proposal-follow-up",
                    "title": follow_up.get("title") or "Proposal follow-up",
                    "body": follow_up.get("summary")
                    or "The workspace has a persisted follow-up path after policy evaluation.",
                    "tags": ["proposal", "follow-up", trip["mode"]],
                    "status": (
                        "positive"
                        if follow_up.get("status") in {"resolved", "approval_pending"}
                        else (
                            "critical"
                            if follow_up.get("status") == "reoptimization_required"
                            else "caution"
                        )
                    ),
                    "highlights": list(follow_up.get("guidance") or [])[:2],
                }
            )
            next_step_actions.insert(
                0,
                {
                    "action_id": f"action:{trip['trip_id']}:proposal-follow-up",
                    "action_kind": follow_up.get("recommended_action") or "review_follow_up",
                    "label": follow_up.get("recommended_label") or "Review proposal follow-up",
                    "description": follow_up.get("summary")
                    or "Inspect the persisted follow-up lane for the latest policy result.",
                    "emphasis": "primary",
                    "target_section": "approval",
                },
            )

    runtime_config = get_planner_runtime_config()
    return {
        "trip": trip,
        "option_set": option_set,
        "proposal": proposal,
        "policy_evaluation": policy_evaluation,
        "pending_decisions": mapped_decisions,
        "outputs": outputs,
        "planner_behavior": {
            "trip_stage": "compare" if scenarios else "bootstrap",
            "runtime_mode": runtime_config.mode,
            "runtime_status": runtime_config.status,
            "runtime_label": runtime_config.title,
            "runtime_summary": runtime_config.summary,
            "ask_before_next_major_change": session["interaction_state"].get(
                "ask_before_major_change",
                True,
            ),
            "target_research_passes": max(
                1,
                session["interaction_state"].get("auto_advance_research_passes", 1) + 1,
            ),
            "target_options_before_checkpoint": max(2, min(3, len(option_set["options"]))),
            "surface_options_early": session["interaction_state"].get(
                "option_preview_timing",
                "balanced",
            )
            != "deferred",
            "explanation_density": "standard",
        },
        "next_step_actions": next_step_actions,
    }


def get_workspace_payload(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    include_debug: bool = True,
) -> dict[str, Any] | None:
    fixture = _FIXTURES.get(trip_id)
    if fixture is not None:
        _db_record = db_session.scalar(
            select(PersistedTrip)
            .where(PersistedTrip.trip_id == trip_id)
            .where(PersistedTrip.user_id == user.user_id)
        )
        if _db_record is not None:
            fixture = None
    if fixture is not None:
        trip_record = _load_trip_record(fixture.trip_fixture)
        saved_scenarios, scenario_comparison = _load_saved_scenarios(fixture.scenarios_fixture)
        session = _load_session(fixture.session_fixture)
        _canonicalize_saved_scenario_ids(session, saved_scenarios)
        inventory_assembly_input = _build_inventory_assembly_input(
            trip_id=trip_id,
            trip_mode=trip_record.trip.mode,
            primary_regions=tuple(trip_record.trip.trip_frame.primary_regions),
            duration_days=trip_record.trip.trip_frame.duration_days,
        )
        inventory_bundles = assemble_inventory_bundles_for_trip(
            assembly_input=inventory_assembly_input,
        )
        scenario_search = _build_scenario_search(
            trip_id=trip_id,
            trip_mode=trip_record.trip.mode,
            bundles=inventory_bundles,
            trip_title=trip_record.trip.title,
            primary_regions=tuple(trip_record.trip.trip_frame.primary_regions),
            duration_days=trip_record.trip.trip_frame.duration_days,
            traveler_party_kind=trip_record.trip.trip_frame.traveler_party.kind,
        )
        feasibility_summary = build_feasibility_summary_payload(inventory_bundles)
        runtime_scenario_comparison = _build_runtime_scenario_comparison(
            trip_id=trip_id,
            trip_title=trip_record.trip.title,
            scenario_search=scenario_search.to_dict(),
            session=session.to_dict(),
        )
        ranking = build_scenario_ranking_payload(
            trip_id=trip_id,
            scenario_search=scenario_search.to_dict(),
        )
        inventory_summary = build_inventory_summary_payload(
            inventory_bundles,
            assembly_input=inventory_assembly_input,
        )

        fixture_payload: dict[str, Any] = {
            "trip_record": trip_record.to_dict(),
            "session": session.to_dict(),
            "saved_scenarios": [record.to_dict() for record in saved_scenarios],
            "scenario_comparison": (scenario_comparison.to_dict() if scenario_comparison else None),
            "scenario_search": scenario_search.to_dict(),
            "ranking": ranking,
            "route_comparison": runtime_scenario_comparison,
            "runtime_scenario_comparison": runtime_scenario_comparison,
            "activity_log": [],
            "planning_ledger": _planning_ledger_state([]),
            "planning_notebook": _planning_notebook_state([]),
            "planner_memory": {
                "current_checkpoint_id": session.current_checkpoint_id,
                "checkpoints": [],
                "artifacts": [],
            },
            "planner_panel_state": _build_planner_panel_state(
                trip=trip_record.to_dict()["trip"],
                scenario_search=scenario_search.to_dict(),
                session=session.to_dict(),
                saved_scenarios=[record.to_dict() for record in saved_scenarios],
                activity_log=[],
                feasibility_summary=feasibility_summary,
                policy_context=None,
                proposal_context=None,
            ),
            "runtime_state": _build_workspace_runtime_state(
                inventory_summary=inventory_summary,
                runtime_scenario_comparison=runtime_scenario_comparison,
            ),
            "feasibility_summary": feasibility_summary,
            "inventory_summary": inventory_summary,
            "budget_state": build_fixture_budget_payload(
                trip_id=trip_id,
                trip_mode=trip_record.trip.mode,
            ),
            "policy_state": None,
            "proposal_state": None,
        }
        fixture_payload["view_model"] = _build_workspace_view_model(
            fixture_payload,
            trip_mode=trip_record.trip.mode,
            include_debug=include_debug,
        )
        return fixture_payload

    record = db_session.scalar(
        select(PersistedTrip)
        .where(PersistedTrip.trip_id == trip_id)
        .where(PersistedTrip.user_id == user.user_id)
    )
    if record is None:
        return None
    session_record = _get_or_create_workspace_session_record(db_session, record=record)
    persisted_saved_scenarios = list(
        db_session.scalars(
            select(PersistedSavedScenario)
            .where(PersistedSavedScenario.trip_id == trip_id)
            .order_by(PersistedSavedScenario.updated_at.desc())
        ).all()
    )
    bootstrap_updated = False
    if not persisted_saved_scenarios:
        persisted_saved_scenarios = _create_bootstrap_saved_scenarios(
            db_session,
            record=record,
            session_record=session_record,
        )
        bootstrap_updated = True
    persisted_inventory_bundles, inventory_summary = _build_workspace_inventory_inputs(record)
    inventory_status = str((inventory_summary.get("runtime_state") or {}).get("status") or "empty")
    runtime_search = _build_runtime_scenario_search_for_trip(
        record=record,
        inventory_bundles=persisted_inventory_bundles,
        saved_scenarios=[
            {
                "saved_scenario_id": scenario.saved_scenario_id,
                "trip_id": scenario.trip_id,
                "current_version_id": scenario.current_version_id,
                "versions": list(scenario.versions),
                "comparisons": list(scenario.comparisons),
                "tags": list(scenario.tags),
                "notes": list(scenario.notes),
            }
            for scenario in persisted_saved_scenarios
        ],
        inventory_status=inventory_status,
    )
    if _sync_workspace_session_record(
        session_record,
        record=record,
        saved_scenarios=persisted_saved_scenarios,
        runtime_option_ids=[
            scenario["scenario_id"] for scenario in runtime_search.get("scenarios", [])
        ],
    ):
        bootstrap_updated = True
    if bootstrap_updated:
        db_session.commit()
        refreshed_session_record = db_session.get(
            PersistedPlanningSessionState,
            f"session:{trip_id}",
        )
        if refreshed_session_record is None:
            return None
        session_record = refreshed_session_record
        persisted_saved_scenarios = list(
            db_session.scalars(
                select(PersistedSavedScenario)
                .where(PersistedSavedScenario.trip_id == trip_id)
                .order_by(PersistedSavedScenario.updated_at.desc())
            ).all()
        )
    activity_records = db_session.scalars(
        select(PersistedActivityLogEvent)
        .where(PersistedActivityLogEvent.trip_id == trip_id)
        .order_by(PersistedActivityLogEvent.occurred_at.desc())
        .limit(WORKSPACE_ACTIVITY_LOG_LIMIT)
    ).all()
    ledger_records = db_session.scalars(
        select(PersistedPlanningLedgerEntry)
        .where(PersistedPlanningLedgerEntry.trip_id == trip_id)
        .order_by(PersistedPlanningLedgerEntry.updated_at.desc())
        .limit(PLANNING_LEDGER_LIMIT)
    ).all()
    notebook_records = db_session.scalars(
        select(PersistedPlanningNotebookItem)
        .where(PersistedPlanningNotebookItem.trip_id == trip_id)
        .order_by(PersistedPlanningNotebookItem.updated_at.desc())
        .limit(PLANNING_NOTEBOOK_LIMIT)
    ).all()
    feasibility_summary = build_feasibility_summary_payload(persisted_inventory_bundles)
    return _build_persisted_trip_workspace(
        record,
        session=(_serialize_session_record(session_record) if session_record is not None else None),
        saved_scenarios=[
            {
                "saved_scenario_id": scenario.saved_scenario_id,
                "trip_id": scenario.trip_id,
                "current_version_id": scenario.current_version_id,
                "versions": list(scenario.versions),
                "comparisons": list(scenario.comparisons),
                "tags": list(scenario.tags),
                "notes": list(scenario.notes),
            }
            for scenario in persisted_saved_scenarios
        ],
        activity_log=[_serialize_activity_record(item) for item in activity_records],
        planning_ledger=_planning_ledger_state(
            [_serialize_ledger_entry(item) for item in ledger_records]
        ),
        planning_notebook=_planning_notebook_state(
            [_serialize_notebook_item(item) for item in notebook_records],
            focus_category=session_record.notebook_focus_category,
            focus_item_id=session_record.notebook_focus_item_id,
        ),
        planner_memory=build_planner_memory_payload(
            db_session,
            trip_id=trip_id,
            session_state_id=session_record.session_state_id,
        ),
        budget_state=load_budget_payload_for_workspace(db_session, record=record),
        policy_context=(
            get_workspace_policy_payload(db_session, user=user, trip_id=trip_id)
            if record.mode == "business" or include_debug
            else None
        ),
        proposal_context=(
            get_workspace_proposal_payload(db_session, user=user, trip_id=trip_id)
            if record.mode == "business" or include_debug
            else None
        ),
        inventory_bundles=persisted_inventory_bundles,
        inventory_summary=inventory_summary,
        scenario_search=runtime_search,
        feasibility_summary=feasibility_summary,
        include_debug=include_debug,
    )


def get_workspace_scenario_comparison_payload(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
) -> dict[str, Any] | None:
    payload = _build_runtime_scenario_comparison_payload(
        db_session,
        user=user,
        trip_id=trip_id,
    )
    if payload is None:
        return None
    return dict(payload)


def _get_owned_trip_record(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
) -> PersistedTrip:
    record = db_session.scalar(
        select(PersistedTrip)
        .where(PersistedTrip.trip_id == trip_id)
        .where(PersistedTrip.user_id == user.user_id)
    )
    if record is None:
        raise WorkspaceTripNotFoundError(f"Trip '{trip_id}' was not found.")
    return record


def _get_or_create_workspace_session_record(
    db_session: Session,
    *,
    record: PersistedTrip,
) -> PersistedPlanningSessionState:
    session_state_id = f"session:{record.trip_id}"
    existing = db_session.get(PersistedPlanningSessionState, session_state_id)
    if existing is not None:
        return existing

    default_session = _default_workspace_session(record)
    persisted = PersistedPlanningSessionState(
        session_state_id=default_session.session_state_id,
        trip_id=default_session.trip_id,
        user_id=default_session.user_id,
        owner_profile_id=default_session.owner_profile_id,
        mode=default_session.mode,
        started_at=default_session.started_at,
        last_updated_at=default_session.updated_at,
        interaction_state=default_session.interaction_state.to_dict(),
        recent_option_presentations=[
            item.to_dict() for item in default_session.recent_option_presentations
        ],
        pending_decisions=[item.to_dict() for item in default_session.pending_decisions],
        status=default_session.status,
        selected_planning_mode=default_session.selected_planning_mode,
        current_checkpoint_id=default_session.current_checkpoint_id,
        current_saved_scenario_id=default_session.current_saved_scenario_id,
        active_budget_plan_id=default_session.active_budget_plan_id,
        activity_log_id=default_session.activity_log_id,
        schema_version=default_session.schema_version,
        tags=list(default_session.tags),
        notes=list(default_session.notes),
    )
    db_session.add(persisted)
    db_session.flush()
    return persisted


def update_workspace_planning_mode(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    planning_mode: str,
    include_debug: bool = True,
) -> dict[str, Any]:
    if planning_mode not in PLANNING_MODES:
        raise ValueError(f"planning_mode must be one of {', '.join(PLANNING_MODES)}")
    try:
        record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    except ValueError as error:
        raise WorkspaceTripNotFoundError(str(error)) from error

    session_record = _get_or_create_workspace_session_record(db_session, record=record)
    now = datetime.now(UTC)
    timestamp = _isoformat(now)
    session_record.selected_planning_mode = planning_mode
    session_record.last_updated_at = timestamp
    record.updated_at = now
    db_session.commit()

    payload = get_workspace_payload(
        db_session,
        user=user,
        trip_id=trip_id,
        include_debug=include_debug,
    )
    if payload is None:
        raise WorkspaceTripNotFoundError(f"Trip '{trip_id}' was not found.")
    return payload


def create_planning_ledger_entry(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    item_type: str,
    summary: str,
    status: str = "active",
    category: str = "general",
    detail: str = "",
    source_message_ids: list[str] | None = None,
    source_refs: list[str] | None = None,
    related_option_id: str | None = None,
    related_decision_id: str | None = None,
) -> dict[str, Any]:
    record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    session_record = _get_or_create_workspace_session_record(db_session, record=record)
    entry = _add_planning_ledger_entry(
        db_session,
        trip_id=trip_id,
        session_state_id=session_record.session_state_id,
        item_type=item_type,
        status=status,
        category=category,
        summary=summary,
        detail=detail,
        source_message_ids=source_message_ids,
        source_refs=source_refs,
        related_option_id=related_option_id,
        related_decision_id=related_decision_id,
        metadata={"created_by": "workspace_api"},
    )
    record.updated_at = datetime.now(UTC)
    db_session.commit()
    db_session.refresh(entry)
    return _serialize_ledger_entry(entry)


def update_planning_ledger_entry(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    ledger_entry_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    entry = db_session.scalar(
        select(PersistedPlanningLedgerEntry)
        .where(PersistedPlanningLedgerEntry.trip_id == trip_id)
        .where(PersistedPlanningLedgerEntry.ledger_entry_id == ledger_entry_id)
    )
    if entry is None:
        raise WorkspaceTripNotFoundError(f"Ledger entry '{ledger_entry_id}' was not found.")
    if updates.get("status") is not None:
        status = str(updates["status"])
        if status not in PLANNING_LEDGER_STATUSES:
            raise ValueError(f"status must be one of {', '.join(PLANNING_LEDGER_STATUSES)}")
        entry.status = status
    if "supersedes_entry_id" in updates:
        raw_supersedes_entry_id = updates["supersedes_entry_id"]
        supersedes_entry_id = (
            None
            if raw_supersedes_entry_id is None
            else str(raw_supersedes_entry_id).strip() or None
        )
        if supersedes_entry_id is not None:
            _validate_planning_ledger_supersedes_target(
                db_session,
                trip_id=trip_id,
                ledger_entry_id=ledger_entry_id,
                supersedes_entry_id=supersedes_entry_id,
            )
        entry.supersedes_entry_id = supersedes_entry_id
    for field in (
        "category",
        "summary",
        "detail",
        "related_option_id",
        "related_decision_id",
    ):
        if updates.get(field) is not None:
            setattr(entry, field, updates[field])
    if updates.get("source_message_ids") is not None:
        entry.source_message_ids = list(updates["source_message_ids"])
    if updates.get("source_refs") is not None:
        entry.source_refs = list(updates["source_refs"])
    entry.updated_at = datetime.now(UTC)
    db_session.commit()
    db_session.refresh(entry)
    return _serialize_ledger_entry(entry)


def _validate_notebook_choice(field: str, value: str, allowed: tuple[str, ...]) -> str:
    if value not in allowed:
        raise ValueError(f"{field} must be one of {', '.join(allowed)}")
    return value


def create_planning_notebook_item(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    title: str,
    note: str = "",
    category: str = "other",
    status: str = "active",
    priority: str = "normal",
    source: str = "user",
    linked_ledger_entry_id: str | None = None,
    source_message_ids: list[str] | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    _validate_notebook_choice("category", category, PLANNING_NOTEBOOK_CATEGORIES)
    _validate_notebook_choice("status", status, PLANNING_NOTEBOOK_STATUSES)
    _validate_notebook_choice("priority", priority, PLANNING_NOTEBOOK_PRIORITIES)
    _validate_notebook_choice("source", source, PLANNING_NOTEBOOK_SOURCES)
    record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    session_record = _get_or_create_workspace_session_record(db_session, record=record)
    now = datetime.now(UTC)
    item = PersistedPlanningNotebookItem(
        notebook_item_id=f"notebook:{secrets.token_hex(16)}",
        trip_id=trip_id,
        session_state_id=session_record.session_state_id,
        title=title[:240],
        note=note,
        category=category,
        status=status,
        priority=priority,
        source=source,
        linked_ledger_entry_id=linked_ledger_entry_id,
        source_message_ids=list(source_message_ids or []),
        tags=list(tags or []),
        metadata_payload={"created_by": "workspace_api"},
        completed_at=now if status == "completed" else None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(item)
    record.updated_at = now
    db_session.commit()
    db_session.refresh(item)
    return _serialize_notebook_item(item)


def update_planning_notebook_item(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    notebook_item_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    item = db_session.scalar(
        select(PersistedPlanningNotebookItem)
        .where(PersistedPlanningNotebookItem.trip_id == trip_id)
        .where(PersistedPlanningNotebookItem.notebook_item_id == notebook_item_id)
    )
    if item is None:
        raise WorkspaceTripNotFoundError(f"Notebook item '{notebook_item_id}' was not found.")
    if updates.get("category") is not None:
        item.category = _validate_notebook_choice(
            "category", str(updates["category"]), PLANNING_NOTEBOOK_CATEGORIES
        )
    if updates.get("priority") is not None:
        item.priority = _validate_notebook_choice(
            "priority", str(updates["priority"]), PLANNING_NOTEBOOK_PRIORITIES
        )
    if updates.get("status") is not None:
        new_status = _validate_notebook_choice(
            "status", str(updates["status"]), PLANNING_NOTEBOOK_STATUSES
        )
        now = datetime.now(UTC)
        if new_status == "completed" and item.status != "completed":
            item.completed_at = now
        elif new_status != "completed":
            item.completed_at = None
        item.status = new_status
    for field in ("title", "note", "linked_ledger_entry_id"):
        if updates.get(field) is not None:
            setattr(item, field, updates[field])
    if updates.get("source_message_ids") is not None:
        item.source_message_ids = list(updates["source_message_ids"])
    if updates.get("tags") is not None:
        item.tags = list(updates["tags"])
    now = datetime.now(UTC)
    item.updated_at = now
    record.updated_at = now
    db_session.commit()
    db_session.refresh(item)
    return _serialize_notebook_item(item)


def delete_planning_notebook_item(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    notebook_item_id: str,
) -> None:
    record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    item = db_session.scalar(
        select(PersistedPlanningNotebookItem)
        .where(PersistedPlanningNotebookItem.trip_id == trip_id)
        .where(PersistedPlanningNotebookItem.notebook_item_id == notebook_item_id)
    )
    if item is None:
        raise WorkspaceTripNotFoundError(f"Notebook item '{notebook_item_id}' was not found.")
    session_record = _get_or_create_workspace_session_record(db_session, record=record)
    if session_record.notebook_focus_item_id == notebook_item_id:
        session_record.notebook_focus_item_id = None
    db_session.delete(item)
    record.updated_at = datetime.now(UTC)
    db_session.commit()


def set_planning_notebook_focus(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    category: str | None,
    notebook_item_id: str | None,
) -> dict[str, Any]:
    if category is not None:
        _validate_notebook_choice("category", category, PLANNING_NOTEBOOK_CATEGORIES)
    record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    session_record = _get_or_create_workspace_session_record(db_session, record=record)
    if notebook_item_id is not None:
        item = db_session.scalar(
            select(PersistedPlanningNotebookItem)
            .where(PersistedPlanningNotebookItem.trip_id == trip_id)
            .where(PersistedPlanningNotebookItem.notebook_item_id == notebook_item_id)
        )
        if item is None:
            raise WorkspaceTripNotFoundError(f"Notebook item '{notebook_item_id}' was not found.")
        if category is None:
            category = item.category
        elif category != item.category:
            raise ValueError(
                f"category '{category}' does not match notebook item category '{item.category}'."
            )
    session_record.notebook_focus_category = category
    session_record.notebook_focus_item_id = notebook_item_id
    record.updated_at = datetime.now(UTC)
    db_session.commit()
    return {"category": category, "notebook_item_id": notebook_item_id}


def _current_workspace_option_set(
    session: PlanningSessionState,
    *,
    trip_id: str,
) -> tuple[str, list[str]]:
    presentation = (
        session.recent_option_presentations[0]
        if session.recent_option_presentations
        else _default_workspace_presentation(trip_id, session.updated_at)
    )
    option_set_id = presentation.option_set_id or f"option-set:{trip_id}:workspace-bootstrap"
    option_ids = [option_id for option_id in presentation.surfaced_option_ids if option_id]
    return option_set_id, option_ids


def _append_activity_event(
    db_session: Session,
    *,
    activity_event_id: str,
    trip_id: str,
    session_state_id: str,
    occurred_at: str,
    event_kind: str,
    summary: str,
    actor: str = "traveler",
    related_decision_id: str | None = None,
    related_option_set_id: str | None = None,
    metadata: dict[str, str] | None = None,
) -> None:
    db_session.add(
        PersistedActivityLogEvent(
            activity_event_id=activity_event_id,
            trip_id=trip_id,
            session_state_id=session_state_id,
            occurred_at=occurred_at,
            event_kind=event_kind,
            summary=summary,
            actor=actor,
            related_decision_id=related_decision_id,
            related_option_set_id=related_option_set_id,
            metadata_payload=metadata or {},
            tags=["workspace", "planner-action"],
            notes=[],
        )
    )


def _record_planner_action(
    db_session: Session,
    *,
    trip_id: str,
    session_state_id: str,
    activity_event_id: str,
    occurred_at: str,
    action_type: str,
    decision_id: str | None = None,
    option_set_id: str | None = None,
    option_id: str | None = None,
    choice: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    db_session.add(
        PersistedPlannerAction(
            planner_action_id=f"planner-action:{trip_id}:{secrets.token_hex(4)}",
            trip_id=trip_id,
            session_state_id=session_state_id,
            activity_event_id=activity_event_id,
            occurred_at=occurred_at,
            action_type=action_type,
            decision_id=decision_id,
            option_set_id=option_set_id,
            option_id=option_id,
            choice=choice,
            payload=payload or {},
        )
    )


def answer_workspace_planner_decision(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    decision_id: str,
    choice: str,
    include_debug: bool = True,
) -> dict[str, Any]:
    record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    session_record = _get_or_create_workspace_session_record(db_session, record=record)
    session = PlanningSessionState.from_dict(_serialize_session_record(session_record))
    matching = next(
        (decision for decision in session.pending_decisions if decision.decision_id == decision_id),
        None,
    )
    if matching is None:
        raise ValueError(f"Decision '{decision_id}' was not found in the workspace session.")
    if choice not in matching.choices:
        raise ValueError(f"Choice '{choice}' is not valid for decision '{decision_id}'.")

    session.pending_decisions = [
        decision for decision in session.pending_decisions if decision.decision_id != decision_id
    ]
    session.updated_at = _isoformat(datetime.now(UTC))
    session.notes.append(f"decision:{decision_id}:{choice}")
    session_record.pending_decisions = [item.to_dict() for item in session.pending_decisions]
    session_record.notes = list(session.notes)
    session_record.last_updated_at = session.updated_at
    record.updated_at = datetime.now(UTC)
    activity_event_id = f"activity:{trip_id}:{secrets.token_hex(4)}"
    occurred_at = _isoformat(datetime.now(UTC))
    _append_activity_event(
        db_session,
        activity_event_id=activity_event_id,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        occurred_at=occurred_at,
        event_kind="decision_recorded",
        summary=f"Traveler answered '{matching.title}' with '{choice}'.",
        related_decision_id=decision_id,
        related_option_set_id=matching.related_option_set_id,
        metadata={"choice": choice},
    )
    _record_planner_action(
        db_session,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        activity_event_id=activity_event_id,
        occurred_at=occurred_at,
        action_type="decision_answer",
        decision_id=decision_id,
        option_set_id=matching.related_option_set_id,
        choice=choice,
        payload={"decision_title": matching.title},
    )
    _add_planning_ledger_entry(
        db_session,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        item_type="decision",
        status="completed",
        category="decisions",
        summary=f"{matching.title}: {choice}",
        detail=matching.prompt,
        source_refs=[activity_event_id],
        related_decision_id=decision_id,
        metadata={"choice": choice},
    )
    db_session.commit()
    return (
        get_workspace_payload(
            db_session,
            user=user,
            trip_id=trip_id,
            include_debug=include_debug,
        )
        or {}
    )


def submit_workspace_option_feedback(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    option_id: str,
    action_type: str,
    decision_id: str | None = None,
    include_debug: bool = True,
) -> dict[str, Any]:
    record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    session_record = _get_or_create_workspace_session_record(db_session, record=record)
    session = PlanningSessionState.from_dict(_serialize_session_record(session_record))
    option_set_id, valid_option_ids = _current_workspace_option_set(session, trip_id=trip_id)
    if option_id not in valid_option_ids:
        raise ValueError(
            f"Option '{option_id}' is not available in the current workspace option set."
        )
    presentation = (
        session.recent_option_presentations[0]
        if session.recent_option_presentations
        else _default_workspace_presentation(trip_id, session.updated_at)
    )
    presentation.surfaced_option_ids = valid_option_ids
    presentation.option_set_id = option_set_id
    if presentation.highlighted_option_id not in valid_option_ids:
        presentation.highlighted_option_id = valid_option_ids[0]
    if presentation.selected_option_id not in valid_option_ids:
        presentation.selected_option_id = None
    presentation.rejected_option_ids = [
        item for item in presentation.rejected_option_ids if item in valid_option_ids
    ]

    if action_type == "accept":
        presentation.selected_option_id = option_id
        presentation.rejected_option_ids = [
            item for item in presentation.rejected_option_ids if item != option_id
        ]
        event_kind = "decision_recorded"
        summary = f"Traveler accepted option '{option_id}' from the workspace planner panel."
    elif action_type == "reject":
        if option_id not in presentation.rejected_option_ids:
            presentation.rejected_option_ids.append(option_id)
        if presentation.selected_option_id == option_id:
            presentation.selected_option_id = None
        event_kind = "option_rejected"
        summary = f"Traveler rejected option '{option_id}' from the workspace planner panel."
    elif action_type == "save_as_fallback":
        presentation.notes = [
            note for note in presentation.notes if not note.startswith("fallback:")
        ]
        presentation.notes.append(f"fallback:{option_id}")
        event_kind = "decision_recorded"
        summary = (
            f"Traveler saved option '{option_id}' as a fallback in the workspace planner panel."
        )
    else:
        session.interaction_state.auto_advance_research_passes += 1
        event_kind = "rerank_requested"
        summary = f"Traveler requested '{action_type}' for option '{option_id}' in the workspace planner panel."

    presentation.summary = summary
    session.recent_option_presentations = [presentation]
    session.updated_at = _isoformat(datetime.now(UTC))
    session.notes.append(f"feedback:{action_type}:{option_id}")
    if action_type in {"revise", "do_more_before_asking_again"} and not session.pending_decisions:
        session.pending_decisions = [
            PendingDecision(
                decision_id=f"decision:{trip_id}:follow-up",
                title="Confirm the next planner pass",
                prompt="Should the planner keep iterating before another checkpoint?",
                created_at=session.updated_at,
                choices=[
                    "Keep the current direction.",
                    "Compare another planner-backed option first.",
                ],
                related_option_set_id=option_set_id,
                notes=["Generated after workspace option feedback."],
            )
        ]

    session_record.recent_option_presentations = [
        item.to_dict() for item in session.recent_option_presentations
    ]
    session_record.pending_decisions = [item.to_dict() for item in session.pending_decisions]
    session_record.interaction_state = session.interaction_state.to_dict()
    session_record.notes = list(session.notes)
    session_record.last_updated_at = session.updated_at
    record.updated_at = datetime.now(UTC)
    activity_event_id = f"activity:{trip_id}:{secrets.token_hex(4)}"
    occurred_at = _isoformat(datetime.now(UTC))
    _append_activity_event(
        db_session,
        activity_event_id=activity_event_id,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        occurred_at=occurred_at,
        event_kind=event_kind,
        summary=summary,
        related_decision_id=decision_id,
        related_option_set_id=option_set_id,
        metadata={"action_type": action_type, "option_id": option_id},
    )
    _record_planner_action(
        db_session,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        activity_event_id=activity_event_id,
        occurred_at=occurred_at,
        action_type=action_type,
        decision_id=decision_id,
        option_set_id=option_set_id,
        option_id=option_id,
        payload={"summary": summary},
    )
    ledger_type = "option_rejected" if action_type == "reject" else "option_considered"
    ledger_status = (
        "rejected"
        if action_type == "reject"
        else (
            "completed"
            if action_type == "accept"
            else "deferred" if action_type == "save_as_fallback" else "active"
        )
    )
    _add_planning_ledger_entry(
        db_session,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        item_type=ledger_type,
        status=ledger_status,
        summary=summary,
        detail=f"Planner panel feedback action: {action_type}",
        source_refs=[activity_event_id],
        related_option_id=option_id,
        related_decision_id=decision_id,
        metadata={"action_type": action_type, "option_set_id": option_set_id},
    )
    db_session.commit()
    return (
        get_workspace_payload(
            db_session,
            user=user,
            trip_id=trip_id,
            include_debug=include_debug,
        )
        or {}
    )


def _without_route_option_notes(notes: list[str], option_id: str) -> list[str]:
    managed_prefixes = ("fallback:", "needs_research:")
    managed_tokens = {f"{prefix}{option_id}" for prefix in managed_prefixes}
    return [note for note in notes if note not in managed_tokens]


def submit_workspace_route_option_action(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    option_id: str,
    action_type: str,
    include_debug: bool = True,
) -> dict[str, Any]:
    if action_type not in ROUTE_OPTION_ACTIONS:
        raise ValueError(f"action_type must be one of {', '.join(ROUTE_OPTION_ACTIONS)}")

    record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    session_record = _get_or_create_workspace_session_record(db_session, record=record)
    session = PlanningSessionState.from_dict(_serialize_session_record(session_record))
    option_set_id, valid_option_ids = _current_workspace_option_set(session, trip_id=trip_id)
    if option_id not in valid_option_ids:
        raise ValueError(
            f"Route option '{option_id}' is not available in the current workspace comparison."
        )

    presentation = (
        session.recent_option_presentations[0]
        if session.recent_option_presentations
        else _default_workspace_presentation(trip_id, session.updated_at)
    )
    presentation.surfaced_option_ids = valid_option_ids
    presentation.option_set_id = option_set_id
    if presentation.highlighted_option_id not in valid_option_ids:
        presentation.highlighted_option_id = valid_option_ids[0]
    if presentation.selected_option_id not in valid_option_ids:
        presentation.selected_option_id = None
    presentation.rejected_option_ids = [
        item for item in presentation.rejected_option_ids if item in valid_option_ids
    ]
    presentation.notes = _without_route_option_notes(list(presentation.notes), option_id)

    if action_type == "make_baseline":
        presentation.selected_option_id = option_id
        presentation.rejected_option_ids = [
            item for item in presentation.rejected_option_ids if item != option_id
        ]
        event_kind = "decision_recorded"
        summary = f"Traveler made route option '{option_id}' the comparison baseline."
    elif action_type == "keep":
        presentation.rejected_option_ids = [
            item for item in presentation.rejected_option_ids if item != option_id
        ]
        if presentation.selected_option_id == option_id:
            presentation.selected_option_id = None
        presentation.notes.append(f"fallback:{option_id}")
        event_kind = "decision_recorded"
        summary = f"Traveler kept route option '{option_id}' for later comparison."
    elif action_type == "reject":
        if option_id not in presentation.rejected_option_ids:
            presentation.rejected_option_ids.append(option_id)
        if presentation.selected_option_id == option_id:
            presentation.selected_option_id = None
        event_kind = "option_rejected"
        summary = f"Traveler rejected route option '{option_id}'."
    elif action_type == "reopen":
        presentation.rejected_option_ids = [
            item for item in presentation.rejected_option_ids if item != option_id
        ]
        event_kind = "decision_recorded"
        summary = f"Traveler reopened route option '{option_id}' for comparison."
    else:
        presentation.rejected_option_ids = [
            item for item in presentation.rejected_option_ids if item != option_id
        ]
        presentation.notes.append(f"needs_research:{option_id}")
        session.interaction_state.auto_advance_research_passes += 1
        event_kind = "rerank_requested"
        summary = f"Traveler asked the planner to revise route option '{option_id}'."

    presentation.summary = summary
    session.recent_option_presentations = [presentation]
    session.updated_at = _isoformat(datetime.now(UTC))
    session.notes.append(f"route-option:{action_type}:{option_id}")
    if action_type == "revise" and not session.pending_decisions:
        session.pending_decisions = [
            PendingDecision(
                decision_id=f"decision:{trip_id}:route-option-revision",
                title="Confirm route revision focus",
                prompt="Should the planner revise this route before comparing options again?",
                created_at=session.updated_at,
                choices=[
                    "Revise this route option.",
                    "Keep comparing the current options.",
                ],
                related_option_set_id=option_set_id,
                notes=["Generated after a route-option revision request."],
            )
        ]

    session_record.recent_option_presentations = [
        item.to_dict() for item in session.recent_option_presentations
    ]
    session_record.pending_decisions = [item.to_dict() for item in session.pending_decisions]
    session_record.interaction_state = session.interaction_state.to_dict()
    session_record.notes = list(session.notes)
    session_record.last_updated_at = session.updated_at
    record.updated_at = datetime.now(UTC)
    activity_event_id = f"activity:{trip_id}:{secrets.token_hex(4)}"
    occurred_at = _isoformat(datetime.now(UTC))
    _append_activity_event(
        db_session,
        activity_event_id=activity_event_id,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        occurred_at=occurred_at,
        event_kind=event_kind,
        summary=summary,
        related_option_set_id=option_set_id,
        metadata={"action_type": action_type, "option_id": option_id},
    )
    _record_planner_action(
        db_session,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        activity_event_id=activity_event_id,
        occurred_at=occurred_at,
        action_type=f"route_option_{action_type}",
        option_set_id=option_set_id,
        option_id=option_id,
        payload={
            "summary": summary,
            "route_option_action": action_type,
        },
    )
    ledger_type = "option_rejected" if action_type == "reject" else "option_considered"
    ledger_status = (
        "rejected"
        if action_type == "reject"
        else (
            "completed"
            if action_type == "make_baseline"
            else "deferred" if action_type == "keep" else "active"
        )
    )
    _add_planning_ledger_entry(
        db_session,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        item_type=ledger_type,
        status=ledger_status,
        summary=summary,
        detail=f"Route option action: {action_type}",
        source_refs=[activity_event_id],
        related_option_id=option_id,
        metadata={"action_type": action_type, "option_set_id": option_set_id},
    )
    db_session.commit()
    return (
        get_workspace_payload(
            db_session,
            user=user,
            trip_id=trip_id,
            include_debug=include_debug,
        )
        or {}
    )
