"""Evidence contracts for leisure preference inference."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from . import schema

EVIDENCE_TYPES: tuple[str, ...] = (
    "direct_statement",
    "hard_constraint_declaration",
    "anchor_declaration",
    "forced_tradeoff_choice",
    "scenario_reaction",
    "option_selection",
    "option_rejection",
    "trip_revision",
)
EVIDENCE_SOURCE_TYPES: tuple[str, ...] = (
    "user_message",
    "structured_input",
    "option_menu",
    "scenario_prompt",
    "planner_inference_review",
    "trip_revision",
    "imported_trip_notes",
)
EVIDENCE_SUPPORT_LEVELS: tuple[str, ...] = ("weak", "medium", "strong")
SIGNAL_DIRECTIONS: tuple[str, ...] = ("positive", "negative", "contradiction")
OPTION_KINDS: tuple[str, ...] = (
    "lodging",
    "transport",
    "activity",
    "destination_bundle",
    "mixed_bundle",
)


def _require_probability(value: float, field_name: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")


def _require_strings(values: list[str], field_name: str) -> None:
    if any(not isinstance(item, str) or not item for item in values):
        raise ValueError(f"{field_name} must contain only non-empty strings")


@dataclass(slots=True)
class OptionEvidence:
    option_set_id: str
    option_id: str
    option_kind: str
    presented_option_ids: list[str] = field(default_factory=list)
    comparison_label: str = ""

    def __post_init__(self) -> None:
        if not self.option_set_id:
            raise ValueError("option_set_id is required")
        if not self.option_id:
            raise ValueError("option_id is required")
        if self.option_kind not in OPTION_KINDS:
            raise ValueError(f"option_kind must be one of {OPTION_KINDS}")
        _require_strings(self.presented_option_ids, "presented_option_ids")
        if self.presented_option_ids and self.option_id not in self.presented_option_ids:
            raise ValueError("presented_option_ids must include option_id when provided")
        if len(self.presented_option_ids) != len(set(self.presented_option_ids)):
            raise ValueError("presented_option_ids cannot contain duplicates")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ContradictionMarker:
    previous_evidence_id: str
    reason: str
    weakening_strength: float = 1.0

    def __post_init__(self) -> None:
        if not self.previous_evidence_id:
            raise ValueError("previous_evidence_id is required")
        if not self.reason:
            raise ValueError("reason is required")
        _require_probability(self.weakening_strength, "weakening_strength")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PreferenceEvidence:
    id: str
    evidence_type: str
    source_type: str
    affected_dimensions: list[str] = field(default_factory=list)
    affected_hybrid_factors: list[str] = field(default_factory=list)
    anchor_groups: list[str] = field(default_factory=list)
    signal_direction: str = "positive"
    confidence_hint: float = 0.5
    salience_hint: float = 0.5
    observed_at: str | None = None
    sequence: int | None = None
    note: str = ""
    option_evidence: OptionEvidence | None = None
    contradictions: list[ContradictionMarker] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("id is required")
        if self.evidence_type not in EVIDENCE_TYPES:
            raise ValueError(f"evidence_type must be one of {EVIDENCE_TYPES}")
        if self.source_type not in EVIDENCE_SOURCE_TYPES:
            raise ValueError(f"source_type must be one of {EVIDENCE_SOURCE_TYPES}")
        if self.signal_direction not in SIGNAL_DIRECTIONS:
            raise ValueError(f"signal_direction must be one of {SIGNAL_DIRECTIONS}")
        if self.sequence is None and self.observed_at is None:
            raise ValueError("PreferenceEvidence requires observed_at or sequence")
        if self.sequence is not None and self.sequence < 0:
            raise ValueError("sequence cannot be negative")
        _require_probability(self.confidence_hint, "confidence_hint")
        _require_probability(self.salience_hint, "salience_hint")
        _require_strings(self.affected_dimensions, "affected_dimensions")
        _require_strings(self.affected_hybrid_factors, "affected_hybrid_factors")
        _require_strings(self.anchor_groups, "anchor_groups")
        invalid_dimensions = set(self.affected_dimensions) - set(schema.TRADEOFF_DIMENSION_KEYS)
        if invalid_dimensions:
            raise ValueError(f"unsupported dimensions: {sorted(invalid_dimensions)}")
        invalid_hybrid = set(self.affected_hybrid_factors) - set(schema.HYBRID_FACTOR_KEYS)
        if invalid_hybrid:
            raise ValueError(f"unsupported hybrid factors: {sorted(invalid_hybrid)}")
        invalid_anchor_groups = set(self.anchor_groups) - set(schema.ANCHOR_GROUPS)
        if invalid_anchor_groups:
            raise ValueError(f"unsupported anchor groups: {sorted(invalid_anchor_groups)}")
        if not (self.affected_dimensions or self.affected_hybrid_factors or self.anchor_groups):
            raise ValueError("PreferenceEvidence must affect at least one target")
        if self.evidence_type in {"option_selection", "option_rejection"}:
            if self.option_evidence is None:
                raise ValueError(
                    "option_evidence is required for option_selection and option_rejection"
                )
        elif self.option_evidence is not None:
            raise ValueError(
                "option_evidence is only allowed for option_selection and option_rejection"
            )
        if any(not isinstance(item, ContradictionMarker) for item in self.contradictions):
            raise ValueError("contradictions must contain ContradictionMarker instances")
        from .evidence_catalog import validate_evidence_support

        validate_evidence_support(self)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
