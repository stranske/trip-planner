"""Normalize raw questionnaire answers to canonical preference dimensions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

from .questionnaire import QUESTION_REGISTRY, validate_response

# Maps each dimension question id to the canonical TRADEOFF_DIMENSION_KEYS key.
_QUESTION_TO_DIMENSION: Final[dict[str, str]] = {
    "q_movement_vs_friction": "movement_vs_friction",
    "q_recovery_vs_intensity": "recovery_vs_intensity",
    "q_nature_vs_culture": "nature_vs_culture",
    "q_structure_vs_elasticity": "structure_vs_elasticity",
    "q_breadth_vs_depth": "breadth_vs_depth",
    "q_self_reliance_vs_convenience": "self_reliance_vs_convenience",
    "q_historic_vs_contemporary": "historic_vs_contemporary",
    "q_scenic_transit_vs_destination_time": "scenic_transit_vs_destination_time",
    "q_route_coherence_vs_eclectic_contrast": "route_coherence_vs_eclectic_contrast",
    "q_social_energy_vs_solitude": "social_energy_vs_solitude",
    "q_iconic_vs_discovery": "iconic_vs_discovery",
}

# Maps hybrid-salience question ids to HYBRID_FACTOR_KEYS keys.
_QUESTION_TO_HYBRID: Final[dict[str, str]] = {
    "q_food_salience": "food",
    "q_rest_salience": "rest",
    "q_music_salience": "music",
}

# Confidence assigned when the traveler explicitly answered a dimension question.
_EXPLICIT_CONFIDENCE: Final[float] = 0.7
# Confidence assigned when the default value was used (question was skipped).
_DEFAULT_CONFIDENCE: Final[float] = 0.1

# Hybrid salience when route_modes_preference is non-empty vs empty.
_ROUTE_MODES_SALIENCE_EXPLICIT: Final[float] = 0.8
_ROUTE_MODES_SALIENCE_DEFAULT: Final[float] = 0.2


def _scale_to_axis(rating: int) -> float:
    """Map a 1–5 Likert rating to the [-1.0, 1.0] dimension axis.

    1 → -1.0 (strong left pole per POLARITY_MAP)
    3 →  0.0 (neutral / balanced)
    5 → +1.0 (strong right pole per POLARITY_MAP)
    """
    return (rating - 3) / 2.0


def _scale_to_probability(rating: int) -> float:
    """Map a 1–5 Likert rating to a [0.0, 1.0] probability.

    1 → 0.0
    3 → 0.5
    5 → 1.0
    """
    return (rating - 1) / 4.0


@dataclass(slots=True)
class NormalizedPreferences:
    """Canonical preference dimensions derived from questionnaire answers.

    All eleven tradeoff dimension values are always present — unanswered
    questions receive the neutral default (0.0) with low confidence (0.1).
    All four hybrid factor salience scores are always present.
    """

    traveler_party: str
    trip_stage: str
    duration_days: int | None
    # Dimension key → axis value in [-1.0, 1.0].  Keys match TRADEOFF_DIMENSION_KEYS.
    tradeoff_values: dict[str, float] = field(default_factory=dict)
    # Dimension key → confidence in [0.0, 1.0].
    tradeoff_confidence: dict[str, float] = field(default_factory=dict)
    budget_sensitivity: float = 0.0  # [0.0, 1.0]
    splurge_allowed: bool = False
    # Hybrid factor key → salience in [0.0, 1.0].  Keys match HYBRID_FACTOR_KEYS.
    hybrid_salience: dict[str, float] = field(default_factory=dict)
    route_modes: list[str] = field(default_factory=list)


def normalize(answers: dict[str, Any]) -> NormalizedPreferences:
    """Normalize a validated response dict into canonical preference dimensions.

    Raises ValueError (via validate_response) if any answer is invalid.
    Missing optional answers are replaced with their registered defaults.
    """
    validate_response(answers)

    def _get(question_id: str) -> Any:
        value = answers.get(question_id)
        if value is None:
            return QUESTION_REGISTRY[question_id].default
        return value

    # ── Tradeoff dimensions ───────────────────────────────────────────────────
    tradeoff_values: dict[str, float] = {}
    tradeoff_confidence: dict[str, float] = {}
    for q_id, dim_key in _QUESTION_TO_DIMENSION.items():
        raw = answers.get(q_id)
        if raw is None:
            rating: int = QUESTION_REGISTRY[q_id].default
            confidence = _DEFAULT_CONFIDENCE
        else:
            rating = raw
            confidence = _EXPLICIT_CONFIDENCE
        tradeoff_values[dim_key] = _scale_to_axis(rating)
        tradeoff_confidence[dim_key] = confidence

    # ── Budget ────────────────────────────────────────────────────────────────
    budget_sensitivity = _scale_to_probability(answers["q_budget_sensitivity"])
    splurge_allowed: bool = _get("q_splurge_allowed")

    # ── Hybrid factor salience ────────────────────────────────────────────────
    hybrid_salience: dict[str, float] = {}
    for q_id, factor_key in _QUESTION_TO_HYBRID.items():
        hybrid_salience[factor_key] = _scale_to_probability(_get(q_id))

    route_modes: list[str] = _get("q_route_modes_preference")
    hybrid_salience["route_modes"] = (
        _ROUTE_MODES_SALIENCE_EXPLICIT if route_modes else _ROUTE_MODES_SALIENCE_DEFAULT
    )

    return NormalizedPreferences(
        traveler_party=answers["q_traveler_party"],
        trip_stage=_get("q_trip_stage"),
        duration_days=_get("q_duration_days"),
        tradeoff_values=tradeoff_values,
        tradeoff_confidence=tradeoff_confidence,
        budget_sensitivity=budget_sensitivity,
        splurge_allowed=splurge_allowed,
        hybrid_salience=hybrid_salience,
        route_modes=route_modes,
    )
