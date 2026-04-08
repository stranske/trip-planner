from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from trip_planner.app.services.auth import AuthenticatedUser
from trip_planner.options import InventoryBundle, MixedOption
from trip_planner.persistence.models.trip import PersistedTrip

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


def _load_mixed_option_fixture(name: str) -> MixedOption:
    payload = json.loads(
        resources.files(_BUNDLE_RESOURCE_PACKAGE).joinpath(name).read_text(encoding="utf-8")
    )
    return MixedOption.from_dict(payload)


def assemble_inventory_bundles_for_trip(*, trip_id: str, trip_mode: str) -> list[InventoryBundle]:
    fixture_seed = _FIXTURE_BUNDLE_INPUTS.get(trip_id)
    if fixture_seed is None or fixture_seed.trip_mode != trip_mode:
        return []

    bundles: list[InventoryBundle] = []
    for fixture_name in fixture_seed.fixture_names:
        mixed_option = _load_mixed_option_fixture(fixture_name)
        bundles.extend(mixed_option.bundles)
    return bundles


def build_inventory_summary_payload(bundles: list[InventoryBundle]) -> dict[str, Any]:
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
        "notes": (
            [
                "Bundle summaries are assembled from normalized destination, lodging, transport, and activity records."
            ]
            if bundles
            else [
                "Bundle assembly will appear here once normalized option inputs are available for the trip."
            ]
        ),
    }


def get_inventory_payload(
    db_session: Session,
    *,
    user: AuthenticatedUser,
    trip_id: str,
) -> dict[str, Any] | None:
    fixture_seed = _FIXTURE_BUNDLE_INPUTS.get(trip_id)
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

    bundles = assemble_inventory_bundles_for_trip(trip_id=trip_id, trip_mode=trip_mode)
    return {
        "trip_id": trip_id,
        "bundle_count": len(bundles),
        "bundles": [bundle.to_dict() for bundle in bundles],
        "summary": build_inventory_summary_payload(bundles),
    }
