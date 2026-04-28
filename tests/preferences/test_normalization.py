"""Tests for questionnaire normalization: deterministic canonical dimensions."""

import json
import pathlib

import pytest

from trip_planner.preferences.normalization import (
    NormalizedPreferences,
    _scale_to_axis,
    _scale_to_probability,
    normalize,
)
from trip_planner.preferences.schema import HYBRID_FACTOR_KEYS, TRADEOFF_DIMENSION_KEYS

_FIXTURE_PATH = (
    pathlib.Path(__file__).parent.parent
    / "fixtures"
    / "preferences"
    / "questionnaire_responses.json"
)


def _load_fixture(fixture_id: str) -> dict:
    data = json.loads(_FIXTURE_PATH.read_text())
    return next(f for f in data["fixtures"] if f["id"] == fixture_id)


# ── Scale conversion helpers ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "rating, expected",
    [
        (1, -1.0),
        (2, -0.5),
        (3, 0.0),
        (4, 0.5),
        (5, 1.0),
    ],
)
def test_scale_to_axis_converts_correctly(rating: int, expected: float) -> None:
    assert _scale_to_axis(rating) == pytest.approx(expected)


@pytest.mark.parametrize(
    "rating, expected",
    [
        (1, 0.0),
        (3, 0.5),
        (5, 1.0),
    ],
)
def test_scale_to_probability_converts_correctly(rating: int, expected: float) -> None:
    assert _scale_to_probability(rating) == pytest.approx(expected)


# ── Normalize: complete response fixture ─────────────────────────────────────


def test_normalize_complete_returns_normalized_preferences() -> None:
    fx = _load_fixture("complete")
    result = normalize(fx["answers"])
    assert isinstance(result, NormalizedPreferences)


def test_normalize_complete_trip_frame_fields() -> None:
    fx = _load_fixture("complete")
    result = normalize(fx["answers"])
    expected = fx["expected"]
    assert result.traveler_party == expected["traveler_party"]
    assert result.trip_stage == expected["trip_stage"]
    assert result.duration_days == expected["duration_days"]


def test_normalize_complete_all_11_tradeoff_dimensions_present() -> None:
    fx = _load_fixture("complete")
    result = normalize(fx["answers"])
    assert set(result.tradeoff_values) == set(TRADEOFF_DIMENSION_KEYS)
    assert set(result.tradeoff_confidence) == set(TRADEOFF_DIMENSION_KEYS)


def test_normalize_complete_tradeoff_values_match_expected() -> None:
    fx = _load_fixture("complete")
    result = normalize(fx["answers"])
    for dim, expected_val in fx["expected"]["tradeoff_values"].items():
        assert result.tradeoff_values[dim] == pytest.approx(
            expected_val
        ), f"Dimension {dim!r}: expected {expected_val}, got {result.tradeoff_values[dim]}"


def test_normalize_complete_all_4_hybrid_factors_present() -> None:
    fx = _load_fixture("complete")
    result = normalize(fx["answers"])
    assert set(result.hybrid_salience) == set(HYBRID_FACTOR_KEYS)


def test_normalize_complete_budget_and_splurge() -> None:
    fx = _load_fixture("complete")
    result = normalize(fx["answers"])
    assert result.budget_sensitivity == pytest.approx(fx["expected"]["budget_sensitivity"])
    assert result.splurge_allowed is fx["expected"]["splurge_allowed"]


def test_normalize_complete_route_modes() -> None:
    fx = _load_fixture("complete")
    result = normalize(fx["answers"])
    assert result.route_modes == fx["expected"]["route_modes"]


def test_normalize_complete_explicit_answers_get_high_confidence() -> None:
    fx = _load_fixture("complete")
    result = normalize(fx["answers"])
    for dim in TRADEOFF_DIMENSION_KEYS:
        if f"q_{dim}" in fx["answers"] or any(q.replace("q_", "") == dim for q in fx["answers"]):
            # Explicitly answered questions should have confidence 0.7
            assert result.tradeoff_confidence[dim] == pytest.approx(
                0.7
            ), f"Dimension {dim!r} was answered, expected confidence 0.7"


def test_normalize_is_deterministic() -> None:
    fx = _load_fixture("complete")
    r1 = normalize(fx["answers"])
    r2 = normalize(fx["answers"])
    assert r1.tradeoff_values == r2.tradeoff_values
    assert r1.tradeoff_confidence == r2.tradeoff_confidence
    assert r1.budget_sensitivity == r2.budget_sensitivity


# ── Normalize: partial response fixture ──────────────────────────────────────


def test_normalize_partial_succeeds_with_only_required_fields() -> None:
    fx = _load_fixture("partial")
    result = normalize(fx["answers"])
    assert isinstance(result, NormalizedPreferences)


def test_normalize_partial_defaults_trip_stage() -> None:
    fx = _load_fixture("partial")
    result = normalize(fx["answers"])
    assert result.trip_stage == fx["expected"]["trip_stage"]


def test_normalize_partial_duration_days_is_none() -> None:
    fx = _load_fixture("partial")
    result = normalize(fx["answers"])
    assert result.duration_days is None


def test_normalize_partial_all_dimensions_default_to_neutral() -> None:
    fx = _load_fixture("partial")
    result = normalize(fx["answers"])
    expected_vals = fx["expected"]["tradeoff_values"]
    for dim, val in expected_vals.items():
        assert result.tradeoff_values[dim] == pytest.approx(
            val
        ), f"Dimension {dim!r}: expected default {val}, got {result.tradeoff_values[dim]}"


def test_normalize_partial_unanswered_dimensions_get_low_confidence() -> None:
    fx = _load_fixture("partial")
    result = normalize(fx["answers"])
    for dim in TRADEOFF_DIMENSION_KEYS:
        assert result.tradeoff_confidence[dim] == pytest.approx(
            0.1
        ), f"Unanswered dimension {dim!r} should have low confidence 0.1"


def test_normalize_partial_splurge_defaults_false() -> None:
    fx = _load_fixture("partial")
    result = normalize(fx["answers"])
    assert result.splurge_allowed is False


def test_normalize_partial_route_modes_defaults_empty() -> None:
    fx = _load_fixture("partial")
    result = normalize(fx["answers"])
    assert result.route_modes == []


# ── Normalize: contradictory response fixture ─────────────────────────────────


def test_normalize_contradictory_succeeds() -> None:
    """Contradictory answers are valid input — normalization must not reject them."""
    fx = _load_fixture("contradictory")
    result = normalize(fx["answers"])
    assert isinstance(result, NormalizedPreferences)


def test_normalize_contradictory_breadth_maps_to_minus_one() -> None:
    fx = _load_fixture("contradictory")
    result = normalize(fx["answers"])
    assert result.tradeoff_values["breadth_vs_depth"] == pytest.approx(-1.0)


def test_normalize_contradictory_recovery_maps_to_plus_one() -> None:
    fx = _load_fixture("contradictory")
    result = normalize(fx["answers"])
    assert result.tradeoff_values["recovery_vs_intensity"] == pytest.approx(1.0)


def test_normalize_contradictory_breadth_recovery_tension_detectable() -> None:
    """Confirm the values that trigger breadth_x_recovery interaction rule are present."""
    fx = _load_fixture("contradictory")
    result = normalize(fx["answers"])
    # breadth_vs_depth <= -0.4 and recovery_vs_intensity >= 0.4 triggers the rule
    assert result.tradeoff_values["breadth_vs_depth"] <= -0.4
    assert result.tradeoff_values["recovery_vs_intensity"] >= 0.4


# ── Normalize: invalid responses raise ValueError ────────────────────────────


def test_normalize_missing_required_raises() -> None:
    fx = _load_fixture("invalid_missing_required")
    with pytest.raises(ValueError) as exc_info:
        normalize(fx["answers"])
    msg = str(exc_info.value)
    for fragment in fx["expected_error_fragments"]:
        assert fragment in msg, f"Expected error fragment {fragment!r} not in message: {msg}"


def test_normalize_out_of_range_raises() -> None:
    fx = _load_fixture("invalid_out_of_range")
    with pytest.raises(ValueError) as exc_info:
        normalize(fx["answers"])
    msg = str(exc_info.value)
    for fragment in fx["expected_error_fragments"]:
        assert fragment in msg


def test_normalize_wrong_type_raises() -> None:
    fx = _load_fixture("invalid_wrong_type")
    with pytest.raises(ValueError) as exc_info:
        normalize(fx["answers"])
    msg = str(exc_info.value)
    for fragment in fx["expected_error_fragments"]:
        assert fragment in msg


def test_normalize_unknown_choice_raises() -> None:
    fx = _load_fixture("invalid_unknown_choice")
    with pytest.raises(ValueError) as exc_info:
        normalize(fx["answers"])
    msg = str(exc_info.value)
    for fragment in fx["expected_error_fragments"]:
        assert fragment in msg


def test_normalize_unknown_question_id_raises() -> None:
    fx = _load_fixture("invalid_unknown_question_id")
    with pytest.raises(ValueError) as exc_info:
        normalize(fx["answers"])
    msg = str(exc_info.value)
    for fragment in fx["expected_error_fragments"]:
        assert fragment in msg


def test_normalize_bad_route_mode_raises() -> None:
    fx = _load_fixture("invalid_bad_route_mode")
    with pytest.raises(ValueError) as exc_info:
        normalize(fx["answers"])
    msg = str(exc_info.value)
    for fragment in fx["expected_error_fragments"]:
        assert fragment in msg


# ── Normalize: route_modes salience ──────────────────────────────────────────


def test_route_modes_salience_high_when_modes_provided() -> None:
    result = normalize(
        {
            "q_traveler_party": "solo",
            "q_budget_sensitivity": 3,
            "q_route_modes_preference": ["rail"],
        }
    )
    assert result.hybrid_salience["route_modes"] == pytest.approx(0.8)


def test_route_modes_salience_low_when_no_modes_provided() -> None:
    result = normalize(
        {
            "q_traveler_party": "solo",
            "q_budget_sensitivity": 3,
        }
    )
    assert result.hybrid_salience["route_modes"] == pytest.approx(0.2)
