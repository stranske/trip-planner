"""Tests for the deterministic source-quality scoring engine."""

from __future__ import annotations

from dataclasses import replace

import pytest

from trip_planner.app.services.inventory import (
    _build_inventory_assembly_input,
    assemble_inventory_bundles_for_trip,
)
from trip_planner.app.services.planner_tools import _commerciality_preference_from_runtime_state
from trip_planner.sources import (
    CONFIDENCE_LABELS,
    ProvenanceReference,
    QualityValueFitSummary,
    SourceConfidenceSummary,
    SourceQualityScore,
    SourceQualityScorer,
    SourceRecord,
    SourceTrustSignals,
    summarize_sources,
)


def _official_amtrak_source() -> SourceRecord:
    return SourceRecord(
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
    )


def _commercial_booking_source() -> SourceRecord:
    return SourceRecord(
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
    )


def _crowd_review_source() -> SourceRecord:
    return SourceRecord(
        source_id="tripadvisor-reviews",
        provider_name="TripAdvisor",
        display_name="TripAdvisor Reviews",
        category="ratings_reviews",
        coverage_scope="global",
        supported_option_kinds=["lodging", "activity"],
        trust_signals=SourceTrustSignals(
            freshness_days=20,
            freshness_confidence=0.7,
            commerciality=0.55,
            editorial_independence=0.45,
            operational_reliability=0.5,
            review_consistency=0.55,
        ),
        quality_summary=QualityValueFitSummary(
            quality_signal=0.6,
            value_signal=0.55,
            fit_signal=0.55,
            confidence=0.55,
        ),
    )


def _stale_editorial_source() -> SourceRecord:
    return SourceRecord(
        source_id="stale-city-guide",
        provider_name="Old Guide",
        display_name="Old City Guide",
        category="editorial",
        coverage_scope="regional",
        supported_option_kinds=["activity", "route"],
        trust_signals=SourceTrustSignals(
            freshness_days=540,  # ~18 months
            freshness_confidence=0.3,
            commerciality=0.2,
            editorial_independence=0.75,
            operational_reliability=0.45,
            review_consistency=0.4,
        ),
        quality_summary=QualityValueFitSummary(
            quality_signal=0.5,
            value_signal=0.5,
            fit_signal=0.5,
            confidence=0.4,
        ),
    )


def _conflicting_strong_review_source() -> SourceRecord:
    return SourceRecord(
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
            quality_signal=0.9,
            value_signal=0.8,
            fit_signal=0.7,
            confidence=0.8,
        ),
    )


def _conflicting_weak_review_source() -> SourceRecord:
    return SourceRecord(
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
            quality_signal=0.25,
            value_signal=0.3,
            fit_signal=0.3,
            confidence=0.45,
        ),
    )


def _sparse_unknown_source() -> SourceRecord:
    return SourceRecord(
        source_id="sparse-local-blog",
        provider_name="Local Blog",
        display_name="Local Blog",
        category="specialist_non_commercial",
        coverage_scope="local",
        supported_option_kinds=[],
        trust_signals=SourceTrustSignals(),
        quality_summary=QualityValueFitSummary(),
    )


def _commerciality_probe_source(source_id: str, commerciality: float) -> SourceRecord:
    return replace(
        _commercial_booking_source(),
        source_id=source_id,
        provider_name="Commerciality Probe",
        display_name="Commerciality Probe",
        trust_signals=SourceTrustSignals(
            freshness_days=2,
            freshness_confidence=0.9,
            commerciality=commerciality,
            editorial_independence=0.5,
            operational_reliability=0.75,
            review_consistency=0.6,
        ),
    )


def test_official_operational_source_scores_very_high() -> None:
    scorer = SourceQualityScorer()
    score = scorer.score_source(
        _official_amtrak_source(),
        intended_option_kind="rail",
    )

    assert isinstance(score, SourceQualityScore)
    assert score.confidence_label == "very_high"
    assert score.confidence >= 0.80
    assert "official" in score.tags
    assert "fresh" in score.tags
    assert "stale" not in score.tags
    assert "stranske" not in score.explanation_fragment  # sanity check on copy


def test_commercial_inventory_source_scores_high() -> None:
    scorer = SourceQualityScorer()
    score = scorer.score_source(
        _commercial_booking_source(),
        intended_option_kind="lodging",
    )

    assert score.confidence_label in {"high", "very_high"}
    assert score.confidence >= 0.65
    assert "commercial" in score.tags


def test_commerciality_preference_reorders_toward_non_commercial() -> None:
    scorer = SourceQualityScorer()
    non_commercial_source = _commerciality_probe_source("non-commercial-probe", 0.15)
    commercial_source = _commerciality_probe_source("commercial-probe", 0.85)

    non_commercial_preference_scores = {
        "non_commercial": scorer.score_source(
            non_commercial_source,
            commerciality_preference=0.1,
            intended_option_kind="lodging",
        ),
        "commercial": scorer.score_source(
            commercial_source,
            commerciality_preference=0.1,
            intended_option_kind="lodging",
        ),
    }
    commercial_preference_scores = {
        "non_commercial": scorer.score_source(
            non_commercial_source,
            commerciality_preference=0.9,
            intended_option_kind="lodging",
        ),
        "commercial": scorer.score_source(
            commercial_source,
            commerciality_preference=0.9,
            intended_option_kind="lodging",
        ),
    }

    assert (
        non_commercial_preference_scores["non_commercial"].confidence
        > non_commercial_preference_scores["commercial"].confidence
    )
    assert (
        commercial_preference_scores["commercial"].confidence
        > commercial_preference_scores["non_commercial"].confidence
    )


def test_crowd_review_source_scores_moderate() -> None:
    scorer = SourceQualityScorer()
    score = scorer.score_source(
        _crowd_review_source(),
        intended_option_kind="lodging",
    )

    # Crowd reviews should be moderate-confidence: useful but not authoritative.
    assert score.confidence_label in {"moderate", "high"}
    assert 0.45 <= score.confidence < 0.85
    assert "crowd-review" in score.tags
    assert "stale" not in score.tags


def _assert_stale_editorial_source_is_flagged_and_uncertain() -> None:
    scorer = SourceQualityScorer()
    source = replace(
        _stale_editorial_source(),
        trust_signals=SourceTrustSignals(
            freshness_days=90,
            freshness_confidence=0.1,
            commerciality=0.95,
            editorial_independence=0.05,
            operational_reliability=0.05,
            review_consistency=0.05,
        ),
        quality_summary=QualityValueFitSummary(
            quality_signal=0.2,
            value_signal=0.2,
            fit_signal=0.1,
            confidence=0.1,
        ),
    )
    score = scorer.score_source(source, intended_option_kind="activity")

    assert score.confidence_label in {"uncertain", "sparse"}
    assert "stale" in score.tags
    assert score.freshness_score < 0.3
    # Stale options should still be visible, not zero-confidence.
    assert score.confidence > 0.0


def test_stale_editorial_source_is_flagged_and_uncertain() -> None:
    _assert_stale_editorial_source_is_flagged_and_uncertain()


def test_low_freshness_confidence_marks_stale_editorial_source_uncertain() -> None:
    _assert_stale_editorial_source_is_flagged_and_uncertain()


def test_stale_editorial_source_deliberate_break_requires_freshness_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def freshness_score_without_confidence(
        self: SourceQualityScorer,
        trust: SourceTrustSignals,
    ) -> float:
        days = trust.freshness_days
        if days is None:
            base = 0.40
        else:
            base = self.FRESHNESS_HALF_LIFE_DAYS / (
                self.FRESHNESS_HALF_LIFE_DAYS + max(0, days)
            )
        return max(0.0, min(1.0, base))

    _assert_stale_editorial_source_is_flagged_and_uncertain()
    monkeypatch.setattr(
        SourceQualityScorer,
        "_freshness_score",
        freshness_score_without_confidence,
    )
    with pytest.raises(AssertionError):
        _assert_stale_editorial_source_is_flagged_and_uncertain()


def test_sparse_unknown_source_does_not_crash_and_is_low_confidence() -> None:
    scorer = SourceQualityScorer()
    score = scorer.score_source(_sparse_unknown_source())

    assert score.confidence_label in {"uncertain", "sparse", "moderate"}
    # No trust signals at all should still produce a bounded score.
    assert 0.0 <= score.confidence <= 1.0


def test_summarize_handles_empty_input_with_sparse_label() -> None:
    summary = summarize_sources([])

    assert isinstance(summary, SourceConfidenceSummary)
    assert summary.confidence == 0.0
    assert summary.confidence_label == "sparse"
    assert summary.contributing_source_count == 0
    assert summary.tags == ["sparse"]
    assert summary.conflict_detected is False
    assert summary.mutates_state is False
    assert summary.freshness_summary == "no source records"


def test_summarize_mixes_official_commercial_editorial_into_high_confidence() -> None:
    summary = summarize_sources(
        [
            _official_amtrak_source(),
            _commercial_booking_source(),
            _stale_editorial_source(),
        ],
        subject_kind="option",
    )

    assert summary.confidence_label in {"high", "very_high", "moderate"}
    assert summary.contributing_source_count == 3
    assert summary.category_counts["official_operational"] == 1
    assert summary.category_counts["commercial_inventory"] == 1
    assert summary.category_counts["editorial"] == 1
    # The stale editorial source must still contribute and be visible via tags.
    assert "stale" in summary.tags
    assert "official" in summary.tags
    assert summary.freshness_summary.startswith("freshness span")


def test_summarize_detects_conflict_between_strong_and_weak_signals() -> None:
    summary = summarize_sources(
        [
            _conflicting_strong_review_source(),
            _conflicting_weak_review_source(),
        ]
    )

    assert summary.conflict_detected is True
    assert "quality" in summary.conflict_summary
    assert "conflict" in summary.tags
    assert summary.contributing_source_count == 2
    # Sources disagreeing should depress fused confidence but not zero it.
    assert 0.0 < summary.confidence < 0.85
    assert any("disagree" in fragment.lower() for fragment in summary.explanation_fragments)


def test_summarize_single_source_marks_sparse() -> None:
    summary = summarize_sources([_commercial_booking_source()])

    assert summary.contributing_source_count == 1
    assert "sparse" in summary.tags
    # Single-source summaries still produce non-empty fragments.
    assert summary.explanation_fragments
    assert all(isinstance(fragment, str) and fragment for fragment in summary.explanation_fragments)


def test_summary_explanation_fragments_are_traveler_facing() -> None:
    summary = summarize_sources(
        [
            _official_amtrak_source(),
            _commercial_booking_source(),
        ]
    )

    joined = " ".join(summary.explanation_fragments).lower()
    # Should avoid raw IDs, internal field names, or developer terminology.
    assert "freshness_days" not in joined
    assert "operational_reliability" not in joined
    assert "source_id" not in joined


def test_summarize_is_deterministic_across_reorderings() -> None:
    records = [
        _official_amtrak_source(),
        _commercial_booking_source(),
        _crowd_review_source(),
    ]

    forward = summarize_sources(records)
    reverse = summarize_sources(list(reversed(records)))

    assert forward.confidence == reverse.confidence
    assert forward.confidence_label == reverse.confidence_label
    assert forward.tags == reverse.tags
    assert [s.source_id for s in forward.per_source_scores] == [
        s.source_id for s in reverse.per_source_scores
    ]


def test_scorer_accepts_provenance_reference_with_trust_snapshot() -> None:
    reference = ProvenanceReference(
        provenance_id="prov-1",
        source_id="booking-com",
        source_category="commercial_inventory",
        subject_kind="option",
        subject_id="lodging-option-1",
        contribution_kind="pricing",
        summary="Provided the working nightly rate and cancellation terms.",
        freshness_days_at_capture=1,
        trust_snapshot=SourceTrustSignals(
            freshness_days=1,
            freshness_confidence=0.9,
            commerciality=0.8,
            editorial_independence=0.1,
            operational_reliability=0.7,
            review_consistency=0.6,
        ),
        quality_value_fit=QualityValueFitSummary(
            quality_signal=0.7,
            value_signal=0.8,
            fit_signal=0.6,
            confidence=0.7,
        ),
    )

    scorer = SourceQualityScorer()
    score = scorer.score_provenance(reference, intended_option_kind="lodging")

    assert isinstance(score, SourceQualityScore)
    assert score.source_id == "booking-com"
    assert score.confidence_label in {"moderate", "high", "very_high"}


def test_summarize_accepts_mixed_record_and_provenance_inputs() -> None:
    reference = ProvenanceReference(
        provenance_id="prov-mixed",
        source_id="official-rail",
        source_category="official_operational",
        subject_kind="option",
        subject_id="rail-option-1",
        contribution_kind="operational",
        summary="Real-time service alerts on the candidate rail leg.",
        freshness_days_at_capture=0,
        trust_snapshot=SourceTrustSignals(
            freshness_days=0,
            freshness_confidence=0.95,
            commerciality=0.3,
            operational_reliability=0.9,
            review_consistency=0.55,
        ),
    )

    summary = summarize_sources([_commercial_booking_source(), reference])

    assert summary.contributing_source_count == 2
    # Mixed inputs should still produce a single bounded summary.
    assert summary.confidence_label in CONFIDENCE_LABELS
    assert summary.category_counts["commercial_inventory"] == 1
    assert summary.category_counts["official_operational"] == 1


def test_runtime_inventory_bundles_feed_source_quality_summary() -> None:
    assembly_input = _build_inventory_assembly_input(
        trip_id="trip-runtime-source-quality",
        trip_mode="leisure",
        primary_regions=("Kyoto",),
        start_date="2026-06-01",
        end_date="2026-06-05",
        duration_days=4,
        trip_title="Kyoto source quality smoke",
        traveler_party_kind="couple",
        traveler_count=2,
        allow_fixture_fallback=False,
    )

    bundles = assemble_inventory_bundles_for_trip(assembly_input=assembly_input)
    source_records = [record for bundle in bundles for record in bundle.source_records]
    summary = SourceQualityScorer().summarize(
        source_records,
        subject_kind="option",
        intended_option_kind="mixed",
    )

    assert bundles
    assert source_records
    assert summary.contributing_source_count == len(source_records)
    assert summary.confidence > 0
    assert summary.confidence_label in CONFIDENCE_LABELS
    assert summary.category_counts["commercial_inventory"] >= 1


def test_scorer_rejects_invalid_intended_option_kind() -> None:
    scorer = SourceQualityScorer()
    with pytest.raises(ValueError, match="intended_option_kind"):
        scorer.score_source(_commercial_booking_source(), intended_option_kind="spaceship")


def test_scorer_rejects_invalid_traveler_relevance_hint() -> None:
    scorer = SourceQualityScorer()
    with pytest.raises(ValueError, match="traveler_relevance_hint"):
        scorer.score_source(_commercial_booking_source(), traveler_relevance_hint=2.0)


def test_scorer_rejects_invalid_commerciality_preference() -> None:
    scorer = SourceQualityScorer()
    with pytest.raises(ValueError, match="commerciality_preference"):
        scorer.score_source(_commercial_booking_source(), commerciality_preference=2.0)


@pytest.mark.parametrize(
    ("runtime_state", "expected"),
    [
        ({"commerciality_preference": "0.25"}, 0.25),
        ({"commerciality_preference": ""}, None),
        ({"commerciality_preference": "low"}, None),
        ({"commerciality_preference": ["0.2"]}, None),
        ({"commerciality_preference": 1.5}, None),
    ],
)
def test_runtime_commerciality_preference_ignores_invalid_payloads(
    runtime_state: dict[str, object],
    expected: float | None,
) -> None:
    assert _commerciality_preference_from_runtime_state(runtime_state) == expected


def test_summary_rejects_invalid_subject_kind() -> None:
    with pytest.raises(ValueError, match="subject_kind"):
        summarize_sources([_commercial_booking_source()], subject_kind="city_vibe")


def test_summary_rejects_non_source_inputs() -> None:
    with pytest.raises(ValueError, match="SourceRecord or ProvenanceReference"):
        summarize_sources(["not a source"])  # type: ignore[list-item]


def test_summary_round_trip_to_dict_preserves_fields() -> None:
    summary = summarize_sources([_official_amtrak_source()])
    payload = summary.to_dict()

    assert payload["subject_kind"] == "option"
    assert payload["confidence_label"] == summary.confidence_label
    assert payload["per_source_scores"][0]["source_id"] == "amtrak-service-alerts"
    assert payload["mutates_state"] is False
