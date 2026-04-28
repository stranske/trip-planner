"""Structured explanation output for leisure preference resolution."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class MaterialInfluence:
    source_kind: str
    source_id: str
    weight: float
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DimensionResolutionExplanation:
    dimension_key: str
    initial_value: float
    resolved_value: float
    confidence: float
    salience: float
    stability: float
    value_delta: float = 0.0
    influences: list[MaterialInfluence] = field(default_factory=list)
    interaction_rule_ids: list[str] = field(default_factory=list)
    tension_flag_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HybridFactorExplanation:
    hybrid_factor_key: str
    mode: str
    salience: float
    anchor_strength: float
    influences: list[MaterialInfluence] = field(default_factory=list)
    interaction_rule_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class InteractionActivation:
    rule_id: str
    dimensions: list[str]
    planning_biases: dict[str, float] = field(default_factory=dict)
    triggered_tension_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ResolutionExplanation:
    dimension_explanations: dict[str, DimensionResolutionExplanation] = field(default_factory=dict)
    hybrid_factor_explanations: dict[str, HybridFactorExplanation] = field(default_factory=dict)
    activated_interactions: list[InteractionActivation] = field(default_factory=list)
    tension_explanations: dict[str, list[MaterialInfluence]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ResolvedLeisureProfile:
    profile: Any
    explanation: ResolutionExplanation

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.to_dict(),
            "explanation": self.explanation.to_dict(),
        }
