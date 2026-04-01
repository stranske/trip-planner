import json
from pathlib import Path

import pytest

from trip_planner.contracts import MoneyRange
from trip_planner.options import (
    TransportBookingTerms,
    TransportCostSummary,
    TransportExperienceSummary,
    TransportFeasibility,
    TransportFitSummary,
    TransportOption,
    TransportPolicySummary,
    TransportSegment,
    TransportTimingSummary,
    TransportTransferBurden,
)
from trip_planner.sources import (
    ProvenanceReference,
    QualityValueFitSummary,
    SourceTrustSignals,
)


def _fixture_path(name: str) -> Path:
    return Path("tests/fixtures/options/transport") / name


def _load_option(name: str) -> TransportOption:
    payload = json.loads(_fixture_path(name).read_text(encoding="utf-8"))
    return TransportOption.from_dict(payload)


def test_transport_fixtures_cover_representative_option_shapes() -> None:
    fixtures = {
        "coastal_flight.json": "flight",
        "scenic_rail.json": "rail",
        "island_ferry.json": "ferry",
        "regional_rental_car.json": "car",
        "downtown_local_ground.json": "local_ground",
    }

    for name, expected_kind in fixtures.items():
        option = _load_option(name)
        assert option.transport_kind == expected_kind
        assert option.to_dict()["transport_kind"] == expected_kind


def test_transport_examples_keep_cheapest_easiest_and_best_fit_distinct() -> None:
    flight = _load_option("coastal_flight.json")
    rail = _load_option("scenic_rail.json")
    car = _load_option("regional_rental_car.json")

    assert car.cost_summary.total is not None
    assert flight.cost_summary.total is not None
    assert car.cost_summary.total.typical_amount is not None
    assert flight.cost_summary.total.typical_amount is not None
    assert rail.fit_summary.overall_signal is not None
    assert flight.fit_summary.overall_signal is not None
    assert car.cost_summary.total.typical_amount < flight.cost_summary.total.typical_amount
    assert flight.transfer_burden.transfer_count < rail.transfer_burden.transfer_count
    assert rail.fit_summary.overall_signal > flight.fit_summary.overall_signal


def test_transport_round_trips_nested_contracts_and_policy_context() -> None:
    option = TransportOption(
        option_id="transport-kyoto-osaka-rail",
        name="Haruka + local rail transfer",
        transport_kind="rail",
        origin_id="dest-kix",
        destination_id="dest-kyoto",
        timing_summary=TransportTimingSummary(
            departure_local="2026-04-05T09:05:00+09:00",
            arrival_local="2026-04-05T10:33:00+09:00",
            duration_minutes=88,
            departure_timezone="Asia/Tokyo",
            arrival_timezone="Asia/Tokyo",
        ),
        segments=[
            TransportSegment(
                segment_id="seg-haruka",
                mode="rail",
                origin_label="KIX Airport Station",
                destination_label="Kyoto Station",
                departure_local="2026-04-05T09:16:00+09:00",
                arrival_local="2026-04-05T10:31:00+09:00",
                carrier="JR West",
                service_number="Haruka 14",
                duration_minutes=75,
            )
        ],
        transfer_burden=TransportTransferBurden(
            transfer_count=0,
            self_navigation_burden_signal=0.18,
            baggage_complexity_signal=0.2,
            schedule_protection_signal=0.84,
        ),
        booking_terms=TransportBookingTerms(
            booking_channel="jr-west",
            refundable=False,
            class_of_service="standard",
            approved_channels=["jr-west", "travel-desk"],
            comparable_reference_ids=["cmp-flight-1"],
        ),
        cost_summary=TransportCostSummary(
            total=MoneyRange(currency="USD", typical_amount=29.0),
            base_fare=MoneyRange(currency="USD", typical_amount=24.0),
        ),
        experience_summary=TransportExperienceSummary(
            scenic_value_signal=0.55,
            workability_signal=0.72,
            comfort_signal=0.7,
        ),
        fit_summary=TransportFitSummary(
            overall_signal=0.86,
            schedule_fit_signal=0.84,
            friction_fit_signal=0.88,
            policy_fit_signal=0.95,
        ),
        policy_summary=TransportPolicySummary(
            business_approval_status="preferred",
            approved_booking_channel=True,
            class_of_service="standard",
            comparable_reference_ids=["cmp-flight-1"],
        ),
        feasibility=TransportFeasibility(
            available=True,
            accessibility_notes=["Step-free transfer available with elevator routing."],
        ),
        booking_links=["https://example.com/haruka"],
        source_refs=[
            ProvenanceReference(
                provenance_id="prov-haruka",
                source_id="jr-west-haruka",
                source_category="official_operational",
                subject_kind="option",
                subject_id="transport-kyoto-osaka-rail",
                contribution_kind="operational",
                summary="Official timetable confirms direct airport express timings.",
                trust_snapshot=SourceTrustSignals(
                    freshness_days=3,
                    editorial_independence=0.7,
                    operational_reliability=0.94,
                ),
                quality_value_fit=QualityValueFitSummary(
                    quality_signal=0.74,
                    value_signal=0.87,
                    fit_signal=0.86,
                ),
            )
        ],
        tags=["airport-transfer", "rail"],
    )

    payload = option.to_dict()

    assert payload["timing_summary"]["duration_minutes"] == 88
    assert payload["segments"][0]["carrier"] == "JR West"
    assert payload["policy_summary"]["business_approval_status"] == "preferred"
    assert payload["source_refs"][0]["quality_value_fit"]["value_signal"] == 0.87


def test_transport_rejects_invalid_kind_segment_and_schema_values() -> None:
    with pytest.raises(ValueError, match="transport_kind"):
        TransportOption(
            option_id="bad-kind",
            name="Broken",
            transport_kind="helicopter",
            origin_id="orig",
            destination_id="dest",
            timing_summary=TransportTimingSummary(
                departure_local="2026-04-05T09:00:00+09:00",
                arrival_local="2026-04-05T10:00:00+09:00",
                duration_minutes=60,
            ),
            segments=[
                TransportSegment(
                    segment_id="seg-1",
                    mode="flight",
                    origin_label="A",
                    destination_label="B",
                )
            ],
        )

    with pytest.raises(ValueError, match="mode"):
        TransportSegment(
            segment_id="seg-bad",
            mode="helicopter",
            origin_label="A",
            destination_label="B",
        )

    payload = json.loads(_fixture_path("coastal_flight.json").read_text(encoding="utf-8"))
    payload["schema_version"] = "9.9.9"
    with pytest.raises(ValueError, match="schema_version"):
        TransportOption.from_dict(payload)


def test_transport_rejects_invalid_nested_values() -> None:
    with pytest.raises(ValueError, match="duration_minutes"):
        TransportTimingSummary(
            departure_local="2026-04-05T09:00:00+09:00",
            arrival_local="2026-04-05T08:00:00+09:00",
            duration_minutes=-1,
        )

    with pytest.raises(ValueError, match="class_of_service"):
        TransportBookingTerms(class_of_service="ultra-luxe")

    payload = json.loads(_fixture_path("scenic_rail.json").read_text(encoding="utf-8"))
    payload["source_refs"][0]["source_category"] = "unsupported"
    with pytest.raises(ValueError, match="source_category"):
        TransportOption.from_dict(payload)


def test_transport_normalizes_legacy_rental_car_kind() -> None:
    payload = json.loads(_fixture_path("regional_rental_car.json").read_text(encoding="utf-8"))
    payload["transport_kind"] = "rental_car"

    option = TransportOption.from_dict(payload)

    assert option.transport_kind == "car"
    assert option.to_dict()["transport_kind"] == "car"


def test_transport_requires_non_empty_segments_and_list_fields() -> None:
    with pytest.raises(ValueError, match="segments"):
        TransportOption(
            option_id="no-segments",
            name="Broken",
            transport_kind="rail",
            origin_id="orig",
            destination_id="dest",
            timing_summary=TransportTimingSummary(
                departure_local="2026-04-05T09:00:00+09:00",
                arrival_local="2026-04-05T10:00:00+09:00",
                duration_minutes=60,
            ),
            segments=[],
        )

    payload = json.loads(_fixture_path("regional_rental_car.json").read_text(encoding="utf-8"))
    payload["booking_links"] = "https://example.com/not-a-list"
    with pytest.raises(ValueError, match="booking_links must be a list"):
        TransportOption.from_dict(payload)
