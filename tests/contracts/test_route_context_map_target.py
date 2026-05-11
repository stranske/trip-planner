"""Schema test for the route-context map target contract.

Validates the canonical fixture in
``tests/fixtures/maps/route_context_map_target.json`` against the documented
contract in ``docs/contracts/route-context-map-target.md`` (issue #959).

If the workspace payload schema drops a documented field, this test fails with
an explicit "missing required map target field" message naming the missing
field. If a fallback provider field shape changes incompatibly, the test
fails likewise.

Run with::

    pytest -q tests/contracts/test_route_context_map_target.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "maps" / "route_context_map_target.json"
)


def _load_fixture() -> dict:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


# ---- Documented required field sets (mirrored from the contract doc) ----

_REQUIRED_TRIP_FIELDS = ("trip_id", "primary_regions")
_REQUIRED_FEASIBILITY_FIELDS = ("assessments",)
_REQUIRED_BUNDLE_FIELDS = ("bundle_id", "destination_names")
_REQUIRED_SCENARIO_FIELDS = (
    "scenario_id",
    "route_sequence",
    "route_summary",
    "policy_posture",
    "map_view",
    "map_diagnostics",
)
_REQUIRED_MAP_VIEW_FIELDS = (
    "active_scope",
    "active_route_option_id",
    "selected_segment_id",
    "place_markers",
    "rough_route_geometry",
    "confidence",
)
_REQUIRED_MARKER_FIELDS = ("id", "label", "x", "y")
_REQUIRED_GEOMETRY_FIELDS = ("id", "from_label", "to_label", "x1", "y1", "x2", "y2")


def _missing(payload: dict, fields: tuple[str, ...], label: str) -> list[str]:
    return [f"{label}.{name}" for name in fields if name not in payload]


def test_route_context_map_target_fixture_exposes_required_fields() -> None:
    """The canonical fixture carries every field the contract requires."""
    fixture = _load_fixture()
    missing: list[str] = []

    trip = fixture.get("trip") or {}
    missing += _missing(trip, _REQUIRED_TRIP_FIELDS, "trip")

    feasibility = fixture.get("feasibility_summary") or {}
    missing += _missing(feasibility, _REQUIRED_FEASIBILITY_FIELDS, "feasibility_summary")

    bundles = (fixture.get("inventory_summary") or {}).get("bundles") or []
    assert bundles, (
        "Fixture is missing inventory_summary.bundles. The route-context map "
        "target requires at least one bundle to anchor destination context per "
        "docs/contracts/route-context-map-target.md."
    )
    for index, bundle in enumerate(bundles):
        missing += _missing(bundle, _REQUIRED_BUNDLE_FIELDS, f"bundles[{index}]")

    scenarios = (fixture.get("runtime_scenario_comparison") or {}).get("scenarios") or []
    assert scenarios, (
        "Fixture is missing runtime_scenario_comparison.scenarios. The "
        "route-context map target requires at least one scenario to render."
    )
    for index, scenario in enumerate(scenarios):
        missing += _missing(scenario, _REQUIRED_SCENARIO_FIELDS, f"scenarios[{index}]")
        map_view = scenario.get("map_view") or {}
        missing += _missing(map_view, _REQUIRED_MAP_VIEW_FIELDS, f"scenarios[{index}].map_view")
        for marker_index, marker in enumerate(map_view.get("place_markers") or []):
            missing += _missing(
                marker,
                _REQUIRED_MARKER_FIELDS,
                f"scenarios[{index}].map_view.place_markers[{marker_index}]",
            )
        for seg_index, segment in enumerate(map_view.get("rough_route_geometry") or []):
            missing += _missing(
                segment,
                _REQUIRED_GEOMETRY_FIELDS,
                f"scenarios[{index}].map_view.rough_route_geometry[{seg_index}]",
            )

    assert not missing, (
        f"Route-context map target fixture is missing required fields: {missing}. "
        f"Required by docs/contracts/route-context-map-target.md. Either restore "
        f"the fields in the fixture, or update the contract doc and this test "
        f"if the requirement is intentionally being relaxed."
    )


def test_route_context_map_target_segments_use_normalized_coordinates() -> None:
    """Segments use 0-1 normalized coordinates so the fallback schematic renders.

    The contract specifies that fallback rendering must remain feature-
    equivalent without provider-native tiles. The route segments therefore
    carry normalized geometry (x1/y1/x2/y2 in [0, 1]) rather than provider-
    specific projections, so the SVG/CSS fallback can position them directly.
    """
    fixture = _load_fixture()
    out_of_range: list[str] = []

    for scenario in fixture["runtime_scenario_comparison"]["scenarios"]:
        map_view = scenario.get("map_view") or {}
        for segment in map_view.get("rough_route_geometry") or []:
            for axis in ("x1", "y1", "x2", "y2"):
                value = segment.get(axis)
                if value is None or not (0.0 <= float(value) <= 1.0):
                    out_of_range.append(
                        f"scenario={scenario.get('scenario_id')!r} "
                        f"segment={segment.get('id')!r} {axis}={value!r}"
                    )

    assert not out_of_range, (
        "Route segments must use normalized 0..1 coordinates so the fallback "
        f"map schematic can render without provider tiles. Out-of-range: {out_of_range}. "
        "See docs/contracts/route-context-map-target.md."
    )


def test_route_context_map_target_segments_emit_optional_warning_field() -> None:
    """The contract reserves ``warning`` (string|null) on each segment.

    The fallback schematic uses this to highlight policy-debt segments. Tests
    enforce that even null is present so consumers can rely on the key existing.
    """
    fixture = _load_fixture()
    for scenario in fixture["runtime_scenario_comparison"]["scenarios"]:
        map_view = scenario.get("map_view") or {}
        for segment in map_view.get("rough_route_geometry") or []:
            assert "warning" in segment, (
                f"Segment {segment.get('id')!r} on scenario "
                f"{scenario.get('scenario_id')!r} is missing the documented "
                "``warning`` field (may be null). The fallback schematic "
                "consumes this field to render policy-exception highlights."
            )
            warning_value = segment["warning"]
            assert warning_value is None or isinstance(warning_value, str), (
                f"Segment {segment.get('id')!r} warning value is not a string|null: "
                f"{warning_value!r}."
            )


def test_route_context_map_target_scenarios_carry_metrics_estimated_total_currency_when_present() -> (
    None
):
    """``metrics.estimated_total`` is optional, but if present must carry currency + amounts.

    The map surface formats this via Intl.NumberFormat. A scenario carrying a
    non-null estimated_total without a currency code would crash the formatter,
    so the contract requires the currency field whenever the object is present.
    """
    fixture = _load_fixture()
    for scenario in fixture["runtime_scenario_comparison"]["scenarios"]:
        metrics = scenario.get("metrics") or {}
        total = metrics.get("estimated_total")
        if total is None:
            continue
        for required in ("currency", "typical_amount"):
            assert required in total, (
                f"scenario={scenario.get('scenario_id')!r} "
                f"metrics.estimated_total is missing required field {required!r}. "
                "The route-context map formatter requires both fields whenever the "
                "estimated_total object is non-null. See "
                "docs/contracts/route-context-map-target.md."
            )


@pytest.mark.parametrize(
    "deferred_feature",
    [
        "timeline_only_view",
        "scenario_comparison_map",
        "geography_first_state_model",
        "directions_iframe_fallback",
    ],
)
def test_route_context_map_target_does_not_absorb_deferred_features(
    deferred_feature: str,
) -> None:
    """The fixture must not include deferred features (sanity guard).

    Each deferred feature is owned by a separate epic/issue per the contract.
    If a future change starts hanging timeline blocks, comparison cards, or
    iframe URLs off the map fixture, this test fails — that is the signal to
    extend a separate contract rather than overload route-context.
    """
    fixture = _load_fixture()
    serialized = json.dumps(fixture).lower()

    forbidden_substrings = {
        "timeline_only_view": ("timeline_blocks", "timeline_only"),
        "scenario_comparison_map": ("comparison_card", "scenario_comparison_map"),
        "geography_first_state_model": ("browser_geography_state",),
        "directions_iframe_fallback": ("iframe", "directions_iframe"),
    }[deferred_feature]

    for substring in forbidden_substrings:
        assert substring not in serialized, (
            f"Route-context map target fixture contains '{substring}', which "
            f"belongs to the deferred feature '{deferred_feature}'. Per "
            "docs/contracts/route-context-map-target.md, deferred features "
            "must live in their own contract surfaces (timeline, comparison, "
            "etc.) rather than be absorbed into the route-context fixture."
        )
