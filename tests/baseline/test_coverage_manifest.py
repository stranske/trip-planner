"""Coverage manifest -- which metric dimensions are exercised; emit report.

Uses the generic ``baseline_kit.CoverageManifest``. The app supplies the input
space (the transport metric dimensions) and the touched set (metrics referenced
by an ordering).
"""

from __future__ import annotations

import copy
import csv
import json
import math
import os
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

import pytest
from baseline_kit import (
    DEFAULT_TOLERANCE,
    CoverageManifest,
    assert_invariants,
    evaluate_direction,
    load_catalog,
)

from . import adapter, invariants
from .conftest import CATALOG_PATH, REPO_ROOT

REPORT_PATH = REPO_ROOT / "docs" / "reports" / "baseline-coverage.md"


def _catalog_fixtures(catalog: dict) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for fixture in catalog.get("fixtures", []):
        if fixture not in seen:
            ordered.append(fixture)
            seen.add(fixture)
    for ordering in catalog.get("orderings", []):
        for side in ("left", "right"):
            fixture = ordering.get(side)
            if isinstance(fixture, str) and fixture not in seen:
                ordered.append(fixture)
                seen.add(fixture)
    return ordered


def _observed_reads(fixtures: Iterable[str], *, allowed_keys: Iterable[str]) -> set[str]:
    observer = getattr(adapter, "observed_reads_for", None)
    if observer is None:
        return set()
    return set(observer(fixtures, allowed_keys=allowed_keys))


def _build_manifest(*, extra_keys: Iterable[str] = ()) -> CoverageManifest:
    catalog = load_catalog(CATALOG_PATH)
    all_keys = set(adapter.METRIC_KEYS) | set(extra_keys)
    touched = {o["metric"] for o in catalog.get("orderings", [])}
    read_keys = _observed_reads(_catalog_fixtures(catalog), allowed_keys=all_keys)
    return CoverageManifest(
        all_keys=all_keys,
        touched_keys=touched,
        priority_params=list(catalog.get("priority_metrics", [])),
        read_keys=read_keys,
        title="Trip-planner baseline coverage manifest",
    )


def test_ordering_metrics_exist():
    m = _build_manifest()
    assert not m.unknown_catalog_keys, (
        "Catalog references metrics not produced by the adapter: "
        f"{sorted(m.unknown_catalog_keys)}"
    )


def test_priority_metrics_covered():
    m = _build_manifest()
    assert not m.priority_gaps, "Priority metrics with no ordering: " + ", ".join(m.priority_gaps)


def test_emit_coverage_report(tmp_path: Path):
    m = _build_manifest()
    report_path = (
        REPORT_PATH
        if os.environ.get("BASELINE_REFRESH_REPORT") == "1"
        else tmp_path / "baseline-coverage.md"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(m.to_markdown())
    assert report_path.exists()


def _golden_csv_path(fixture: str) -> Path:
    stem = fixture.replace(".json", "").replace("/", "_")
    filename = f"test_transport_metrics_golden_{stem}_.csv"
    return REPO_ROOT / "tests" / "baseline" / "test_golden" / filename


def test_non_transport_roundtrips_use_canonical_models(tmp_path: Path, record_property):
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{REPO_ROOT}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(REPO_ROOT)
    )
    import_probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from trip_planner.ranking import ExplanationRecord, RankedResultSet; "
                "print(f'{RankedResultSet.__name__}:{ExplanationRecord.__name__}')"
            ),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert import_probe.returncode == 0, import_probe.stderr
    assert import_probe.stdout.strip() == "RankedResultSet:ExplanationRecord"

    reverse_import_probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from trip_planner.itinerary import ItineraryScenario; "
                "from trip_planner.ranking import RankedResultSet; "
                "print(f'{ItineraryScenario.__name__}:{RankedResultSet.__name__}')"
            ),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert reverse_import_probe.returncode == 0, reverse_import_probe.stderr
    assert reverse_import_probe.stdout.strip() == "ItineraryScenario:RankedResultSet"

    from trip_planner.options import LodgingOption, TransportOption
    from trip_planner.ranking import RankedResultSet

    assert isinstance(adapter.load_model("coastal_flight.json"), TransportOption)
    assert isinstance(
        adapter.load_model("tests/fixtures/options/lodging/central_urban_hotel.json"),
        LodgingOption,
    )
    assert isinstance(
        adapter.load_model("tests/fixtures/ranking/results/leisure_candidate_result.json"),
        RankedResultSet,
    )

    catalog = load_catalog(CATALOG_PATH)
    fixtures = _catalog_fixtures(catalog)
    for fixture in [*fixtures, "tests/fixtures/ranking/results/route_bundle_result.json"]:
        assert (
            adapter.roundtrip_is_stable(fixture) is True
        ), f"Expected canonical roundtrip: {fixture}"

    non_object_payload = tmp_path / "non_object_fixture.json"
    non_object_payload.write_text("[]", encoding="utf-8")
    assert adapter.roundtrip_is_stable(str(non_object_payload)) is False

    central_lodging_path = REPO_ROOT / "tests/fixtures/options/lodging/central_urban_hotel.json"
    central_payload = json.loads(central_lodging_path.read_text(encoding="utf-8"))

    broken_lodging = tmp_path / "broken_lodging.json"
    broken_lodging_payload = copy.deepcopy(central_payload)
    broken_lodging_payload["schema_version"] = "9.9.9"
    broken_lodging.write_text(json.dumps(broken_lodging_payload), encoding="utf-8")
    assert adapter.roundtrip_is_stable(str(broken_lodging)) is False

    leisure_ranking_path = (
        REPO_ROOT / "tests/fixtures/ranking/results/leisure_candidate_result.json"
    )
    leisure_payload = json.loads(leisure_ranking_path.read_text(encoding="utf-8"))

    broken_ranking = tmp_path / "broken_ranking.json"
    broken_ranking_payload = copy.deepcopy(leisure_payload)
    broken_ranking_payload["results"][0]["score_breakdown"]["final_score"] = 0.61
    broken_ranking.write_text(json.dumps(broken_ranking_payload), encoding="utf-8")
    assert adapter.roundtrip_is_stable(str(broken_ranking)) is False

    aged_lodging = tmp_path / "aged_central_hotel.json"
    aged_lodging_payload = copy.deepcopy(central_payload)
    aged_lodging_payload["source_refs"][0]["freshness_days_at_capture"] = 180
    aged_lodging_payload["source_refs"][0]["trust_snapshot"]["freshness_days"] = 180
    aged_lodging.write_text(json.dumps(aged_lodging_payload), encoding="utf-8")

    low_commerciality_lodging = tmp_path / "low_commerciality_central_hotel.json"
    low_commerciality_payload = copy.deepcopy(central_payload)
    low_commerciality_payload["source_refs"][0]["trust_snapshot"]["commerciality"] = 0.1
    low_commerciality_lodging.write_text(
        json.dumps(low_commerciality_payload),
        encoding="utf-8",
    )

    central_metrics = adapter.metrics_for("tests/fixtures/options/lodging/central_urban_hotel.json")
    aged_metrics = adapter.metrics_for(str(aged_lodging))
    low_commerciality_metrics = adapter.metrics_for(str(low_commerciality_lodging))
    assert central_metrics["quality_signal"] == pytest.approx(0.81)
    assert central_metrics["value_signal"] == pytest.approx(0.73)
    assert central_metrics["fit_signal"] == pytest.approx(0.76)
    assert central_metrics["freshness_confidence"] > aged_metrics["freshness_confidence"]
    assert central_metrics["commerciality"] == pytest.approx(0.732)
    assert central_metrics["commerciality"] > low_commerciality_metrics["commerciality"]

    business_metrics = adapter.metrics_for(
        "tests/fixtures/ranking/results/business_candidate_result.json"
    )
    assert business_metrics["anchor_alignment"] == 0.0
    assert business_metrics["quality_floor_fit"] == 0.0
    assert business_metrics["discovery_fit"] == 0.0

    route_metrics = adapter.metrics_for("tests/fixtures/ranking/results/route_bundle_result.json")
    assert route_metrics["anchor_alignment"] == 0.0
    assert route_metrics["quality_floor_fit"] == 0.0
    assert route_metrics["discovery_fit"] == 0.0

    reordered_leisure = tmp_path / "reordered_leisure_result.json"
    reordered_payload = copy.deepcopy(leisure_payload)
    reordered_payload["results"][0]["score_breakdown"]["component_contributions"] = list(
        reversed(reordered_payload["results"][0]["score_breakdown"]["component_contributions"])
    )
    reordered_leisure.write_text(json.dumps(reordered_payload), encoding="utf-8")

    leisure_metrics = adapter.metrics_for(
        "tests/fixtures/ranking/results/leisure_candidate_result.json"
    )
    reordered_metrics = adapter.metrics_for(str(reordered_leisure))
    for key in ("anchor_alignment", "quality_floor_fit", "discovery_fit"):
        assert leisure_metrics[key] > 0.0
        assert leisure_metrics[key] == pytest.approx(reordered_metrics[key])

    canonical_engine_contributions = [
        {
            "contribution_id": "anchor_alignment",
            "label": "Anchor alignment",
            "axis_key": "anchor_alignment",
            "direction": "higher_better",
            "raw_value": 0.91,
            "normalized_signal": 0.91,
            "weighted_impact": 0.15,
            "summary": "Aligned with primary anchor.",
        },
        {
            "contribution_id": "quality_floor_fit",
            "label": "Quality floor fit",
            "axis_key": "quality_floor_fit",
            "direction": "higher_better",
            "raw_value": 0.77,
            "normalized_signal": 0.77,
            "weighted_impact": 0.10,
            "summary": "Meets lodging quality floor.",
        },
        {
            "contribution_id": "discovery_fit",
            "label": "Discovery fit",
            "axis_key": "discovery_fit",
            "direction": "higher_better",
            "raw_value": 0.64,
            "normalized_signal": 0.64,
            "weighted_impact": 0.08,
            "summary": "Supports neighborhood wandering.",
        },
    ]
    canonical_ranking_file = tmp_path / "canonical_engine_ranking.json"
    canonical_ranking_payload = copy.deepcopy(leisure_payload)
    canonical_ranking_payload["results"][0]["score_breakdown"][
        "component_contributions"
    ] = canonical_engine_contributions
    canonical_ranking_file.write_text(json.dumps(canonical_ranking_payload), encoding="utf-8")
    assert adapter.roundtrip_is_stable(str(canonical_ranking_file)) is True

    reversed_canonical_ranking_file = tmp_path / "reversed_canonical_engine_ranking.json"
    reversed_canonical_payload = copy.deepcopy(canonical_ranking_payload)
    reversed_canonical_payload["results"][0]["score_breakdown"]["component_contributions"] = list(
        reversed(canonical_engine_contributions)
    )
    reversed_canonical_ranking_file.write_text(
        json.dumps(reversed_canonical_payload),
        encoding="utf-8",
    )

    canonical_ranking_metrics = adapter.metrics_for(str(canonical_ranking_file))
    reversed_canonical_metrics = adapter.metrics_for(str(reversed_canonical_ranking_file))
    assert canonical_ranking_metrics["anchor_alignment"] == pytest.approx(0.91)
    assert canonical_ranking_metrics["quality_floor_fit"] == pytest.approx(0.77)
    assert canonical_ranking_metrics["discovery_fit"] == pytest.approx(0.64)
    for key in ("anchor_alignment", "quality_floor_fit", "discovery_fit"):
        assert canonical_ranking_metrics[key] == pytest.approx(reversed_canonical_metrics[key])

    partial_canonical_ranking_file = tmp_path / "partial_canonical_engine_ranking.json"
    partial_canonical_payload = copy.deepcopy(canonical_ranking_payload)
    partial_canonical_payload["results"][0]["score_breakdown"]["component_contributions"] = (
        canonical_engine_contributions[:2]
    )
    partial_canonical_payload["results"][0]["score"] = 0.61
    partial_canonical_payload["results"][0]["score_breakdown"]["final_score"] = 0.61
    partial_canonical_ranking_file.write_text(
        json.dumps(partial_canonical_payload),
        encoding="utf-8",
    )
    assert adapter.roundtrip_is_stable(str(partial_canonical_ranking_file)) is True
    partial_eval = adapter.evaluate_fixture(str(partial_canonical_ranking_file))
    assert partial_eval.metrics["discovery_fit"] == 0.0
    assert {"anchor_alignment", "quality_floor_fit"} <= partial_eval.observed_reads
    assert "discovery_fit" not in partial_eval.observed_reads

    unused_control_key = "unused_baseline_control_signal"
    manifest_with_control = _build_manifest(extra_keys={unused_control_key})
    assert unused_control_key in manifest_with_control.all_keys
    assert unused_control_key not in manifest_with_control.read_keys
    assert manifest_with_control.read_keys == set(adapter.METRIC_KEYS)

    vacation_reads = _observed_reads(
        ["tests/fixtures/options/lodging/vacation_rental.json"],
        allowed_keys=adapter.METRIC_KEYS,
    )
    assert {"quality_signal", "value_signal", "fit_signal", "overall_signal"} <= vacation_reads
    assert "freshness_confidence" not in vacation_reads
    assert "commerciality" not in vacation_reads
    assert "anchor_alignment" not in vacation_reads

    business_reads = _observed_reads(
        ["tests/fixtures/ranking/results/business_candidate_result.json"],
        allowed_keys=adapter.METRIC_KEYS,
    )
    expected_business_reads = {
        "input_coverage",
        "scoring_stability",
        "quality_signal",
        "value_signal",
        "fit_signal",
    }
    assert expected_business_reads <= business_reads
    assert "anchor_alignment" not in business_reads
    assert "quality_floor_fit" not in business_reads
    assert "discovery_fit" not in business_reads

    route_reads = _observed_reads(
        ["tests/fixtures/ranking/results/route_bundle_result.json"],
        allowed_keys=adapter.METRIC_KEYS,
    )
    assert route_reads == {"input_coverage", "scoring_stability"}

    manifest = _build_manifest()
    assert not manifest.unknown_catalog_keys
    assert not manifest.priority_gaps
    assert REPORT_PATH.read_text(encoding="utf-8") == manifest.to_markdown()
    for scen in catalog["orderings"]:
        left = adapter.metrics_for(scen["left"])[scen["metric"]]
        right = adapter.metrics_for(scen["right"])[scen["metric"]]
        assert evaluate_direction(scen["direction"], left, right), scen["id"]
    for fixture in fixtures:
        assert_invariants(invariants.check_option(fixture), context=fixture)
        with _golden_csv_path(fixture).open(encoding="utf-8", newline="") as handle:
            golden_row = next(csv.DictReader(handle))
        actual_metrics = adapter.metrics_for(fixture)
        for col, actual_val in actual_metrics.items():
            raw_expected = golden_row[col]
            expected_val = float("nan") if raw_expected == "" else float(raw_expected)
            if math.isnan(actual_val):
                assert math.isnan(expected_val), f"{fixture}:{col}"
            else:
                assert actual_val == pytest.approx(
                    expected_val,
                    rel=DEFAULT_TOLERANCE["rtol"],
                    abs=DEFAULT_TOLERANCE["atol"],
                ), f"{fixture}:{col} actual={actual_val} expected={expected_val}"

    record_property(
        "observed_reads_summary",
        {
            "observed_count": len(manifest.read_keys),
            "unused_control_absent": unused_control_key not in manifest_with_control.read_keys,
            "leisure_components": {
                key: leisure_metrics[key]
                for key in ("anchor_alignment", "quality_floor_fit", "discovery_fit")
            },
            "central_lodging_source": {
                key: central_metrics[key]
                for key in ("freshness_confidence", "commerciality", "quality_signal")
            },
            "low_commerciality_lodging": low_commerciality_metrics["commerciality"],
            "partial_canonical_ranking_discovery_absent": (
                "discovery_fit" not in partial_eval.observed_reads
            ),
        },
    )
