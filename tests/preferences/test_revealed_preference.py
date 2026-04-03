from copy import deepcopy

from tests.preferences.fixture_corpus import load_fixture_corpus
from trip_planner.preferences.models import Anchor
from trip_planner.preferences.revealed_preference import (
    REVEALED_PREFERENCE_FALLBACK_SEQUENCE,
    RevealedPreferenceSignal,
    build_revealed_preference_update,
)


def test_revealed_preference_update_emits_option_evidence() -> None:
    fixture = next(item for item in load_fixture_corpus() if item.id == "discovery-wanderer")
    signal = RevealedPreferenceSignal(
        signal_id="signal-1",
        trip_stage="inventory_selection",
        reaction_type="selected",
        option_set_id="options-1",
        option_id="option-1",
        option_kind="destination_bundle",
        signal_strength=0.8,
        dimension_biases={
            "structure_vs_elasticity": 0.7,
            "iconic_vs_discovery": 0.8,
        },
        hybrid_biases={"rest": 0.4},
        summary="Traveler chose the loose-structure discovery set over the fixed landmark schedule.",
    )

    update = build_revealed_preference_update(fixture.profile, signal)

    assert update.transient is False
    assert update.blocked_overwrites == []
    assert update.emitted_evidence[0].evidence_type == "option_selection"
    assert update.emitted_evidence[0].sequence == REVEALED_PREFERENCE_FALLBACK_SEQUENCE
    assert set(update.emitted_evidence[0].affected_dimensions) == {
        "structure_vs_elasticity",
        "iconic_vs_discovery",
    }


def test_revealed_preference_guardrail_blocks_overwrite_of_stable_dimension() -> None:
    fixture = next(item for item in load_fixture_corpus() if item.id == "urban-historian")
    profile = deepcopy(fixture.profile)
    profile.tradeoff_dimensions["breadth_vs_depth"].salience = 0.92
    profile.tradeoff_dimensions["breadth_vs_depth"].stability = 0.9

    signal = RevealedPreferenceSignal(
        signal_id="signal-2",
        trip_stage="inventory_selection",
        reaction_type="selected",
        option_set_id="options-2",
        option_id="option-2",
        option_kind="destination_bundle",
        signal_strength=0.9,
        dimension_biases={"breadth_vs_depth": -0.9},
        summary="Traveler clicked a wider multi-city option once.",
    )

    update = build_revealed_preference_update(profile, signal)

    assert update.blocked_overwrites == ["breadth_vs_depth"]
    assert update.emitted_evidence[0].signal_direction == "contradiction"
    assert "anchors" in update.protected_targets or "hard_constraints" in update.protected_targets


def test_revealed_preference_marks_transient_clicks() -> None:
    fixture = next(item for item in load_fixture_corpus() if item.id == "food-splurger")
    signal = RevealedPreferenceSignal(
        signal_id="signal-3",
        trip_stage="inventory_selection",
        reaction_type="ignored",
        option_set_id="options-3",
        option_id="option-3",
        option_kind="lodging",
        signal_strength=0.3,
        dimension_biases={"self_reliance_vs_convenience": 0.4},
        summary="Traveler glanced at a hotel but did not meaningfully engage.",
    )

    update = build_revealed_preference_update(fixture.profile, signal)

    assert update.transient is True
    assert update.emitted_evidence[0].confidence_hint < 0.2
    assert any("transient" in note for note in update.notes)


def test_revealed_preference_protects_all_active_constraint_and_anchor_groups() -> None:
    fixture = next(item for item in load_fixture_corpus() if item.id == "food-splurger")
    profile = deepcopy(fixture.profile)
    profile.hard_constraints.budget_ceiling = 2500.0
    profile.anchors["place_anchors"] = []
    profile.anchors["experience_anchors"] = []
    profile.anchors["calendar_anchors"] = []
    profile.anchors["mode_anchors"] = [
        Anchor(
            type="transport_mode",
            label="Rail-first",
            strength=0.7,
            flexibility=0.35,
            notes="Synthetic non-legacy anchor for regression coverage.",
        )
    ]

    signal = RevealedPreferenceSignal(
        signal_id="signal-4",
        trip_stage="inventory_selection",
        reaction_type="selected",
        option_set_id="options-4",
        option_id="option-4",
        option_kind="activity",
        signal_strength=0.8,
        dimension_biases={"movement_vs_friction": 0.5},
        summary="Traveler picked an activity that should not clear active guardrails.",
    )

    update = build_revealed_preference_update(profile, signal)

    assert "hard_constraints" in update.protected_targets
    assert "anchors" in update.protected_targets
