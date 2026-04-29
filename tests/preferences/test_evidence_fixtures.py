import json
from pathlib import Path

from trip_planner.preferences.evidence import (
    EVIDENCE_SOURCE_TYPES,
    DimensionEvidenceRecord,
    EvidenceProvenance,
)
from trip_planner.preferences.schema import (
    DIMENSION_CONFIDENCE_GUIDANCE,
    DIMENSION_EVIDENCE_SOURCE_GUIDANCE,
    SCHEMA_VERSION,
    TRADEOFF_DIMENSION_KEYS,
)

EXPECTED_FIXTURE_CASES = {
    "explicit-answer": ("explicit_answer", "user_message", "direct_statement"),
    "revealed-behavior": ("revealed_behavior", "option_menu", "option_selection"),
    "default-assumption": (
        "default_assumption",
        "planner_inference_review",
        "scenario_reaction",
    ),
    "conflicting-explicit": (
        "explicit_answer",
        "structured_input",
        "direct_statement",
    ),
}


def _fixture_payload() -> dict:
    path = Path("tests/fixtures/preferences/evidence_records.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _record(entry: dict) -> DimensionEvidenceRecord:
    return DimensionEvidenceRecord(
        dimension=entry["dimension"],
        signal_type=entry["signal_type"],
        value=entry["value"],
        source=entry["source"],
        confidence=entry["confidence"],
        observed_at=entry["observed_at"],
        provenance=EvidenceProvenance(**entry["provenance"]),
        evidence_type=entry.get("evidence_type"),
        evidence_id=entry.get("evidence_id", ""),
    )


def test_evidence_fixture_records_validate_against_schema() -> None:
    payload = _fixture_payload()
    assert payload["schema_version"] == SCHEMA_VERSION

    records = [_record(entry) for entry in payload["records"]]

    assert len(records) >= 4
    assert all(record.dimension for record in records)
    assert all(record.source for record in records)


def test_evidence_fixtures_cover_explicit_revealed_and_default_signals() -> None:
    records = {entry["name"]: _record(entry) for entry in _fixture_payload()["records"]}

    assert set(EXPECTED_FIXTURE_CASES).issubset(records)
    for name, (signal_type, source, evidence_type) in EXPECTED_FIXTURE_CASES.items():
        assert records[name].signal_type == signal_type
        assert records[name].source == source
        assert records[name].evidence_type == evidence_type


def test_default_assumption_fixture_is_stale() -> None:
    records = {entry["name"]: _record(entry) for entry in _fixture_payload()["records"]}

    assert records["default-assumption"].is_stale(
        as_of="2026-04-28T00:00:00Z",
        max_age_days=30,
    )


def test_conflicting_fixture_records_detect_directional_conflict() -> None:
    records = {entry["name"]: _record(entry) for entry in _fixture_payload()["records"]}

    assert records["revealed-behavior"].conflicts_with(records["conflicting-explicit"])


def test_confidence_guidance_covers_every_tradeoff_dimension() -> None:
    assert set(DIMENSION_CONFIDENCE_GUIDANCE) == set(TRADEOFF_DIMENSION_KEYS)
    assert all(DIMENSION_CONFIDENCE_GUIDANCE.values())


def test_source_guidance_covers_every_tradeoff_dimension_with_supported_sources() -> None:
    assert set(DIMENSION_EVIDENCE_SOURCE_GUIDANCE) == set(TRADEOFF_DIMENSION_KEYS)
    supported_sources = set(EVIDENCE_SOURCE_TYPES)

    for dimension, guidance in DIMENSION_EVIDENCE_SOURCE_GUIDANCE.items():
        assert guidance["confidence_rule"]
        assert guidance["stale_when"]
        assert set(guidance["primary_sources"]).issubset(supported_sources), dimension
