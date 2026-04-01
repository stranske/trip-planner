"""Normalized destination and place-context contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, TypeAlias

from trip_planner._validators import (
    require_non_empty,
    require_non_negative,
    require_optional_non_empty,
    require_probability,
    require_strings,
)
from trip_planner.sources import schema as source_schema

SCHEMA_VERSION = "0.1.0"

PLACE_KINDS: tuple[str, ...] = ("city", "region", "neighborhood", "landscape", "site")
PLACE_RELATIONSHIP_KINDS: tuple[str, ...] = (
    "parent_region",
    "parent_city",
    "parent_neighborhood",
    "parent_landscape",
    "parent_site",
)
ADJACENCY_KINDS: tuple[str, ...] = (
    "adjacent_region",
    "nearby_region",
    "contiguous_region",
    "day_trip",
    "gateway",
)
SEASONS: tuple[str, ...] = ("winter", "spring", "summer", "autumn", "shoulder")
SEASONAL_IMPACTS: tuple[str, ...] = ("positive", "negative", "mixed", "contextual")
EXPERIENCE_SENTIMENTS: tuple[str, ...] = ("positive", "negative", "mixed", "contextual")
MOBILITY_MODES: tuple[str, ...] = (
    "walk",
    "transit",
    "rail",
    "car",
    "bike",
    "ferry",
    "rideshare",
    "shuttle",
)
TAG_SCOPES: tuple[str, ...] = (
    "identity",
    "routing",
    "experience",
    "seasonal",
    "operational",
)
PROVENANCE_ROLES: tuple[str, ...] = (
    "identity",
    "seasonal",
    "operational",
    "experience",
    "routing",
)
OPERATIONAL_NOTE_KINDS: tuple[str, ...] = (
    "access",
    "crowding",
    "hours",
    "seasonal",
    "safety",
    "booking",
)
OPERATIONAL_NOTE_IMPACTS: tuple[str, ...] = ("low", "medium", "high")
EXPANSION_MODES: tuple[str, ...] = ("day_trip", "overnight", "hub_spoke", "contiguous")
PLACE_CONTEXT_ROLES: tuple[str, ...] = (
    "trip_anchor",
    "base",
    "micro_context",
    "gateway",
    "day_trip_area",
    "expansion_area",
)
PLACE_CONTEXT_BOUNDARIES: tuple[str, ...] = (
    "exact_place",
    "walkable_cluster",
    "district",
    "citywide",
    "regional",
)

PlaceKind: TypeAlias = Literal["city", "region", "neighborhood", "landscape", "site"]
PlaceRelationshipKind: TypeAlias = Literal[
    "parent_region",
    "parent_city",
    "parent_neighborhood",
    "parent_landscape",
    "parent_site",
]
AdjacencyKind: TypeAlias = Literal[
    "adjacent_region",
    "nearby_region",
    "contiguous_region",
    "day_trip",
    "gateway",
]
PlaceContextRole: TypeAlias = Literal[
    "trip_anchor",
    "base",
    "micro_context",
    "gateway",
    "day_trip_area",
    "expansion_area",
]


def _require_months(months: list[int], field_name: str) -> None:
    for month in months:
        if not isinstance(month, int):
            raise ValueError(f"{field_name} must contain only integers")
        if month < 1 or month > 12:
            raise ValueError(f"{field_name} months must be between 1 and 12")


def _require_modes(modes: list[str], field_name: str) -> None:
    require_strings(modes, field_name)
    for mode in modes:
        if mode not in MOBILITY_MODES:
            raise ValueError(f"{field_name} must contain only {MOBILITY_MODES}")


def _optional_list_field(payload: dict[str, Any], field_name: str) -> list[Any]:
    value = payload.get(field_name, [])
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list when provided")
    return value


def _optional_mapping_field(payload: dict[str, Any], field_name: str) -> dict[str, Any]:
    value = payload.get(field_name, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a mapping when provided")
    return value


@dataclass(slots=True)
class DestinationGeo:
    latitude: float
    longitude: float
    country_code: str
    region_code: str = ""
    time_zone: str = ""
    locality_hint: str = ""

    def __post_init__(self) -> None:
        if not -90.0 <= self.latitude <= 90.0:
            raise ValueError("latitude must be between -90.0 and 90.0")
        if not -180.0 <= self.longitude <= 180.0:
            raise ValueError("longitude must be between -180.0 and 180.0")
        require_non_empty(self.country_code, "country_code")
        require_optional_non_empty(self.region_code or None, "region_code")
        require_optional_non_empty(self.time_zone or None, "time_zone")
        require_optional_non_empty(self.locality_hint or None, "locality_hint")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PlaceHierarchyRef:
    destination_id: str
    relationship_kind: PlaceRelationshipKind
    label: str = ""
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.destination_id, "destination_id")
        if self.relationship_kind not in PLACE_RELATIONSHIP_KINDS:
            raise ValueError(
                f"relationship_kind must be one of {PLACE_RELATIONSHIP_KINDS}"
            )
        require_optional_non_empty(self.label or None, "label")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SeasonalSignal:
    season: str
    summary: str
    impact: str = "contextual"
    peak_months: list[int] = field(default_factory=list)
    source_ref_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.season not in SEASONS:
            raise ValueError(f"season must be one of {SEASONS}")
        require_non_empty(self.summary, "summary")
        if self.impact not in SEASONAL_IMPACTS:
            raise ValueError(f"impact must be one of {SEASONAL_IMPACTS}")
        _require_months(self.peak_months, "peak_months")
        require_strings(self.source_ref_ids, "source_ref_ids")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExperienceSignal:
    key: str
    label: str
    sentiment: str = "positive"
    strength: float | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.key, "key")
        require_non_empty(self.label, "label")
        if self.sentiment not in EXPERIENCE_SENTIMENTS:
            raise ValueError(f"sentiment must be one of {EXPERIENCE_SENTIMENTS}")
        if self.strength is not None:
            require_probability(self.strength, "strength")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DestinationTag:
    key: str
    label: str
    scope: str = "identity"
    weight: float | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.key, "key")
        require_non_empty(self.label, "label")
        if self.scope not in TAG_SCOPES:
            raise ValueError(f"scope must be one of {TAG_SCOPES}")
        if self.weight is not None:
            require_probability(self.weight, "weight")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MobilityProfile:
    arrival_modes: list[str] = field(default_factory=list)
    local_modes: list[str] = field(default_factory=list)
    access_constraints: list[str] = field(default_factory=list)
    interchange_hubs: list[str] = field(default_factory=list)
    walkability: float | None = None
    transit_coverage: float | None = None
    car_dependency: float | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_modes(self.arrival_modes, "arrival_modes")
        _require_modes(self.local_modes, "local_modes")
        require_strings(self.access_constraints, "access_constraints")
        require_strings(self.interchange_hubs, "interchange_hubs")
        for field_name in ("walkability", "transit_coverage", "car_dependency"):
            value = getattr(self, field_name)
            if value is not None:
                require_probability(value, field_name)
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DestinationSourceRef:
    provenance_id: str
    role: str = "identity"
    source_id: str = ""
    source_category: str = ""
    contribution_kind: str = ""
    summary: str = ""
    freshness_days_at_capture: int | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.provenance_id, "provenance_id")
        if self.role not in PROVENANCE_ROLES:
            raise ValueError(f"role must be one of {PROVENANCE_ROLES}")
        require_optional_non_empty(self.source_id or None, "source_id")
        require_optional_non_empty(self.source_category or None, "source_category")
        if (
            self.source_category
            and self.source_category not in source_schema.SOURCE_CATEGORIES
        ):
            raise ValueError(
                f"source_category must be one of {source_schema.SOURCE_CATEGORIES}"
            )
        require_optional_non_empty(self.contribution_kind or None, "contribution_kind")
        if (
            self.contribution_kind
            and self.contribution_kind not in source_schema.CONTRIBUTION_KINDS
        ):
            raise ValueError(
                f"contribution_kind must be one of {source_schema.CONTRIBUTION_KINDS}"
            )
        require_optional_non_empty(self.summary or None, "summary")
        if self.freshness_days_at_capture is not None:
            require_non_negative(
                self.freshness_days_at_capture, "freshness_days_at_capture"
            )
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class NearbyDestinationRef:
    destination_id: str
    relationship_kind: AdjacencyKind
    summary: str = ""
    transit_time_minutes: int | None = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.destination_id, "destination_id")
        if self.relationship_kind not in ADJACENCY_KINDS:
            raise ValueError(f"relationship_kind must be one of {ADJACENCY_KINDS}")
        require_optional_non_empty(self.summary or None, "summary")
        if self.transit_time_minutes is not None:
            require_non_negative(self.transit_time_minutes, "transit_time_minutes")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RegionExpansionRef:
    destination_id: str
    relationship_kind: AdjacencyKind
    expansion_mode: str
    summary: str = ""
    requires_base_change: bool = False
    transit_time_minutes: int | None = None
    trigger_tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_non_empty(self.destination_id, "destination_id")
        if self.relationship_kind not in ADJACENCY_KINDS:
            raise ValueError(f"relationship_kind must be one of {ADJACENCY_KINDS}")
        if self.expansion_mode not in EXPANSION_MODES:
            raise ValueError(f"expansion_mode must be one of {EXPANSION_MODES}")
        require_optional_non_empty(self.summary or None, "summary")
        if self.transit_time_minutes is not None:
            require_non_negative(self.transit_time_minutes, "transit_time_minutes")
        require_strings(self.trigger_tags, "trigger_tags")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class OperationalNote:
    kind: str
    summary: str
    impact: str = "medium"
    applies_in_months: list[int] = field(default_factory=list)
    source_ref_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.kind not in OPERATIONAL_NOTE_KINDS:
            raise ValueError(f"kind must be one of {OPERATIONAL_NOTE_KINDS}")
        require_non_empty(self.summary, "summary")
        if self.impact not in OPERATIONAL_NOTE_IMPACTS:
            raise ValueError(f"impact must be one of {OPERATIONAL_NOTE_IMPACTS}")
        _require_months(self.applies_in_months, "applies_in_months")
        require_strings(self.source_ref_ids, "source_ref_ids")
        require_strings(self.notes, "notes")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Destination:
    destination_id: str
    place_kind: PlaceKind
    name: str
    geo: DestinationGeo
    summary: str = ""
    parent_refs: list[PlaceHierarchyRef] = field(default_factory=list)
    tags: list[DestinationTag] = field(default_factory=list)
    seasonal_signals: list[SeasonalSignal] = field(default_factory=list)
    mobility_profile: MobilityProfile = field(default_factory=MobilityProfile)
    experience_signals: list[ExperienceSignal] = field(default_factory=list)
    adjacency_refs: list[NearbyDestinationRef] = field(default_factory=list)
    region_expansion_refs: list[RegionExpansionRef] = field(default_factory=list)
    source_refs: list[DestinationSourceRef] = field(default_factory=list)
    operational_notes: list[OperationalNote] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_non_empty(self.destination_id, "destination_id")
        require_non_empty(self.name, "name")
        if self.place_kind not in PLACE_KINDS:
            raise ValueError(f"place_kind must be one of {PLACE_KINDS}")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
        if not isinstance(self.geo, DestinationGeo):
            raise ValueError("geo must be a DestinationGeo")
        if any(not isinstance(item, PlaceHierarchyRef) for item in self.parent_refs):
            raise ValueError("parent_refs must contain PlaceHierarchyRef instances")
        if any(not isinstance(item, DestinationTag) for item in self.tags):
            raise ValueError("tags must contain DestinationTag instances")
        if any(not isinstance(item, SeasonalSignal) for item in self.seasonal_signals):
            raise ValueError("seasonal_signals must contain SeasonalSignal instances")
        if not isinstance(self.mobility_profile, MobilityProfile):
            raise ValueError("mobility_profile must be a MobilityProfile")
        if any(
            not isinstance(item, ExperienceSignal) for item in self.experience_signals
        ):
            raise ValueError(
                "experience_signals must contain ExperienceSignal instances"
            )
        if any(
            not isinstance(item, NearbyDestinationRef) for item in self.adjacency_refs
        ):
            raise ValueError(
                "adjacency_refs must contain NearbyDestinationRef instances"
            )
        if any(
            not isinstance(item, RegionExpansionRef)
            for item in self.region_expansion_refs
        ):
            raise ValueError(
                "region_expansion_refs must contain RegionExpansionRef instances"
            )
        if any(not isinstance(item, DestinationSourceRef) for item in self.source_refs):
            raise ValueError("source_refs must contain DestinationSourceRef instances")
        if any(
            not isinstance(item, OperationalNote) for item in self.operational_notes
        ):
            raise ValueError("operational_notes must contain OperationalNote instances")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Destination":
        return cls(
            destination_id=payload["destination_id"],
            place_kind=payload["place_kind"],
            name=payload["name"],
            geo=DestinationGeo(**payload["geo"]),
            summary=payload.get("summary", ""),
            parent_refs=[
                PlaceHierarchyRef(**item)
                for item in _optional_list_field(payload, "parent_refs")
            ],
            tags=[
                DestinationTag(**item) for item in _optional_list_field(payload, "tags")
            ],
            seasonal_signals=[
                SeasonalSignal(**item)
                for item in _optional_list_field(payload, "seasonal_signals")
            ],
            mobility_profile=MobilityProfile(
                **_optional_mapping_field(payload, "mobility_profile")
            ),
            experience_signals=[
                ExperienceSignal(**item)
                for item in _optional_list_field(payload, "experience_signals")
            ],
            adjacency_refs=[
                NearbyDestinationRef(**item)
                for item in _optional_list_field(payload, "adjacency_refs")
            ],
            region_expansion_refs=[
                RegionExpansionRef(**item)
                for item in _optional_list_field(payload, "region_expansion_refs")
            ],
            source_refs=[
                DestinationSourceRef(**item)
                for item in _optional_list_field(payload, "source_refs")
            ],
            operational_notes=[
                OperationalNote(**item)
                for item in _optional_list_field(payload, "operational_notes")
            ],
            schema_version=payload.get("schema_version", SCHEMA_VERSION),
        )


@dataclass(slots=True)
class PlaceContext:
    context_id: str
    destination_id: str
    place_kind: PlaceKind
    role: PlaceContextRole
    label: str
    boundary_mode: str = "district"
    summary: str = ""
    parent_context_ids: list[str] = field(default_factory=list)
    supporting_destination_ids: list[str] = field(default_factory=list)
    tag_keys: list[str] = field(default_factory=list)
    source_ref_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_non_empty(self.context_id, "context_id")
        require_non_empty(self.destination_id, "destination_id")
        require_non_empty(self.label, "label")
        if self.place_kind not in PLACE_KINDS:
            raise ValueError(f"place_kind must be one of {PLACE_KINDS}")
        if self.role not in PLACE_CONTEXT_ROLES:
            raise ValueError(f"role must be one of {PLACE_CONTEXT_ROLES}")
        if self.boundary_mode not in PLACE_CONTEXT_BOUNDARIES:
            raise ValueError(f"boundary_mode must be one of {PLACE_CONTEXT_BOUNDARIES}")
        require_optional_non_empty(self.summary or None, "summary")
        require_strings(self.parent_context_ids, "parent_context_ids")
        require_strings(self.supporting_destination_ids, "supporting_destination_ids")
        require_strings(self.tag_keys, "tag_keys")
        require_strings(self.source_ref_ids, "source_ref_ids")
        require_strings(self.notes, "notes")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PlaceContext":
        return cls(
            context_id=payload["context_id"],
            destination_id=payload["destination_id"],
            place_kind=payload["place_kind"],
            role=payload["role"],
            label=payload["label"],
            boundary_mode=payload.get("boundary_mode", "district"),
            summary=payload.get("summary", ""),
            parent_context_ids=_optional_list_field(payload, "parent_context_ids"),
            supporting_destination_ids=_optional_list_field(
                payload, "supporting_destination_ids"
            ),
            tag_keys=_optional_list_field(payload, "tag_keys"),
            source_ref_ids=_optional_list_field(payload, "source_ref_ids"),
            notes=_optional_list_field(payload, "notes"),
            schema_version=payload.get("schema_version", SCHEMA_VERSION),
        )

    @classmethod
    def from_destination(
        cls,
        destination: Destination,
        *,
        context_id: str,
        role: PlaceContextRole,
        label: str | None = None,
        boundary_mode: str = "district",
        summary: str = "",
        parent_context_ids: list[str] | None = None,
        supporting_destination_ids: list[str] | None = None,
        tag_keys: list[str] | None = None,
        source_ref_ids: list[str] | None = None,
        notes: list[str] | None = None,
    ) -> "PlaceContext":
        if not isinstance(destination, Destination):
            raise ValueError("destination must be a Destination")

        return cls(
            context_id=context_id,
            destination_id=destination.destination_id,
            place_kind=destination.place_kind,
            role=role,
            label=label or destination.name,
            boundary_mode=boundary_mode,
            summary=summary or destination.summary,
            parent_context_ids=parent_context_ids or [],
            supporting_destination_ids=supporting_destination_ids
            or [destination.destination_id],
            tag_keys=tag_keys or [tag.key for tag in destination.tags],
            source_ref_ids=source_ref_ids
            or [source.provenance_id for source in destination.source_refs],
            notes=notes or [],
        )
