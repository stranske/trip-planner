import json
from pathlib import Path

from trip_planner.contracts import (
    ActivityOption,
    Destination,
    LodgingOption,
    PlaceContext,
    PlaceKind,
    RegionExpansionRef,
)


def _fixture_path(name: str) -> Path:
    return Path("tests/fixtures/options/destinations") / name


def test_contracts_namespace_exposes_destination_contracts() -> None:
    payload = json.loads(_fixture_path("kyoto_city.json").read_text(encoding="utf-8"))
    destination = Destination.from_dict(payload)
    place_kind: PlaceKind = destination.place_kind

    assert place_kind == "city"
    assert destination.parent_refs[0].relationship_kind == "parent_region"
    assert isinstance(destination.region_expansion_refs[0], RegionExpansionRef)


def test_contracts_namespace_exposes_place_context_contracts() -> None:
    payload = {
        "context_id": "ctx-kyoto-higashiyama",
        "destination_id": "dest-city-kyoto",
        "place_kind": "city",
        "role": "micro_context",
        "label": "Eastern Kyoto walking cluster",
        "boundary_mode": "walkable_cluster",
        "summary": "Useful for lodging and activity options concentrated around Higashiyama.",
        "supporting_destination_ids": ["dest-city-kyoto", "dest-neighborhood-gion"],
        "tag_keys": ["culture", "walkable-core"],
        "source_ref_ids": ["prov-kyoto-editorial"],
    }

    place_context = PlaceContext.from_dict(payload)

    assert place_context.role == "micro_context"
    assert place_context.supporting_destination_ids[1] == "dest-neighborhood-gion"


def test_contracts_namespace_exposes_lodging_contracts() -> None:
    payload = json.loads(
        Path("tests/fixtures/options/lodging/conference_hotel.json").read_text(
            encoding="utf-8"
        )
    )

    lodging = LodgingOption.from_dict(payload)

    assert lodging.room_summary.lodging_kind == "hotel"
    assert lodging.feasibility.business_approval_status == "preferred"


def test_contracts_namespace_exposes_activity_contracts() -> None:
    payload = json.loads(
        Path("tests/fixtures/options/activities/major_museum.json").read_text(
            encoding="utf-8"
        )
    )

    activity = ActivityOption.from_dict(payload)

    assert activity.activity_kind == "museum"
    assert activity.significance_summary.anchor_worthy is True
