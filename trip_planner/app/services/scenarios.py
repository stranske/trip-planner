from __future__ import annotations

from copy import deepcopy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from trip_planner.business import (
    BusinessTravelProfile,
    PolicyConstraintSet,
    derive_business_planning_objectives,
)
from trip_planner.itinerary import (
    assemble_itinerary_scenarios,
    derive_itinerary_objectives,
    evaluate_bundle_feasibility,
)
from trip_planner.options import InventoryBundle
from trip_planner.preferences import resolve_leisure_profile
from trip_planner.ranking import (
    BusinessRankingEngine,
    LeisureRankingEngine,
    RankedResult,
    RankedResultSet,
)
from tests.preferences.fixture_corpus import load_fixture_map


@dataclass(frozen=True, slots=True)
class ScenarioFixtureSeed:
    trip_mode: str
    title: str
    leisure_fixture_id: str | None = None
    business_profile_fixture: str | None = None
    business_constraint_fixture: str | None = None


_SCENARIO_FIXTURE_SEEDS: dict[str, ScenarioFixtureSeed] = {
    "trip-leisure-kyoto-draft": ScenarioFixtureSeed(
        trip_mode="leisure",
        title="Kyoto ranked scenario workspace",
        leisure_fixture_id="urban-historian",
    ),
    "trip-business-client-summit": ScenarioFixtureSeed(
        trip_mode="business",
        title="Client summit ranked scenarios",
        business_profile_fixture="client_meeting_profile.json",
        business_constraint_fixture="policy_round_trip_exception.json",
    ),
}

_DEFAULT_LEISURE_FIXTURE_ID = "urban-historian"
_DEFAULT_BUSINESS_PROFILE_FIXTURE = "client_meeting_profile.json"
_DEFAULT_BUSINESS_CONSTRAINT_FIXTURE = "policy_round_trip_exception.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _business_fixture_dir() -> Path:
    return _repo_root() / "tests" / "fixtures" / "business"


def _default_scenario_title(
    *,
    trip_mode: str,
    trip_title: str | None,
    primary_regions: tuple[str, ...],
) -> str:
    subject = trip_title or ", ".join(primary_regions[:2]) or "Persisted trip"
    suffix = "ranked scenarios" if trip_mode == "business" else "runtime scenarios"
    return f"{subject} {suffix}"


def _bundle_ranked_results(
    ranked_results: RankedResultSet,
    bundles: list[InventoryBundle],
) -> RankedResultSet:
    bundle_map = {bundle.bundle_id: bundle for bundle in bundles}

    return RankedResultSet(
        result_set_id=ranked_results.result_set_id,
        trip_id=ranked_results.trip_id,
        purpose=ranked_results.purpose,
        scope=ranked_results.scope,
        title=ranked_results.title,
        explanation=list(ranked_results.explanation),
        source_refs=list(ranked_results.source_refs),
        schema_version=ranked_results.schema_version,
        results=[
            RankedResult(
                result_id=result.result_id.replace("ranked:item:", "ranked:bundle:", 1),
                result_kind="bundle",
                rank=result.rank,
                score=result.score,
                target_bundle_id=(
                    result.target_option.option_id
                    if result.target_option is not None
                    else result.explanation_records[0].target_id
                ),
                supporting_option_ids=list(result.supporting_option_ids),
                supporting_destination_ids=list(result.supporting_destination_ids),
                route_sequence=list(
                    result.route_sequence
                    or bundle_map[
                        result.target_option.option_id
                        if result.target_option is not None
                        else result.explanation_records[0].target_id
                    ].destination_ids
                ),
                score_breakdown=result.score_breakdown,
                confidence_summary=result.confidence_summary,
                explanation_records=list(result.explanation_records),
                unresolved_risks=list(result.unresolved_risks),
                source_refs=list(result.source_refs),
                notes=list(result.notes),
            )
            for result in ranked_results.results
        ],
    )


def build_workspace_scenario_search(
    *,
    trip_id: str,
    trip_mode: str,
    bundles: list[InventoryBundle],
    trip_title: str | None = None,
    primary_regions: tuple[str, ...] = (),
    duration_days: int | None = None,
    traveler_party_kind: str | None = None,
):
    fixture_seed = _SCENARIO_FIXTURE_SEEDS.get(trip_id)
    title = _default_scenario_title(
        trip_mode=trip_mode,
        trip_title=trip_title,
        primary_regions=primary_regions,
    )
    if fixture_seed is not None and fixture_seed.trip_mode != trip_mode:
        raise KeyError(f"Unsupported scenario fixture trip: {trip_id}")
    if not bundles:
        raise ValueError("Workspace scenario search requires at least one inventory bundle")

    feasibility_outputs = {
        bundle.bundle_id: evaluate_bundle_feasibility(bundle) for bundle in bundles
    }

    scenario_objectives: object

    if trip_mode == "leisure":
        leisure_fixture_id = (
            fixture_seed.leisure_fixture_id
            if fixture_seed is not None and fixture_seed.leisure_fixture_id is not None
            else _DEFAULT_LEISURE_FIXTURE_ID
        )
        traveler_fixture = load_fixture_map()[leisure_fixture_id]
        profile = deepcopy(traveler_fixture.profile)
        if duration_days is not None:
            profile.trip_frame.duration_days = duration_days
        if primary_regions:
            profile.trip_frame.regions_in_scope = list(primary_regions)
        if traveler_party_kind in {"solo", "pair", "family", "friends"}:
            profile.trip_frame.traveler_party = traveler_party_kind
        resolved_profile = resolve_leisure_profile(
            profile,
            traveler_fixture.evidence,
        )
        leisure_objectives = derive_itinerary_objectives(
            resolved_profile,
            trip_id=trip_id,
            objective_id=f"objective:{trip_id}:ranking",
        )
        ranked_results = LeisureRankingEngine().rank_bundles(
            resolved_profile.profile,
            leisure_objectives,
            bundles,
            trip_id=trip_id,
            title=fixture_seed.title if fixture_seed is not None else title,
            feasibility_outputs=feasibility_outputs,
        )
        scenario_objectives = leisure_objectives
    else:
        business_profile_fixture = (
            fixture_seed.business_profile_fixture
            if fixture_seed is not None and fixture_seed.business_profile_fixture is not None
            else _DEFAULT_BUSINESS_PROFILE_FIXTURE
        )
        business_constraint_fixture = (
            fixture_seed.business_constraint_fixture
            if fixture_seed is not None and fixture_seed.business_constraint_fixture is not None
            else _DEFAULT_BUSINESS_CONSTRAINT_FIXTURE
        )
        profile = BusinessTravelProfile.from_dict(
            _load_json(_business_fixture_dir() / business_profile_fixture)
        )
        constraint_payload = _load_json(
            _business_fixture_dir() / business_constraint_fixture
        )
        constraint_set = PolicyConstraintSet(**constraint_payload["constraint_set"])
        business_objectives = derive_business_planning_objectives(
            profile,
            trip_id=trip_id,
            constraint_set=constraint_set,
        )
        ranked_results = BusinessRankingEngine().rank_bundles(
            profile,
            business_objectives,
            bundles,
            trip_id=trip_id,
            title=fixture_seed.title if fixture_seed is not None else title,
            constraint_set=constraint_set,
            feasibility_outputs=feasibility_outputs,
        )
        scenario_objectives = business_objectives

    return assemble_itinerary_scenarios(
        _bundle_ranked_results(ranked_results, bundles),
        bundles=bundles,
        objectives=scenario_objectives,
        feasibility_outputs=feasibility_outputs,
        title=fixture_seed.title if fixture_seed is not None else title,
    )


def _scenario_output_status(scenario: dict[str, Any]) -> str:
    if not scenario["scenario_summary"]["feasible"]:
        return "critical"
    if scenario["scenario_summary"]["recommended_for_selection"]:
        return "positive"
    return "caution"


def build_scenario_ranking_outputs(
    *,
    trip_id: str,
    scenario_search: dict[str, Any],
) -> list[dict[str, Any]]:
    scenarios = list(scenario_search.get("scenarios", []))
    if not scenarios:
        return []

    lead = scenarios[0]
    outputs: list[dict[str, Any]] = [
        {
            "output_id": f"output:{trip_id}:scenario-ranking-summary",
            "title": "Scenario ranking summary",
            "body": (
                f"{len(scenarios)} ranked scenario(s) are ready for workspace review. "
                f"Top scenario: {lead['title']}."
            ),
            "tags": ["scenario-ranking", "workspace-runtime"],
            "status": _scenario_output_status(lead),
            "highlights": [
                scenario_search.get("title") or "Scenario ranking is active.",
                f"Primary route: {' -> '.join(lead['scenario_summary'].get('route_sequence', [])) or 'not surfaced yet'}.",
                f"Generated from {scenario_search.get('source_result_set_id', 'ranked workspace scenarios')}.",
            ],
        }
    ]

    for scenario in scenarios[:3]:
        outputs.append(
            {
                "output_id": f"output:{trip_id}:scenario-rank:{scenario['rank']}",
                "title": f"Rank #{scenario['rank']} {scenario['title']}",
                "body": (
                    f"{scenario['scenario_summary']['headline']} "
                    f"Score {scenario['score']:.2f} with "
                    f"{scenario['scenario_summary']['total_travel_minutes']} travel minutes and "
                    f"{scenario['scenario_summary']['total_transfer_count']} transfer(s)."
                ),
                "tags": [
                    "scenario-ranking",
                    scenario["scenario_summary"]["scenario_kind"],
                    "recommended"
                    if scenario["scenario_summary"]["recommended_for_selection"]
                    else "fallback",
                ],
                "status": _scenario_output_status(scenario),
                "highlights": [
                    f"Route: {' -> '.join(scenario['scenario_summary'].get('route_sequence', [])) or 'not surfaced yet'}.",
                    *[
                        tradeoff["summary"]
                        for tradeoff in scenario.get("unresolved_tradeoffs", [])[:2]
                    ],
                ]
                or ["No unresolved tradeoffs are currently surfaced."],
            }
        )

    return outputs
