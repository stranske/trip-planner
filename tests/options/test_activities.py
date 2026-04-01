import json
from pathlib import Path

import pytest

from trip_planner.contracts import MoneyRange
from trip_planner.options import (
    ActivityBookingTerms,
    ActivityCategory,
    ActivityCostSummary,
    ActivityEffortSummary,
    ActivityFeasibility,
    ActivityFitSummary,
    ActivityOption,
    ActivityQualitySummary,
    ActivitySignificanceSummary,
    ActivityTimingSummary,
    ActivityValueSummary,
)
from trip_planner.sources import (
    ProvenanceReference,
    QualityValueFitSummary,
    SourceTrustSignals,
)


def _fixture_path(name: str) -> Path:
    return Path("tests/fixtures/options/activities") / name


def _load_option(name: str) -> ActivityOption:
    payload = json.loads(_fixture_path(name).read_text(encoding="utf-8"))
    return ActivityOption.from_dict(payload)


def test_activity_fixtures_cover_structured_and_open_ended_shapes() -> None:
    fixtures = {
        "major_museum.json": "museum",
        "landscape_hike.json": "landscape",
        "wandering_district.json": "district",
        "ticketed_event.json": "event",
    }

    for name, expected_kind in fixtures.items():
        option = _load_option(name)
        assert option.activity_kind == expected_kind
        assert option.to_dict()["activity_kind"] == expected_kind


def test_activity_examples_keep_significance_and_fit_distinct() -> None:
    museum = _load_option("major_museum.json")
    hike = _load_option("landscape_hike.json")
    district = _load_option("wandering_district.json")

    assert museum.significance_summary.overall_signal is not None
    assert museum.fit_summary.overall_signal is not None
    assert museum.significance_summary.overall_signal > museum.fit_summary.overall_signal
    assert hike.significance_summary.anchor_worthy is True
    assert district.category.open_ended is True


def test_activity_round_trips_nested_contracts_and_provenance() -> None:
    option = ActivityOption(
        option_id="activity-night-market-food-tour",
        name="Shilin night market tasting walk",
        activity_kind="tour",
        destination_id="dest-taipei",
        place_id="place-shilin-market",
        category=ActivityCategory(
            primary="food-tour",
            secondary=["street-food", "guided-walk"],
            tags=["evening", "group-friendly"],
        ),
        timing_summary=ActivityTimingSummary(
            duration_minutes=150,
            typical_start_window="18:30-20:30",
            timing_sensitivity_signal=0.68,
            crowd_pressure_signal=0.74,
        ),
        significance_summary=ActivitySignificanceSummary(
            overall_signal=0.72,
            local_icon_signal=0.66,
            cultural_signal=0.81,
            anchor_worthy=False,
            optional=True,
        ),
        effort_summary=ActivityEffortSummary(
            effort_level="moderate",
            walking_minutes=90,
            intensity_signal=0.37,
        ),
        booking_terms=ActivityBookingTerms(
            activity_format="reservation_required",
            booking_required=True,
            ticketed=True,
            booking_channel="market-tours",
            approved_channels=["market-tours", "hotel-concierge"],
        ),
        cost_summary=ActivityCostSummary(
            total=MoneyRange(currency="USD", typical_amount=88.0),
            per_person=MoneyRange(currency="USD", typical_amount=44.0),
        ),
        quality_summary=ActivityQualitySummary(
            overall_signal=0.78,
            content_quality_signal=0.8,
            hospitality_signal=0.76,
        ),
        value_summary=ActivityValueSummary(
            overall_signal=0.74,
            uniqueness_signal=0.79,
            time_value_signal=0.7,
        ),
        fit_summary=ActivityFitSummary(
            overall_signal=0.69,
            traveler_fit_signal=0.73,
            pacing_fit_signal=0.65,
            group_fit_signal=0.8,
        ),
        feasibility=ActivityFeasibility(
            available=True,
            availability_status="available",
            indoor_outdoor="mixed",
            accessibility_notes=["Mostly flat route with occasional crowd bottlenecks."],
        ),
        booking_links=["https://example.com/night-market-tour"],
        source_refs=[
            ProvenanceReference(
                provenance_id="prov-night-market-tour",
                source_id="taipei-food-guides",
                source_category="editorial",
                subject_kind="option",
                subject_id="activity-night-market-food-tour",
                contribution_kind="editorial",
                summary="Guide coverage confirms pacing, stall mix, and evening crowd patterns.",
                trust_snapshot=SourceTrustSignals(
                    freshness_days=14,
                    editorial_independence=0.86,
                    operational_reliability=0.61,
                ),
                quality_value_fit=QualityValueFitSummary(
                    quality_signal=0.78,
                    value_signal=0.73,
                    fit_signal=0.69,
                ),
            )
        ],
        tags=["food", "nightlife"],
    )

    payload = option.to_dict()

    assert payload["category"]["primary"] == "food-tour"
    assert payload["booking_terms"]["booking_required"] is True
    assert payload["source_refs"][0]["quality_value_fit"]["fit_signal"] == 0.69


def test_activity_rejects_invalid_kind_format_and_schema_values() -> None:
    with pytest.raises(ValueError, match="activity_kind"):
        ActivityOption(
            option_id="bad-kind",
            name="Broken",
            activity_kind="cruise",
            destination_id="dest",
            place_id="place",
            category=ActivityCategory(primary="museum"),
            timing_summary=ActivityTimingSummary(duration_minutes=60),
        )

    with pytest.raises(ValueError, match="activity_format"):
        ActivityBookingTerms(activity_format="walk-up-only")

    payload = json.loads(_fixture_path("major_museum.json").read_text(encoding="utf-8"))
    payload["schema_version"] = "9.9.9"
    with pytest.raises(ValueError, match="schema_version"):
        ActivityOption.from_dict(payload)


def test_activity_rejects_invalid_nested_values() -> None:
    with pytest.raises(ValueError, match="duration_minutes"):
        ActivityTimingSummary(duration_minutes=-10)

    with pytest.raises(ValueError, match="effort_level"):
        ActivityEffortSummary(effort_level="extreme")

    payload = json.loads(_fixture_path("ticketed_event.json").read_text(encoding="utf-8"))
    payload["source_refs"][0]["source_category"] = "unsupported"
    with pytest.raises(ValueError, match="source_category"):
        ActivityOption.from_dict(payload)


def test_activity_requires_non_empty_list_fields() -> None:
    payload = json.loads(_fixture_path("wandering_district.json").read_text(encoding="utf-8"))
    payload["booking_links"] = "https://example.com/not-a-list"
    with pytest.raises(ValueError, match="booking_links must be a list"):
        ActivityOption.from_dict(payload)

    with pytest.raises(ValueError, match="tags must contain only non-empty strings"):
        ActivityCategory(primary="district", tags=["historic", ""])
