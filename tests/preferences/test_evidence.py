from trip_planner.preferences.evidence import (
    ContradictionMarker,
    OptionEvidence,
    PreferenceEvidence,
)


def test_preference_evidence_serializes_option_and_contradictions() -> None:
    record = PreferenceEvidence(
        id="ev-001",
        evidence_type="option_selection",
        source_type="option_menu",
        affected_dimensions=["movement_vs_friction"],
        affected_hybrid_factors=["route_modes"],
        signal_direction="positive",
        confidence_hint=0.8,
        salience_hint=0.9,
        sequence=4,
        note="Traveler chose the rail-heavy route bundle.",
        option_evidence=OptionEvidence(
            option_set_id="set-1",
            option_id="opt-rail",
            option_kind="mixed_bundle",
            presented_option_ids=["opt-rail", "opt-fly", "opt-road"],
        ),
        contradictions=[
            ContradictionMarker(
                previous_evidence_id="ev-000",
                reason="Selection contradicts earlier preference for direct flights.",
                weakening_strength=0.7,
            )
        ],
    )

    payload = record.to_dict()

    assert payload["option_evidence"]["option_id"] == "opt-rail"
    assert payload["contradictions"][0]["previous_evidence_id"] == "ev-000"


def test_preference_evidence_requires_time_or_sequence() -> None:
    try:
        PreferenceEvidence(
            id="ev-002",
            evidence_type="direct_statement",
            source_type="user_message",
            affected_dimensions=["nature_vs_culture"],
        )
    except ValueError as exc:
        assert "observed_at or sequence" in str(exc)
    else:
        raise AssertionError("Evidence should require an ordering signal")


def test_option_evidence_required_for_option_selection() -> None:
    try:
        PreferenceEvidence(
            id="ev-003",
            evidence_type="option_selection",
            source_type="option_menu",
            affected_dimensions=["breadth_vs_depth"],
            sequence=2,
        )
    except ValueError as exc:
        assert "option_evidence" in str(exc)
    else:
        raise AssertionError("Option evidence should be required for selection events")


def test_preference_evidence_rejects_unknown_dimension() -> None:
    try:
        PreferenceEvidence(
            id="ev-004",
            evidence_type="direct_statement",
            source_type="user_message",
            affected_dimensions=["unknown_dimension"],
            sequence=1,
        )
    except ValueError as exc:
        assert "unsupported dimensions" in str(exc)
    else:
        raise AssertionError("Unknown dimensions should fail validation")
