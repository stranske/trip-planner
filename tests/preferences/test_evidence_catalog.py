from trip_planner.preferences.evidence import PreferenceEvidence
from trip_planner.preferences.evidence_catalog import (
    ANCHOR_SIGNAL_GUIDANCE,
    support_for_dimension,
    support_for_hybrid_factor,
    validate_evidence_support,
)


def test_support_registry_exposes_strength_levels() -> None:
    assert support_for_dimension("movement_vs_friction", "option_selection") == "strong"
    assert support_for_hybrid_factor("food", "option_rejection") == "strong"
    assert "Anchor signals" in ANCHOR_SIGNAL_GUIDANCE


def test_validate_evidence_support_accepts_valid_tradeoff_path() -> None:
    record = PreferenceEvidence(
        id="ev-101",
        evidence_type="forced_tradeoff_choice",
        source_type="scenario_prompt",
        affected_dimensions=["breadth_vs_depth"],
        sequence=6,
        note="Traveler chose fewer stops to get more time in each city.",
    )

    validate_evidence_support(record)


def test_validate_evidence_support_accepts_valid_anchor_path() -> None:
    record = PreferenceEvidence(
        id="ev-102",
        evidence_type="anchor_declaration",
        source_type="structured_input",
        anchor_groups=["experience_anchors"],
        sequence=1,
        note="Food is one of the primary reasons for the trip.",
    )

    validate_evidence_support(record)


def test_validate_evidence_support_rejects_invalid_dimension_combo() -> None:
    try:
        PreferenceEvidence(
            id="ev-103",
            evidence_type="hard_constraint_declaration",
            source_type="structured_input",
            affected_dimensions=["social_energy_vs_solitude"],
            sequence=1,
            note="This should not work for a normal tradeoff dimension.",
        )
    except ValueError as exc:
        assert "not valid evidence for dimension" in str(exc)
    else:
        raise AssertionError("Invalid dimension evidence combinations should fail clearly")


def test_validate_evidence_support_rejects_invalid_hybrid_combo() -> None:
    try:
        PreferenceEvidence(
            id="ev-104",
            evidence_type="hard_constraint_declaration",
            source_type="structured_input",
            affected_hybrid_factors=["music"],
            sequence=3,
        )
    except ValueError as exc:
        assert "not valid evidence for hybrid factor" in str(exc)
    else:
        raise AssertionError("Invalid hybrid evidence combinations should fail clearly")
