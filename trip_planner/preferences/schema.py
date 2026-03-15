"""Schema constants and factories for leisure preference contracts."""

from __future__ import annotations

from typing import Final

SCHEMA_VERSION: Final[str] = "0.1.0"
PROFILE_KIND: Final[str] = "leisure"

TRAVELER_PARTIES: Final[tuple[str, ...]] = ("solo", "pair", "family", "friends")
TRIP_STAGES: Final[tuple[str, ...]] = (
    "first_visit",
    "repeat_visit",
    "mixed",
)
PLANNING_STAGES: Final[tuple[str, ...]] = (
    "initial_design",
    "inventory_selection",
    "daily_activity_design",
    "in_trip_adjustment",
)
DIMENSION_SCOPES: Final[tuple[str, ...]] = (
    "global",
    "segment_specific",
    "conditional",
)
HYBRID_FACTOR_MODES: Final[tuple[str, ...]] = ("anchor", "tradeoff", "both")
HYBRID_FACTOR_ROLES: Final[tuple[str, ...]] = (
    "cost",
    "rhythm",
    "atmosphere",
    "route_design",
    "none",
)
ANCHOR_GROUPS: Final[tuple[str, ...]] = (
    "place_anchors",
    "experience_anchors",
    "mode_anchors",
    "rhythm_anchors",
    "calendar_anchors",
    "quality_floor_anchors",
    "regional_adjacency_preferences",
)
TRADEOFF_DIMENSION_KEYS: Final[tuple[str, ...]] = (
    "movement_vs_friction",
    "recovery_vs_intensity",
    "nature_vs_culture",
    "structure_vs_elasticity",
    "breadth_vs_depth",
    "self_reliance_vs_convenience",
    "historic_vs_contemporary",
    "scenic_transit_vs_destination_time",
    "route_coherence_vs_eclectic_contrast",
    "social_energy_vs_solitude",
    "iconic_vs_discovery",
)
HYBRID_FACTOR_KEYS: Final[tuple[str, ...]] = (
    "food",
    "rest",
    "music",
    "route_modes",
)
POLARITY_MAP: Final[dict[str, tuple[str, str]]] = {
    "movement_vs_friction": ("movement appetite", "friction sensitivity"),
    "recovery_vs_intensity": ("recovery need", "sustainable intensity"),
    "nature_vs_culture": ("nature", "culture"),
    "structure_vs_elasticity": ("structured days", "elastic days"),
    "breadth_vs_depth": ("breadth", "depth"),
    "self_reliance_vs_convenience": (
        "logistical self-reliance",
        "convenience support",
    ),
    "historic_vs_contemporary": ("historic depth", "contemporary life"),
    "scenic_transit_vs_destination_time": (
        "scenic transit",
        "destination time",
    ),
    "route_coherence_vs_eclectic_contrast": (
        "route coherence",
        "eclectic contrast",
    ),
    "social_energy_vs_solitude": ("social energy", "solitude"),
    "iconic_vs_discovery": ("iconic certainty", "curious discovery"),
}
COMPLEXITY_TOLERANCE_MAP: Final[dict[str, dict[str, float]]] = {
    "low": {
        "movement_vs_friction": -0.75,
        "recovery_vs_intensity": 0.45,
        "self_reliance_vs_convenience": -0.65,
    },
    "medium": {
        "movement_vs_friction": 0.0,
        "recovery_vs_intensity": 0.0,
        "self_reliance_vs_convenience": 0.0,
    },
    "high": {
        "movement_vs_friction": 0.75,
        "recovery_vs_intensity": -0.45,
        "self_reliance_vs_convenience": 0.65,
    },
}
