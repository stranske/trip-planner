from __future__ import annotations

import hashlib
import json
import secrets
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
        return _build_scenario_search(
            trip_id=record.trip_id,
            trip_mode=record.mode,
            bundles=inventory_bundles,
            trip_title=record.title,
            primary_regions=tuple(record.primary_regions),
            duration_days=record.duration_days,
            traveler_party_kind=record.traveler_party_kind,
        ).to_dict()

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


def _build_runtime_scenario_comparison(
    *,
    trip_id: str,
    trip_title: str,
    scenario_search: dict[str, Any],
) -> dict[str, Any]:
    scenarios = list(scenario_search.get("scenarios", []))
    comparison_axes = [
        {"key": "score", "label": "Planner score", "direction": "higher_better"},
        {"key": "travel_minutes", "label": "Travel minutes", "direction": "lower_better"},
        {"key": "transfers", "label": "Transfers", "direction": "lower_better"},
        {"key": "estimated_total", "label": "Estimated total", "direction": "lower_better"},
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

    lead = scenarios[0]
    rows = []
    for scenario in scenarios:
        summary = scenario["scenario_summary"]
        estimated_total = summary.get("estimated_total")
        rows.append(
            {
                "scenario_id": scenario["scenario_id"],
                "title": scenario["title"],
                "rank": scenario["rank"],
                "status": _comparison_status_label(scenario),
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
        trip_id=record.trip_id,
        trip_mode=record.mode,
        primary_regions=record.primary_regions,
        duration_days=record.duration_days,
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


def _ordered_saved_scenarios(saved_scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _build_persisted_trip_workspace(
    record: PersistedTrip,
    *,
    session: dict[str, Any] | None = None,
    saved_scenarios: list[dict[str, Any]] | None = None,
    activity_log: list[dict[str, Any]] | None = None,
    planner_memory: dict[str, Any] | None = None,
    budget_state: dict[str, Any] | None = None,
    policy_context: dict[str, Any] | None = None,
    proposal_context: dict[str, Any] | None = None,
    inventory_bundles: list[InventoryBundle] | None = None,
    inventory_summary: dict[str, Any] | None = None,
    scenario_search: dict[str, Any] | None = None,
    feasibility_summary: dict[str, Any] | None = None,
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
        trip_id=record.trip_id,
        trip_mode=record.mode,
        primary_regions=record.primary_regions,
        duration_days=record.duration_days,
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
    )
    runtime_state = _build_workspace_runtime_state(
        inventory_summary=resolved_inventory_summary,
        runtime_scenario_comparison=runtime_scenario_comparison,
    )

    return {
        "trip_record": trip_record,
        "session": resolved_session,
        "saved_scenarios": ordered_saved_scenarios,
        "scenario_comparison": (
            ordered_saved_scenarios[0]["comparisons"][0]
            if ordered_saved_scenarios and ordered_saved_scenarios[0].get("comparisons")
            else None
        ),
        "scenario_search": resolved_scenario_search,
        "runtime_scenario_comparison": runtime_scenario_comparison,
        "activity_log": resolved_activity_log,
        "planner_memory": planner_memory
        or {
            "current_checkpoint_id": resolved_session.get("current_checkpoint_id"),
            "checkpoints": [],
            "artifacts": [],
        },
        "planner_panel_state": _build_planner_panel_state(
            trip=trip_record["trip"],
            scenario_search=resolved_scenario_search,
            session=resolved_session,
            saved_scenarios=ordered_saved_scenarios,
            activity_log=resolved_activity_log,
            feasibility_summary=resolved_feasibility_summary,
            policy_context=policy_context,
            proposal_context=proposal_context,
        ),
        "runtime_state": runtime_state,
        "feasibility_summary": resolved_feasibility_summary,
        "inventory_summary": resolved_inventory_summary,
        "budget_state": resolved_budget_state,
        "policy_state": (policy_context or {}).get("policy_state"),
        "proposal_state": (proposal_context or {}).get("proposal_state"),
    }


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
        trip_record = _load_trip_record(fixture.trip_fixture)
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
        )

    try:
        record = _get_owned_trip_record(db_session, user=user, trip_id=trip_id)
    except WorkspaceTripNotFoundError:
        return None

    persisted_saved_scenarios_records = list(
        db_session.scalars(
            select(PersistedSavedScenario)
            .where(PersistedSavedScenario.trip_id == trip_id)
            .order_by(PersistedSavedScenario.updated_at.desc())
        ).all()
    )
    if not persisted_saved_scenarios_records:
        session_record = _get_or_create_workspace_session_record(db_session, record=record)
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
            session_record.pending_decisions = [decision, *session_record.pending_decisions[1:]]
            updated = True

    if updated:
        session_record.last_updated_at = _isoformat(datetime.now(UTC))
        notes = list(session_record.notes)
        if "workspace-bootstrap:scenario-scaffold" not in notes:
            notes.append("workspace-bootstrap:scenario-scaffold")
        session_record.notes = notes
    return updated


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
                {"key": "score", "label": "Planner score", "direction": "higher_better"},
                {"key": "travel_minutes", "label": "Travel minutes", "direction": "lower_better"},
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
                {"key": "scope", "label": "Planning scope", "direction": "higher_better"},
                {"key": "specificity", "label": "Trip specificity", "direction": "higher_better"},
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
                "title": "Policy posture loaded",
                "body": "The workspace is using persisted policy inputs instead of mock approval-readiness state.",
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
                "label": "Review policy posture",
                "description": "Inspect imported policy constraints and approval-readiness before moving to submission work.",
                "emphasis": "primary",
                "target_section": "approval",
            },
        )
    if proposal_state is not None:
        summary = dict(proposal_state.get("summary") or {})
        follow_up = dict(proposal_state.get("follow_up") or {})
        outputs.append(
            {
                "output_id": f"output:{trip['trip_id']}:proposal-lifecycle",
                "title": "Proposal lifecycle loaded",
                "body": "The workspace now carries persisted proposal submission and evaluation state.",
                "tags": ["proposal", "approval", trip["mode"]],
                "status": (
                    "positive"
                    if summary.get("approval_ready")
                    else ("caution" if summary.get("evaluation_transport_status") else "neutral")
                ),
                "highlights": list(summary.get("highlights") or [])[:3],
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
) -> dict[str, Any] | None:
    fixture = _FIXTURES.get(trip_id)
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
        )
        inventory_summary = build_inventory_summary_payload(
            inventory_bundles,
            assembly_input=inventory_assembly_input,
        )

        return {
            "trip_record": trip_record.to_dict(),
            "session": session.to_dict(),
            "saved_scenarios": [record.to_dict() for record in saved_scenarios],
            "scenario_comparison": scenario_comparison.to_dict() if scenario_comparison else None,
            "scenario_search": scenario_search.to_dict(),
            "runtime_scenario_comparison": runtime_scenario_comparison,
            "activity_log": [],
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
        planner_memory=build_planner_memory_payload(
            db_session,
            trip_id=trip_id,
            session_state_id=session_record.session_state_id,
        ),
        budget_state=load_budget_payload_for_workspace(db_session, record=record),
        policy_context=(
            get_workspace_policy_payload(db_session, user=user, trip_id=trip_id)
            if record.mode == "business"
            else None
        ),
        proposal_context=(
            get_workspace_proposal_payload(db_session, user=user, trip_id=trip_id)
            if record.mode == "business"
            else None
        ),
        inventory_bundles=persisted_inventory_bundles,
        inventory_summary=inventory_summary,
        scenario_search=runtime_search,
        feasibility_summary=feasibility_summary,
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
    db_session.commit()
    return get_workspace_payload(db_session, user=user, trip_id=trip_id) or {}


def submit_workspace_option_feedback(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
    option_id: str,
    action_type: str,
    decision_id: str | None = None,
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
    db_session.commit()
    return get_workspace_payload(db_session, user=user, trip_id=trip_id) or {}
