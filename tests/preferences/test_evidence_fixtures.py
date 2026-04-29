import json
from pathlib import Path

from trip_planner.preferences.evidence import DimensionEvidenceRecord, EvidenceProvenance
from trip_planner.preferences.schema import (
    DIMENSION_CONFIDENCE_GUIDANCE,
    SCHEMA_VERSION,
    TRADEOFF_DIMENSION_KEYS,
)


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

    assert records["explicit-answer"].signal_type == "explicit_answer"
    assert records["revealed-behavior"].signal_type == "revealed_behavior"
    assert records["default-assumption"].signal_type == "default_assumption"


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
