from trip_planner.preferences.models import (
    Anchor,
    BudgetModel,
    DateWindow,
    DurationBounds,
    EvidenceSummary,
    HardConstraints,
    HybridFactor,
    InteractionRule,
    LeisurePreferenceProfile,
    TensionFlag,
    TradeoffDimension,
    TripFrame,
)
from trip_planner.preferences.schema import ANCHOR_GROUPS, HYBRID_FACTOR_KEYS, TRADEOFF_DIMENSION_KEYS


def _make_profile() -> LeisurePreferenceProfile:
    anchors = {group: [] for group in ANCHOR_GROUPS}
    anchors["place_anchors"] = [
        Anchor(type="place", label="Kyoto", strength=0.9, flexibility=0.2)
    ]
    return LeisurePreferenceProfile(
        trip_frame=TripFrame(
            duration_days=28,
            traveler_party="pair",
            season_window=["October"],
            trip_stage="first_visit",
        ),
        hard_constraints=HardConstraints(
            date_window=DateWindow(start="2025-10-01", end="2025-10-28"),
            duration_bounds=DurationBounds(min_days=21, max_days=35),
            must_include_places=["Kyoto"],
        ),
        anchors=anchors,
        budget_model=BudgetModel(
            total_budget_sensitivity=0.4,
            spending_priorities={"lodging_location": 0.8},
        ),
        tradeoff_dimensions={
            key: TradeoffDimension(value=0.0, confidence=0.2, salience=0.2, stability=0.2)
            for key in TRADEOFF_DIMENSION_KEYS
        },
        hybrid_factors={
            key: HybridFactor(mode="tradeoff")
            for key in HYBRID_FACTOR_KEYS
        },
        interaction_rules=[
            InteractionRule(
                id="breadth_x_recovery",
                dimensions=["breadth_vs_depth", "recovery_vs_intensity"],
                strength=0.8,
                priority=0.8,
            )
        ],
        tension_flags=[
            TensionFlag(
                id="too_many_moves",
                severity=0.6,
                description="Move density is too high for the desired trip rhythm.",
            )
        ],
        evidence_summary=EvidenceSummary(
            sources={"direct_statements": ["Traveler wants a slow pace."]},
            confidence_notes=["Initial profile only."],
        ),
    )


def test_profile_serializes_with_canonical_keys() -> None:
    profile = _make_profile()

    serialized = profile.to_dict()

    assert serialized["profile_kind"] == "leisure"
    assert set(serialized["tradeoff_dimensions"]) == set(TRADEOFF_DIMENSION_KEYS)
    assert set(serialized["hybrid_factors"]) == set(HYBRID_FACTOR_KEYS)
    assert set(serialized["anchors"]) == set(ANCHOR_GROUPS)
    assert serialized["hard_constraints"]["must_include_places"] == ["Kyoto"]


def test_trip_frame_rejects_invalid_party() -> None:
    try:
        TripFrame(traveler_party="enterprise")
    except ValueError as exc:
        assert "traveler_party" in str(exc)
    else:
        raise AssertionError("TripFrame should reject unsupported traveler parties")


def test_hard_constraints_reject_inverted_duration_bounds() -> None:
    try:
        DurationBounds(min_days=20, max_days=10)
    except ValueError as exc:
        assert "min_days" in str(exc)
    else:
        raise AssertionError("DurationBounds should reject inverted bounds")


def test_anchor_rejects_out_of_range_strength() -> None:
    try:
        Anchor(type="place", label="Rome", strength=1.5, flexibility=0.2)
    except ValueError as exc:
        assert "strength" in str(exc)
    else:
        raise AssertionError("Anchor should reject invalid strength values")


def test_budget_model_rejects_invalid_spending_priority() -> None:
    try:
        BudgetModel(total_budget_sensitivity=0.5, spending_priorities={"food": 1.5})
    except ValueError as exc:
        assert "spending_priorities" in str(exc)
    else:
        raise AssertionError("BudgetModel should reject invalid spending priorities")


def test_tradeoff_dimension_rejects_invalid_scope() -> None:
    try:
        TradeoffDimension(scope="unknown")
    except ValueError as exc:
        assert "scope" in str(exc)
    else:
        raise AssertionError("TradeoffDimension should reject invalid scopes")


def test_hybrid_factor_rejects_invalid_mode() -> None:
    try:
        HybridFactor(mode="dynamic")
    except ValueError as exc:
        assert "mode" in str(exc)
    else:
        raise AssertionError("HybridFactor should reject invalid modes")


def test_interaction_rule_rejects_invalid_priority() -> None:
    try:
        InteractionRule(id="rule", dimensions=["movement_vs_friction"], priority=1.2)
    except ValueError as exc:
        assert "priority" in str(exc)
    else:
        raise AssertionError("InteractionRule should reject invalid priority values")


def test_evidence_summary_rejects_non_string_sources() -> None:
    try:
        EvidenceSummary(sources={"direct_statements": ["ok", 3]})  # type: ignore[list-item]
    except ValueError as exc:
        assert "sources" in str(exc)
    else:
        raise AssertionError("EvidenceSummary should reject non-string source values")


def test_profile_rejects_missing_dimension_keys() -> None:
    profile = _make_profile()
    tradeoff_dimensions = dict(profile.tradeoff_dimensions)
    tradeoff_dimensions.pop("nature_vs_culture")

    try:
        LeisurePreferenceProfile(
            trip_frame=profile.trip_frame,
            hard_constraints=profile.hard_constraints,
            anchors=profile.anchors,
            budget_model=profile.budget_model,
            tradeoff_dimensions=tradeoff_dimensions,
            hybrid_factors=profile.hybrid_factors,
            interaction_rules=profile.interaction_rules,
            tension_flags=profile.tension_flags,
            evidence_summary=profile.evidence_summary,
        )
    except ValueError as exc:
        assert "tradeoff_dimensions" in str(exc)
    else:
        raise AssertionError("Profile should reject missing canonical dimension keys")


def test_profile_rejects_missing_anchor_groups() -> None:
    profile = _make_profile()
    anchors = dict(profile.anchors)
    anchors.pop("calendar_anchors")

    try:
        LeisurePreferenceProfile(
            trip_frame=profile.trip_frame,
            hard_constraints=profile.hard_constraints,
            anchors=anchors,
            budget_model=profile.budget_model,
            tradeoff_dimensions=profile.tradeoff_dimensions,
            hybrid_factors=profile.hybrid_factors,
            interaction_rules=profile.interaction_rules,
            tension_flags=profile.tension_flags,
            evidence_summary=profile.evidence_summary,
        )
    except ValueError as exc:
        assert "anchors" in str(exc)
    else:
        raise AssertionError("Profile should reject missing anchor groups")
