from typing import Any, cast

import pytest

from trip_planner.business import (
    BusinessPlanningObjectives,
    ObjectiveExplanationBundle,
    PlanningPathObjectives,
)


def test_business_planning_objectives_serialize_structured_paths_and_explanations() -> None:
    objectives = BusinessPlanningObjectives(
        objective_id="obj-business-1",
        trip_id="trip-business-1",
        compliant_first_path=PlanningPathObjectives(
            mode="compliant_first",
            active=True,
            trigger_signals=["approved_only_channels"],
        ),
        policy_nearest_fallback=PlanningPathObjectives(
            mode="policy_nearest",
            active=True,
            trigger_signals=["mission_critical_schedule", "exception_preclearance"],
            notes=["Keep a policy-nearest fallback objective bundle ready."],
        ),
        explanation_bundle=ObjectiveExplanationBundle(
            summary=["policy_nearest_fallback_active:true"],
            category_reasons={
                "planning_paths": ["primary=compliant_first", "fallback_active=true"],
                "exception_path_posture": ["posture=exception_ready"],
            },
        ),
        explanations=["policy_nearest_fallback_active:true"],
    )

    payload = objectives.to_dict()

    assert payload["compliant_first_path"]["mode"] == "compliant_first"
    assert payload["policy_nearest_fallback"]["trigger_signals"] == [
        "mission_critical_schedule",
        "exception_preclearance",
    ]
    assert payload["explanation_bundle"]["category_reasons"]["planning_paths"][0] == (
        "primary=compliant_first"
    )


@pytest.mark.parametrize("value", ["not-a-list", {"bad": "shape"}, True])
def test_objective_explanation_bundle_rejects_non_list_category_reasons(
    value: object,
) -> None:
    with pytest.raises(ValueError, match=r"category_reasons\[planning_paths\] must be a list"):
        ObjectiveExplanationBundle(
            summary=[],
            category_reasons={"planning_paths": cast(Any, value)},
        )
