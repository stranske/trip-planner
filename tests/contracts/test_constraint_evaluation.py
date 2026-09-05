from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from trip_planner.app.services.inventory import (
    _build_inventory_assembly_input,
    assemble_inventory_bundles_for_trip,
)
from trip_planner.persistence.models.trip import PersistedTrip
from trip_planner.options.bundles import BundleFeasibility, ConstraintEvaluation, InventoryBundle


def _assert_bundle_payload_includes_constraint_evaluation(
    bundle_payload: dict[str, object],
) -> None:
    assert "constraint_evaluation" in bundle_payload
    evaluation = bundle_payload["constraint_evaluation"]
    assert isinstance(evaluation, dict)
    assert evaluation.get("status") == "evaluated"
    assert evaluation.get("overall_pass") is True
    assert evaluation.get("evaluated_constraint_ids")


def test_bundle_includes_evaluation() -> None:
    assembly_input = _build_inventory_assembly_input(
        trip_id="trip-leisure-kyoto-draft",
        trip_mode="leisure",
        primary_regions=("Kyoto",),
        duration_days=4,
    )
    bundles = assemble_inventory_bundles_for_trip(assembly_input=assembly_input)

    assert bundles
    emitted_payload = bundles[0].to_dict()
    _assert_bundle_payload_includes_constraint_evaluation(emitted_payload)

    without_evaluation = dict(emitted_payload)
    without_evaluation.pop("constraint_evaluation")
    with pytest.raises(AssertionError):
        _assert_bundle_payload_includes_constraint_evaluation(without_evaluation)


def test_runtime_inventory_emitter_includes_constraint_evaluation() -> None:
    persisted_trip = PersistedTrip(
        trip_id="trip-business-client-summit",
        user_id="user-test",
        title="Client summit",
        summary="Runtime inventory should emit constraint evaluation.",
        mode="business",
        status="draft",
        start_date="2026-08-01",
        end_date="2026-08-04",
        duration_days=4,
        primary_regions=["Chicago"],
        traveler_party_kind="solo",
        traveler_count=1,
        traveler_notes="",
    )
    assembly_input = _build_inventory_assembly_input(
        trip_id=persisted_trip.trip_id,
        trip_mode=persisted_trip.mode,
        persisted_trip=persisted_trip,
    )
    bundles = assemble_inventory_bundles_for_trip(assembly_input=assembly_input)

    assert len(bundles) == 1
    payload = bundles[0].to_dict()
    _assert_bundle_payload_includes_constraint_evaluation(payload)
    assert payload["constraint_evaluation"]["policy_constraints_satisfied"] is True


def _bundle_payload() -> dict:
    fixture = Path("tests/fixtures/options/bundles/lodging_only_comparison.json")
    return json.loads(fixture.read_text())["bundles"][0]


@pytest.mark.parametrize("raw", [[], "invalid", False, 0, {}])
def test_bundle_rejects_invalid_explicit_evaluation(raw: object) -> None:
    payload = _bundle_payload()
    payload["constraint_evaluation"] = raw
    with pytest.raises(ValueError, match="constraint_evaluation.*mapping"):
        InventoryBundle.from_dict(payload)


@pytest.mark.parametrize(
    "field_name", ["overall_pass", "hard_constraints_satisfied", "policy_constraints_satisfied"]
)
@pytest.mark.parametrize("invalid", ["false", "true", 0, 1, [], {}])
@pytest.mark.parametrize("deserialize", [False, True])
def test_evaluation_rejects_non_boolean_fields(
    field_name: str, invalid: object, deserialize: bool
) -> None:
    payload = {field_name: invalid}
    with pytest.raises(ValueError, match=field_name + ".*boolean"):
        if deserialize:
            ConstraintEvaluation.from_dict(payload)
        else:
            ConstraintEvaluation(**payload)


@pytest.mark.parametrize("field_name", ["overall_pass", "hard_constraints_satisfied"])
def test_required_evaluation_booleans_reject_null(field_name: str) -> None:
    with pytest.raises(ValueError, match=field_name + ".*boolean"):
        ConstraintEvaluation.from_dict({field_name: None})


@pytest.mark.parametrize("policy", [True, False, None])
def test_evaluation_preserves_real_booleans(policy: bool | None) -> None:
    payload = {
        "overall_pass": False,
        "hard_constraints_satisfied": False,
        "policy_constraints_satisfied": policy,
        "blocking_constraint_ids": ["capacity"],
    }
    evaluation = ConstraintEvaluation.from_dict(payload)
    assert evaluation.overall_pass is False
    assert evaluation.hard_constraints_satisfied is False
    assert evaluation.policy_constraints_satisfied is policy
    assert ConstraintEvaluation.from_dict(evaluation.to_dict()) == evaluation


@pytest.mark.parametrize("unmet", [None, "available", "internally_consistent"])
@pytest.mark.parametrize("null_evaluation", [False, True])
def test_missing_evaluation_derives_from_feasibility(
    unmet: str | None, null_evaluation: bool
) -> None:
    payload = _bundle_payload()
    payload.pop("constraint_evaluation", None)
    if null_evaluation:
        payload["constraint_evaluation"] = None
    feasibility = {
        "available": True,
        "internally_consistent": True,
        "blocking_reasons": [],
        "notes": ["source evidence"],
    }
    if unmet:
        feasibility[unmet] = False
        feasibility["blocking_reasons"] = ["Inventory is not available for these dates."]
    payload["feasibility"] = feasibility
    bundle = InventoryBundle.from_dict(payload)
    evaluation = bundle.to_dict()["constraint_evaluation"]
    assert evaluation["overall_pass"] is (unmet is None)
    assert evaluation["hard_constraints_satisfied"] is (unmet is None)
    assert evaluation["blocking_constraint_ids"] == feasibility["blocking_reasons"]
    assert evaluation["notes"] == ["source evidence"]
    assert evaluation["evaluated_constraint_ids"] == [
        "bundle.feasibility.available",
        "bundle.feasibility.internally_consistent",
    ]


@pytest.mark.parametrize("unmet", ["available", "internally_consistent"])
def test_direct_construction_derives_failing_evaluation(unmet: str) -> None:
    bundle = InventoryBundle.from_dict(_bundle_payload())
    feasibility = BundleFeasibility(**{unmet: False}, blocking_reasons=["capacity"])
    direct = InventoryBundle(
        bundle_id=bundle.bundle_id,
        title=bundle.title,
        destinations=bundle.destinations,
        lodging_options=bundle.lodging_options,
        feasibility=feasibility,
    )
    evaluation = direct.to_dict()["constraint_evaluation"]
    assert evaluation["overall_pass"] is False
    assert evaluation["hard_constraints_satisfied"] is False
    assert evaluation["blocking_constraint_ids"] == ["capacity"]


def test_explicit_evaluation_is_preserved() -> None:
    bundle = InventoryBundle.from_dict(_bundle_payload())
    explicit = ConstraintEvaluation(
        status="partial",
        overall_pass=False,
        hard_constraints_satisfied=True,
        policy_constraints_satisfied=False,
        blocking_constraint_ids=["policy.approval"],
    )
    direct = replace(bundle, constraint_evaluation=explicit)
    assert direct.constraint_evaluation is explicit
    assert (
        InventoryBundle.from_dict(direct.to_dict()).to_dict()["constraint_evaluation"]
        == explicit.to_dict()
    )


def test_public_contract_exports() -> None:
    import trip_planner.contracts as contracts
    import trip_planner.options as options

    assert contracts.ConstraintEvaluation is ConstraintEvaluation
    assert "ConstraintEvaluation" in contracts.__all__
    assert "constraint_evaluation_from_feasibility" in options.__all__
