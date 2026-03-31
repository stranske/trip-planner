"""Canonical shared planning contracts for destinations, trips, options, and objectives."""

from __future__ import annotations

from importlib import import_module

_EXPORTS: dict[str, str] = {
    "ACTIVITY_AVAILABILITY_STATUSES": "trip_planner.contracts.activities",
    "ACTIVITY_FORMATS": "trip_planner.contracts.activities",
    "ACTIVITY_KINDS": "trip_planner.contracts.activities",
    "ACTIVITY_SCHEMA_VERSION": "trip_planner.contracts.activities",
    "ADJACENCY_KINDS": "trip_planner.contracts.destinations",
    "AdjacencyKind": "trip_planner.contracts.destinations",
    "ActivityBookingTerms": "trip_planner.contracts.activities",
    "ActivityCategory": "trip_planner.contracts.activities",
    "ActivityCostSummary": "trip_planner.contracts.activities",
    "ActivityEffortSummary": "trip_planner.contracts.activities",
    "ActivityFeasibility": "trip_planner.contracts.activities",
    "ActivityFitSummary": "trip_planner.contracts.activities",
    "ActivityOption": "trip_planner.contracts.activities",
    "ActivityQualitySummary": "trip_planner.contracts.activities",
    "ActivitySignificanceSummary": "trip_planner.contracts.activities",
    "ActivityTimingSummary": "trip_planner.contracts.activities",
    "ActivityValueSummary": "trip_planner.contracts.activities",
    "BudgetProtection": "trip_planner.contracts.objectives",
    "ComparisonAxis": "trip_planner.contracts.options",
    "CountRange": "trip_planner.contracts.objectives",
    "DayStructureObjectives": "trip_planner.contracts.objectives",
    "Destination": "trip_planner.contracts.destinations",
    "DestinationGeo": "trip_planner.contracts.destinations",
    "DestinationSourceRef": "trip_planner.contracts.destinations",
    "DestinationTag": "trip_planner.contracts.destinations",
    "EFFORT_LEVELS": "trip_planner.contracts.activities",
    "DiscoveryStrategy": "trip_planner.contracts.objectives",
    "EXPERIENCE_SENTIMENTS": "trip_planner.contracts.destinations",
    "ExperienceSignal": "trip_planner.contracts.destinations",
    "EXPANSION_MODES": "trip_planner.contracts.destinations",
    "INVENTORY_STATUSES": "trip_planner.contracts.lodging",
    "ItineraryObjectives": "trip_planner.contracts.objectives",
    "LodgingBookingTerms": "trip_planner.contracts.lodging",
    "LodgingCostSummary": "trip_planner.contracts.lodging",
    "LodgingFeasibility": "trip_planner.contracts.lodging",
    "LodgingFitSummary": "trip_planner.contracts.lodging",
    "LodgingLocationSummary": "trip_planner.contracts.lodging",
    "LodgingOption": "trip_planner.contracts.lodging",
    "LodgingQualitySummary": "trip_planner.contracts.lodging",
    "LodgingRoomSummary": "trip_planner.contracts.lodging",
    "LodgingStrategy": "trip_planner.contracts.objectives",
    "LodgingValueSummary": "trip_planner.contracts.lodging",
    "LOCATION_CONTEXTS": "trip_planner.contracts.lodging",
    "LODGING_KINDS": "trip_planner.contracts.lodging",
    "MOBILITY_MODES": "trip_planner.contracts.destinations",
    "MobilityProfile": "trip_planner.contracts.destinations",
    "MoneyRange": "trip_planner.contracts.options",
    "MoveDensityTarget": "trip_planner.contracts.objectives",
    "NearbyDestinationRef": "trip_planner.contracts.destinations",
    "OPERATIONAL_NOTE_IMPACTS": "trip_planner.contracts.destinations",
    "OPERATIONAL_NOTE_KINDS": "trip_planner.contracts.destinations",
    "OperationalNote": "trip_planner.contracts.destinations",
    "Option": "trip_planner.contracts.options",
    "OptionCostSummary": "trip_planner.contracts.options",
    "OptionQualitySummary": "trip_planner.contracts.options",
    "OptionSet": "trip_planner.contracts.options",
    "PLACE_CONTEXT_BOUNDARIES": "trip_planner.contracts.destinations",
    "PLACE_CONTEXT_ROLES": "trip_planner.contracts.destinations",
    "PLACE_KINDS": "trip_planner.contracts.destinations",
    "PLACE_RELATIONSHIP_KINDS": "trip_planner.contracts.destinations",
    "PROVENANCE_ROLES": "trip_planner.contracts.destinations",
    "PlaceContext": "trip_planner.contracts.destinations",
    "PlaceContextRole": "trip_planner.contracts.destinations",
    "PlaceHierarchyRef": "trip_planner.contracts.destinations",
    "PlaceKind": "trip_planner.contracts.destinations",
    "PlaceRelationshipKind": "trip_planner.contracts.destinations",
    "ProfileRefs": "trip_planner.contracts.trip",
    "QualityFloorProtection": "trip_planner.contracts.objectives",
    "RecoveryExpectations": "trip_planner.contracts.objectives",
    "RegionExpansionRef": "trip_planner.contracts.destinations",
    "SCHEMA_VERSION": "trip_planner.contracts.destinations",
    "SEASONS": "trip_planner.contracts.destinations",
    "SEASONAL_IMPACTS": "trip_planner.contracts.destinations",
    "SeasonalSignal": "trip_planner.contracts.destinations",
    "TAG_SCOPES": "trip_planner.contracts.destinations",
    "TransportStrategy": "trip_planner.contracts.objectives",
    "TravelerPartySummary": "trip_planner.contracts.trip",
    "Trip": "trip_planner.contracts.trip",
    "TripArtifactRefs": "trip_planner.contracts.trip",
    "TripFrameSummary": "trip_planner.contracts.trip",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> object:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value
