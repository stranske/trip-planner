"""Tests for the source-confidence ExplanationRecord builder."""

from __future__ import annotations

import pytest

# Importing trip_planner.itinerary.feasibility first breaks a pre-existing
# circular import between trip_planner.ranking and trip_planner.itinerary.search;
# mirrors the import order in tests/ranking/test_leisure_ranking.py.
from trip_planner.itinerary.feasibility import FeasibilityAssessment  # noqa: F401
from trip_planner.ranking.explanations import (
    EXPLANATION_RECORD_TYPES,
    ExplanationRecord,
    build_source_confidence_explanation,
)
from trip_planner.sources import (
    ProvenanceReference,
    QualityValueFitSummary,
    SourceConfidenceSummary,
    SourceRecord,
    SourceTrustSignals,
    summarize_sources,
)


def _strong_summary() -> SourceConfidenceSummary:
    return summarize_sources(
        [
            SourceRecord(
                source_id="amtrak-service-alerts",
                provider_name="Amtrak",
                display_name="Amtrak Service Alerts",
                category="official_operational",
                coverage_scope="national",
                supported_option_kinds=["rail"],
                trust_signals=SourceTrustSignals(
                    freshness_days=0,
                    freshness_confidence=0.95,
                    commerciality=0.3,
                    editorial_independence=0.4,
                    operational_reliability=0.92,
                    review_consistency=0.55,
                ),
                quality_summary=QualityValueFitSummary(
                    quality_signal=0.85,
                    value_signal=0.7,
                    fit_signal=0.8,
                    confidence=0.85,
                ),
            ),
            SourceRecord(
                source_id="booking-dot-com",
                provider_name="Booking",
                display_name="Booking.com",
                category="commercial_inventory",
                coverage_scope="global",
                supported_option_kinds=["lodging"],
                trust_signals=SourceTrustSignals(
                    freshness_days=2,
                    freshness_confidence=0.9,
                    commerciality=0.85,
                    editorial_independence=0.1,
                    operational_reliability=0.75,
                    review_consistency=0.6,
                ),
                quality_summary=QualityValueFitSummary(
                    quality_signal=0.75,
                    value_signal=0.8,
                    fit_signal=0.65,
                    confidence=0.75,
                ),
            ),
        ]
    )


def _sparse_summary() -> SourceConfidenceSummary:
    return summarize_sources([])


def test_builder_produces_confidence_record_for_strong_coverage() -> None:
    summary = _strong_summary()

    record = build_source_confidence_explanation(
        target_id="option:rail-1",
        target_kind="item",
        summary=summary,
        source_refs=["external:rail-leg-1"],
    )

    assert isinstance(record, ExplanationRecord)
    assert record.record_type == "confidence"
    assert record.record_type in EXPLANATION_RECORD_TYPES
    assert record.target_kind == "item"
    assert record.target_id == "option:rail-1"
    assert record.machine_context["source_confidence_label"] == summary.confidence_label
    assert record.machine_context["contributing_source_count"] == str(
        summary.contributing_source_count
    )
    assert "external:rail-leg-1" in record.source_refs
    # source_ids from the per-source scores should also be present.
    assert any(ref.startswith("amtrak") or ref.startswith("booking") for ref in record.source_refs)


def test_builder_handles_sparse_summary_with_uncertain_language() -> None:
    summary = _sparse_summary()

    record = build_source_confidence_explanation(
        target_id="option:sparse-1",
        summary=summary,
    )

    assert record.record_type == "confidence"
    assert record.machine_context["source_confidence_label"] == "sparse"
    assert record.machine_context["contributing_source_count"] == "0"
    assert record.headline == "Sparse source coverage"
    assert "sparse" in record.summary.lower() or "uncertainty" in record.summary.lower()


def test_builder_flags_conflict_in_machine_context() -> None:
    summary = summarize_sources(
        [
            SourceRecord(
                source_id="enthusiast-blog",
                provider_name="Enthusiast Blog",
                display_name="Enthusiast Travel Blog",
                category="specialist_non_commercial",
                coverage_scope="regional",
                supported_option_kinds=["lodging"],
                trust_signals=SourceTrustSignals(
                    freshness_days=14,
                    freshness_confidence=0.7,
                    commerciality=0.15,
                    editorial_independence=0.85,
                    operational_reliability=0.6,
                    review_consistency=0.55,
                ),
                quality_summary=QualityValueFitSummary(
                    quality_signal=0.9, value_signal=0.8, fit_signal=0.7, confidence=0.8
                ),
            ),
            SourceRecord(
                source_id="ratings-platform",
                provider_name="Ratings Platform",
                display_name="Cheap Ratings Platform",
                category="ratings_reviews",
                coverage_scope="global",
                supported_option_kinds=["lodging"],
                trust_signals=SourceTrustSignals(
                    freshness_days=10,
                    freshness_confidence=0.6,
                    commerciality=0.7,
                    editorial_independence=0.3,
                    operational_reliability=0.5,
                    review_consistency=0.5,
                ),
                quality_summary=QualityValueFitSummary(
                    quality_signal=0.25, value_signal=0.3, fit_signal=0.3, confidence=0.45
                ),
            ),
        ]
    )

    record = build_source_confidence_explanation(
        target_id="option:lodging-conflict-1",
        summary=summary,
    )

    assert record.machine_context["conflict_detected"] == "true"
    # The traveler-facing summary should mention disagreement somewhere.
    assert any("disagree" in fragment.lower() for fragment in record.human_summary)


def test_builder_rejects_non_summary_input() -> None:
    with pytest.raises(ValueError, match="SourceConfidenceSummary"):
        build_source_confidence_explanation(
            target_id="option:bad",
            summary="not a summary",  # type: ignore[arg-type]
        )


def test_builder_rejects_invalid_target_kind() -> None:
    summary = _strong_summary()
    with pytest.raises(ValueError, match="target_kind"):
        build_source_confidence_explanation(
            target_id="option:bad-kind",
            target_kind="city",  # not in EXPLANATION_TARGET_KINDS
            summary=summary,
        )


def test_builder_works_with_provenance_only_summary() -> None:
    reference = ProvenanceReference(
        provenance_id="prov-rail-1",
        source_id="official-rail",
        source_category="official_operational",
        subject_kind="option",
        subject_id="rail-option-1",
        contribution_kind="operational",
        summary="Service alert for the rail option.",
        freshness_days_at_capture=0,
        trust_snapshot=SourceTrustSignals(
            freshness_days=0,
            freshness_confidence=0.95,
            commerciality=0.3,
            operational_reliability=0.9,
            review_consistency=0.55,
        ),
    )
    summary = summarize_sources([reference])

    record = build_source_confidence_explanation(
        target_id="option:rail-prov-only",
        summary=summary,
    )

    assert record.record_type == "confidence"
    assert record.machine_context["contributing_source_count"] == "1"
    assert "official-rail" in record.source_refs
