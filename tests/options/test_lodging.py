import json
from pathlib import Path

import pytest

from trip_planner.contracts import MoneyRange
from trip_planner.options import (
    LodgingBookingTerms,
    LodgingCostSummary,
    LodgingFeasibility,
    LodgingFitSummary,
    LodgingLocationSummary,
    LodgingOption,
    LodgingQualitySummary,
    LodgingRoomSummary,
    LodgingValueSummary,
)
from trip_planner.sources import ProvenanceReference, QualityValueFitSummary, SourceTrustSignals


def _fixture_path(name: str) -> Path:
    return Path("tests/fixtures/options/lodging") / name


def _load_option(name: str) -> LodgingOption:
    payload = json.loads(_fixture_path(name).read_text(encoding="utf-8"))
    return LodgingOption.from_dict(payload)


def test_lodging_fixtures_cover_representative_option_shapes() -> None:
    fixtures = {
        "central_urban_hotel.json": "hotel",
        "quiet_outer_area_hotel.json": "hotel",
        "vacation_rental.json": "vacation_rental",
        "conference_hotel.json": "hotel",
    }

    for name, expected_kind in fixtures.items():
        option = _load_option(name)
        assert option.room_summary.lodging_kind == expected_kind
        assert option.to_dict()["room_summary"]["lodging_kind"] == expected_kind


def test_conference_hotel_preserves_business_approval_and_workspace_context() -> None:
    option = _load_option("conference_hotel.json")

    assert option.feasibility.business_approval_status == "preferred"
    assert option.room_summary.workspace_signal == pytest.approx(0.91)
    assert option.location_summary.business_access_signal == pytest.approx(0.95)
    assert option.source_refs[0].source_category == "managed_travel_policy"


def test_vacation_rental_keeps_quality_value_and_fit_distinct() -> None:
    option = _load_option("vacation_rental.json")

    assert option.quality_summary.overall_signal == pytest.approx(0.72)
    assert option.value_summary.overall_signal == pytest.approx(0.88)
    assert option.fit_summary.overall_signal == pytest.approx(0.9)
    assert option.fit_summary.quiet_recovery_signal > option.quality_summary.sleep_quality_signal


def test_lodging_round_trips_nested_contracts_and_provenance() -> None:
    option = LodgingOption(
        option_id="lodg-kyoto-riverside-suite",
        name="Kyoto Riverside Suites",
        destination_id="dest-city-kyoto",
        summary="Apartment-style stay that favors space and quiet over concierge service.",
        location_summary=LodgingLocationSummary(
            destination_id="dest-city-kyoto",
            location_context="inner_neighborhood",
            neighborhood="Okazaki",
            access_summary="Walkable to the canal and direct bus access to Higashiyama.",
            walk_minutes_to_anchor=12,
            quiet_signal=0.85,
            recovery_signal=0.89,
            place_context_ids=["dest-city-kyoto", "dest-neighborhood-okazaki"],
        ),
        room_summary=LodgingRoomSummary(
            lodging_kind="apartment",
            room_type="Studio apartment",
            bed_configuration="1 queen bed",
            comfort_signal=0.81,
            cleanliness_signal=0.8,
            privacy_signal=0.93,
            amenities=["kitchenette", "washer", "balcony"],
        ),
        booking_terms=LodgingBookingTerms(
            cancellation_summary="Free cancellation until 72 hours before arrival.",
            refundable=True,
            booking_channel="direct",
        ),
        cost_summary=LodgingCostSummary(
            nightly=MoneyRange(currency="USD", typical_amount=165.0, min_amount=150.0, max_amount=180.0),
            total=MoneyRange(currency="USD", typical_amount=660.0),
        ),
        quality_summary=LodgingQualitySummary(overall_signal=0.77, sleep_quality_signal=0.82),
        value_summary=LodgingValueSummary(overall_signal=0.86, space_value_signal=0.91),
        fit_summary=LodgingFitSummary(overall_signal=0.9, quiet_recovery_signal=0.92),
        feasibility=LodgingFeasibility(
            inventory_status="available",
            available=True,
            business_approval_status="unknown",
        ),
        booking_links=["https://example.com/kyoto-riverside-suites"],
        source_refs=[
            ProvenanceReference(
                provenance_id="prov-kyoto-editorial",
                source_id="kyoto-handbook",
                source_category="editorial",
                subject_kind="option",
                subject_id="lodg-kyoto-riverside-suite",
                contribution_kind="editorial",
                summary="Editorial review highlights quiet canal-facing rooms and practical walkability.",
                trust_snapshot=SourceTrustSignals(
                    freshness_days=21,
                    editorial_independence=0.9,
                    operational_reliability=0.72,
                ),
                quality_value_fit=QualityValueFitSummary(
                    quality_signal=0.76,
                    value_signal=0.82,
                    fit_signal=0.88,
                ),
            )
        ],
        tags=["quiet-recovery", "apartment-style"],
        notes=["Useful when the trip needs a slower middle section."],
    )

    payload = option.to_dict()

    assert payload["location_summary"]["neighborhood"] == "Okazaki"
    assert payload["cost_summary"]["nightly"]["typical_amount"] == 165.0
    assert payload["source_refs"][0]["quality_value_fit"]["fit_signal"] == 0.88
    assert payload["fit_summary"]["quiet_recovery_signal"] == 0.92


def test_lodging_rejects_invalid_kind_approval_and_schema_values() -> None:
    with pytest.raises(ValueError, match="lodging_kind"):
        LodgingRoomSummary(lodging_kind="capsule")

    with pytest.raises(ValueError, match="business_approval_status"):
        LodgingFeasibility(business_approval_status="escalate")

    payload = json.loads(_fixture_path("central_urban_hotel.json").read_text(encoding="utf-8"))
    payload["schema_version"] = "9.9.9"
    with pytest.raises(ValueError, match="schema_version"):
        LodgingOption.from_dict(payload)


def test_lodging_rejects_invalid_nested_values() -> None:
    with pytest.raises(ValueError, match="walk_minutes_to_anchor"):
        LodgingLocationSummary(
            destination_id="dest-city-kyoto",
            location_context="urban_core",
            walk_minutes_to_anchor=-1,
        )

    payload = json.loads(_fixture_path("conference_hotel.json").read_text(encoding="utf-8"))
    payload["source_refs"][0]["source_category"] = "unsupported"
    with pytest.raises(ValueError, match="source_category"):
        LodgingOption.from_dict(payload)


def test_lodging_requires_positive_min_stay_and_matching_destination_id() -> None:
    with pytest.raises(ValueError, match="min_stay_nights"):
        LodgingBookingTerms(min_stay_nights=0)

    with pytest.raises(ValueError, match="destination_id on LodgingOption must match"):
        LodgingOption(
            option_id="lodg-mismatch",
            name="Mismatch Stay",
            destination_id="dest-a",
            location_summary=LodgingLocationSummary(
                destination_id="dest-b",
                location_context="urban_core",
            ),
            room_summary=LodgingRoomSummary(lodging_kind="hotel"),
        )


def test_lodging_rejects_plain_strings_for_list_fields() -> None:
    with pytest.raises(ValueError, match="booking_links must be a list"):
        LodgingOption(
            option_id="lodg-string-links",
            name="String Links Stay",
            destination_id="dest-city-kyoto",
            location_summary=LodgingLocationSummary(
                destination_id="dest-city-kyoto",
                location_context="urban_core",
            ),
            room_summary=LodgingRoomSummary(lodging_kind="hotel"),
            booking_links="https://example.com/not-a-list",  # type: ignore[arg-type]
        )

    payload = json.loads(_fixture_path("central_urban_hotel.json").read_text(encoding="utf-8"))
    payload["cost_summary"]["notes"] = "not-a-list"
    with pytest.raises(ValueError, match="notes must be a list"):
        LodgingOption.from_dict(payload)
