"""Canonical shared planning contracts for destinations, trips, options, and objectives."""

from __future__ import annotations

from importlib import import_module

_MODULE_EXPORTS: dict[str, tuple[str, ...]] = {
    "trip_planner.contracts.options": (
        "ComparisonAxis",
        "MoneyRange",
        "Option",
        "OptionCostSummary",
        "OptionQualitySummary",
        "OptionSet",
    ),
    "trip_planner.contracts.activities": (
        "ACTIVITY_AVAILABILITY_STATUSES",
        "ACTIVITY_FORMATS",
        "ACTIVITY_KINDS",
        "ACTIVITY_SCHEMA_VERSION",
        "ActivityBookingTerms",
        "ActivityCategory",
        "ActivityCostSummary",
        "ActivityEffortSummary",
        "ActivityFeasibility",
        "ActivityFitSummary",
        "ActivityOption",
        "ActivityQualitySummary",
        "ActivitySignificanceSummary",
        "ActivityTimingSummary",
        "ActivityValueSummary",
        "EFFORT_LEVELS",
    ),
    "trip_planner.contracts.destinations": (
        "ADJACENCY_KINDS",
        "AdjacencyKind",
        "Destination",
        "DestinationGeo",
        "DestinationSourceRef",
        "DestinationTag",
        "EXPERIENCE_SENTIMENTS",
        "ExperienceSignal",
        "EXPANSION_MODES",
        "MOBILITY_MODES",
        "MobilityProfile",
        "NearbyDestinationRef",
        "OPERATIONAL_NOTE_IMPACTS",
        "OPERATIONAL_NOTE_KINDS",
        "OperationalNote",
        "PlaceContext",
        "PLACE_CONTEXT_BOUNDARIES",
        "PLACE_CONTEXT_ROLES",
        "PLACE_KINDS",
        "PLACE_RELATIONSHIP_KINDS",
        "PlaceContextRole",
        "PlaceHierarchyRef",
        "PlaceKind",
        "PlaceRelationshipKind",
        "PROVENANCE_ROLES",
        "RegionExpansionRef",
        "SCHEMA_VERSION",
        "SEASONS",
        "SEASONAL_IMPACTS",
        "SeasonalSignal",
        "TAG_SCOPES",
    ),
    "trip_planner.contracts.lodging": (
        "INVENTORY_STATUSES",
        "LOCATION_CONTEXTS",
        "LODGING_KINDS",
        "LodgingBookingTerms",
        "LodgingCostSummary",
        "LodgingFeasibility",
        "LodgingFitSummary",
        "LodgingLocationSummary",
        "LodgingOption",
        "LodgingQualitySummary",
        "LodgingRoomSummary",
        "LodgingValueSummary",
    ),
    "trip_planner.contracts.objectives": (
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
    ),
    "trip_planner.contracts.trip": (
        "ProfileRefs",
        "TravelerPartySummary",
        "Trip",
        "TripArtifactRefs",
        "TripFrameSummary",
    ),
}

__all__ = [export_name for export_names in _MODULE_EXPORTS.values() for export_name in export_names]

_EXPORT_TO_MODULE = {
    export_name: module_name
    for module_name, export_names in _MODULE_EXPORTS.items()
    for export_name in export_names
}


def __getattr__(name: str) -> object:
    module_name = _EXPORT_TO_MODULE.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value
