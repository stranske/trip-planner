"""Tests for the questionnaire schema: ids, answer types, allowed values, defaults, validation."""

import pytest

from trip_planner.preferences.questionnaire import (
    QUESTION_IDS,
    QUESTION_REGISTRY,
    ROUTE_MODE_VALUES,
    QuestionSpec,
    validate_response,
)
from trip_planner.preferences.schema import TRAVELER_PARTIES, TRIP_STAGES

# ── Registry shape ────────────────────────────────────────────────────────────


def test_registry_covers_all_11_dimension_questions() -> None:
    dimension_qs = [
        q
        for q in QUESTION_IDS
        if q.startswith("q_")
        and "salience" not in q
        and q
        not in (
            "q_traveler_party",
            "q_trip_stage",
            "q_duration_days",
            "q_budget_sensitivity",
            "q_splurge_allowed",
            "q_route_modes_preference",
        )
    ]
    assert len(dimension_qs) == 11, f"Expected 11 dimension questions, found: {dimension_qs}"


def test_registry_ids_match_spec_ids() -> None:
    for key, spec in QUESTION_REGISTRY.items():
        assert key == spec.id, f"Registry key {key!r} does not match spec.id {spec.id!r}"


def test_required_questions_have_none_default() -> None:
    for spec in QUESTION_REGISTRY.values():
        if spec.required:
            assert spec.default is None, f"Required question '{spec.id}' should have default=None"


def test_optional_questions_have_non_none_default_or_none_is_acceptable() -> None:
    for spec in QUESTION_REGISTRY.values():
        if not spec.required:
            # default=None is valid for optional integer questions (means "not set")
            if spec.answer_type == "integer":
                continue
            if spec.answer_type == "text_list":
                assert isinstance(
                    spec.default, list
                ), f"Optional text_list question '{spec.id}' must default to a list"
            elif spec.answer_type == "scale":
                assert isinstance(
                    spec.default, int
                ), f"Optional scale question '{spec.id}' must default to an int"


def test_scale_questions_have_min_max() -> None:
    for spec in QUESTION_REGISTRY.values():
        if spec.answer_type == "scale":
            assert (
                spec.min_value is not None and spec.max_value is not None
            ), f"Scale question '{spec.id}' must define min_value and max_value"
            assert (
                spec.min_value == 1 and spec.max_value == 5
            ), f"Scale question '{spec.id}' must use 1–5 range"


def test_choice_questions_have_allowed_values() -> None:
    for spec in QUESTION_REGISTRY.values():
        if spec.answer_type == "choice":
            assert (
                spec.allowed_values is not None and len(spec.allowed_values) > 0
            ), f"Choice question '{spec.id}' must declare allowed_values"


def test_traveler_party_allowed_values_match_schema() -> None:
    spec = QUESTION_REGISTRY["q_traveler_party"]
    assert set(spec.allowed_values) == set(TRAVELER_PARTIES)


def test_trip_stage_allowed_values_match_schema() -> None:
    spec = QUESTION_REGISTRY["q_trip_stage"]
    assert set(spec.allowed_values) == set(TRIP_STAGES)


def test_route_modes_allowed_values_match_constant() -> None:
    spec = QUESTION_REGISTRY["q_route_modes_preference"]
    assert set(spec.allowed_values) == set(ROUTE_MODE_VALUES)


# ── QuestionSpec.validate individual cases ────────────────────────────────────


def test_required_question_rejects_none() -> None:
    spec = QUESTION_REGISTRY["q_traveler_party"]
    with pytest.raises(ValueError, match="required"):
        spec.validate(None)


def test_optional_question_accepts_none() -> None:
    spec = QUESTION_REGISTRY["q_nature_vs_culture"]
    spec.validate(None)  # must not raise


def test_choice_accepts_valid_value() -> None:
    spec = QUESTION_REGISTRY["q_traveler_party"]
    spec.validate("solo")


def test_choice_rejects_unknown_value() -> None:
    spec = QUESTION_REGISTRY["q_traveler_party"]
    with pytest.raises(ValueError, match="enterprise"):
        spec.validate("enterprise")


def test_scale_accepts_boundary_values() -> None:
    spec = QUESTION_REGISTRY["q_movement_vs_friction"]
    spec.validate(1)
    spec.validate(3)
    spec.validate(5)


def test_scale_rejects_zero() -> None:
    spec = QUESTION_REGISTRY["q_budget_sensitivity"]
    with pytest.raises(ValueError, match="1–5"):
        spec.validate(0)


def test_scale_rejects_six() -> None:
    spec = QUESTION_REGISTRY["q_budget_sensitivity"]
    with pytest.raises(ValueError, match="1–5"):
        spec.validate(6)


def test_scale_rejects_string() -> None:
    spec = QUESTION_REGISTRY["q_budget_sensitivity"]
    with pytest.raises(ValueError, match="q_budget_sensitivity"):
        spec.validate("three")


def test_scale_rejects_float() -> None:
    spec = QUESTION_REGISTRY["q_movement_vs_friction"]
    with pytest.raises(ValueError, match="q_movement_vs_friction"):
        spec.validate(2.5)


def test_scale_rejects_bool() -> None:
    # bool is a subclass of int, so we must explicitly reject it
    spec = QUESTION_REGISTRY["q_budget_sensitivity"]
    with pytest.raises(ValueError, match="q_budget_sensitivity"):
        spec.validate(True)


def test_integer_accepts_valid_value() -> None:
    spec = QUESTION_REGISTRY["q_duration_days"]
    spec.validate(14)


def test_integer_rejects_zero() -> None:
    spec = QUESTION_REGISTRY["q_duration_days"]
    with pytest.raises(ValueError, match="q_duration_days"):
        spec.validate(0)


def test_integer_rejects_negative() -> None:
    spec = QUESTION_REGISTRY["q_duration_days"]
    with pytest.raises(ValueError, match="q_duration_days"):
        spec.validate(-5)


def test_boolean_accepts_true_and_false() -> None:
    spec = QUESTION_REGISTRY["q_splurge_allowed"]
    spec.validate(True)
    spec.validate(False)


def test_boolean_rejects_string() -> None:
    spec = QUESTION_REGISTRY["q_splurge_allowed"]
    with pytest.raises(ValueError, match="bool"):
        spec.validate("yes")


def test_text_list_accepts_valid_modes() -> None:
    spec = QUESTION_REGISTRY["q_route_modes_preference"]
    spec.validate(["rail", "boat"])


def test_text_list_accepts_empty_list() -> None:
    spec = QUESTION_REGISTRY["q_route_modes_preference"]
    spec.validate([])


def test_text_list_rejects_unknown_mode() -> None:
    spec = QUESTION_REGISTRY["q_route_modes_preference"]
    with pytest.raises(ValueError, match="helicopter"):
        spec.validate(["rail", "helicopter"])


def test_text_list_rejects_non_string_elements() -> None:
    spec = QUESTION_REGISTRY["q_route_modes_preference"]
    with pytest.raises(ValueError, match="q_route_modes_preference"):
        spec.validate([1, 2])  # type: ignore[list-item]


def test_text_list_rejects_empty_string_element() -> None:
    spec = QUESTION_REGISTRY["q_route_modes_preference"]
    with pytest.raises(ValueError, match="q_route_modes_preference"):
        spec.validate(["rail", ""])


# ── validate_response: full-response validation ───────────────────────────────


def test_validate_response_passes_minimal_required() -> None:
    validate_response({"q_traveler_party": "solo", "q_budget_sensitivity": 3})


def test_validate_response_passes_complete_response() -> None:
    answers = {
        "q_traveler_party": "pair",
        "q_trip_stage": "first_visit",
        "q_duration_days": 14,
        "q_movement_vs_friction": 2,
        "q_recovery_vs_intensity": 4,
        "q_nature_vs_culture": 2,
        "q_structure_vs_elasticity": 3,
        "q_breadth_vs_depth": 2,
        "q_self_reliance_vs_convenience": 2,
        "q_historic_vs_contemporary": 2,
        "q_scenic_transit_vs_destination_time": 1,
        "q_route_coherence_vs_eclectic_contrast": 2,
        "q_social_energy_vs_solitude": 3,
        "q_iconic_vs_discovery": 4,
        "q_budget_sensitivity": 3,
        "q_splurge_allowed": True,
        "q_food_salience": 4,
        "q_rest_salience": 3,
        "q_music_salience": 1,
        "q_route_modes_preference": ["rail"],
    }
    validate_response(answers)


def test_validate_response_collects_both_missing_required_errors() -> None:
    with pytest.raises(ValueError) as exc_info:
        validate_response({"q_nature_vs_culture": 3})
    msg = str(exc_info.value)
    assert "q_traveler_party" in msg
    assert "q_budget_sensitivity" in msg


def test_validate_response_reports_unknown_question_id() -> None:
    with pytest.raises(ValueError, match="q_nonexistent"):
        validate_response(
            {
                "q_traveler_party": "solo",
                "q_budget_sensitivity": 3,
                "q_nonexistent": "value",
            }
        )


def test_validate_response_reports_out_of_range_scale() -> None:
    with pytest.raises(ValueError, match="1–5"):
        validate_response({"q_traveler_party": "solo", "q_budget_sensitivity": 6})


def test_validate_response_reports_invalid_choice() -> None:
    with pytest.raises(ValueError, match="enterprise"):
        validate_response({"q_traveler_party": "enterprise", "q_budget_sensitivity": 3})


def test_validate_response_error_message_lists_all_problems() -> None:
    # Three simultaneous problems: missing required, out-of-range, unknown id
    with pytest.raises(ValueError) as exc_info:
        validate_response(
            {
                "q_traveler_party": "solo",
                "q_budget_sensitivity": 9,  # out of range
                "q_totally_unknown": "x",  # unknown id
            }
        )
    msg = str(exc_info.value)
    assert "q_budget_sensitivity" in msg
    assert "q_totally_unknown" in msg
