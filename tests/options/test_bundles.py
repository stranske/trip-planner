import json
from pathlib import Path

import pytest

from trip_planner.options import InventoryBundle, MixedOption


def _fixture_path(name: str) -> Path:
    return Path("tests/fixtures/options/bundles") / name


def _load_mixed_option(name: str) -> MixedOption:
    payload = json.loads(_fixture_path(name).read_text(encoding="utf-8"))
    return MixedOption.from_dict(payload)


def test_bundle_fixtures_cover_representative_assembly_shapes() -> None:
    lodging = _load_mixed_option("lodging_only_comparison.json")
    arrival = _load_mixed_option("transport_lodging_bundle.json")
    route = _load_mixed_option("route_level_mixed_option.json")

    assert lodging.bundles[0].bundle_context == "lodging_only"
    assert arrival.bundles[0].bundle_context == "transport_lodging"
    assert route.bundles[1].bundle_context == "route_level"
    assert route.bundles[1].activity_options[0].activity_kind == "museum"


def test_transport_plus_lodging_bundle_preserves_category_specific_detail() -> None:
    mixed_option = _load_mixed_option("transport_lodging_bundle.json")
    bundle = mixed_option.bundles[0]

    assert bundle.transport_options[0].transport_kind == "rail"
    assert bundle.lodging_options[0].room_summary.lodging_kind == "hotel"
    assert bundle.transport_options[0].timing_summary.duration_minutes == 88
    assert bundle.lodging_options[0].location_summary.business_access_signal == pytest.approx(0.93)


def test_route_level_mixed_option_round_trips_and_converts_to_option_entry() -> None:
    mixed_option = _load_mixed_option("route_level_mixed_option.json")

    payload = mixed_option.to_dict()
    option = mixed_option.to_option()

    assert payload["route_coherence"]["destination_sequence"][-1] == "dest-city-kyoto"
    assert payload["bundles"][1]["activity_options"][0]["activity_kind"] == "museum"
    assert option.kind == "mixed"
    assert "route_coherence" in option.fit_signals
    assert "dest-city-kyoto" in option.supporting_place_ids
    assert "https://example.com/museum" in option.booking_links


def test_mixed_option_keeps_normalized_contracts_distinct_while_assembling_shared_option() -> None:
    mixed_option = _load_mixed_option("route_level_mixed_option.json")
    cultural_bundle = mixed_option.bundles[1]
    lodging_option = cultural_bundle.lodging_options[0]
    transport_option = cultural_bundle.transport_options[0]
    activity_option = cultural_bundle.activity_options[0]
    option = mixed_option.to_option()

    assert lodging_option.fit_summary.location_fit_signal == pytest.approx(0.91)
    assert transport_option.policy_summary.business_approval_status == "approved"
    assert activity_option.significance_summary.overall_signal == pytest.approx(0.95)
    assert activity_option.fit_summary.overall_signal == pytest.approx(0.66)
    assert (
        activity_option.significance_summary.overall_signal
        > activity_option.fit_summary.overall_signal
    )
    assert activity_option.feasibility.indoor_outdoor == "indoor"
    assert option.fit_signals == {
        "route_coherence": pytest.approx(0.89),
        "schedule_fit": pytest.approx(0.84),
        "budget_posture": pytest.approx(0.74),
    }
    assert option.source_refs == ["prov-major-museum"]
    assert option.booking_links == ["https://example.com/museum"]


def test_inventory_bundle_accepts_explicitly_infeasible_but_explained_bundle() -> None:
    payload = json.loads(_fixture_path("transport_lodging_bundle.json").read_text(encoding="utf-8"))
    payload["bundles"][0]["feasibility"] = {
        "available": False,
        "internally_consistent": True,
        "blocking_reasons": ["Rail maintenance blocks the arrival window."],
    }

    mixed_option = MixedOption.from_dict(payload)

    assert mixed_option.bundles[0].feasibility.available is False
    assert mixed_option.bundles[0].feasibility.blocking_reasons == [
        "Rail maintenance blocks the arrival window."
    ]
    assert "Rail maintenance blocks the arrival window." in mixed_option.to_option().drawbacks


def test_transport_only_bundle_requires_destinations_for_transport_endpoints() -> None:
    payload = json.loads(_fixture_path("transport_lodging_bundle.json").read_text(encoding="utf-8"))
    bundle = payload["bundles"][0]
    bundle["destinations"] = []
    bundle["lodging_options"] = []

    with pytest.raises(
        ValueError, match="destinations must include each origin_id and destination_id"
    ):
        InventoryBundle.from_dict(bundle)


def test_bundles_reject_inconsistent_destination_and_invalid_mixed_option_metadata() -> None:
    payload = json.loads(_fixture_path("route_level_mixed_option.json").read_text(encoding="utf-8"))
    payload["bundles"][1]["activity_options"][0]["destination_id"] = "dest-city-nara"
    with pytest.raises(ValueError, match="destinations must include each destination referenced"):
        InventoryBundle.from_dict(payload["bundles"][1])

    payload = json.loads(_fixture_path("lodging_only_comparison.json").read_text(encoding="utf-8"))
    payload["supported_purposes"] = ["profile_learning", "profile_learning"]
    with pytest.raises(ValueError, match="supported_purposes must not contain duplicates"):
        MixedOption.from_dict(payload)

    payload = json.loads(_fixture_path("transport_lodging_bundle.json").read_text(encoding="utf-8"))
    payload["route_coherence"]["destination_sequence"] = ["dest-city-osaka"]
    with pytest.raises(ValueError, match="route_coherence.destination_sequence must cover"):
        MixedOption.from_dict(payload)
