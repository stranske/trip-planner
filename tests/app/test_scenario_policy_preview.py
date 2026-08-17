from trip_planner.app.services.scenario_policy_preview import build_scenario_policy_preview

FIXTURE_POLICY = {
    "constraint_set": {
        "budget_rules": {"rule_id": "BUD-001", "max_trip_total_usd": 2300},
        "lodging_rules": {"rule_id": "LOD-001", "max_nightly_rate_usd": 325},
    }
}


def test_compliant_scenario_preview_when_under_trip_cap() -> None:
    preview = build_scenario_policy_preview(
        policy_state=FIXTURE_POLICY,
        trip_mode="business",
        duration_days=4,
        estimated_total={"currency": "USD", "typical_amount": 2280},
        unresolved_tradeoffs=[],
        scenario_notes=["compliant-first"],
    )

    assert preview["snapshot_available"] is True
    assert preview["compliant"] is True
    assert preview["status_label"] == "In policy (preview)"
    assert preview["violations"] == []


def test_non_compliant_scenario_preview_includes_cap_vs_actual() -> None:
    preview = build_scenario_policy_preview(
        policy_state=FIXTURE_POLICY,
        trip_mode="business",
        duration_days=4,
        estimated_total={"currency": "USD", "typical_amount": 2410},
        unresolved_tradeoffs=[
            {
                "code": "policy_exception_path",
                "summary": "Requires exception approval before booking.",
                "blocking": True,
            }
        ],
        scenario_notes=["exception-nearest"],
    )

    assert preview["compliant"] is False
    bud_violation = next(item for item in preview["violations"] if item["rule_id"] == "BUD-001")
    assert bud_violation["cap_amount"] == 2300
    assert bud_violation["actual_amount"] == 2410
    assert any(item["rule_id"] == "POL-EXC" for item in preview["violations"])


def test_missing_policy_snapshot_is_not_marked_compliant() -> None:
    preview = build_scenario_policy_preview(
        policy_state=None,
        trip_mode="business",
        duration_days=4,
        estimated_total={"currency": "USD", "typical_amount": 2280},
    )

    assert preview["snapshot_available"] is False
    assert preview["status_label"] == "No policy snapshot available"
    assert preview["compliant"] is None
