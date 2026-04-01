import json
from pathlib import Path

import pytest

from trip_planner.options import (
    Destination,
    DestinationGeo,
    RegionExpansionRef,
    DestinationSourceRef,
    DestinationTag,
    MobilityProfile,
    OperationalNote,
    PlaceContext,
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
    assert destination.region_expansion_refs[0].expansion_mode == "day_trip"
    assert destination.region_expansion_refs[0].trigger_tags == [
        "culture",
        "rail-access",
    ]
    assert destination.tags[0].scope == "experience"
    assert destination.mobility_profile.local_modes == ["walk", "transit", "bike"]
    assert destination.mobility_profile.interchange_hubs == [
        "Kyoto Station",
        "Karasuma Oike",
    ]
    assert destination.experience_signals[0].key == "culture_density"


def test_site_destination_carries_operational_notes_and_source_refs() -> None:
    destination = _load_destination("fushimi_inari_site.json")

    payload = destination.to_dict()

    assert payload["operational_notes"][0]["summary"].startswith("Expect early")
    assert payload["source_refs"][0]["provenance_id"] == "prov-site-editorial"
    assert payload["source_refs"][1]["source_category"] == "specialist_non_commercial"
    assert payload["operational_notes"][0]["source_ref_ids"] == [
        "prov-site-operational"
    ]
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
                source_id="arashiyama-guide",
                source_category="editorial",
                contribution_kind="editorial",
                summary="Defines the bamboo grove as a landscape context.",
                freshness_days_at_capture=12,
                notes=["Supports the landscape framing."],
            )
        ],
        operational_notes=[
            OperationalNote(
                kind="crowding",
                summary="Early arrival matters before the main coach arrivals.",
                impact="high",
                applies_in_months=[3, 4, 11],
                source_ref_ids=["prov-arashiyama-editorial"],
                notes=[
                    "Crowding pressure spikes during spring and autumn demand peaks."
                ],
            )
        ],
    )

    payload = destination.to_dict()

    assert payload["tags"][0]["key"] == "nature"
    assert payload["source_refs"][0]["role"] == "experience"
    assert payload["source_refs"][0]["source_id"] == "arashiyama-guide"
    assert payload["operational_notes"][0]["impact"] == "high"
    assert payload["operational_notes"][0]["source_ref_ids"] == [
        "prov-arashiyama-editorial"
    ]


def test_place_context_can_be_derived_from_destination() -> None:
    destination = _load_destination("gion_neighborhood.json")

    place_context = PlaceContext.from_destination(
        destination,
        context_id="ctx-gion-evening-loop",
        role="micro_context",
        boundary_mode="walkable_cluster",
        label="Gion evening loop",
        supporting_destination_ids=[
            destination.destination_id,
            "dest-site-kiyomizu-dera",
        ],
        notes=["Use for short evening wandering and dining comparisons."],
    )

    payload = place_context.to_dict()

    assert payload["destination_id"] == "dest-neighborhood-gion"
    assert payload["place_kind"] == "neighborhood"
    assert payload["tag_keys"] == ["evening-friendly", "historic-streets", "walk-first"]
    assert payload["source_ref_ids"] == ["prov-gion-editorial"]


def test_place_context_rejects_invalid_role_boundary_and_schema() -> None:
    with pytest.raises(ValueError, match="role"):
        PlaceContext(
            context_id="ctx-invalid-role",
            destination_id="dest-city-kyoto",
            place_kind="city",
            role="ranking_surface",  # type: ignore[arg-type]
            label="Invalid role",
        )

    with pytest.raises(ValueError, match="boundary_mode"):
        PlaceContext(
            context_id="ctx-invalid-boundary",
            destination_id="dest-city-kyoto",
            place_kind="city",
            role="base",
            label="Invalid boundary",
            boundary_mode="metroplex",
        )

    with pytest.raises(ValueError, match="schema_version"):
        PlaceContext(
            context_id="ctx-invalid-version",
            destination_id="dest-city-kyoto",
            place_kind="city",
            role="base",
            label="Invalid schema version",
            schema_version="9.9.9",
        )


def test_region_expansion_refs_expose_explicit_expansion_strategy() -> None:
    destination = _load_destination("kansai_region.json")

    ref = destination.region_expansion_refs[0]

    assert isinstance(ref, RegionExpansionRef)
    assert ref.relationship_kind == "contiguous_region"
    assert ref.expansion_mode == "contiguous"
    assert ref.requires_base_change is True
    assert ref.trigger_tags == ["rail-connected", "multi-base"]


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


def test_destination_rejects_invalid_tag_provenance_and_operational_note_values() -> (
    None
):
    with pytest.raises(ValueError, match="scope"):
        DestinationTag(key="culture", label="Culture", scope="ranking")

    with pytest.raises(ValueError, match="role"):
        DestinationSourceRef(provenance_id="prov-1", role="pricing")

    with pytest.raises(ValueError, match="source_category"):
        DestinationSourceRef(
            provenance_id="prov-1",
            source_category="unsupported",
        )

    with pytest.raises(ValueError, match="kind"):
        OperationalNote(kind="closure", summary="Invalid note kind.")


def test_mobility_profile_rejects_unknown_modes() -> None:
    with pytest.raises(ValueError, match="arrival_modes"):
        MobilityProfile(arrival_modes=["camel"])

    with pytest.raises(ValueError, match="interchange_hubs"):
        MobilityProfile(interchange_hubs=[""])


def test_destination_from_dict_treats_null_mobility_profile_as_unknown() -> None:
    payload = json.loads(_fixture_path("kyoto_city.json").read_text(encoding="utf-8"))
    payload["mobility_profile"] = None

    destination = Destination.from_dict(payload)

    assert destination.mobility_profile == MobilityProfile()


def test_region_expansion_ref_rejects_unknown_expansion_mode() -> None:
    with pytest.raises(ValueError, match="expansion_mode"):
        RegionExpansionRef(
            destination_id="dest-region-osaka-bay",
            relationship_kind="adjacent_region",
            expansion_mode="teleport",
        )


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
