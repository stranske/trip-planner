import json
from copy import deepcopy
from pathlib import Path

from trip_planner.candidates import CandidateSeed, CandidateSet
from trip_planner.itinerary import derive_itinerary_objectives
from trip_planner.options import (
    ActivityOption,
    BundleCompositionSummary,
    BundleExplanation,
    BundleFeasibility,
    BundleProvenanceSummary,
    BundleQualityValueFitSummary,
    Destination,
    InventoryBundle,
    LodgingOption,
    TransportOption,
)
from trip_planner.preferences import resolve_leisure_profile
from trip_planner.ranking import rank_leisure_candidates
from tests.preferences.fixture_corpus import load_fixture_map


def _fixture_path(name: str) -> Path:
    return Path("tests/fixtures/ranking") / name


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _deep_merge(base: dict, patch: dict) -> dict:
    merged = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _load_entry(entry: dict, parser):
    if "path" in entry:
        payload = _load_json(Path(entry["path"]))
    else:
        payload = deepcopy(entry["payload"])
    if "overrides" in entry:
        payload = _deep_merge(payload, entry["overrides"])
    return parser(payload)


def _mean_or_none(values: list[float | None]) -> float | None:
    numeric = [value for value in values if value is not None]
    if not numeric:
        return None
    return round(sum(numeric) / len(numeric), 4)


def _aggregate_source_refs(*collections) -> list[str]:
    seen: set[str] = set()
    refs: list[str] = []
    for collection in collections:
        for option in collection:
            for source_ref in option.source_refs:
                provenance_id = getattr(source_ref, "provenance_id", "")
                if provenance_id and provenance_id not in seen:
                    seen.add(provenance_id)
                    refs.append(provenance_id)
    return refs


def _aggregate_booking_links(*collections) -> list[str]:
    seen: set[str] = set()
    links: list[str] = []
    for collection in collections:
        for option in collection:
            for link in option.booking_links:
                if link and link not in seen:
                    seen.add(link)
                    links.append(link)
    return links


def _load_candidate_set(name: str) -> CandidateSet:
    payload = _load_json(_fixture_path(name))
    seeds: list[CandidateSeed] = []
    for index, item in enumerate(payload["candidates"]):
        destinations = [
            _load_entry(entry, Destination.from_dict) for entry in item["destinations"]
        ]
        lodging_options = [
            _load_entry(entry, LodgingOption.from_dict)
            for entry in item["lodging_options"]
        ]
        transport_options = [
            _load_entry(entry, TransportOption.from_dict)
            for entry in item["transport_options"]
        ]
        activity_options = [
            _load_entry(entry, ActivityOption.from_dict)
            for entry in item["activity_options"]
        ]
        bundle = InventoryBundle(
            bundle_id=item["bundle_id"],
            title=item["title"],
            bundle_context=item.get("bundle_context", "mixed"),
            destinations=destinations,
            lodging_options=lodging_options,
            transport_options=transport_options,
            activity_options=activity_options,
            composition_summary=BundleCompositionSummary(
                sequence_index=index,
                assembly_role="candidate_seed",
                primary_destination_id=destinations[0].destination_id,
                component_option_ids=[
                    option.option_id
                    for option in lodging_options + transport_options + activity_options
                ],
                notes=["Representative ranking showcase candidate."],
            ),
            provenance_summary=BundleProvenanceSummary(
                source_refs=_aggregate_source_refs(
                    destinations,
                    lodging_options,
                    transport_options,
                    activity_options,
                ),
                booking_links=_aggregate_booking_links(
                    lodging_options,
                    transport_options,
                    activity_options,
                ),
            ),
            quality_value_fit=BundleQualityValueFitSummary(
                quality_signal=_mean_or_none(
                    [
                        option.quality_summary.overall_signal
                        for option in lodging_options
                    ]
                    + [
                        option.quality_summary.overall_signal
                        for option in activity_options
                    ]
                    + [
                        option.experience_summary.comfort_signal
                        for option in transport_options
                    ]
                ),
                value_signal=_mean_or_none(
                    [option.value_summary.overall_signal for option in lodging_options]
                    + [
                        option.value_summary.overall_signal
                        for option in activity_options
                    ]
                    + [
                        option.fit_summary.policy_fit_signal
                        for option in transport_options
                    ]
                ),
                fit_signal=_mean_or_none(
                    [option.fit_summary.overall_signal for option in lodging_options]
                    + [option.fit_summary.overall_signal for option in activity_options]
                    + [
                        option.fit_summary.overall_signal
                        for option in transport_options
                    ]
                ),
            ),
            feasibility=BundleFeasibility(
                available=True,
                internally_consistent=True,
            ),
            explanation=BundleExplanation(
                headline=item["title"],
                strengths=list(item.get("strengths", [])),
                tradeoffs=list(item.get("tradeoffs", [])),
                evidence=["Built from representative ranking showcase fixtures."],
            ),
            summary=item["summary"],
            tags=list(item.get("tags", [])),
            notes=list(item.get("notes", [])),
        )
        seeds.append(
            CandidateSeed(
                candidate_id=item["candidate_id"],
                bundle=bundle,
                supported_purposes=["profile_learning"],
                inclusion_reasons=list(item.get("strengths", [])),
                unresolved_risks=list(item.get("tradeoffs", [])),
                policy_ready=True,
            )
        )
    return CandidateSet(
        candidate_set_id=f"candidate-set:{payload['trip_id']}:showcase",
        trip_id=payload["trip_id"],
        purpose="profile_learning",
        seeds=seeds,
        explanation=[
            "Representative candidate showcase for deterministic leisure ranking tests."
        ],
        source_refs=[
            source_ref
            for seed in seeds
            for source_ref in seed.bundle.provenance_summary.source_refs
        ],
        selection_limit=len(seeds),
    )


def test_rank_leisure_candidates_emits_bundle_rankings_with_explanations() -> None:
    candidate_set = _load_candidate_set("leisure_candidate_showcase.json")
    fixture = load_fixture_map()["discovery-wanderer"]
    resolved = resolve_leisure_profile(fixture.profile, fixture.evidence)
    objectives = derive_itinerary_objectives(resolved, trip_id=candidate_set.trip_id)

    result_set = rank_leisure_candidates(
        trip_id=candidate_set.trip_id,
        resolved_profile=resolved,
        candidate_set=candidate_set,
        objectives=objectives,
    )

    assert result_set.title == "Leisure candidate ranking"
    assert len(result_set.results) == 4
    assert result_set.results[0].result_kind == "bundle"
    assert result_set.results[0].target_bundle_id is not None
    assert result_set.results[0].explanation_records
    assert result_set.results[0].confidence_summary.overall_confidence is not None
    assert result_set.results[0].score_breakdown.component_contributions


def test_rank_leisure_candidates_reorders_same_candidates_for_different_profiles() -> (
    None
):
    candidate_set = _load_candidate_set("leisure_candidate_showcase.json")
    fixtures = load_fixture_map()

    urban = resolve_leisure_profile(
        fixtures["urban-historian"].profile,
        fixtures["urban-historian"].evidence,
    )
    quality_floor = resolve_leisure_profile(
        fixtures["quality-floors-under-budget-pressure"].profile,
        fixtures["quality-floors-under-budget-pressure"].evidence,
    )

    urban_ranked = rank_leisure_candidates(
        trip_id=candidate_set.trip_id,
        resolved_profile=urban,
        candidate_set=candidate_set,
    )
    quality_ranked = rank_leisure_candidates(
        trip_id=candidate_set.trip_id,
        resolved_profile=quality_floor,
        candidate_set=candidate_set,
    )

    assert urban_ranked.results[0].target_bundle_id == "bundle:discovery-drift"
    assert quality_ranked.results[0].target_bundle_id == "bundle:comfort-floor"
    assert (
        urban_ranked.results[0].target_bundle_id
        != quality_ranked.results[0].target_bundle_id
    )


def test_rank_leisure_candidates_keeps_tension_and_low_confidence_visible() -> None:
    candidate_set = _load_candidate_set("leisure_candidate_showcase.json")
    fixture = load_fixture_map()["breadth-under-recovery-pressure"]
    resolved = resolve_leisure_profile(fixture.profile, fixture.evidence)

    result_set = rank_leisure_candidates(
        trip_id=candidate_set.trip_id,
        resolved_profile=resolved,
        candidate_set=candidate_set,
    )

    first_result = result_set.results[0]
    assert first_result.confidence_summary.low_confidence_flags
    assert any(
        penalty.reason_code == "preference_tension"
        for penalty in first_result.score_breakdown.penalties
    )
    assert any(
        risk.code == "preference_tension" for risk in first_result.unresolved_risks
    )


def test_rank_leisure_candidates_accepts_raw_bundles() -> None:
    candidate_set = _load_candidate_set("leisure_candidate_showcase.json")
    fixture = load_fixture_map()["route-coherence-first"]
    resolved = resolve_leisure_profile(fixture.profile, fixture.evidence)

    result_set = rank_leisure_candidates(
        trip_id=candidate_set.trip_id,
        resolved_profile=resolved,
        bundles=[seed.bundle for seed in candidate_set.seeds],
    )

    assert len(result_set.results) == len(candidate_set.seeds)
    assert result_set.results[0].target_bundle_id is not None
    assert (
        result_set.results[0].score == result_set.results[0].score_breakdown.final_score
    )


def test_rank_leisure_candidates_filters_empty_human_summary_entries() -> None:
    candidate_set = _load_candidate_set("leisure_candidate_showcase.json")
    first_bundle = candidate_set.seeds[0].bundle
    first_bundle.summary = ""
    first_bundle.explanation.strengths = []

    fixture = load_fixture_map()["discovery-wanderer"]
    resolved = resolve_leisure_profile(fixture.profile, fixture.evidence)

    result_set = rank_leisure_candidates(
        trip_id=candidate_set.trip_id,
        resolved_profile=resolved,
        candidate_set=candidate_set,
    )

    for record in result_set.results[0].explanation_records:
        assert record.human_summary
        assert all(item for item in record.human_summary)
