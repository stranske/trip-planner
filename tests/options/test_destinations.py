import json
from pathlib import Path

import pytest

from trip_planner.options import Destination, DestinationGeo, MobilityProfile


def _fixture_path(name: str) -> Path:
    return Path("tests/fixtures/options/destinations") / name


def _load_destination(name: str) -> Destination:
    payload = json.loads(_fixture_path(name).read_text(encoding="utf-8"))
    return Destination.from_dict(payload)


def test_destination_fixtures_cover_multiple_place_kinds() -> None:
    fixtures = {
        "kansai_region.json": "region",
        "kyoto_city.json": "city",
        "gion_neighborhood.json": "neighborhood",
        "fushimi_inari_site.json": "site",
    }

    for name, expected_kind in fixtures.items():
        destination = _load_destination(name)
        assert destination.place_kind == expected_kind
        assert destination.to_dict()["place_kind"] == expected_kind


def test_city_destination_preserves_hierarchy_and_expansion_context() -> None:
    destination = _load_destination("kyoto_city.json")

    assert destination.parent_refs[0].destination_id == "dest-region-kansai"
    assert destination.adjacency_refs[0].destination_id == "dest-city-osaka"
    assert destination.region_expansion_refs[0].relationship_kind == "day_trip"
    assert destination.mobility_profile.local_modes == ["walk", "transit", "bike"]
    assert destination.experience_signals[0].key == "culture_density"


def test_site_destination_carries_operational_notes_and_source_refs() -> None:
    destination = _load_destination("fushimi_inari_site.json")

    payload = destination.to_dict()

    assert payload["operational_notes"][0].startswith("Expect early")
    assert payload["source_refs"] == ["prov-site-editorial", "prov-site-operational"]
    assert payload["parent_refs"][0]["destination_id"] == "dest-city-kyoto"


def test_destination_rejects_invalid_place_kind() -> None:
    with pytest.raises(ValueError, match="place_kind"):
        Destination(
            destination_id="dest-invalid",
            place_kind="district",
            name="Invalid",
            geo=DestinationGeo(latitude=35.0, longitude=135.0, country_code="JP"),
        )


def test_destination_rejects_invalid_geo_and_adjacency_values() -> None:
    with pytest.raises(ValueError, match="latitude"):
        DestinationGeo(latitude=95.0, longitude=135.0, country_code="JP")

    payload = json.loads(_fixture_path("kyoto_city.json").read_text(encoding="utf-8"))
    payload["adjacency_refs"][0]["transit_time_minutes"] = -10
    with pytest.raises(ValueError, match="transit_time_minutes"):
        Destination.from_dict(payload)


def test_mobility_profile_rejects_unknown_modes() -> None:
    with pytest.raises(ValueError, match="arrival_modes"):
        MobilityProfile(arrival_modes=["camel"])
