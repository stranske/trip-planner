from trip_planner.sources import (
    ProvenanceReference,
    QualityValueFitSummary,
    SourceTrustSignals,
)


def test_provenance_reference_supports_option_explanation() -> None:
    reference = ProvenanceReference(
        provenance_id="prov-lodging-1",
        source_id="booking-dot-com",
        source_category="commercial_inventory",
        subject_kind="option",
        subject_id="lodging-option-1",
        contribution_kind="pricing",
        summary="Provided the working nightly rate and cancellation terms.",
        locator="https://booking.example/hotel/123",
        captured_at="2026-03-15T10:00:00Z",
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
            confidence=0.75,
            notes=["Useful for price realism, not final taste judgment."],
        ),
        notes=["Attach this reference to the eventual LodgingOption source_refs list."],
    )

    payload = reference.to_dict()

    assert payload["subject_kind"] == "option"
    assert payload["quality_value_fit"]["value_signal"] == 0.8
    assert payload["trust_snapshot"]["freshness_confidence"] == 0.9


def test_provenance_reference_supports_policy_ready_proposal() -> None:
    reference = ProvenanceReference(
        provenance_id="prov-proposal-1",
        source_id="concur-travel",
        source_category="managed_travel_policy",
        subject_kind="proposal",
        subject_id="proposal-1",
        contribution_kind="policy",
        summary="Confirmed the chosen fare and hotel were inside approved channels.",
        locator="policy://org/demo/travel",
        captured_at="2026-03-15T12:00:00Z",
        freshness_days_at_capture=0,
        notes=[
            "Retain this record in the approval packet for downstream audit trails."
        ],
    )

    assert reference.subject_kind == "proposal"
    assert reference.contribution_kind == "policy"


def test_provenance_reference_rejects_invalid_subject_kind() -> None:
    try:
        ProvenanceReference(
            provenance_id="prov-bad-subject",
            source_id="tripadvisor",
            source_category="ratings_reviews",
            subject_kind="city_vibe",
            subject_id="destination-1",
            contribution_kind="review",
            summary="Invalid subject kind.",
        )
    except ValueError as exc:
        assert "subject_kind" in str(exc)
    else:
        raise AssertionError("ProvenanceReference should reject invalid subject kinds")


def test_provenance_reference_rejects_invalid_contribution_kind() -> None:
    try:
        ProvenanceReference(
            provenance_id="prov-bad-contribution",
            source_id="tripadvisor",
            source_category="ratings_reviews",
            subject_kind="destination",
            subject_id="destination-1",
            contribution_kind="vibes",
            summary="Invalid contribution kind.",
        )
    except ValueError as exc:
        assert "contribution_kind" in str(exc)
    else:
        raise AssertionError(
            "ProvenanceReference should reject invalid contribution kinds"
        )


def test_provenance_reference_rejects_negative_capture_freshness() -> None:
    try:
        ProvenanceReference(
            provenance_id="prov-negative-freshness",
            source_id="city-guide",
            source_category="editorial",
            subject_kind="destination",
            subject_id="destination-2",
            contribution_kind="editorial",
            summary="Negative freshness is invalid.",
            freshness_days_at_capture=-2,
        )
    except ValueError as exc:
        assert "freshness_days_at_capture" in str(exc)
    else:
        raise AssertionError(
            "ProvenanceReference should reject negative freshness_days_at_capture"
        )
