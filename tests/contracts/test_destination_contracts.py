import json
from pathlib import Path

from trip_planner.contracts import Destination, PlaceKind, RegionExpansionRef


def _fixture_path(name: str) -> Path:
    return Path("tests/fixtures/options/destinations") / name


def test_contracts_namespace_exposes_destination_contracts() -> None:
    payload = json.loads(_fixture_path("kyoto_city.json").read_text(encoding="utf-8"))
    destination = Destination.from_dict(payload)
    place_kind: PlaceKind = destination.place_kind

    assert place_kind == "city"
    assert destination.parent_refs[0].relationship_kind == "parent_region"
    assert isinstance(destination.region_expansion_refs[0], RegionExpansionRef)
