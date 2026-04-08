from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
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
from trip_planner.preferences.fixture_corpus import load_fixture_map
from trip_planner.ranking import (
    BusinessRankingEngine,
    LeisureRankingEngine,
    RankedResult,
    RankedResultSet,
)

_BUSINESS_RESOURCE_PACKAGE = "trip_planner.resources.business"


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

def _load_business_fixture(name: str) -> dict[str, Any]:
    return json.loads(
        resources.files(_BUSINESS_RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")
    )


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
):
    fixture_seed = _SCENARIO_FIXTURE_SEEDS.get(trip_id)
    if fixture_seed is None or fixture_seed.trip_mode != trip_mode:
        raise KeyError(f"Unsupported scenario fixture trip: {trip_id}")
    if not bundles:
        raise ValueError("Workspace scenario search requires at least one inventory bundle")

    feasibility_outputs = {
        bundle.bundle_id: evaluate_bundle_feasibility(bundle) for bundle in bundles
    }
    objectives: object

    if trip_mode == "leisure":
        traveler_fixture = load_fixture_map()[fixture_seed.leisure_fixture_id or ""]
        resolved_profile = resolve_leisure_profile(
            traveler_fixture.profile,
            traveler_fixture.evidence,
        )
        objectives = derive_itinerary_objectives(
            resolved_profile,
            trip_id=trip_id,
            objective_id=f"objective:{trip_id}:ranking",
        )
        ranked_results = LeisureRankingEngine().rank_bundles(
            traveler_fixture.profile,
            objectives,
            bundles,
            trip_id=trip_id,
            title=fixture_seed.title,
            feasibility_outputs=feasibility_outputs,
        )
    else:
        profile = BusinessTravelProfile.from_dict(
            _load_business_fixture(fixture_seed.business_profile_fixture or "")
        )
        constraint_payload = _load_business_fixture(
            fixture_seed.business_constraint_fixture or ""
        )
        constraint_set = PolicyConstraintSet(**constraint_payload["constraint_set"])
        objectives = derive_business_planning_objectives(
            profile,
            trip_id=trip_id,
            constraint_set=constraint_set,
        )
        ranked_results = BusinessRankingEngine().rank_bundles(
            profile,
            objectives,
            bundles,
            trip_id=trip_id,
            title=fixture_seed.title,
            constraint_set=constraint_set,
            feasibility_outputs=feasibility_outputs,
        )

    return assemble_itinerary_scenarios(
        _bundle_ranked_results(ranked_results, bundles),
        bundles=bundles,
        objectives=objectives,
        feasibility_outputs=feasibility_outputs,
        title=fixture_seed.title,
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
