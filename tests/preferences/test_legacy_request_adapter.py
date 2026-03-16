import json
from pathlib import Path

from trip_planner.preferences.legacy_request_adapter import (
    adapt_legacy_request,
    load_legacy_request,
)


def test_legacy_request_adapter_maps_existing_request_shape() -> None:
    request_path = Path("request.json")
    payload = json.loads(request_path.read_text(encoding="utf-8"))

    profile = adapt_legacy_request(payload)

    assert profile.hard_constraints.must_include_places == payload["must_see"]
    assert profile.trip_frame.season_window == payload["trip_window"]["months"]
    assert profile.budget_model.total_budget_sensitivity == payload["cost_sensitivity"]
    assert (
        "Mapped from legacy nature_ratio field."
        in profile.tradeoff_dimensions["nature_vs_culture"].notes
    )
    assert profile.hybrid_factors["route_modes"].preferences["rail"] == 1.0


def test_legacy_request_adapter_maps_nature_ratio_onto_canonical_axis() -> None:
    profile = adapt_legacy_request(
        {
            "trip_window": {"months": ["May"]},
            "must_see": [],
            "nature_ratio": 0.75,
            "complexity_tolerance": "medium",
            "cost_sensitivity": 0.3,
        }
    )

    assert profile.tradeoff_dimensions["nature_vs_culture"].value == 0.5


def test_legacy_request_adapter_maps_complexity_tolerance() -> None:
    profile = adapt_legacy_request(
        {
            "trip_window": {"months": ["June"]},
            "must_see": [],
            "nature_ratio": 0.5,
            "complexity_tolerance": "low",
            "cost_sensitivity": 0.3,
        }
    )

    assert profile.tradeoff_dimensions["movement_vs_friction"].value < 0
    assert profile.tradeoff_dimensions["recovery_vs_intensity"].value > 0
    assert profile.tradeoff_dimensions["self_reliance_vs_convenience"].value < 0


def test_legacy_request_adapter_rejects_invalid_budget_sensitivity() -> None:
    try:
        adapt_legacy_request(
            {
                "trip_window": {"months": ["June"]},
                "must_see": [],
                "nature_ratio": 0.5,
                "complexity_tolerance": "medium",
                "cost_sensitivity": 1.5,
            }
        )
    except ValueError as exc:
        assert "total_budget_sensitivity" in str(exc)
    else:
        raise AssertionError("Invalid legacy budget sensitivity should fail validation")


def test_load_legacy_request_reads_from_path(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "trip_window": {
                    "months": ["September"],
                    "min_weeks": 2,
                    "max_weeks": 3,
                },
                "must_see": ["Kyoto"],
                "nature_ratio": 0.4,
                "complexity_tolerance": "high",
                "cost_sensitivity": 0.2,
                "route_passions": {"train": 4},
            }
        ),
        encoding="utf-8",
    )

    profile = load_legacy_request(request_path)

    assert profile.hard_constraints.must_include_places == ["Kyoto"]
    assert profile.hybrid_factors["route_modes"].preferences["rail"] == 1.0
