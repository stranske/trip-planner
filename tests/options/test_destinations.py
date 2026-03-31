import json
from pathlib import Path

import pytest

from trip_planner.options import (
    Destination,
    DestinationGeo,
    DestinationSourceRef,
    DestinationTag,
    MobilityProfile,
    OperationalNote,
)


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
    assert destination.tags[0].scope == "experience"
    assert destination.mobility_profile.local_modes == ["walk", "transit", "bike"]
    assert destination.experience_signals[0].key == "culture_density"


def test_site_destination_carries_operational_notes_and_source_refs() -> None:
    destination = _load_destination("fushimi_inari_site.json")

    payload = destination.to_dict()

    assert payload["operational_notes"][0]["summary"].startswith("Expect early")
    assert payload["source_refs"][0]["provenance_id"] == "prov-site-editorial"
    assert payload["parent_refs"][0]["destination_id"] == "dest-city-kyoto"


def test_destination_supporting_records_round_trip() -> None:
    destination = Destination(
        destination_id="dest-landscape-arashiyama",
        place_kind="landscape",
        name="Arashiyama Bamboo Grove",
        geo=DestinationGeo(latitude=35.017, longitude=135.6713, country_code="JP"),
        tags=[
            DestinationTag(
                key="nature",
                label="Nature-forward",
                scope="experience",
                weight=0.8,
                notes=["Useful when balancing dense city days."],
            )
        ],
        source_refs=[
            DestinationSourceRef(
                provenance_id="prov-arashiyama-editorial",
                role="experience",
                notes=["Supports the landscape framing."],
            )
        ],
        operational_notes=[
            OperationalNote(
                kind="crowding",
                summary="Early arrival matters before the main coach arrivals.",
                impact="high",
                applies_in_months=[3, 4, 11],
                notes=["Crowding pressure spikes during spring and autumn demand peaks."],
            )
        ],
    )

    payload = destination.to_dict()

    assert payload["tags"][0]["key"] == "nature"
    assert payload["source_refs"][0]["role"] == "experience"
    assert payload["operational_notes"][0]["impact"] == "high"


def test_destination_rejects_invalid_place_kind() -> None:
    payload = {
        "destination_id": "dest-invalid",
        "place_kind": "district",
        "name": "Invalid",
        "geo": {"latitude": 35.0, "longitude": 135.0, "country_code": "JP"},
    }

    with pytest.raises(ValueError, match="place_kind"):
        Destination.from_dict(payload)


def test_destination_rejects_invalid_geo_and_adjacency_values() -> None:
    with pytest.raises(ValueError, match="latitude"):
        DestinationGeo(latitude=95.0, longitude=135.0, country_code="JP")

    payload = json.loads(_fixture_path("kyoto_city.json").read_text(encoding="utf-8"))
    payload["adjacency_refs"][0]["transit_time_minutes"] = -10
    with pytest.raises(ValueError, match="transit_time_minutes"):
        Destination.from_dict(payload)


def test_destination_rejects_invalid_tag_provenance_and_operational_note_values() -> None:
    with pytest.raises(ValueError, match="scope"):
        DestinationTag(key="culture", label="Culture", scope="ranking")

    with pytest.raises(ValueError, match="role"):
        DestinationSourceRef(provenance_id="prov-1", role="pricing")

    with pytest.raises(ValueError, match="kind"):
        OperationalNote(kind="closure", summary="Invalid note kind.")


def test_mobility_profile_rejects_unknown_modes() -> None:
    with pytest.raises(ValueError, match="arrival_modes"):
        MobilityProfile(arrival_modes=["camel"])


def test_destination_from_dict_treats_null_mobility_profile_as_unknown() -> None:
    payload = json.loads(_fixture_path("kyoto_city.json").read_text(encoding="utf-8"))
    payload["mobility_profile"] = None

    destination = Destination.from_dict(payload)

    assert destination.mobility_profile == MobilityProfile()


def test_destination_rejects_unexpected_schema_version() -> None:
    payload = json.loads(_fixture_path("kyoto_city.json").read_text(encoding="utf-8"))
    payload["schema_version"] = "9.9.9"

    with pytest.raises(ValueError, match="schema_version"):
        Destination.from_dict(payload)

    with pytest.raises(ValueError, match="schema_version"):
        Destination(
            destination_id="dest-kyoto",
            place_kind="city",
            name="Kyoto",
            geo=DestinationGeo(latitude=35.0116, longitude=135.7681, country_code="JP"),
            schema_version="9.9.9",
        )
