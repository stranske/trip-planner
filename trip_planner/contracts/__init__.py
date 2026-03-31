"""Canonical shared planning contracts for destinations, trips, options, and objectives."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .objectives import (
        BudgetProtection,
        CountRange,
        DayStructureObjectives,
        DiscoveryStrategy,
        ItineraryObjectives,
        LodgingStrategy,
        MoveDensityTarget,
        QualityFloorProtection,
        RecoveryExpectations,
        TransportStrategy,
    )

_DESTINATION_EXPORTS = {
    "ADJACENCY_KINDS",
    "EXPERIENCE_SENTIMENTS",
    "EXPANSION_MODES",
    "MOBILITY_MODES",
    "OPERATIONAL_NOTE_IMPACTS",
    "OPERATIONAL_NOTE_KINDS",
    "PLACE_KINDS",
    "PLACE_RELATIONSHIP_KINDS",
    "PROVENANCE_ROLES",
    "SCHEMA_VERSION",
    "SEASONS",
    "SEASONAL_IMPACTS",
    "TAG_SCOPES",
    "AdjacencyKind",
    "Destination",
    "DestinationGeo",
    "DestinationSourceRef",
    "DestinationTag",
    "ExperienceSignal",
    "MobilityProfile",
    "NearbyDestinationRef",
    "OperationalNote",
    "PlaceHierarchyRef",
    "PlaceKind",
    "PlaceRelationshipKind",
    "RegionExpansionRef",
    "SeasonalSignal",
}

_OBJECTIVE_EXPORTS = {
    "BudgetProtection",
    "CountRange",
    "DayStructureObjectives",
    "DiscoveryStrategy",
    "ItineraryObjectives",
    "LodgingStrategy",
    "MoveDensityTarget",
    "QualityFloorProtection",
    "RecoveryExpectations",
    "TransportStrategy",
}

_OPTION_EXPORTS = {
    "ComparisonAxis",
    "MoneyRange",
    "Option",
    "OptionCostSummary",
    "OptionQualitySummary",
    "OptionSet",
}

_TRIP_EXPORTS = {
    "ProfileRefs",
    "TravelerPartySummary",
    "Trip",
    "TripArtifactRefs",
    "TripFrameSummary",
}

__all__ = sorted(
    _DESTINATION_EXPORTS | _OBJECTIVE_EXPORTS | _OPTION_EXPORTS | _TRIP_EXPORTS
)


def __getattr__(name: str) -> object:
    if name in _DESTINATION_EXPORTS:
        module = import_module(".destinations", __name__)
        return getattr(module, name)
    if name in _OBJECTIVE_EXPORTS:
        module = import_module(".objectives", __name__)
        return getattr(module, name)
    if name in _OPTION_EXPORTS:
        module = import_module(".options", __name__)
        return getattr(module, name)
    if name in _TRIP_EXPORTS:
        module = import_module(".trip", __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
