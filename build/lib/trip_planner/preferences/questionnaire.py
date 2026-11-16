"""Questionnaire schema: stable question ids, answer types, allowed values, defaults, and missing-answer behavior."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Literal

from . import schema

AnswerType = Literal["choice", "integer", "scale", "boolean", "text_list"]

_SCALE_MIN: Final[int] = 1
_SCALE_MAX: Final[int] = 5

# Allowed values for q_route_modes_preference
ROUTE_MODE_VALUES: Final[tuple[str, ...]] = ("rail", "boat", "road", "air", "walking")


@dataclass(slots=True, frozen=True)
class QuestionSpec:
    """Specification for a single questionnaire question.

    Missing-answer behavior:
    - required=True, answer absent → validate() raises ValueError
    - required=False, answer absent → normalize() substitutes default
    """

    id: str
    answer_type: AnswerType
    required: bool
    default: Any
    description: str
    allowed_values: tuple[Any, ...] | None = None
    min_value: int | None = None
    max_value: int | None = None

    def validate(self, value: Any) -> None:
        """Raise ValueError with a useful message when value is invalid."""
        if value is None:
            if self.required:
                raise ValueError(f"'{self.id}' is required but was not answered")
            return

        if self.answer_type == "choice":
            if self.allowed_values is not None and value not in self.allowed_values:
                raise ValueError(
                    f"'{self.id}': {value!r} is not one of {list(self.allowed_values)}"
                )

        elif self.answer_type == "scale":
            lo = self.min_value if self.min_value is not None else _SCALE_MIN
            hi = self.max_value if self.max_value is not None else _SCALE_MAX
            if not isinstance(value, int) or isinstance(value, bool) or not (lo <= value <= hi):
                raise ValueError(f"'{self.id}': expected integer {lo}–{hi}, got {value!r}")

        elif self.answer_type == "integer":
            lo = self.min_value if self.min_value is not None else 1
            hi = self.max_value if self.max_value is not None else 10_000
            if not isinstance(value, int) or isinstance(value, bool) or not (lo <= value <= hi):
                raise ValueError(f"'{self.id}': expected integer {lo}–{hi}, got {value!r}")

        elif self.answer_type == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"'{self.id}': expected bool, got {value!r}")

        elif self.answer_type == "text_list":
            if not isinstance(value, list) or any(not isinstance(s, str) or not s for s in value):
                raise ValueError(f"'{self.id}': expected list of non-empty strings")
            if self.allowed_values is not None:
                bad = [v for v in value if v not in self.allowed_values]
                if bad:
                    raise ValueError(
                        f"'{self.id}': unrecognized values {bad!r},"
                        f" allowed: {list(self.allowed_values)}"
                    )


QUESTION_REGISTRY: Final[dict[str, QuestionSpec]] = {
    # ── Trip frame ────────────────────────────────────────────────────────────
    "q_traveler_party": QuestionSpec(
        id="q_traveler_party",
        answer_type="choice",
        required=True,
        default=None,
        allowed_values=schema.TRAVELER_PARTIES,
        description="Who are you traveling with? (solo, pair, family, friends)",
    ),
    "q_trip_stage": QuestionSpec(
        id="q_trip_stage",
        answer_type="choice",
        required=False,
        default="first_visit",
        allowed_values=schema.TRIP_STAGES,
        description="Is this your first visit, a repeat visit, or mixed?",
    ),
    "q_duration_days": QuestionSpec(
        id="q_duration_days",
        answer_type="integer",
        required=False,
        default=None,
        min_value=1,
        max_value=365,
        description="How many days will the trip be?",
    ),
    # ── Tradeoff dimensions (1 = left pole, 5 = right pole per POLARITY_MAP) ─
    "q_movement_vs_friction": QuestionSpec(
        id="q_movement_vs_friction",
        answer_type="scale",
        required=False,
        default=3,
        min_value=_SCALE_MIN,
        max_value=_SCALE_MAX,
        description="1=happy moving frequently, 5=prefer fewer longer stays",
    ),
    "q_recovery_vs_intensity": QuestionSpec(
        id="q_recovery_vs_intensity",
        answer_type="scale",
        required=False,
        default=3,
        min_value=_SCALE_MIN,
        max_value=_SCALE_MAX,
        description="1=packed days are fine, 5=I need built-in rest",
    ),
    "q_nature_vs_culture": QuestionSpec(
        id="q_nature_vs_culture",
        answer_type="scale",
        required=False,
        default=3,
        min_value=_SCALE_MIN,
        max_value=_SCALE_MAX,
        description="1=nature and landscapes, 5=cities and culture",
    ),
    "q_structure_vs_elasticity": QuestionSpec(
        id="q_structure_vs_elasticity",
        answer_type="scale",
        required=False,
        default=3,
        min_value=_SCALE_MIN,
        max_value=_SCALE_MAX,
        description="1=detailed daily plan, 5=keep it flexible",
    ),
    "q_breadth_vs_depth": QuestionSpec(
        id="q_breadth_vs_depth",
        answer_type="scale",
        required=False,
        default=3,
        min_value=_SCALE_MIN,
        max_value=_SCALE_MAX,
        description="1=cover many places, 5=linger and go deep",
    ),
    "q_self_reliance_vs_convenience": QuestionSpec(
        id="q_self_reliance_vs_convenience",
        answer_type="scale",
        required=False,
        default=3,
        min_value=_SCALE_MIN,
        max_value=_SCALE_MAX,
        description="1=handle all logistics myself, 5=prefer pre-arranged convenience",
    ),
    "q_historic_vs_contemporary": QuestionSpec(
        id="q_historic_vs_contemporary",
        answer_type="scale",
        required=False,
        default=3,
        min_value=_SCALE_MIN,
        max_value=_SCALE_MAX,
        description="1=history and heritage, 5=contemporary life",
    ),
    "q_scenic_transit_vs_destination_time": QuestionSpec(
        id="q_scenic_transit_vs_destination_time",
        answer_type="scale",
        required=False,
        default=3,
        min_value=_SCALE_MIN,
        max_value=_SCALE_MAX,
        description="1=scenic travel days are worthwhile, 5=maximize time at destinations",
    ),
    "q_route_coherence_vs_eclectic_contrast": QuestionSpec(
        id="q_route_coherence_vs_eclectic_contrast",
        answer_type="scale",
        required=False,
        default=3,
        min_value=_SCALE_MIN,
        max_value=_SCALE_MAX,
        description="1=coherent thematic route, 5=eclectic mix of contrasting places",
    ),
    "q_social_energy_vs_solitude": QuestionSpec(
        id="q_social_energy_vs_solitude",
        answer_type="scale",
        required=False,
        default=3,
        min_value=_SCALE_MIN,
        max_value=_SCALE_MAX,
        description="1=social energy and bustle, 5=solitude and quiet",
    ),
    "q_iconic_vs_discovery": QuestionSpec(
        id="q_iconic_vs_discovery",
        answer_type="scale",
        required=False,
        default=3,
        min_value=_SCALE_MIN,
        max_value=_SCALE_MAX,
        description="1=iconic must-see sights, 5=off-the-beaten-path discovery",
    ),
    # ── Budget ────────────────────────────────────────────────────────────────
    "q_budget_sensitivity": QuestionSpec(
        id="q_budget_sensitivity",
        answer_type="scale",
        required=True,
        default=None,
        min_value=_SCALE_MIN,
        max_value=_SCALE_MAX,
        description="1=price is no concern, 5=keeping costs down is a priority",
    ),
    "q_splurge_allowed": QuestionSpec(
        id="q_splurge_allowed",
        answer_type="boolean",
        required=False,
        default=False,
        description="Would you pay more for a clearly better experience in select categories?",
    ),
    # ── Hybrid factors ────────────────────────────────────────────────────────
    "q_food_salience": QuestionSpec(
        id="q_food_salience",
        answer_type="scale",
        required=False,
        default=3,
        min_value=_SCALE_MIN,
        max_value=_SCALE_MAX,
        description="1=food is just fuel, 5=dining is central to the trip",
    ),
    "q_rest_salience": QuestionSpec(
        id="q_rest_salience",
        answer_type="scale",
        required=False,
        default=3,
        min_value=_SCALE_MIN,
        max_value=_SCALE_MAX,
        description="1=sleep anywhere, 5=quality rest is non-negotiable",
    ),
    "q_music_salience": QuestionSpec(
        id="q_music_salience",
        answer_type="scale",
        required=False,
        default=1,
        min_value=_SCALE_MIN,
        max_value=_SCALE_MAX,
        description="1=music scenes are not a factor, 5=live music is a trip anchor",
    ),
    "q_route_modes_preference": QuestionSpec(
        id="q_route_modes_preference",
        answer_type="text_list",
        required=False,
        default=[],
        allowed_values=ROUTE_MODE_VALUES,
        description=(f"Preferred transport modes (any subset of {list(ROUTE_MODE_VALUES)})"),
    ),
}

# Stable ordered tuple of all question ids — useful for iterating in display order.
QUESTION_IDS: Final[tuple[str, ...]] = tuple(QUESTION_REGISTRY)


def validate_response(answers: dict[str, Any]) -> None:
    """Validate a response dict against the registry.

    Collects all errors before raising so callers see the full list in one pass.
    Raises ValueError listing every problem found.
    """
    errors: list[str] = []

    for spec in QUESTION_REGISTRY.values():
        value = answers.get(spec.id)
        try:
            spec.validate(value)
        except ValueError as exc:
            errors.append(str(exc))

    unknown = sorted(k for k in answers if k not in QUESTION_REGISTRY)
    for key in unknown:
        errors.append(f"Unknown question id: {key!r}")

    if errors:
        bullet_list = "\n".join(f"  - {e}" for e in errors)
        raise ValueError(f"Questionnaire validation failed:\n{bullet_list}")
