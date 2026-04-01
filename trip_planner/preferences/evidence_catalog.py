"""Evidence eligibility and support catalog for leisure preference inference."""

from __future__ import annotations

from typing import Final

from . import schema
from .evidence import EVIDENCE_SUPPORT_LEVELS, PreferenceEvidence

EvidenceSupportCatalog = dict[str, dict[str, str]]

ANCHOR_SIGNAL_GUIDANCE: Final[str] = (
    "Anchor signals should be treated as commitment-like evidence about what the trip must "
    "protect or organize around. Normal tradeoff evidence expresses directional preference "
    "within a dimension; anchor evidence identifies non-interchangeable priorities."
)
ANCHOR_GROUP_EVIDENCE_STRENGTH: Final[dict[str, dict[str, str]]] = {
    "place_anchors": {
        "hard_constraint_declaration": "strong",
        "anchor_declaration": "strong",
        "trip_revision": "medium",
        "option_selection": "medium",
    },
    "experience_anchors": {
        "anchor_declaration": "strong",
        "direct_statement": "medium",
        "scenario_reaction": "medium",
        "option_selection": "strong",
        "trip_revision": "strong",
    },
    "mode_anchors": {
        "anchor_declaration": "strong",
        "forced_tradeoff_choice": "medium",
        "option_selection": "strong",
        "option_rejection": "medium",
    },
    "rhythm_anchors": {
        "anchor_declaration": "strong",
        "scenario_reaction": "medium",
        "option_selection": "medium",
        "trip_revision": "strong",
    },
    "calendar_anchors": {
        "hard_constraint_declaration": "strong",
        "anchor_declaration": "strong",
        "trip_revision": "medium",
    },
    "quality_floor_anchors": {
        "hard_constraint_declaration": "strong",
        "anchor_declaration": "strong",
        "option_rejection": "strong",
        "trip_revision": "medium",
    },
    "regional_adjacency_preferences": {
        "anchor_declaration": "medium",
        "scenario_reaction": "medium",
        "option_selection": "strong",
        "trip_revision": "medium",
    },
}
DIMENSION_EVIDENCE_STRENGTH: Final[EvidenceSupportCatalog] = {
    "movement_vs_friction": {
        "direct_statement": "medium",
        "forced_tradeoff_choice": "strong",
        "scenario_reaction": "strong",
        "option_selection": "strong",
        "option_rejection": "medium",
        "trip_revision": "strong",
    },
    "recovery_vs_intensity": {
        "direct_statement": "medium",
        "forced_tradeoff_choice": "strong",
        "scenario_reaction": "strong",
        "option_selection": "strong",
        "option_rejection": "medium",
        "trip_revision": "strong",
    },
    "nature_vs_culture": {
        "direct_statement": "medium",
        "forced_tradeoff_choice": "strong",
        "scenario_reaction": "strong",
        "option_selection": "strong",
        "option_rejection": "medium",
        "trip_revision": "medium",
    },
    "structure_vs_elasticity": {
        "direct_statement": "medium",
        "scenario_reaction": "strong",
        "forced_tradeoff_choice": "strong",
        "option_selection": "medium",
        "trip_revision": "strong",
    },
    "breadth_vs_depth": {
        "direct_statement": "medium",
        "forced_tradeoff_choice": "strong",
        "scenario_reaction": "strong",
        "option_selection": "medium",
        "trip_revision": "strong",
    },
    "self_reliance_vs_convenience": {
        "direct_statement": "medium",
        "forced_tradeoff_choice": "strong",
        "scenario_reaction": "strong",
        "option_selection": "strong",
        "option_rejection": "medium",
        "trip_revision": "medium",
    },
    "historic_vs_contemporary": {
        "direct_statement": "medium",
        "forced_tradeoff_choice": "strong",
        "scenario_reaction": "strong",
        "option_selection": "medium",
        "trip_revision": "medium",
    },
    "scenic_transit_vs_destination_time": {
        "direct_statement": "medium",
        "forced_tradeoff_choice": "strong",
        "scenario_reaction": "strong",
        "option_selection": "strong",
        "option_rejection": "medium",
    },
    "route_coherence_vs_eclectic_contrast": {
        "direct_statement": "medium",
        "forced_tradeoff_choice": "strong",
        "scenario_reaction": "strong",
        "option_selection": "medium",
        "trip_revision": "strong",
    },
    "social_energy_vs_solitude": {
        "direct_statement": "medium",
        "forced_tradeoff_choice": "strong",
        "scenario_reaction": "strong",
        "option_selection": "medium",
        "trip_revision": "medium",
    },
    "iconic_vs_discovery": {
        "direct_statement": "medium",
        "forced_tradeoff_choice": "strong",
        "scenario_reaction": "strong",
        "option_selection": "strong",
        "option_rejection": "medium",
    },
}
HYBRID_FACTOR_EVIDENCE_STRENGTH: Final[EvidenceSupportCatalog] = {
    "food": {
        "direct_statement": "medium",
        "anchor_declaration": "strong",
        "scenario_reaction": "medium",
        "option_selection": "strong",
        "option_rejection": "strong",
        "trip_revision": "medium",
    },
    "rest": {
        "direct_statement": "medium",
        "anchor_declaration": "strong",
        "scenario_reaction": "strong",
        "option_selection": "strong",
        "option_rejection": "medium",
        "trip_revision": "strong",
    },
    "music": {
        "direct_statement": "medium",
        "anchor_declaration": "strong",
        "scenario_reaction": "medium",
        "option_selection": "strong",
        "trip_revision": "medium",
    },
    "route_modes": {
        "direct_statement": "medium",
        "anchor_declaration": "strong",
        "forced_tradeoff_choice": "medium",
        "option_selection": "strong",
        "option_rejection": "strong",
        "trip_revision": "medium",
    },
}


def _require_support_level(level: str) -> None:
    if level not in EVIDENCE_SUPPORT_LEVELS:
        raise ValueError(f"support level must be one of {EVIDENCE_SUPPORT_LEVELS}")


def support_for_dimension(dimension_key: str, evidence_type: str) -> str | None:
    if dimension_key not in schema.TRADEOFF_DIMENSION_KEYS:
        raise ValueError(
            f"dimension_key must be one of {schema.TRADEOFF_DIMENSION_KEYS}"
        )
    level = DIMENSION_EVIDENCE_STRENGTH[dimension_key].get(evidence_type)
    if level is not None:
        _require_support_level(level)
    return level


def support_for_hybrid_factor(hybrid_factor_key: str, evidence_type: str) -> str | None:
    if hybrid_factor_key not in schema.HYBRID_FACTOR_KEYS:
        raise ValueError(
            f"hybrid_factor_key must be one of {schema.HYBRID_FACTOR_KEYS}"
        )
    level = HYBRID_FACTOR_EVIDENCE_STRENGTH[hybrid_factor_key].get(evidence_type)
    if level is not None:
        _require_support_level(level)
    return level


def support_for_anchor_group(anchor_group: str, evidence_type: str) -> str | None:
    if anchor_group not in schema.ANCHOR_GROUPS:
        raise ValueError(f"anchor_group must be one of {schema.ANCHOR_GROUPS}")
    level = ANCHOR_GROUP_EVIDENCE_STRENGTH[anchor_group].get(evidence_type)
    if level is not None:
        _require_support_level(level)
    return level


def validate_evidence_support(record: PreferenceEvidence) -> None:
    for dimension in record.affected_dimensions:
        if support_for_dimension(dimension, record.evidence_type) is None:
            raise ValueError(
                f"{record.evidence_type!r} is not valid evidence for dimension {dimension!r}"
            )
    for hybrid_factor in record.affected_hybrid_factors:
        if support_for_hybrid_factor(hybrid_factor, record.evidence_type) is None:
            raise ValueError(
                f"{record.evidence_type!r} is not valid evidence for hybrid factor "
                f"{hybrid_factor!r}"
            )
    for anchor_group in record.anchor_groups:
        if support_for_anchor_group(anchor_group, record.evidence_type) is None:
            raise ValueError(
                f"{record.evidence_type!r} is not valid evidence for anchor group "
                f"{anchor_group!r}"
            )
