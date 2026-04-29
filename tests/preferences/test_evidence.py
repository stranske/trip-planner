from trip_planner.preferences.evidence import (
    ContradictionMarker,
    OptionEvidence,
    PreferenceEvidence,
    baseline_confidence_hint,
    evidence_signal_family,
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


def test_option_evidence_requires_selected_option_in_presented_list() -> None:
    try:
        OptionEvidence(
            option_set_id="set-2",
            option_id="opt-hotel",
            option_kind="lodging",
            presented_option_ids=["opt-hostel", "opt-villa"],
        )
    except ValueError as exc:
        assert "must include option_id" in str(exc)
    else:
        raise AssertionError("Presented option lists should include the selected option")


def test_preference_evidence_rejects_option_payload_on_non_option_types() -> None:
    try:
        PreferenceEvidence(
            id="ev-005",
            evidence_type="direct_statement",
            source_type="user_message",
            affected_dimensions=["nature_vs_culture"],
            sequence=3,
            option_evidence=OptionEvidence(
                option_set_id="set-1",
                option_id="opt-rail",
                option_kind="mixed_bundle",
                presented_option_ids=["opt-rail"],
            ),
        )
    except ValueError as exc:
        assert "only allowed" in str(exc)
    else:
        raise AssertionError("Non-option evidence should reject option payloads")


def test_preference_evidence_rejects_invalid_support_path_at_construction() -> None:
    try:
        PreferenceEvidence(
            id="ev-006",
            evidence_type="hard_constraint_declaration",
            source_type="structured_input",
            affected_dimensions=["social_energy_vs_solitude"],
            sequence=5,
        )
    except ValueError as exc:
        assert "not valid evidence for dimension" in str(exc)
    else:
        raise AssertionError("Invalid support paths should fail during construction")


def test_option_rejection_cannot_have_positive_signal_direction() -> None:
    try:
        PreferenceEvidence(
            id="ev-007",
            evidence_type="option_rejection",
            source_type="option_menu",
            affected_dimensions=["movement_vs_friction"],
            sequence=8,
            signal_direction="positive",
            option_evidence=OptionEvidence(
                option_set_id="set-3",
                option_id="opt-bus",
                option_kind="transport",
                presented_option_ids=["opt-bus", "opt-rail"],
            ),
        )
    except ValueError as exc:
        assert "cannot use a positive signal_direction" in str(exc)
    else:
        raise AssertionError("Option rejection should not allow positive signal direction")


def test_signal_family_classification_for_explicit_revealed_and_default() -> None:
    assert (
        evidence_signal_family(evidence_type="direct_statement", source_type="user_message")
        == "explicit_answer"
    )
    assert (
        evidence_signal_family(evidence_type="option_selection", source_type="option_menu")
        == "revealed_behavior"
    )
    assert (
        evidence_signal_family(
            evidence_type="scenario_reaction", source_type="planner_inference_review"
        )
        == "default_assumption"
    )


def test_signal_family_classifies_scenario_reactions_as_revealed_behavior() -> None:
    # scenario_reaction is behavioral evidence (the user reacted to a presented scenario);
    # it should not be reclassified as an explicit_answer just because the source_type is
    # 'scenario_prompt'.
    assert (
        evidence_signal_family(evidence_type="scenario_reaction", source_type="scenario_prompt")
        == "revealed_behavior"
    )


def test_signal_family_treats_planner_inference_as_default_for_any_evidence_type() -> None:
    assert (
        evidence_signal_family(
            evidence_type="option_selection", source_type="planner_inference_review"
        )
        == "default_assumption"
    )


def test_baseline_confidence_prefers_revealed_then_explicit_then_default() -> None:
    explicit = baseline_confidence_hint(
        evidence_type="direct_statement",
        source_type="user_message",
    )
    revealed = baseline_confidence_hint(
        evidence_type="option_selection",
        source_type="option_menu",
    )
    default = baseline_confidence_hint(
        evidence_type="scenario_reaction",
        source_type="planner_inference_review",
    )
    assert revealed > explicit > default
