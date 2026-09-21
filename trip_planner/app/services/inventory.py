from __future__ import annotations

import itertools
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from importlib import resources
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.geo import ResolvedPlace, distance_km, resolve_place
from trip_planner.options import InventoryBundle, MixedOption
from trip_planner.persistence.models.trip import PersistedTrip
from trip_planner.sources import (
    AdapterIssue,
    NormalizationHandoff,
    ProvenanceReference,
    QualityValueFitSummary,
    RawSnapshot,
    RawSourceRecord,
    SourceAdapter,
    SourceQuery,
    SourceRecord,
    SourceTrustSignals,
)

_BUNDLE_RESOURCE_PACKAGE = "trip_planner.resources.options.bundles"

_CATEGORY_COMMERCIALITY: dict[str, float] = {
    "official_operational": 0.20,
    "managed_travel_policy": 0.35,
    "commercial_inventory": 0.75,
    "ratings_reviews": 0.45,
    "editorial": 0.20,
    "specialist_non_commercial": 0.15,
}


def _commerciality_for_category(category: str) -> float:
    return _CATEGORY_COMMERCIALITY.get(category, 0.5)


class UnsupportedDestinationError(ValueError):
    """Raised when the planner has no geographic coverage for a destination.

    The planner may only plan places it actually knows. Anything else must surface as
    a stated limit, never as a bundle built from an invented location.
    """

    def __init__(self, message: str, *, region: str) -> None:
        super().__init__(message)
        self.region = region


def supported_destinations() -> list[str]:
    """Curated fallback destinations; real coverage comes from the GeoNames dataset."""

    return sorted(_REGION_GEO_DEFAULTS)


#: Nightly lodging allowance by trip mode, in USD. A documented planning assumption,
#: not a quoted rate; the traveller refines it on the Budget tab.
LODGING_NIGHTLY_RATE_USD: dict[str, float] = {"business": 230.0, "leisure": 165.0}

#: Daily activity/incidental allowance by trip mode, in USD.
ACTIVITY_ALLOWANCE_USD: dict[str, float] = {"business": 75.0, "leisure": 120.0}

#: Above this great-circle distance the journey is modelled as a flight. Set at 700 km
#: because surface rail stays competitive with air below roughly that range on the
#: corridors this planner sees (e.g. Stockholm-Oslo at 417 km is a train journey).
AIR_THRESHOLD_KM = 700.0

#: Modelled surface speed (km/h) and per-km cost for a ground leg.
GROUND_SPEED_KMH = 80.0
GROUND_COST_PER_KM_USD = 0.28

#: Modelled cruise speed (km/h) for an air leg, plus fixed airport overhead in minutes
#: (check-in, security, taxi, transfer) applied once per flown leg.
AIR_SPEED_KMH = 780.0
AIR_OVERHEAD_MINUTES = 150
AIR_BASE_COST_USD = 90.0
AIR_COST_PER_KM_USD = 0.11

#: A local gateway transfer (airport or station to the city) applied per destination.
LOCAL_TRANSFER_MINUTES = 45
LOCAL_TRANSFER_COST_USD = 55.0


@dataclass(frozen=True)
class JourneyProfile:
    """Travel time and transport cost derived from the trip's real geography.

    These are modelled estimates whose inputs are real: the great-circle distance
    between the places the traveller actually named. They vary with the trip. They are
    not quoted fares, and every component records its basis in `assumptions`.
    """

    destination: ResolvedPlace
    legs: tuple[tuple[str, str, float], ...]
    total_distance_km: float
    travel_minutes: int
    transport_cost_usd: float
    assumptions: tuple[str, ...]


def _leg_time_and_cost(distance_km_value: float) -> tuple[int, float, str]:
    """Minutes, USD and mode for one leg of a given great-circle distance."""

    if distance_km_value <= AIR_THRESHOLD_KM:
        minutes = round(distance_km_value / GROUND_SPEED_KMH * 60)
        return minutes, round(distance_km_value * GROUND_COST_PER_KM_USD, 2), "ground"
    minutes = round(distance_km_value / AIR_SPEED_KMH * 60) + AIR_OVERHEAD_MINUTES
    cost = AIR_BASE_COST_USD + distance_km_value * AIR_COST_PER_KM_USD
    return minutes, round(cost, 2), "air"


_REGION_GEO_DEFAULTS: dict[str, dict[str, Any]] = {
    "austin": {
        "latitude": 30.2672,
        "longitude": -97.7431,
        "country_code": "US",
        "region_code": "TX",
        "time_zone": "America/Chicago",
    },
    "chicago": {
        "latitude": 41.8781,
        "longitude": -87.6298,
        "country_code": "US",
        "region_code": "IL",
        "time_zone": "America/Chicago",
    },
    "barcelona": {
        "latitude": 41.3851,
        "longitude": 2.1734,
        "country_code": "ES",
        "time_zone": "Europe/Madrid",
    },
    "kyoto": {
        "latitude": 35.0116,
        "longitude": 135.7681,
        "country_code": "JP",
        "time_zone": "Asia/Tokyo",
    },
    "lisbon": {
        "latitude": 38.7223,
        "longitude": -9.1393,
        "country_code": "PT",
        "time_zone": "Europe/Lisbon",
    },
    "osaka": {
        "latitude": 34.6937,
        "longitude": 135.5023,
        "country_code": "JP",
        "time_zone": "Asia/Tokyo",
    },
    "prague": {
        "latitude": 50.0755,
        "longitude": 14.4378,
        "country_code": "CZ",
        "time_zone": "Europe/Prague",
    },
    "seattle": {
        "latitude": 47.6062,
        "longitude": -122.3321,
        "country_code": "US",
        "region_code": "WA",
        "time_zone": "America/Los_Angeles",
    },
    "tokyo": {
        "latitude": 35.6762,
        "longitude": 139.6503,
        "country_code": "JP",
        "time_zone": "Asia/Tokyo",
    },
    "vienna": {
        "latitude": 48.2082,
        "longitude": 16.3738,
        "country_code": "AT",
        "time_zone": "Europe/Vienna",
    },
}


@dataclass(frozen=True)
class InventoryFixtureSeed:
    trip_mode: str
    fixture_names: tuple[str, ...]


_FIXTURE_BUNDLE_INPUTS: dict[str, InventoryFixtureSeed] = {
    "trip-leisure-kyoto-draft": InventoryFixtureSeed(
        trip_mode="leisure",
        fixture_names=("route_level_mixed_option.json",),
    ),
    "trip-business-client-summit": InventoryFixtureSeed(
        trip_mode="business",
        fixture_names=("transport_lodging_bundle.json",),
    ),
}


@dataclass(frozen=True)
class InventoryAssemblyInput:
    trip_id: str
    trip_mode: str
    duration_days: int | None
    query: SourceQuery
    snapshot: RawSnapshot
    handoff: NormalizationHandoff
    record_payloads: tuple[dict[str, Any], ...]
    fixture_names: tuple[str, ...]
    allow_fixture_fallback: bool


@dataclass(frozen=True)
class PersistedTripInventoryContext:
    trip_id: str
    trip_mode: str
    start_date: str | None
    end_date: str | None
    trip_status: str | None
    primary_regions: tuple[str, ...]
    duration_days: int | None
    trip_title: str | None
    trip_summary: str | None
    traveler_party_kind: str | None
    traveler_count: int | None
    origin: str | None = None

    @classmethod
    def from_persisted_trip(cls, record: PersistedTrip) -> PersistedTripInventoryContext:
        return cls(
            trip_id=record.trip_id,
            trip_mode=record.mode,
            origin=getattr(record, "origin", None),
            start_date=record.start_date,
            end_date=record.end_date,
            trip_status=record.status,
            primary_regions=tuple(record.primary_regions),
            duration_days=record.duration_days,
            trip_title=record.title,
            trip_summary=record.summary,
            traveler_party_kind=record.traveler_party_kind,
            traveler_count=record.traveler_count,
        )


class PersistedTripInventoryFixtureAdapter(SourceAdapter):
    """Expose fixture-backed inventory as an explicit adapter seam for persisted trips."""

    def __init__(
        self,
        *,
        trip_id: str,
        trip_mode: str,
        primary_regions: Sequence[str],
        duration_days: int | None = None,
        allow_fixture_fallback: bool = True,
    ) -> None:
        self.trip_id = trip_id
        self.trip_mode = trip_mode
        self.primary_regions = tuple(region.strip() for region in primary_regions if region.strip())
        self.duration_days = duration_days
        self.allow_fixture_fallback = allow_fixture_fallback
        self.adapter_id = "persisted-trip-fixture-inventory"
        self.source_record = SourceRecord(
            source_id="fixture-normalized-inventory",
            provider_name="Trip Planner Fixtures",
            display_name="Fixture-backed normalized inventory",
            category="commercial_inventory",
            coverage_scope="global",
            supported_option_kinds=["mixed", "lodging"],
            trust_signals=SourceTrustSignals(
                freshness_days=0,
                freshness_confidence=0.7,
                commerciality=_commerciality_for_category("commercial_inventory"),
                operational_reliability=0.65,
                notes=["Fixture source freshness is pinned to the bundled fixture capture date."],
            ),
            quality_summary=QualityValueFitSummary(
                quality_signal=0.68,
                value_signal=0.62,
                fit_signal=0.7,
                confidence=0.66,
            ),
            notes=[
                "Provides a bounded adapter seam until live provider-backed inventory is available."
            ],
        )
        self.supported_entity_scopes = ("mixed", "lodging")
        self.supported_option_kinds = ("mixed", "lodging")
        self.capabilities = ("read_fixture", "supports_normalization_handoff")

    def fixture_names(self) -> tuple[str, ...]:
        if not self.allow_fixture_fallback:
            return ()
        fixture_seed = _FIXTURE_BUNDLE_INPUTS.get(self.trip_id)
        if fixture_seed is not None and fixture_seed.trip_mode == self.trip_mode:
            return fixture_seed.fixture_names
        if not self.primary_regions:
            return ()
        if self.duration_days is None or self.duration_days <= 0:
            return ()
        if self.trip_mode == "leisure":
            return ("route_level_mixed_option.json",)
        if self.trip_mode == "business":
            return ("transport_lodging_bundle.json",)
        return ()

    def fetch_snapshot(self, query: SourceQuery) -> RawSnapshot:
        fixture_names = self.fixture_names()
        issues: list[AdapterIssue] = []
        missing_primary_regions = not self.primary_regions
        missing_duration = self.duration_days is None or self.duration_days <= 0
        if not fixture_names:
            if missing_primary_regions:
                issues.append(
                    AdapterIssue(
                        issue_id=f"issue:{self.trip_id}:inventory-missing-regions",
                        stage="availability",
                        severity="warning",
                        code="missing_inventory_primary_regions",
                        message=(
                            "Primary regions are still missing, so the runtime inventory remains empty."
                        ),
                        details={"trip_id": self.trip_id, "trip_mode": self.trip_mode},
                    )
                )
            if missing_duration:
                issues.append(
                    AdapterIssue(
                        issue_id=f"issue:{self.trip_id}:inventory-missing-duration",
                        stage="availability",
                        severity="warning",
                        code="missing_inventory_trip_duration",
                        message=(
                            "Trip dates or duration are still missing, so inventory assembly stays partial."
                        ),
                        details={"trip_id": self.trip_id, "trip_mode": self.trip_mode},
                    )
                )
            if (
                not missing_primary_regions
                and not missing_duration
                and not self.allow_fixture_fallback
            ):
                issues.append(
                    AdapterIssue(
                        issue_id=f"issue:{self.trip_id}:inventory-live-adapter-pending",
                        stage="availability",
                        severity="warning",
                        code="missing_inventory_live_adapter",
                        message=(
                            "Fixture-backed inventory is disabled for the persisted workspace path until a live adapter is connected."
                        ),
                        details={"trip_id": self.trip_id, "trip_mode": self.trip_mode},
                    )
                )
        records: list[RawSourceRecord] = []
        for index, fixture_name in enumerate(fixture_names, start=1):
            mixed_option = _load_mixed_option_fixture(fixture_name)
            source_record_payload = self.source_record.to_dict()
            records.append(
                RawSourceRecord(
                    record_id=f"{query.query_id}:{index}",
                    entity_scope=query.entity_scope,
                    provider_entity_id=f"{self.trip_id}:{fixture_name}",
                    payload_type="normalized_bundle_seed",
                    payload={
                        "fixture_name": fixture_name,
                        "trip_id": self.trip_id,
                        "bundle_payloads": [
                            {
                                **bundle.to_dict(),
                                "source_records": [source_record_payload],
                            }
                            for bundle in mixed_option.bundles
                        ],
                    },
                    captured_at="2026-04-11T00:00:00Z",
                    metadata={
                        "fixture_name": fixture_name,
                        "bundle_count": str(len(mixed_option.bundles)),
                    },
                )
            )
        return RawSnapshot(
            snapshot_id=f"snapshot:{self.trip_id}:inventory",
            adapter_id=self.adapter_id,
            source_id=self.source_record.source_id,
            source_category=self.source_record.category,
            entity_scope=query.entity_scope,
            option_kind=query.option_kind,
            fetched_at="2026-04-11T00:00:00Z",
            query=query,
            records=records,
            issues=issues,
            snapshot_status="complete" if fixture_names else "partial",
            handoff_status="ready" if fixture_names else "partial",
            payload_metadata={
                "trip_id": self.trip_id,
                "trip_mode": self.trip_mode,
                "region_count": str(len(self.primary_regions)),
                "duration_days": "" if self.duration_days is None else str(self.duration_days),
            },
        )

    def build_handoff(self, snapshot: RawSnapshot) -> NormalizationHandoff:
        return NormalizationHandoff(
            handoff_id=f"handoff:{self.trip_id}:inventory",
            snapshot_id=snapshot.snapshot_id,
            target_contract="trip_planner/options/bundles.py",
            entity_scope=snapshot.entity_scope,
            status="ready" if snapshot.records else "partial",
            input_record_ids=[record.record_id for record in snapshot.records],
            blocked_issue_ids=[issue.issue_id for issue in snapshot.issues],
            provenance_refs=[
                ProvenanceReference(
                    provenance_id=f"prov:{record.record_id}",
                    source_id=snapshot.source_id,
                    source_category=snapshot.source_category,
                    subject_kind="option_set",
                    subject_id=f"inventory:{self.trip_id}",
                    contribution_kind="inventory",
                    summary=(
                        "Persisted trip inventory is routed through an adapter-backed fixture seam."
                    ),
                    captured_at=snapshot.fetched_at,
                )
                for record in snapshot.records
            ],
            record_count=len(snapshot.records),
            notes=(
                []
                if snapshot.records
                else [
                    "Return an empty bundle set rather than failing when persisted inventory inputs are missing."
                ]
            ),
        )


class PersistedTripSourceInventoryAdapter(SourceAdapter):
    """Build source-backed runtime inventory inputs from persisted trip context."""

    def __init__(
        self,
        *,
        trip_id: str,
        trip_mode: str,
        primary_regions: Sequence[str],
        origin: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        duration_days: int | None = None,
        trip_title: str | None = None,
        traveler_party_kind: str | None = None,
        traveler_count: int | None = None,
    ) -> None:
        self.trip_id = trip_id
        self.trip_mode = trip_mode
        self.primary_regions = tuple(region.strip() for region in primary_regions if region.strip())
        self.origin = (origin or "").strip() or None
        self.start_date = (start_date or "").strip()
        self.end_date = (end_date or "").strip()
        self.duration_days = duration_days
        self.trip_title = (trip_title or "").strip()
        self.traveler_party_kind = (traveler_party_kind or "").strip()
        self.traveler_count = traveler_count
        self.adapter_id = "persisted-trip-source-inventory"
        self.source_record = SourceRecord(
            source_id="persisted-trip-runtime-source",
            provider_name="Trip Planner Runtime",
            display_name="Persisted trip runtime inventory source",
            category="commercial_inventory",
            coverage_scope="global",
            supported_option_kinds=["mixed", "lodging", "activity", "rail"],
            coverage_regions=list(self.primary_regions),
            trust_signals=SourceTrustSignals(
                freshness_days=0,
                freshness_confidence=0.85,
                commerciality=_commerciality_for_category("commercial_inventory"),
                operational_reliability=0.76,
                notes=[
                    "Runtime inventory is generated from current persisted trip context.",
                    f"Primary region count: {len(self.primary_regions)}.",
                ],
            ),
            quality_summary=QualityValueFitSummary(
                quality_signal=0.78 if trip_mode == "business" else 0.74,
                value_signal=0.72 if trip_mode == "business" else 0.69,
                fit_signal=0.8 if primary_regions else 0.55,
                confidence=0.76 if primary_regions else 0.5,
            ),
            notes=["Derives normalized inventory seeds directly from persisted trip context."],
        )
        self.supported_entity_scopes = ("mixed",)
        self.supported_option_kinds = ("mixed", "lodging", "activity", "rail")
        self.capabilities = ("read_file", "supports_normalization_handoff")

    @classmethod
    def from_persisted_trip(cls, record: PersistedTrip) -> PersistedTripSourceInventoryAdapter:
        return cls(
            trip_id=record.trip_id,
            trip_mode=record.mode,
            primary_regions=tuple(record.primary_regions),
            origin=getattr(record, "origin", None),
            start_date=record.start_date,
            end_date=record.end_date,
            duration_days=record.duration_days,
            trip_title=record.title,
            traveler_party_kind=record.traveler_party_kind,
            traveler_count=record.traveler_count,
        )

    @staticmethod
    def _slug(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "destination"

    def _geo_lookup_keys(self, region: str) -> tuple[str, ...]:
        keys = [self._slug(region)]
        base_region = region.split(",", maxsplit=1)[0].strip()
        if base_region and base_region != region:
            keys.append(self._slug(base_region))
        return tuple(dict.fromkeys(keys))

    def _geo_payload(self, region: str) -> dict[str, Any]:
        # Curated entries carry a time zone and region code the dataset does not, so
        # they win where they exist. Their lookup keys also tolerate "Chicago, IL".
        for key in self._geo_lookup_keys(region):
            curated = _REGION_GEO_DEFAULTS.get(key)
            if curated is not None:
                return dict(curated)
        # Everywhere else comes from the bundled GeoNames dataset.
        place = resolve_place(region)
        if place is not None:
            return place.to_geo_payload()
        # Never invent a location. Emitting (0.0, 0.0) placed every unsupported
        # destination at Null Island and let the planner produce confident
        # route, timing and cost figures for a trip it knows nothing about.
        msg = f"no geographic coverage for destination {region!r}"
        raise UnsupportedDestinationError(msg, region=region)

    def _validate_primary_regions_supported(self) -> None:
        for region in self.primary_regions:
            self._geo_payload(region)

    def _trip_timestamp(self, *, hour: int, minute: int = 0) -> str:
        trip_date = self.start_date or self.end_date or "1970-01-01"
        return f"{trip_date}T{hour:02d}:{minute:02d}:00Z"

    @property
    def stable_source_id(self) -> str:
        """Stable source identifier for all options generated by this adapter.

        All option provenance references produced by this adapter share this
        source_id so that repeated runs with the same repository data yield
        identical source IDs regardless of which snapshot or record IDs are used.
        """
        return self.source_record.source_id

    @property
    def trip_mode_key(self) -> str:
        return "business" if self.trip_mode == "business" else "leisure"

    def _journey_profile(self) -> JourneyProfile:
        """Resolve every named destination and measure the real journey between them."""

        places = []
        origin_name = getattr(self, "origin", None)
        if origin_name:
            origin_place = resolve_place(origin_name)
            if origin_place is None:
                msg = f"no geographic coverage for origin {origin_name!r}"
                raise UnsupportedDestinationError(msg, region=origin_name)
            places.append(origin_place)
        for region in self.primary_regions:
            place = resolve_place(region)
            if place is None:
                msg = f"no geographic coverage for destination {region!r}"
                raise UnsupportedDestinationError(msg, region=region)
            places.append(place)

        legs: list[tuple[str, str, float]] = []
        total_km = 0.0
        minutes = 0
        cost = 0.0
        assumptions: list[str] = []
        for first, second in itertools.pairwise(places):
            leg_km = distance_km(first, second)
            leg_minutes, leg_cost, mode = _leg_time_and_cost(leg_km)
            legs.append((first.name, second.name, round(leg_km, 1)))
            total_km += leg_km
            minutes += leg_minutes
            cost += leg_cost
            assumptions.append(
                f"{first.name} to {second.name}: {leg_km:,.0f} km modelled as {mode}"
            )

        # Every destination also carries a local gateway transfer (airport/station to city).
        minutes += LOCAL_TRANSFER_MINUTES * len(places)
        cost += LOCAL_TRANSFER_COST_USD * len(places)
        assumptions.append(
            f"{len(places)} local gateway transfer(s) at {LOCAL_TRANSFER_MINUTES} min each"
        )

        return JourneyProfile(
            destination=places[1] if origin_name and len(places) > 1 else places[0],
            legs=tuple(legs),
            total_distance_km=round(total_km, 1),
            travel_minutes=minutes,
            transport_cost_usd=round(cost, 2),
            assumptions=tuple(assumptions),
        )

    def _build_runtime_bundle_payload(self) -> dict[str, Any]:
        source_id = self.stable_source_id
        source_category = self.source_record.category
        primary_region = self.primary_regions[0]
        primary_slug = self._slug(primary_region)
        gateway_id = f"dest-gateway-{primary_slug}"
        destination_id = f"dest-city-{primary_slug}"
        destination_name = primary_region
        duration_days = self.duration_days or 1
        journey = self._journey_profile()
        # Per-traveller costs scale with the party. Lodging assumes one room each,
        # which the traveller adjusts on the Budget tab if they are sharing.
        travellers = max(1, int(self.traveler_count or 1))
        lodging_total = round(
            max(1, duration_days) * LODGING_NIGHTLY_RATE_USD[self.trip_mode_key] * travellers, 2
        )
        transport_total = round(journey.transport_cost_usd * travellers, 2)
        activity_total = round(
            ACTIVITY_ALLOWANCE_USD[self.trip_mode_key] * max(1, duration_days) * travellers, 2
        )
        baseline_signal = 0.82 if self.trip_mode == "business" else 0.79
        destination_geo = self._geo_payload(destination_name)
        gateway_geo = dict(destination_geo)
        traveler_scope = (
            f"{self.traveler_party_kind}:{self.traveler_count}"
            if self.traveler_party_kind and self.traveler_count is not None
            else self.traveler_party_kind or "unspecified"
        )
        provenance_base = f"prov:{self.trip_id}:runtime"
        captured_at = self._trip_timestamp(hour=0)
        transport_timing: dict[str, Any] = {"duration_minutes": journey.travel_minutes}
        departure_local = self._trip_timestamp(hour=9)
        arrival_local = self._trip_timestamp(
            hour=9 + journey.travel_minutes // 60, minute=journey.travel_minutes % 60
        )
        transport_timing.update(
            {
                "departure_local": departure_local,
                "arrival_local": arrival_local,
            }
        )

        def _destination_source_ref(provenance_id: str, summary: str) -> dict[str, Any]:
            return {
                "provenance_id": provenance_id,
                "role": "identity",
                "source_id": source_id,
                "source_category": source_category,
                "contribution_kind": "inventory",
                "summary": summary,
            }

        def _provenance_ref(
            *,
            provenance_id: str,
            subject_kind: str,
            subject_id: str,
            summary: str,
        ) -> dict[str, Any]:
            payload = {
                "provenance_id": provenance_id,
                "source_id": source_id,
                "source_category": source_category,
                "subject_kind": subject_kind,
                "subject_id": subject_id,
                "contribution_kind": "inventory",
                "summary": summary,
            }
            payload["captured_at"] = captured_at
            return payload

        lodging_option_id = f"lodging:{self.trip_id}:primary"
        transport_option_id = f"transport:{self.trip_id}:arrival"
        activity_option_id = f"activity:{self.trip_id}:primary"
        option_ids = [lodging_option_id, transport_option_id, activity_option_id]
        source_refs = [
            f"{provenance_base}:destination:gateway",
            f"{provenance_base}:destination:primary",
            f"{provenance_base}:lodging",
            f"{provenance_base}:transport",
            f"{provenance_base}:activity",
        ]

        return {
            "bundle_id": f"bundle-{self.trip_id}-runtime-1-1",
            "title": f"{destination_name} runtime bundle",
            "bundle_context": "mixed",
            "destinations": [
                {
                    "destination_id": gateway_id,
                    "place_kind": "site",
                    "name": f"{destination_name} gateway",
                    "geo": gateway_geo,
                    "source_refs": [
                        _destination_source_ref(
                            f"{provenance_base}:destination:gateway",
                            "Gateway context derived from persisted trip region inputs.",
                        )
                    ],
                },
                {
                    "destination_id": destination_id,
                    "place_kind": "city",
                    "name": destination_name,
                    "geo": destination_geo,
                    "source_refs": [
                        _destination_source_ref(
                            f"{provenance_base}:destination:primary",
                            "Primary destination context derived from persisted trip records.",
                        )
                    ],
                },
            ],
            "lodging_options": [
                {
                    "option_id": lodging_option_id,
                    "name": f"{destination_name} central stay",
                    "destination_id": destination_id,
                    "location_summary": {
                        "destination_id": destination_id,
                        "location_context": "urban_core",
                        "access_summary": "Central location selected from persisted trip scope.",
                    },
                    "room_summary": {"lodging_kind": "hotel"},
                    "booking_terms": {"checkin_window": "15:00-22:00"},
                    "cost_summary": {
                        "total": {"currency": "USD", "typical_amount": lodging_total},
                    },
                    "fit_summary": {"overall_signal": baseline_signal},
                    "feasibility": {
                        "inventory_status": "available",
                        "available": True,
                        "business_approval_status": (
                            "preferred" if self.trip_mode == "business" else "approved"
                        ),
                    },
                    "source_refs": [
                        _provenance_ref(
                            provenance_id=f"{provenance_base}:lodging",
                            subject_kind="option",
                            subject_id=lodging_option_id,
                            summary="Lodging candidate synthesized from persisted trip dates and region.",
                        )
                    ],
                }
            ],
            "transport_options": [
                {
                    "option_id": transport_option_id,
                    "name": f"{destination_name} arrival connector",
                    "transport_kind": "rail",
                    "origin_id": gateway_id,
                    "destination_id": destination_id,
                    "timing_summary": transport_timing,
                    "segments": [
                        {
                            "segment_id": f"segment:{self.trip_id}:arrival-1",
                            "mode": "rail",
                            "origin_label": f"{destination_name} gateway",
                            "destination_label": destination_name,
                        }
                    ],
                    "cost_summary": {
                        "total": {"currency": "USD", "typical_amount": transport_total}
                    },
                    "fit_summary": {"overall_signal": baseline_signal},
                    "policy_summary": {
                        "business_approval_status": (
                            "preferred" if self.trip_mode == "business" else "approved"
                        )
                    },
                    "feasibility": {"available": True, "availability_status": "available"},
                    "source_refs": [
                        _provenance_ref(
                            provenance_id=f"{provenance_base}:transport",
                            subject_kind="option",
                            subject_id=transport_option_id,
                            summary="Transport leg derived from persisted destination and trip mode.",
                        )
                    ],
                }
            ],
            "activity_options": [
                {
                    "option_id": activity_option_id,
                    "name": (
                        "Client priority planning block"
                        if self.trip_mode == "business"
                        else f"{destination_name} anchor experience"
                    ),
                    "activity_kind": "dining" if self.trip_mode == "business" else "museum",
                    "destination_id": destination_id,
                    "place_id": f"place:{self.trip_id}:primary-activity",
                    "category": {
                        "primary": "meeting" if self.trip_mode == "business" else "museum",
                    },
                    "timing_summary": {
                        "duration_minutes": 120,
                        "typical_start_window": "09:00-18:00",
                    },
                    "significance_summary": {
                        "overall_signal": baseline_signal,
                        "anchor_worthy": True,
                    },
                    "cost_summary": {
                        "total": {"currency": "USD", "typical_amount": activity_total}
                    },
                    "fit_summary": {"overall_signal": baseline_signal},
                    "feasibility": {"available": True, "availability_status": "available"},
                    "source_refs": [
                        _provenance_ref(
                            provenance_id=f"{provenance_base}:activity",
                            subject_kind="option",
                            subject_id=activity_option_id,
                            summary="Activity seed is aligned to persisted trip mode and traveler scope.",
                        )
                    ],
                }
            ],
            "composition_summary": {
                "sequence_index": 0,
                "assembly_role": "persisted_trip_runtime",
                "primary_destination_id": destination_id,
                "component_option_ids": option_ids,
            },
            "provenance_summary": {"source_refs": source_refs},
            "quality_value_fit": {
                "quality_signal": baseline_signal,
                "value_signal": baseline_signal - 0.05,
                "fit_signal": baseline_signal,
            },
            "source_records": [self.source_record.to_dict()],
            "feasibility": {"available": True, "internally_consistent": True},
            "constraint_evaluation": {
                "status": "evaluated",
                "overall_pass": True,
                "hard_constraints_satisfied": True,
                "policy_constraints_satisfied": True if self.trip_mode == "business" else None,
                "blocking_constraint_ids": [],
                "evaluated_constraint_ids": [
                    "bundle.feasibility.available",
                    "bundle.feasibility.internally_consistent",
                    "inventory.runtime_seed",
                ],
                "summary": "Runtime bundle assembled with satisfied feasibility constraints.",
                "notes": [],
            },
            "explanation": {
                "headline": "Runtime inventory assembled from persisted trip context.",
                "strengths": [
                    f"Derived from persisted destination scope ({destination_name}).",
                    f"Traveler scope considered: {traveler_scope}.",
                ],
                "tradeoffs": [
                    "This source-backed seed is a bounded baseline until provider ingest is connected."
                ],
            },
            "summary": (
                f"Runtime bundle synthesized for {destination_name} from persisted trip data."
            ),
            "notes": [
                "Source-backed runtime bundle generated without fixture file fallback.",
                f"Trip title hint: {self.trip_title or destination_name}.",
            ],
        }

    def fetch_snapshot(self, query: SourceQuery) -> RawSnapshot:
        issues: list[AdapterIssue] = []
        records: list[RawSourceRecord] = []
        missing_primary_regions = not self.primary_regions
        missing_duration = self.duration_days is None or self.duration_days <= 0
        if missing_primary_regions:
            issues.append(
                AdapterIssue(
                    issue_id=f"issue:{self.trip_id}:inventory-missing-regions",
                    stage="availability",
                    severity="warning",
                    code="missing_inventory_primary_regions",
                    message=(
                        "Primary regions are still missing, so the runtime inventory remains empty."
                    ),
                    details={"trip_id": self.trip_id, "trip_mode": self.trip_mode},
                )
            )
        if missing_duration:
            issues.append(
                AdapterIssue(
                    issue_id=f"issue:{self.trip_id}:inventory-missing-duration",
                    stage="availability",
                    severity="warning",
                    code="missing_inventory_trip_duration",
                    message=(
                        "Trip dates or duration are still missing, so inventory assembly stays partial."
                    ),
                    details={"trip_id": self.trip_id, "trip_mode": self.trip_mode},
                )
            )
        bundle_payload: dict[str, Any] | None = None
        if not missing_primary_regions and not missing_duration:
            try:
                self._validate_primary_regions_supported()
                bundle_payload = self._build_runtime_bundle_payload()
            except UnsupportedDestinationError as error:
                issues.append(
                    AdapterIssue(
                        issue_id=f"issue:{self.trip_id}:inventory-unsupported-destination",
                        stage="availability",
                        severity="warning",
                        code="unsupported_inventory_destination",
                        message=(
                            f"The planner has no coverage for {error.region}, so no route, "
                            "timing or cost options can be assembled for it."
                        ),
                        details={
                            "trip_id": self.trip_id,
                            "trip_mode": self.trip_mode,
                            "region": error.region,
                            "supported_destinations": ", ".join(supported_destinations()),
                        },
                    )
                )
        if bundle_payload is not None:
            records.append(
                RawSourceRecord(
                    record_id=f"{query.query_id}:1",
                    entity_scope=query.entity_scope,
                    provider_entity_id=f"{self.trip_id}:runtime-bundle-seed",
                    payload_type="runtime_bundle_seed",
                    payload={
                        "bundle_payloads": [bundle_payload],
                    },
                    captured_at=self._trip_timestamp(hour=0) or "",
                    metadata={"source_seed": "persisted_trip_runtime"},
                )
            )

        return RawSnapshot(
            snapshot_id=f"snapshot:{self.trip_id}:inventory",
            adapter_id=self.adapter_id,
            source_id=self.source_record.source_id,
            source_category=self.source_record.category,
            entity_scope=query.entity_scope,
            option_kind=query.option_kind,
            fetched_at="2026-04-11T00:00:00Z",
            query=query,
            records=records,
            issues=issues,
            snapshot_status="complete" if records else "partial",
            handoff_status="ready" if records else "partial",
            payload_metadata={
                "trip_id": self.trip_id,
                "trip_mode": self.trip_mode,
                "region_count": str(len(self.primary_regions)),
                "duration_days": "" if self.duration_days is None else str(self.duration_days),
            },
        )

    def build_handoff(self, snapshot: RawSnapshot) -> NormalizationHandoff:
        return NormalizationHandoff(
            handoff_id=f"handoff:{self.trip_id}:inventory",
            snapshot_id=snapshot.snapshot_id,
            target_contract="trip_planner/options/bundles.py",
            entity_scope=snapshot.entity_scope,
            status="ready" if snapshot.records else "partial",
            input_record_ids=[record.record_id for record in snapshot.records],
            blocked_issue_ids=[issue.issue_id for issue in snapshot.issues],
            provenance_refs=[
                ProvenanceReference(
                    provenance_id=f"prov:{record.record_id}",
                    source_id=snapshot.source_id,
                    source_category=snapshot.source_category,
                    subject_kind="option_set",
                    subject_id=f"inventory:{self.trip_id}",
                    contribution_kind="inventory",
                    summary=(
                        "Persisted trip inventory now derives from source-backed runtime seeds."
                    ),
                    captured_at=snapshot.fetched_at,
                )
                for record in snapshot.records
            ],
            record_count=len(snapshot.records),
            notes=(
                []
                if snapshot.records
                else [
                    "Return an empty bundle set rather than failing when persisted inventory inputs are missing."
                ]
            ),
        )


def _load_mixed_option_fixture(name: str) -> MixedOption:
    payload = json.loads(
        resources.files(_BUNDLE_RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")
    )
    return MixedOption.from_dict(payload)


def _build_inventory_assembly_input(
    *,
    trip_id: str,
    trip_mode: str,
    start_date: str | None = None,
    end_date: str | None = None,
    trip_status: str | None = None,
    primary_regions: Sequence[str] = (),
    duration_days: int | None = None,
    trip_title: str | None = None,
    trip_summary: str | None = None,
    traveler_party_kind: str | None = None,
    traveler_count: int | None = None,
    persisted_trip: PersistedTrip | None = None,
    origin: str | None = None,
    allow_fixture_fallback: bool = True,
) -> InventoryAssemblyInput:
    if persisted_trip is not None:
        persisted_context = PersistedTripInventoryContext.from_persisted_trip(persisted_trip)
        trip_id = persisted_context.trip_id
        trip_mode = persisted_context.trip_mode
        start_date = persisted_context.start_date
        end_date = persisted_context.end_date
        trip_status = persisted_context.trip_status
        primary_regions = persisted_context.primary_regions
        origin = persisted_context.origin
        duration_days = persisted_context.duration_days
        trip_title = persisted_context.trip_title
        trip_summary = persisted_context.trip_summary
        traveler_party_kind = persisted_context.traveler_party_kind
        traveler_count = persisted_context.traveler_count

    fixture_seed = _FIXTURE_BUNDLE_INPUTS.get(trip_id)
    use_fixture_seed = (
        fixture_seed is not None and allow_fixture_fallback and persisted_trip is None
    )
    query = SourceQuery(
        query_id=f"inventory-query:{trip_id}",
        entity_scope="mixed",
        option_kind="mixed",
        destination=", ".join(primary_regions[:2]),
        traveler_segment=traveler_party_kind or "",
        trip_phase="inventory_selection",
        filters={
            "trip_mode": trip_mode,
            "trip_status": trip_status or "",
            "start_date": start_date or "",
            "end_date": end_date or "",
            "duration_days": "" if duration_days is None else str(duration_days),
            "traveler_count": "" if traveler_count is None else str(traveler_count),
        },
        notes=[
            "Persisted trip inventory assembly",
            f"persisted_trip:{'yes' if persisted_trip is not None else 'no'}",
            f"trip_title:{trip_title or ''}",
            f"trip_summary:{(trip_summary or '')[:60]}",
            f"start_date:{start_date or ''}",
            f"end_date:{end_date or ''}",
        ],
    )
    if use_fixture_seed:
        adapter: SourceAdapter = PersistedTripInventoryFixtureAdapter(
            trip_id=trip_id,
            trip_mode=trip_mode,
            primary_regions=primary_regions,
            duration_days=duration_days,
            allow_fixture_fallback=allow_fixture_fallback,
        )
    else:
        if persisted_trip is not None:
            adapter = PersistedTripSourceInventoryAdapter.from_persisted_trip(persisted_trip)
        else:
            adapter = PersistedTripSourceInventoryAdapter(
                trip_id=trip_id,
                trip_mode=trip_mode,
                primary_regions=primary_regions,
                origin=origin,
                start_date=start_date,
                end_date=end_date,
                duration_days=duration_days,
                trip_title=trip_title,
                traveler_party_kind=traveler_party_kind,
                traveler_count=traveler_count,
            )
    snapshot = adapter.fetch_snapshot(query)
    handoff = adapter.build_handoff(snapshot)
    return InventoryAssemblyInput(
        trip_id=trip_id,
        trip_mode=trip_mode,
        duration_days=duration_days,
        query=query,
        snapshot=snapshot,
        handoff=handoff,
        record_payloads=tuple(
            record.payload for record in snapshot.records if isinstance(record.payload, dict)
        ),
        fixture_names=tuple(
            record.metadata["fixture_name"]
            for record in snapshot.records
            if "fixture_name" in record.metadata
        ),
        allow_fixture_fallback=allow_fixture_fallback,
    )


def assemble_inventory_bundles_for_trip(
    *,
    trip_id: str | None = None,
    trip_mode: str | None = None,
    primary_regions: Sequence[str] = (),
    duration_days: int | None = None,
    assembly_input: InventoryAssemblyInput | None = None,
) -> list[InventoryBundle]:
    if assembly_input is None:
        if trip_id is None or trip_mode is None:
            msg = "trip_id and trip_mode are required when assembly_input is not provided"
            raise ValueError(msg)
        assembly_input = _build_inventory_assembly_input(
            trip_id=trip_id,
            trip_mode=trip_mode,
            primary_regions=primary_regions,
            duration_days=duration_days,
        )

    bundles: list[InventoryBundle] = []
    for payload in assembly_input.record_payloads:
        bundle_payloads = payload.get("bundle_payloads")
        if not isinstance(bundle_payloads, list):
            continue
        for bundle_payload in bundle_payloads:
            if isinstance(bundle_payload, dict):
                bundles.append(InventoryBundle.from_dict(bundle_payload))
    return bundles


def build_inventory_summary_payload(
    bundles: list[InventoryBundle],
    *,
    assembly_input: InventoryAssemblyInput | None = None,
) -> dict[str, Any]:
    def _issue_reason(issue_code: str) -> str:
        if issue_code == "unsupported_inventory_destination":
            return "unsupported_destination"
        if issue_code == "missing_inventory_primary_regions":
            return "missing_destination"
        if issue_code == "missing_inventory_trip_duration":
            return "missing_dates"
        if issue_code == "missing_inventory_live_adapter":
            return "missing_live_adapter"
        return "runtime_inventory_issue"

    runtime_issues: list[dict[str, Any]] = []
    if assembly_input is not None:
        runtime_issues = [
            {
                **issue.to_dict(),
                "reason": _issue_reason(issue.code),
            }
            for issue in assembly_input.snapshot.issues
        ]
        issue_codes = [issue.code for issue in assembly_input.snapshot.issues]
        source_metadata = {
            "source_type": "persisted_trip",
            "origin": "runtime",
            "adapter_name": assembly_input.snapshot.adapter_id,
            "provenance_context": {
                "trip_id": assembly_input.trip_id,
                "trip_mode": assembly_input.trip_mode,
                "source_id": assembly_input.snapshot.source_id,
                "query_id": assembly_input.query.query_id,
                "handoff_id": assembly_input.handoff.handoff_id,
                "input_record_ids": list(assembly_input.handoff.input_record_ids),
                "issue_codes": issue_codes,
                "filters": dict(assembly_input.query.filters),
                "notes": list(assembly_input.query.notes),
            },
        }
    else:
        source_metadata = {
            "source_type": "unknown",
            "origin": "runtime",
            "adapter_name": "",
            "provenance_context": {},
        }

    if bundles:
        notes = [
            "Bundle summaries are assembled from normalized destination, lodging, transport, and activity records."
        ]
        if assembly_input is not None and assembly_input.snapshot.records:
            notes.append(
                "Persisted trips use an adapter-backed inventory assembly seam instead of a seeded trip-ID gate."
            )
    elif assembly_input is not None and assembly_input.snapshot.issues:
        issue = assembly_input.snapshot.issues[0]
        if issue.code == "missing_inventory_trip_duration":
            notes = [
                "Trip dates or duration are still missing, so runtime inventory stays in a bounded partial state until those inputs are filled in."
            ]
        elif issue.code == "missing_inventory_primary_regions":
            notes = [
                "Primary regions are still missing, so add at least one destination before the workspace can assemble runtime inventory bundles."
            ]
        elif issue.code == "missing_inventory_live_adapter":
            notes = [
                "Persisted workspace reads no longer assemble inventory from fixtures, so runtime inventory will stay empty until a live adapter is wired in."
            ]
        else:
            notes = [
                "No adapter-backed inventory input is available for this persisted trip yet, so the workspace remains available with an empty bundle set."
            ]
    else:
        notes = [
            "Bundle assembly will appear here once normalized option inputs are available for the trip."
        ]

    runtime_state: dict[str, Any]
    if bundles:
        runtime_state = {
            "status": "ready",
            "title": "Runtime inventory is ready",
            "summary": "Persisted trip context is rich enough to assemble comparison-ready inventory bundles.",
            "commerciality_preference": 0.5,
            "issues": [],
        }
    elif assembly_input is not None and assembly_input.snapshot.issues:
        issue = assembly_input.snapshot.issues[0]
        if issue.code == "unsupported_inventory_destination":
            region = str((issue.details or {}).get("region") or "this destination")
            runtime_state = {
                "status": "empty",
                "title": f"The planner does not cover {region} yet",
                "summary": (
                    f"No route, timing or cost options can be produced for {region}. "
                    "Destinations the planner currently covers: "
                    + ", ".join(name.title() for name in supported_destinations())
                    + "."
                ),
                "issues": runtime_issues,
            }
        elif issue.code == "missing_inventory_trip_duration":
            runtime_state = {
                "status": "partial",
                "title": "Runtime inventory is partially specified",
                "summary": "Add trip dates or duration to replace the bounded fallback with runtime bundle assembly.",
                "issues": runtime_issues,
            }
        elif issue.code == "missing_inventory_live_adapter":
            runtime_state = {
                "status": "empty",
                "title": "Runtime inventory is waiting on a live adapter",
                "summary": "The main workspace no longer falls back to bundled fixture inventory for persisted trips.",
                "issues": runtime_issues,
            }
        else:
            runtime_state = {
                "status": "empty",
                "title": "Runtime inventory is still empty",
                "summary": "Add at least one primary region before the workspace can assemble runtime inventory bundles.",
                "issues": runtime_issues,
            }
    else:
        runtime_state = {
            "status": "empty",
            "title": "Runtime inventory is still empty",
            "summary": "Bundle assembly will appear once the trip carries enough persisted runtime context.",
            "issues": [],
        }

    return {
        "bundle_count": len(bundles),
        "bundles": [
            {
                "bundle_id": bundle.bundle_id,
                "title": bundle.title,
                "bundle_context": bundle.bundle_context,
                "summary": bundle.summary or bundle.explanation.headline,
                "destination_names": [destination.name for destination in bundle.destinations],
                "option_count": len(bundle.option_ids),
                "strengths": list(bundle.explanation.strengths[:2]),
                "tradeoffs": list(bundle.explanation.tradeoffs[:2]),
                "source_records": [record.to_dict() for record in bundle.source_records],
            }
            for bundle in bundles
        ],
        "notes": notes,
        "runtime_state": runtime_state,
        "source_metadata": source_metadata,
    }


def get_inventory_payload(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
) -> dict[str, Any] | None:
    fixture_seed = _FIXTURE_BUNDLE_INPUTS.get(trip_id)
    record: PersistedTrip | None = None
    primary_regions: Sequence[str] = ()
    duration_days: int | None = None
    if fixture_seed is not None:
        trip_mode = fixture_seed.trip_mode
    else:
        record = db_session.scalar(
            select(PersistedTrip)
            .where(PersistedTrip.trip_id == trip_id)
            .where(PersistedTrip.user_id == user.user_id)
        )
        if record is None:
            return None
        trip_mode = record.mode
        primary_regions = tuple(record.primary_regions)
        duration_days = record.duration_days

    assembly_input = _build_inventory_assembly_input(
        trip_id=trip_id,
        trip_mode=trip_mode,
        persisted_trip=record,
        primary_regions=primary_regions,
        start_date=record.start_date if record is not None else None,
        end_date=record.end_date if record is not None else None,
        trip_status=record.status if record is not None else None,
        duration_days=duration_days,
        trip_title=record.title if record is not None else None,
        trip_summary=record.summary if record is not None else None,
        traveler_party_kind=record.traveler_party_kind if record is not None else None,
        traveler_count=record.traveler_count if record is not None else None,
    )
    bundles = assemble_inventory_bundles_for_trip(assembly_input=assembly_input)
    return {
        "trip_id": trip_id,
        "bundle_count": len(bundles),
        "bundles": [bundle.to_dict() for bundle in bundles],
        "summary": build_inventory_summary_payload(bundles, assembly_input=assembly_input),
    }
