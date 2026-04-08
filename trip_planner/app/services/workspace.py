from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.app.services.inventory import (
    assemble_inventory_bundles_for_trip,
    build_inventory_summary_payload,
)
from trip_planner.contracts.trip import Trip
from trip_planner.contracts import MoneyRange
from trip_planner.itinerary import (
    ItineraryScenario,
    ScenarioSearchResult,
    ScenarioSummary,
    ScenarioTradeoff,
)
from trip_planner.persistence.models.scenario import (
    PersistedActivityLogEvent,
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


def _build_scenario_search(trip_id: str, variant: str) -> ScenarioSearchResult:
    if variant == "leisure":
        return _leisure_search_result(trip_id)
    if variant == "business":
        return _business_search_result(trip_id)
    raise KeyError(f"Unsupported scenario search variant: {variant}")


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
) -> dict[str, Any]:
    resolved_session = session or _default_workspace_session(record).to_dict()
    trip_record = _serialize_persisted_trip_record(record)
    resolved_saved_scenarios = saved_scenarios or []
    resolved_activity_log = activity_log or []
    scenario_search = {
        "title": "Trip setup workspace",
        "scenarios": [],
        "explanation": [
            "This workspace was opened from a newly created persisted trip.",
            "Scenario search and comparisons will appear after planning begins.",
        ],
        "source_refs": [],
    }

    inventory_bundles = assemble_inventory_bundles_for_trip(
        trip_id=record.trip_id,
        trip_mode=record.mode,
    )

    return {
        "trip_record": trip_record,
        "session": resolved_session,
        "saved_scenarios": resolved_saved_scenarios,
        "scenario_comparison": None,
        "scenario_search": scenario_search,
        "activity_log": resolved_activity_log,
        "planner_panel_state": _build_planner_panel_state(
            trip=trip_record["trip"],
            scenario_search=scenario_search,
            session=resolved_session,
            activity_log=resolved_activity_log,
        ),
        "inventory_summary": build_inventory_summary_payload(inventory_bundles),
    }


def _build_planner_panel_state(
    *,
    trip: dict[str, Any],
    scenario_search: dict[str, Any],
    session: dict[str, Any],
    activity_log: list[dict[str, Any]],
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
                    "drawbacks": ["You may need another pass if the trip should span more regions."],
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
                if isinstance(decision.get("choices"), list) and decision["choices"]
                else [
                    "Keep the current direction.",
                    "Compare another planner-backed option first.",
                ]
            ),
        }
        for decision in session.get("pending_decisions", [])
    ]

    outputs = _workspace_activity_outputs(trip["trip_id"], activity_log) + outputs

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

    return {
        "trip": trip,
        "option_set": option_set,
        "proposal": None,
        "policy_evaluation": None,
        "pending_decisions": mapped_decisions,
        "outputs": outputs,
        "planner_behavior": {
            "trip_stage": "compare" if scenarios else "bootstrap",
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
        scenario_search = _build_scenario_search(trip_id, fixture.scenario_search_variant)
        inventory_bundles = assemble_inventory_bundles_for_trip(
            trip_id=trip_id,
            trip_mode=trip_record.trip.mode,
        )

        return {
            "trip_record": trip_record.to_dict(),
            "session": session.to_dict(),
            "saved_scenarios": [record.to_dict() for record in saved_scenarios],
            "scenario_comparison": scenario_comparison.to_dict() if scenario_comparison else None,
            "scenario_search": scenario_search.to_dict(),
            "activity_log": [],
            "planner_panel_state": _build_planner_panel_state(
                trip=trip_record.to_dict()["trip"],
                scenario_search=scenario_search.to_dict(),
                session=session.to_dict(),
                activity_log=[],
            ),
            "inventory_summary": build_inventory_summary_payload(inventory_bundles),
        }

    record = db_session.scalar(
        select(PersistedTrip)
        .where(PersistedTrip.trip_id == trip_id)
        .where(PersistedTrip.user_id == user.user_id)
    )
    if record is None:
        return None
    session_record = db_session.get(PersistedPlanningSessionState, f"session:{trip_id}")
    persisted_saved_scenarios = db_session.scalars(
        select(PersistedSavedScenario)
        .where(PersistedSavedScenario.trip_id == trip_id)
        .order_by(PersistedSavedScenario.updated_at.desc())
    ).all()
    activity_records = db_session.scalars(
        select(PersistedActivityLogEvent)
        .where(PersistedActivityLogEvent.trip_id == trip_id)
        .order_by(PersistedActivityLogEvent.occurred_at.desc())
        .limit(WORKSPACE_ACTIVITY_LOG_LIMIT)
    ).all()
    return _build_persisted_trip_workspace(
        record,
        session=(
            _serialize_session_record(session_record)
            if session_record is not None
            else None
        ),
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
    )


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


def _append_activity_event(
    db_session: Session,
    *,
    trip_id: str,
    session_state_id: str,
    event_kind: str,
    summary: str,
    related_decision_id: str | None = None,
    related_option_set_id: str | None = None,
    metadata: dict[str, str] | None = None,
) -> None:
    db_session.add(
        PersistedActivityLogEvent(
            activity_event_id=f"activity:{trip_id}:{secrets.token_hex(4)}",
            trip_id=trip_id,
            session_state_id=session_state_id,
            occurred_at=_isoformat(datetime.now(UTC)),
            event_kind=event_kind,
            summary=summary,
            actor="traveler",
            related_decision_id=related_decision_id,
            related_option_set_id=related_option_set_id,
            metadata_payload=metadata or {},
            tags=["workspace", "planner-action"],
            notes=[],
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
    _append_activity_event(
        db_session,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        event_kind="decision_recorded",
        summary=f"Traveler answered '{matching.title}' with '{choice}'.",
        related_decision_id=decision_id,
        related_option_set_id=matching.related_option_set_id,
        metadata={"choice": choice},
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
    option_set_id = (
        session.recent_option_presentations[0].option_set_id
        if session.recent_option_presentations
        else f"option-set:{trip_id}:workspace-bootstrap"
    )
    presentation = (
        session.recent_option_presentations[0]
        if session.recent_option_presentations
        else _default_workspace_presentation(trip_id, session.updated_at)
    )
    presentation.surfaced_option_ids = list(dict.fromkeys(presentation.surfaced_option_ids + [option_id]))
    presentation.option_set_id = option_set_id

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
        presentation.notes = [note for note in presentation.notes if not note.startswith("fallback:")]
        presentation.notes.append(f"fallback:{option_id}")
        event_kind = "decision_recorded"
        summary = f"Traveler saved option '{option_id}' as a fallback in the workspace planner panel."
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
    _append_activity_event(
        db_session,
        trip_id=trip_id,
        session_state_id=session.session_state_id,
        event_kind=event_kind,
        summary=summary,
        related_decision_id=decision_id,
        related_option_set_id=option_set_id,
        metadata={"action_type": action_type, "option_id": option_id},
    )
    db_session.commit()
    return get_workspace_payload(db_session, user=user, trip_id=trip_id) or {}
