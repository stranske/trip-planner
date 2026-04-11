from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.options import InventoryBundle, MixedOption
from trip_planner.persistence.models.trip import PersistedTrip
from trip_planner.sources import (
    AdapterIssue,
    NormalizationHandoff,
    ProvenanceReference,
    RawSnapshot,
    RawSourceRecord,
    SourceAdapter,
    SourceQuery,
    SourceRecord,
)

_BUNDLE_RESOURCE_PACKAGE = "trip_planner.resources.options.bundles"


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
    query: SourceQuery
    snapshot: RawSnapshot
    handoff: NormalizationHandoff
    fixture_names: tuple[str, ...]


class PersistedTripInventoryFixtureAdapter(SourceAdapter):
    """Expose fixture-backed inventory as an explicit adapter seam for persisted trips."""

    def __init__(self, *, trip_id: str, trip_mode: str, primary_regions: Sequence[str]) -> None:
        self.trip_id = trip_id
        self.trip_mode = trip_mode
        self.primary_regions = tuple(region for region in primary_regions if region)
        self.adapter_id = "persisted-trip-fixture-inventory"
        self.source_record = SourceRecord(
            source_id="fixture-normalized-inventory",
            provider_name="Trip Planner Fixtures",
            display_name="Fixture-backed normalized inventory",
            category="commercial_inventory",
            coverage_scope="global",
            supported_option_kinds=["mixed", "lodging"],
            notes=[
                "Provides a bounded adapter seam until live provider-backed inventory is available."
            ],
        )
        self.supported_entity_scopes = ("mixed", "lodging")
        self.supported_option_kinds = ("mixed", "lodging")
        self.capabilities = ("read_fixture", "supports_normalization_handoff")

    def fixture_names(self) -> tuple[str, ...]:
        fixture_seed = _FIXTURE_BUNDLE_INPUTS.get(self.trip_id)
        if fixture_seed is not None and fixture_seed.trip_mode == self.trip_mode:
            return fixture_seed.fixture_names
        if not self.primary_regions:
            return ()
        if self.trip_mode == "leisure":
            return ("route_level_mixed_option.json",)
        if self.trip_mode == "business":
            return ("transport_lodging_bundle.json",)
        return ()

    def fetch_snapshot(self, query: SourceQuery) -> RawSnapshot:
        fixture_names = self.fixture_names()
        issues = (
            []
            if fixture_names
            else [
                AdapterIssue(
                    issue_id=f"issue:{self.trip_id}:inventory-fallback",
                    stage="availability",
                    severity="warning",
                    code="missing_inventory_adapter_input",
                    message=(
                        "No adapter-backed inventory input is available for this persisted trip yet."
                    ),
                    details={"trip_id": self.trip_id, "trip_mode": self.trip_mode},
                )
            ]
        )
        records = [
            RawSourceRecord(
                record_id=f"{query.query_id}:{index}",
                entity_scope=query.entity_scope,
                provider_entity_id=f"{self.trip_id}:{fixture_name}",
                payload_type="fixture_bundle",
                payload={"fixture_name": fixture_name, "trip_id": self.trip_id},
                captured_at="2026-04-11T00:00:00Z",
                metadata={"fixture_name": fixture_name},
            )
            for index, fixture_name in enumerate(fixture_names, start=1)
        ]
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


def _load_mixed_option_fixture(name: str) -> MixedOption:
    payload = json.loads(
        resources.files(_BUNDLE_RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")
    )
    return MixedOption.from_dict(payload)


def _build_inventory_assembly_input(
    *,
    trip_id: str,
    trip_mode: str,
    primary_regions: Sequence[str] = (),
) -> InventoryAssemblyInput:
    query = SourceQuery(
        query_id=f"inventory-query:{trip_id}",
        entity_scope="mixed",
        option_kind="mixed",
        destination=", ".join(primary_regions[:2]),
        trip_phase="inventory_selection",
        filters={"trip_mode": trip_mode},
        notes=["Persisted trip inventory assembly"],
    )
    adapter = PersistedTripInventoryFixtureAdapter(
        trip_id=trip_id,
        trip_mode=trip_mode,
        primary_regions=primary_regions,
    )
    snapshot = adapter.fetch_snapshot(query)
    handoff = adapter.build_handoff(snapshot)
    return InventoryAssemblyInput(
        trip_id=trip_id,
        trip_mode=trip_mode,
        query=query,
        snapshot=snapshot,
        handoff=handoff,
        fixture_names=tuple(
            record.metadata["fixture_name"] for record in snapshot.records if "fixture_name" in record.metadata
        ),
    )


def assemble_inventory_bundles_for_trip(
    *,
    trip_id: str | None = None,
    trip_mode: str | None = None,
    primary_regions: Sequence[str] = (),
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
        )

    bundles: list[InventoryBundle] = []
    for fixture_name in assembly_input.fixture_names:
        mixed_option = _load_mixed_option_fixture(fixture_name)
        bundles.extend(mixed_option.bundles)
    return bundles


def build_inventory_summary_payload(
    bundles: list[InventoryBundle],
    *,
    assembly_input: InventoryAssemblyInput | None = None,
) -> dict[str, Any]:
    if bundles:
        notes = [
            "Bundle summaries are assembled from normalized destination, lodging, transport, and activity records."
        ]
        if assembly_input is not None and assembly_input.snapshot.records:
            notes.append(
                "Persisted trips use an adapter-backed inventory assembly seam instead of a seeded trip-ID gate."
            )
    elif assembly_input is not None and assembly_input.snapshot.issues:
        notes = [
            "No adapter-backed inventory input is available for this persisted trip yet, so the workspace remains available with an empty bundle set."
        ]
    else:
        notes = [
            "Bundle assembly will appear here once normalized option inputs are available for the trip."
        ]

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
            }
            for bundle in bundles
        ],
        "notes": notes,
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

    assembly_input = _build_inventory_assembly_input(
        trip_id=trip_id,
        trip_mode=trip_mode,
        primary_regions=primary_regions,
    )
    bundles = assemble_inventory_bundles_for_trip(assembly_input=assembly_input)
    return {
        "trip_id": trip_id,
        "bundle_count": len(bundles),
        "bundles": [bundle.to_dict() for bundle in bundles],
        "summary": build_inventory_summary_payload(bundles, assembly_input=assembly_input),
    }
