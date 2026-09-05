from __future__ import annotations

import pytest

from trip_planner.app.services.inventory import (
    _build_inventory_assembly_input,
    assemble_inventory_bundles_for_trip,
)
from trip_planner.persistence.models.trip import PersistedTrip


def _assert_bundle_payload_includes_constraint_evaluation(bundle_payload: dict[str, object]) -> None:
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
