"""Revealed-preference update contracts for leisure planning."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from . import schema
from .evidence import ContradictionMarker, OPTION_KINDS, OptionEvidence, PreferenceEvidence
from .models import LeisurePreferenceProfile

REACTION_TYPES: tuple[str, ...] = (
    "selected",
    "rejected",
    "saved_for_later",
    "ignored",
    "requested_more_like_this",
    "requested_less_like_this",
)
REVEALED_PREFERENCE_FALLBACK_SEQUENCE = 10**6


def _require_probability(value: float, field_name: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")


def _require_axis(value: float, field_name: str) -> None:
    if not -1.0 <= value <= 1.0:
        raise ValueError(f"{field_name} must be between -1.0 and 1.0")


def _profile_has_active_hard_constraints(profile: LeisurePreferenceProfile) -> bool:
    constraints = profile.hard_constraints
    return any(
        (
            constraints.date_window.start,
            constraints.date_window.end,
            constraints.duration_bounds.min_days is not None,
            constraints.duration_bounds.max_days is not None,
            constraints.budget_ceiling is not None,
            constraints.must_include_places,
            constraints.must_protect_experiences,
            constraints.mobility_constraints,
            constraints.lodging_constraints,
            constraints.visa_border_constraints,
        )
    )


def _profile_has_active_anchors(profile: LeisurePreferenceProfile) -> bool:
    return any(profile.anchors[group] for group in schema.ANCHOR_GROUPS)


@dataclass(slots=True)
class RevealedPreferenceSignal:
    signal_id: str
    trip_stage: str
    reaction_type: str
    option_set_id: str
    option_id: str
    option_kind: str
    signal_strength: float
    dimension_biases: dict[str, float] = field(default_factory=dict)
    hybrid_biases: dict[str, float] = field(default_factory=dict)
    summary: str = ""

    def __post_init__(self) -> None:
        if not self.signal_id:
            raise ValueError("signal_id is required")
        if self.trip_stage not in schema.PLANNING_STAGES:
            raise ValueError(f"trip_stage must be one of {schema.PLANNING_STAGES}")
        if self.reaction_type not in REACTION_TYPES:
            raise ValueError(f"reaction_type must be one of {REACTION_TYPES}")
        if not self.option_set_id:
            raise ValueError("option_set_id is required")
        if not self.option_id:
            raise ValueError("option_id is required")
        if self.option_kind not in OPTION_KINDS:
            raise ValueError(f"option_kind must be one of {OPTION_KINDS}")
        _require_probability(self.signal_strength, "signal_strength")
        invalid_dimensions = set(self.dimension_biases) - set(schema.TRADEOFF_DIMENSION_KEYS)
        if invalid_dimensions:
            raise ValueError(f"unsupported dimension_biases keys: {sorted(invalid_dimensions)}")
        invalid_hybrid = set(self.hybrid_biases) - set(schema.HYBRID_FACTOR_KEYS)
        if invalid_hybrid:
            raise ValueError(f"unsupported hybrid_biases keys: {sorted(invalid_hybrid)}")
        for key, value in self.dimension_biases.items():
            _require_axis(value, f"dimension_biases[{key}]")
        for key, value in self.hybrid_biases.items():
            _require_axis(value, f"hybrid_biases[{key}]")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RevealedPreferenceUpdate:
    signal: RevealedPreferenceSignal
    emitted_evidence: list[PreferenceEvidence] = field(default_factory=list)
    protected_targets: list[str] = field(default_factory=list)
    blocked_overwrites: list[str] = field(default_factory=list)
    transient: bool = False
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if any(not isinstance(item, PreferenceEvidence) for item in self.emitted_evidence):
            raise ValueError("emitted_evidence must contain PreferenceEvidence instances")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_revealed_preference_update(
    profile: LeisurePreferenceProfile,
    signal: RevealedPreferenceSignal,
) -> RevealedPreferenceUpdate:
    if not isinstance(profile, LeisurePreferenceProfile):
        raise ValueError("profile must be a LeisurePreferenceProfile")

    reaction_direction = {
        "selected": "positive",
        "saved_for_later": "positive",
        "requested_more_like_this": "positive",
        "rejected": "negative",
        "requested_less_like_this": "negative",
        "ignored": "negative",
    }[signal.reaction_type]
    transient = (
        signal.reaction_type in {"ignored", "saved_for_later"} or signal.signal_strength < 0.45
    )
    confidence_hint = min(1.0, max(0.1, signal.signal_strength * (0.45 if transient else 0.85)))
    salience_hint = min(1.0, max(0.1, signal.signal_strength * (0.4 if transient else 0.8)))

    contradictions: list[ContradictionMarker] = []
    blocked_overwrites: list[str] = []
    protected_targets: list[str] = []
    notes: list[str] = []

    for dimension_key, bias in signal.dimension_biases.items():
        current_dimension = profile.tradeoff_dimensions[dimension_key]
        if (
            current_dimension.salience >= 0.75
            and current_dimension.stability >= 0.75
            and current_dimension.value != 0.0
            and (current_dimension.value < 0 < bias or current_dimension.value > 0 > bias)
        ):
            blocked_overwrites.append(dimension_key)
            contradictions.append(
                ContradictionMarker(
                    previous_evidence_id=f"stable:{dimension_key}",
                    reason="Revealed preference conflicts with a stable high-salience dimension.",
                    weakening_strength=0.8,
                )
            )
            notes.append(
                f"{dimension_key} was protected because the reaction conflicts with a stable preference."
            )

    if _profile_has_active_hard_constraints(profile):
        protected_targets.extend(["hard_constraints"])
    if _profile_has_active_anchors(profile):
        protected_targets.extend(["anchors"])
    if protected_targets:
        notes.append(
            "Hard constraints and anchors remain protected from one-off revealed preference updates."
        )

    evidence_type = (
        "option_selection"
        if signal.reaction_type in {"selected", "saved_for_later", "requested_more_like_this"}
        else "option_rejection"
    )
    emitted = PreferenceEvidence(
        id=f"{signal.signal_id}-evidence",
        evidence_type=evidence_type,
        source_type="option_menu",
        affected_dimensions=list(signal.dimension_biases),
        affected_hybrid_factors=list(signal.hybrid_biases),
        signal_direction="contradiction" if blocked_overwrites else reaction_direction,
        confidence_hint=confidence_hint,
        salience_hint=salience_hint,
        sequence=REVEALED_PREFERENCE_FALLBACK_SEQUENCE,
        note=signal.summary or "Revealed preference update from concrete option feedback.",
        option_evidence=OptionEvidence(
            option_set_id=signal.option_set_id,
            option_id=signal.option_id,
            option_kind=signal.option_kind,
            presented_option_ids=[signal.option_id],
            comparison_label="revealed_preference",
        ),
        contradictions=contradictions,
    )

    if transient:
        notes.append(
            "Reaction is treated as transient evidence and should not outweigh stable preferences on its own."
        )

    return RevealedPreferenceUpdate(
        signal=signal,
        emitted_evidence=[emitted],
        protected_targets=sorted(set(protected_targets)),
        blocked_overwrites=sorted(set(blocked_overwrites)),
        transient=transient,
        notes=notes,
    )
