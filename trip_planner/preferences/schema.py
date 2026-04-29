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
# Human-readable descriptions for each tradeoff dimension.
# Tuple: (short_description, negative_extreme_note, positive_extreme_note)
# Value range for all dimensions: [-1.0, 1.0]; 0.0 = balanced / unresolved.
DIMENSION_DESCRIPTIONS: Final[dict[str, tuple[str, str, str]]] = {
    "movement_vs_friction": (
        "How much the traveler enjoys frequent relocation versus preferring fewer, longer stays.",
        "Strong movement appetite: comfortable with daily or near-daily moves, treats transit as part of the experience.",
        "High friction sensitivity: values settled bases, dislikes repeated packing and logistical overhead.",
    ),
    "recovery_vs_intensity": (
        "Balance between needing deliberate rest periods and sustaining a packed, high-activity pace.",
        "High recovery need: requires built-in slow days, fatigue accumulates quickly without rest.",
        "Sustainable intensity: can maintain a full agenda across many consecutive active days.",
    ),
    "nature_vs_culture": (
        "Whether the traveler is drawn toward natural landscapes and outdoor settings or toward urban cultural immersion.",
        "Strong nature preference: landscapes, hiking, wildlife, and open terrain dominate the ideal trip.",
        "Strong culture preference: cities, museums, architecture, food scenes, and human history dominate.",
    ),
    "structure_vs_elasticity": (
        "Preference for pre-planned, detailed itineraries versus open, improvised days.",
        "Structured days: wants bookings, schedules, and an advance plan for most of the trip.",
        "Elastic days: prefers loose scaffolding, follows impulse, resists tight hour-by-hour planning.",
    ),
    "breadth_vs_depth": (
        "Whether the traveler wants to cover many places or linger and go deep in fewer locations.",
        "Strong breadth: maximizes the number of distinct places, regions, or countries visited.",
        "Strong depth: spends multiple days in each stop, prioritizes understanding over coverage.",
    ),
    "self_reliance_vs_convenience": (
        "Preference for handling logistics independently versus relying on pre-arranged services and support.",
        "Logistical self-reliance: books independently, navigates on foot or by public transit, avoids package services.",
        "Convenience support: values pre-arranged transfers, guided access, concierge help, and reduced friction.",
    ),
    "historic_vs_contemporary": (
        "Whether the traveler engages primarily with historical heritage or contemporary local life.",
        "Historic depth: ruins, heritage sites, old towns, museums of history, and layered architectural periods.",
        "Contemporary life: modern neighborhoods, current art, local food culture, and present-day urban texture.",
    ),
    "scenic_transit_vs_destination_time": (
        "Whether travel time between places is valued for scenic experience or minimized to maximize time at destinations.",
        "Scenic transit: slow trains, coastal ferries, and scenic passes are highlights, not overheads.",
        "Destination time: favors fastest practical transport to protect time on the ground.",
    ),
    "route_coherence_vs_eclectic_contrast": (
        "Whether the route should follow a thematic or geographic thread versus assembling contrasting, varied stops.",
        "Route coherence: logical geographic or thematic progression, aesthetic unity across the trip arc.",
        "Eclectic contrast: variety is the point — different landscapes, cultures, and moods in deliberate juxtaposition.",
    ),
    "social_energy_vs_solitude": (
        "Preference for busy, social environments versus quiet, low-stimulus settings.",
        "Social energy: thrives around crowds, lively neighborhoods, street life, and public social spaces.",
        "Solitude: seeks quiet lodging, low-traffic routes, and deliberate separation from tourist density.",
    ),
    "iconic_vs_discovery": (
        "Whether the trip prioritizes well-known must-see experiences or off-the-beaten-path finds.",
        "Iconic certainty: validates the trip through canonical highlights; Eiffel Tower, Colosseum, etc.",
        "Curious discovery: the best moments are unexpected; avoids crowds, seeks lesser-known places.",
    ),
}
DIMENSION_CONFIDENCE_GUIDANCE: Final[dict[str, str]] = {
    "movement_vs_friction": (
        "Prefer revealed routing or relocation choices over stated appetite when they conflict."
    ),
    "recovery_vs_intensity": (
        "Raise confidence when explicit fatigue notes and itinerary edits both protect recovery."
    ),
    "nature_vs_culture": (
        "Treat direct destination interests as strong, but require repeated behavior before overriding them."
    ),
    "structure_vs_elasticity": (
        "Structured-input planning preferences start strong and decay when later trip revisions loosen the plan."
    ),
    "breadth_vs_depth": (
        "Use chosen stay lengths and rejected fast routes as higher-confidence evidence than abstract statements."
    ),
    "self_reliance_vs_convenience": (
        "Option selections involving transfers, guided access, and booking support are the strongest signals."
    ),
    "historic_vs_contemporary": (
        "Keep confidence moderate unless attraction choices repeatedly favor one pole across multiple cities."
    ),
    "scenic_transit_vs_destination_time": (
        "Give revealed transport choices higher confidence than generic travel-style answers."
    ),
    "route_coherence_vs_eclectic_contrast": (
        "Increase confidence when scenario reactions and selected route bundles agree on route shape."
    ),
    "social_energy_vs_solitude": (
        "Treat lodging and neighborhood selections as strong behavioral confirmation of stated social energy."
    ),
    "iconic_vs_discovery": (
        "Use must-see declarations as strong explicit evidence and off-list substitutions as revealed evidence."
    ),
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
