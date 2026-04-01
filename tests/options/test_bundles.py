import json
from pathlib import Path

import pytest

from trip_planner.contracts import OptionSet
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
    assert bundle.lodging_options[
        0
    ].location_summary.business_access_signal == pytest.approx(0.93)
    assert bundle.composition_summary.component_option_ids == [
        "lodg-osaka-station-hotel",
        "transport-kix-osaka-rail",
    ]
    assert bundle.provenance_summary.source_refs == ["prov-haruka"]
    assert bundle.quality_value_fit.fit_signal == pytest.approx(0.81)


def test_route_level_mixed_option_round_trips_and_converts_to_option_entry() -> None:
    mixed_option = _load_mixed_option("route_level_mixed_option.json")

    payload = mixed_option.to_dict()
    option = mixed_option.to_option()

    assert payload["route_coherence"]["destination_sequence"][-1] == "dest-city-kyoto"
    assert payload["bundles"][1]["activity_options"][0]["activity_kind"] == "museum"
    assert (
        payload["composition_summary"]["component_option_ids"][-1]
        == "activity-major-museum"
    )
    assert option.kind == "mixed"
    assert "route_coherence" in option.fit_signals
    assert "dest-city-kyoto" in option.supporting_place_ids
    assert "https://example.com/museum" in option.booking_links
    assert option.quality_summary.quality_signal == pytest.approx(0.89)
    assert option.quality_summary.value_signal == pytest.approx(0.74)
    assert option.quality_summary.fit_signal == pytest.approx(0.84)


def test_mixed_option_imports_through_public_packages_and_feeds_option_set() -> None:
    mixed_option = _load_mixed_option("route_level_mixed_option.json")
    option = mixed_option.to_option()
    option_set = OptionSet(
        option_set_id="optset-route-level",
        trip_id=mixed_option.trip_id,
        purpose="inventory_narrowing",
        scope="mixed",
        title="Mixed route alternatives",
        options=[option],
        source_refs=option.source_refs,
        explanation=option.explanation,
    )

    payload = option_set.to_dict()

    assert payload["options"][0]["kind"] == "mixed"
    assert payload["options"][0]["fit_signals"]["route_coherence"] == pytest.approx(
        0.89
    )
    assert payload["source_refs"] == ["prov-major-museum"]


def test_mixed_option_keeps_normalized_contracts_distinct_while_assembling_shared_option() -> (
    None
):
    mixed_option = _load_mixed_option("route_level_mixed_option.json")
    cultural_bundle = mixed_option.bundles[1]
    lodging_option = cultural_bundle.lodging_options[0]
    transport_option = cultural_bundle.transport_options[0]
    activity_option = cultural_bundle.activity_options[0]
    option = mixed_option.to_option()

    assert lodging_option.fit_summary.location_fit_signal == pytest.approx(0.91)
    assert transport_option.policy_summary.business_approval_status == "approved"
    significance_signal = activity_option.significance_summary.overall_signal
    fit_signal = activity_option.fit_summary.overall_signal
    assert significance_signal is not None
    assert fit_signal is not None
    assert significance_signal == pytest.approx(0.95)
    assert fit_signal == pytest.approx(0.66)
    assert significance_signal > fit_signal
    assert activity_option.feasibility.indoor_outdoor == "indoor"
    assert mixed_option.composition_summary.primary_destination_id == "dest-city-kyoto"
    assert mixed_option.provenance_summary.source_refs == ["prov-major-museum"]
    assert option.fit_signals == {
        "route_coherence": pytest.approx(0.89),
        "schedule_fit": pytest.approx(0.84),
        "budget_posture": pytest.approx(0.74),
    }
    assert option.source_refs == ["prov-major-museum"]
    assert option.booking_links == ["https://example.com/museum"]


def test_inventory_bundle_accepts_explicitly_infeasible_but_explained_bundle() -> None:
    payload = json.loads(
        _fixture_path("transport_lodging_bundle.json").read_text(encoding="utf-8")
    )
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
    assert (
        "Rail maintenance blocks the arrival window."
        in mixed_option.to_option().drawbacks
    )


def test_transport_only_bundle_requires_destinations_for_transport_endpoints() -> None:
    payload = json.loads(
        _fixture_path("transport_lodging_bundle.json").read_text(encoding="utf-8")
    )
    bundle = payload["bundles"][0]
    bundle["destinations"] = []
    bundle["lodging_options"] = []

    with pytest.raises(
        ValueError, match="destinations must include each origin_id and destination_id"
    ):
        InventoryBundle.from_dict(bundle)


def test_bundles_reject_inconsistent_destination_and_invalid_mixed_option_metadata() -> (
    None
):
    payload = json.loads(
        _fixture_path("route_level_mixed_option.json").read_text(encoding="utf-8")
    )
    payload["bundles"][1]["activity_options"][0]["destination_id"] = "dest-city-nara"
    with pytest.raises(
        ValueError, match="destinations must include each destination referenced"
    ):
        InventoryBundle.from_dict(payload["bundles"][1])

    payload = json.loads(
        _fixture_path("lodging_only_comparison.json").read_text(encoding="utf-8")
    )
    payload["supported_purposes"] = ["profile_learning", "profile_learning"]
    with pytest.raises(
        ValueError, match="supported_purposes must not contain duplicates"
    ):
        MixedOption.from_dict(payload)

    payload = json.loads(
        _fixture_path("transport_lodging_bundle.json").read_text(encoding="utf-8")
    )
    payload["route_coherence"]["destination_sequence"] = ["dest-city-osaka"]
    with pytest.raises(
        ValueError, match="route_coherence.destination_sequence must cover"
    ):
        MixedOption.from_dict(payload)

    payload = json.loads(
        _fixture_path("transport_lodging_bundle.json").read_text(encoding="utf-8")
    )
    payload["bundles"][0]["composition_summary"]["component_option_ids"] = [
        "lodg-osaka-station-hotel"
    ]
    with pytest.raises(
        ValueError,
        match="composition_summary.component_option_ids must match the options",
    ):
        InventoryBundle.from_dict(payload["bundles"][0])

    payload = json.loads(
        _fixture_path("route_level_mixed_option.json").read_text(encoding="utf-8")
    )
    payload["provenance_summary"]["source_refs"] = ["prov-not-present"]
    with pytest.raises(
        ValueError, match="source_refs and provenance_summary.source_refs must be drawn"
    ):
        MixedOption.from_dict(payload)

    payload = json.loads(
        _fixture_path("route_level_mixed_option.json").read_text(encoding="utf-8")
    )
    payload["source_refs"] = ["prov-not-present"]
    with pytest.raises(
        ValueError, match="source_refs and provenance_summary.source_refs must be drawn"
    ):
        MixedOption.from_dict(payload)

    payload = json.loads(
        _fixture_path("transport_lodging_bundle.json").read_text(encoding="utf-8")
    )
    payload["booking_links"] = ["https://example.com/not-a-real-bundle-link"]
    with pytest.raises(
        ValueError,
        match="booking_links and provenance_summary.booking_links must be drawn",
    ):
        MixedOption.from_dict(payload)
