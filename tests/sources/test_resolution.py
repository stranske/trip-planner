import json
from pathlib import Path
from typing import Any

import pytest

from trip_planner.sources import (
    AttributeConflict,
    EntityResolution,
    MatchCandidate,
    MergedEntityProvenance,
    ProvenanceReference,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "sources" / "resolution"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / name).read_text())


def build_provenance(canonical_entity_id: str, entity_scope: str) -> MergedEntityProvenance:
    return MergedEntityProvenance(
        canonical_entity_id=canonical_entity_id,
        entity_scope=entity_scope,
        source_record_ids=[
            f"{canonical_entity_id}-record-a",
            f"{canonical_entity_id}-record-b",
        ],
        source_snapshot_ids=[
            f"{canonical_entity_id}-snapshot-a",
            f"{canonical_entity_id}-snapshot-b",
        ],
        provenance_refs=[
            ProvenanceReference(
                provenance_id=f"prov-{canonical_entity_id}",
                source_id="fixture-source",
                source_category=(
                    "commercial_inventory" if entity_scope != "destination" else "editorial"
                ),
                subject_kind=("destination" if entity_scope == "destination" else "option"),
                subject_id=canonical_entity_id,
                contribution_kind=("inventory" if entity_scope != "destination" else "editorial"),
                summary="Fixture provenance survives resolution.",
                captured_at="2026-04-01T00:05:00Z",
            )
        ],
    )


def test_entity_resolution_supports_confident_lodging_match() -> None:
    fixture = load_fixture("clean_lodging_match.json")
    canonical_entity_id = str(fixture.pop("canonical_entity_id"))
    candidate = MatchCandidate(candidate_id="candidate-lodging-1", **fixture)
    resolution = EntityResolution(
        resolution_id="resolution-lodging-1",
        entity_scope="lodging",
        option_kind="lodging",
        status="match",
        canonical_entity_id=canonical_entity_id,
        summary="Confident provider-id alignment merges the listing into one lodging shell.",
        match_candidates=[candidate],
        merged_provenance=build_provenance("lodging-canal-house", "lodging"),
    )

    payload = resolution.to_dict()

    assert payload["status"] == "match"
    assert payload["match_candidates"][0]["score_breakdown"]["provider_id_alignment"] == 1.0


def test_entity_resolution_preserves_ambiguous_destination_conflict() -> None:
    fixture = load_fixture("ambiguous_destination_match.json")
    canonical_entity_id = str(fixture.pop("canonical_entity_id"))
    conflict_data = fixture.pop("conflict")
    candidate = MatchCandidate(candidate_id="candidate-destination-1", **fixture)
    conflict = AttributeConflict(conflict_id="conflict-destination-1", **conflict_data)
    resolution = EntityResolution(
        resolution_id="resolution-destination-1",
        entity_scope="destination",
        option_kind="mixed",
        status="ambiguous",
        canonical_entity_id=canonical_entity_id,
        summary="The neighborhood likely matches, but parent-city labeling conflicts stay explicit.",
        match_candidates=[candidate],
        conflicts=[conflict],
        merged_provenance=build_provenance("destination-rome-trastevere", "destination"),
        review_required=True,
    )

    payload = resolution.to_dict()

    assert payload["review_required"] is True
    assert payload["conflicts"][0]["status"] == "preserved"
    assert "Roma municipality" in payload["conflicts"][0]["values_by_source"].values()


def test_entity_resolution_requires_review_flag_for_ambiguous_matches() -> None:
    fixture = load_fixture("ambiguous_destination_match.json")
    canonical_entity_id = str(fixture["canonical_entity_id"])
    conflict = AttributeConflict(conflict_id="conflict-destination-2", **fixture["conflict"])

    with pytest.raises(ValueError, match="review_required"):
        EntityResolution(
            resolution_id="resolution-destination-2",
            entity_scope="destination",
            option_kind="mixed",
            status="ambiguous",
            canonical_entity_id=canonical_entity_id,
            summary="Ambiguous matches must stay reviewable.",
            conflicts=[conflict],
            merged_provenance=build_provenance("destination-rome-trastevere", "destination"),
        )


def test_attribute_conflict_requires_non_empty_string_values() -> None:
    with pytest.raises(ValueError, match="values_by_source\\[source:ota-a\\]"):
        AttributeConflict(
            conflict_id="conflict-destination-invalid-value",
            attribute_path="destination.parent_city",
            reason="source_disagreement",
            status="preserved",
            values_by_source={
                "source:ota-a": "",
                "source:ota-b": "Rome",
            },
        )


def test_match_candidate_validates_resolution_taxonomy_fields() -> None:
    with pytest.raises(ValueError, match="entity_scope"):
        MatchCandidate(
            candidate_id="candidate-invalid-scope",
            entity_scope="meal",
            option_kind="lodging",
            match_strategy="provider_id",
            confidence=0.9,
        )
    with pytest.raises(ValueError, match="option_kind"):
        MatchCandidate(
            candidate_id="candidate-invalid-kind",
            entity_scope="lodging",
            option_kind="hotel",
            match_strategy="provider_id",
            confidence=0.9,
        )
    with pytest.raises(ValueError, match="match_strategy"):
        MatchCandidate(
            candidate_id="candidate-invalid-strategy",
            entity_scope="lodging",
            option_kind="lodging",
            match_strategy="fuzzy",
            confidence=0.9,
        )


def test_attribute_conflict_selected_status_requires_selected_value() -> None:
    with pytest.raises(ValueError, match="selected_value"):
        AttributeConflict(
            conflict_id="conflict-missing-selection",
            attribute_path="lodging.name",
            reason="source_disagreement",
            status="selected",
            values_by_source={"source:a": "Canal House", "source:b": "Canalhouse"},
        )


def test_attribute_conflict_requires_multiple_sources() -> None:
    with pytest.raises(ValueError, match="at least two source values"):
        AttributeConflict(
            conflict_id="conflict-one-source",
            attribute_path="lodging.name",
            reason="source_disagreement",
            status="preserved",
            values_by_source={"source:a": "Canal House"},
        )


def test_merged_entity_provenance_requires_provenance_references() -> None:
    with pytest.raises(ValueError, match="ProvenanceReference"):
        MergedEntityProvenance(
            canonical_entity_id="lodging-canal-house",
            entity_scope="lodging",
            provenance_refs=["not-a-reference"],  # type: ignore[list-item]
        )


def test_entity_resolution_validates_nested_resolution_members() -> None:
    provenance = build_provenance("lodging-canal-house", "lodging")

    with pytest.raises(ValueError, match="match_candidates"):
        EntityResolution(
            resolution_id="resolution-invalid-candidates",
            entity_scope="lodging",
            option_kind="lodging",
            status="match",
            canonical_entity_id="lodging-canal-house",
            summary="Invalid nested candidate.",
            match_candidates=["not-a-candidate"],  # type: ignore[list-item]
            merged_provenance=provenance,
        )
    with pytest.raises(ValueError, match="conflicts"):
        EntityResolution(
            resolution_id="resolution-invalid-conflicts",
            entity_scope="lodging",
            option_kind="lodging",
            status="blocked",
            canonical_entity_id="lodging-canal-house",
            summary="Invalid nested conflict.",
            conflicts=["not-a-conflict"],  # type: ignore[list-item]
            merged_provenance=provenance,
        )
    with pytest.raises(ValueError, match="MergedEntityProvenance"):
        EntityResolution(
            resolution_id="resolution-invalid-provenance",
            entity_scope="lodging",
            option_kind="lodging",
            status="blocked",
            canonical_entity_id="lodging-canal-house",
            summary="Invalid provenance.",
            merged_provenance="not-provenance",  # type: ignore[arg-type]
        )


def test_entity_resolution_status_specific_context_requirements() -> None:
    with pytest.raises(ValueError, match="match candidate"):
        EntityResolution(
            resolution_id="resolution-match-empty",
            entity_scope="lodging",
            option_kind="lodging",
            status="match",
            canonical_entity_id="lodging-canal-house",
            summary="Match without candidate is invalid.",
            merged_provenance=build_provenance("lodging-canal-house", "lodging"),
        )
    with pytest.raises(ValueError, match="explicit conflicts"):
        EntityResolution(
            resolution_id="resolution-ambiguous-empty",
            entity_scope="lodging",
            option_kind="lodging",
            status="ambiguous",
            canonical_entity_id="lodging-canal-house",
            summary="Ambiguous without conflict is invalid.",
            review_required=True,
            merged_provenance=build_provenance("lodging-canal-house", "lodging"),
        )
    with pytest.raises(ValueError, match="merged_provenance"):
        EntityResolution(
            resolution_id="resolution-distinct-no-provenance",
            entity_scope="lodging",
            option_kind="lodging",
            status="distinct",
            canonical_entity_id="lodging-canal-house",
            summary="Distinct still needs provenance.",
        )
