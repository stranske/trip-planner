import json
from pathlib import Path

from trip_planner.contracts import (
    ComparisonAxis,
    InventoryBundle,
    MoneyRange,
    MixedOption,
    Option,
    OptionCostSummary,
    OptionQualitySummary,
    OptionSet,
)


def test_option_set_serializes_profile_learning_bundle() -> None:
    option_set = OptionSet(
        option_set_id="optset-1",
        trip_id="trip-leisure-1",
        purpose="profile_learning",
        scope="mixed",
        title="Early route and lodging styles",
        options=[
            Option(
                option_id="opt-rail-route",
                kind="route",
                label="Rail-first slower route",
                fit_signals={"movement_fit": 0.88, "scenic_transit_fit": 0.92},
                cost_summary=OptionCostSummary(
                    total=MoneyRange(currency="USD", typical_amount=2650.0),
                ),
                quality_summary=OptionQualitySummary(
                    fit_signal=0.9,
                    value_signal=0.72,
                ),
                drawbacks=["More hotel changes."],
                source_refs=["src-rail"],
                explanation=["Prioritizes scenic transit and coherent progression."],
            ),
            Option(
                option_id="opt-single-base",
                kind="lodging",
                label="Fewer bases with better recovery",
                fit_signals={"recovery_fit": 0.84},
                cost_summary=OptionCostSummary(
                    total=MoneyRange(currency="USD", typical_amount=2380.0),
                ),
                quality_summary=OptionQualitySummary(
                    fit_signal=0.8,
                    quality_signal=0.76,
                ),
                drawbacks=["Less regional coverage."],
                source_refs=["src-lodging"],
                explanation=["Protects recovery and arrival simplicity."],
            ),
        ],
        comparison_axes=[
            ComparisonAxis(
                key="recovery_fit",
                label="Recovery fit",
                direction="higher_better",
            ),
            ComparisonAxis(
                key="move_count",
                label="Move count",
                direction="lower_better",
            ),
        ],
        explanation=["Used to learn whether the traveler prefers breadth or rhythm."],
        source_refs=["planner-generated"],
        selection_limit=1,
    )

    payload = option_set.to_dict()

    assert payload["purpose"] == "profile_learning"
    assert payload["options"][0]["kind"] == "route"
    assert payload["comparison_axes"][1]["direction"] == "lower_better"


def test_option_set_rejects_invalid_selection_limit() -> None:
    try:
        OptionSet(
            option_set_id="optset-2",
            trip_id="trip-leisure-2",
            purpose="inventory_narrowing",
            scope="lodging",
            title="Hotel options",
            options=[Option(option_id="opt-1", kind="lodging", label="Central hotel")],
            selection_limit=2,
        )
    except ValueError as exc:
        assert "selection_limit" in str(exc)
    else:
        raise AssertionError("OptionSet should reject selection_limit values above option count")


def test_option_rejects_invalid_kind() -> None:
    try:
        Option(option_id="opt-2", kind="museum", label="Invalid")
    except ValueError as exc:
        assert "kind" in str(exc)
    else:
        raise AssertionError("Option should reject unsupported kinds")


def test_option_rejects_non_string_fit_signal_keys() -> None:
    try:
        Option(
            option_id="opt-3",
            kind="route",
            label="Broken fit signal mapping",
            fit_signals={1: 0.8},  # type: ignore[dict-item]
        )
    except ValueError as exc:
        assert "fit_signals" in str(exc)
    else:
        raise AssertionError("Option should reject non-string fit_signals keys")


def test_shared_contract_package_exports_inventory_bundle_and_mixed_option() -> None:
    fixture_path = Path("tests/fixtures/options/bundles/transport_lodging_bundle.json")
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    bundle = InventoryBundle.from_dict(payload["bundles"][0])
    mixed_option = MixedOption.from_dict(payload)

    assert bundle.bundle_context == "transport_lodging"
    assert mixed_option.bundles[0].bundle_id == bundle.bundle_id
    assert mixed_option.to_option().kind == "mixed"
