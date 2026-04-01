"""Planning-autonomy controls for leisure trip workflows."""

from __future__ import annotations

from math import ceil
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from . import schema

AUTONOMY_FEEDBACK_KINDS: tuple[str, ...] = (
    "do_more_before_asking",
    "show_options_sooner",
    "ask_me_earlier",
    "explain_more",
    "explain_less",
)
AUTONOMY_FEEDBACK_DELTA_MULTIPLIER = 0.25
CHECKPOINT_FREQUENCY_CONFIRMATION_THRESHOLD = 0.65
OPTION_PREVIEW_EARLY_THRESHOLD = 0.65
EXPLANATION_DENSITY_DETAILED_THRESHOLD = 0.72
EXPLANATION_DENSITY_LEAN_THRESHOLD = 0.35


def _require_probability(value: float, field_name: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")


@dataclass(slots=True)
class AutonomyPreference:
    system_initiative: float = 0.5
    checkpoint_frequency: float = 0.5
    option_preview_timing: float = 0.5
    exploration_depth: float = 0.5
    explanation_depth: float = 0.5

    def __post_init__(self) -> None:
        for field_name in (
            "system_initiative",
            "checkpoint_frequency",
            "option_preview_timing",
            "exploration_depth",
            "explanation_depth",
        ):
            _require_probability(getattr(self, field_name), field_name)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AutonomyGuardrails:
    max_unconfirmed_major_steps: int = 3
    require_confirmation_for_anchor_changes: bool = True
    require_confirmation_for_budget_tradeoffs: bool = True
    require_confirmation_for_constraint_relaxation: bool = True

    def __post_init__(self) -> None:
        if self.max_unconfirmed_major_steps <= 0:
            raise ValueError("max_unconfirmed_major_steps must be positive")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AutonomyFeedback:
    feedback_kind: str
    trip_stage: str
    strength: float = 0.7
    note: str = ""

    def __post_init__(self) -> None:
        if self.feedback_kind not in AUTONOMY_FEEDBACK_KINDS:
            raise ValueError(f"feedback_kind must be one of {AUTONOMY_FEEDBACK_KINDS}")
        if self.trip_stage not in schema.PLANNING_STAGES:
            raise ValueError(f"trip_stage must be one of {schema.PLANNING_STAGES}")
        _require_probability(self.strength, "strength")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PlannerBehaviorMetadata:
    trip_stage: str
    ask_before_next_major_change: bool
    target_research_passes: int
    target_options_before_checkpoint: int
    surface_options_early: bool
    explanation_density: str

    def __post_init__(self) -> None:
        if self.trip_stage not in schema.PLANNING_STAGES:
            raise ValueError(f"trip_stage must be one of {schema.PLANNING_STAGES}")
        if self.target_research_passes <= 0:
            raise ValueError("target_research_passes must be positive")
        if self.target_options_before_checkpoint <= 0:
            raise ValueError("target_options_before_checkpoint must be positive")
        if self.explanation_density not in {"lean", "standard", "detailed"}:
            raise ValueError("explanation_density must be lean, standard, or detailed")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PlanningAutonomyProfile:
    default_preference: AutonomyPreference = field(default_factory=AutonomyPreference)
    stage_preferences: dict[str, AutonomyPreference] = field(default_factory=dict)
    guardrails: AutonomyGuardrails = field(default_factory=AutonomyGuardrails)
    feedback_history: list[AutonomyFeedback] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.default_preference, AutonomyPreference):
            raise ValueError("default_preference must be an AutonomyPreference")
        invalid_stages = set(self.stage_preferences) - set(schema.PLANNING_STAGES)
        if invalid_stages:
            raise ValueError(f"unsupported stage_preferences keys: {sorted(invalid_stages)}")
        if any(
            not isinstance(preference, AutonomyPreference)
            for preference in self.stage_preferences.values()
        ):
            raise ValueError("stage_preferences must contain AutonomyPreference instances")
        self.stage_preferences = {
            stage: replace(self.default_preference) for stage in schema.PLANNING_STAGES
        } | self.stage_preferences
        if any(not isinstance(item, AutonomyFeedback) for item in self.feedback_history):
            raise ValueError("feedback_history must contain AutonomyFeedback instances")

    def preference_for_stage(self, trip_stage: str) -> AutonomyPreference:
        if trip_stage not in schema.PLANNING_STAGES:
            raise ValueError(f"trip_stage must be one of {schema.PLANNING_STAGES}")
        stage_preference = self.stage_preferences[trip_stage]
        return AutonomyPreference(
            system_initiative=stage_preference.system_initiative,
            checkpoint_frequency=stage_preference.checkpoint_frequency,
            option_preview_timing=stage_preference.option_preview_timing,
            exploration_depth=stage_preference.exploration_depth,
            explanation_depth=stage_preference.explanation_depth,
        )

    def behavior_for_stage(self, trip_stage: str) -> PlannerBehaviorMetadata:
        preference = self.preference_for_stage(trip_stage)
        target_research_passes = max(
            1,
            ceil(1 + (preference.system_initiative * 3) + (preference.exploration_depth * 2)),
        )
        target_options_before_checkpoint = max(
            1,
            round(2 + ((1.0 - preference.option_preview_timing) * 4)),
        )
        if preference.explanation_depth >= EXPLANATION_DENSITY_DETAILED_THRESHOLD:
            explanation_density = "detailed"
        elif preference.explanation_depth <= EXPLANATION_DENSITY_LEAN_THRESHOLD:
            explanation_density = "lean"
        else:
            explanation_density = "standard"
        return PlannerBehaviorMetadata(
            trip_stage=trip_stage,
            ask_before_next_major_change=(
                preference.checkpoint_frequency >= CHECKPOINT_FREQUENCY_CONFIRMATION_THRESHOLD
            ),
            target_research_passes=target_research_passes,
            target_options_before_checkpoint=target_options_before_checkpoint,
            surface_options_early=preference.option_preview_timing
            >= OPTION_PREVIEW_EARLY_THRESHOLD,
            explanation_density=explanation_density,
        )

    def apply_feedback(self, feedback: AutonomyFeedback) -> "PlanningAutonomyProfile":
        updated = replace(
            self,
            stage_preferences={
                stage: replace(preference) for stage, preference in self.stage_preferences.items()
            },
            feedback_history=[*self.feedback_history, feedback],
        )
        preference = updated.stage_preferences[feedback.trip_stage]
        delta = feedback.strength * AUTONOMY_FEEDBACK_DELTA_MULTIPLIER

        if feedback.feedback_kind == "do_more_before_asking":
            preference.system_initiative = min(1.0, preference.system_initiative + delta)
            preference.exploration_depth = min(1.0, preference.exploration_depth + delta)
            preference.checkpoint_frequency = max(0.0, preference.checkpoint_frequency - delta)
        elif feedback.feedback_kind == "show_options_sooner":
            preference.option_preview_timing = min(1.0, preference.option_preview_timing + delta)
            preference.checkpoint_frequency = min(
                1.0, preference.checkpoint_frequency + (delta * 0.4)
            )
            preference.exploration_depth = max(0.0, preference.exploration_depth - (delta * 0.5))
        elif feedback.feedback_kind == "ask_me_earlier":
            preference.checkpoint_frequency = min(1.0, preference.checkpoint_frequency + delta)
            preference.system_initiative = max(0.0, preference.system_initiative - (delta * 0.5))
        elif feedback.feedback_kind == "explain_more":
            preference.explanation_depth = min(1.0, preference.explanation_depth + delta)
        elif feedback.feedback_kind == "explain_less":
            preference.explanation_depth = max(0.0, preference.explanation_depth - delta)
        return updated

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
