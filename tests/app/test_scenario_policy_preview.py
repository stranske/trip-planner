import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.app.services.scenario_policy_preview import (
    build_scenario_policy_preview,
)
from trip_planner.persistence.db import get_session_factory, reset_database_state
from trip_planner.persistence.models.policy import PersistedPolicyState

FIXTURE_POLICY = {
    "constraint_set": {
        "budget_rules": {"rule_id": "BUD-001", "max_trip_total_usd": 2300},
        "lodging_rules": {"rule_id": "LOD-001", "max_nightly_rate_usd": 325},
    }
}


@pytest.mark.parametrize(
    "estimated_total",
    [
        None,
        {},
        {"currency": "USD"},
        {"typical_amount": None},
        {"typical_amount": "unknown"},
        {"typical_amount": True},
        {"typical_amount": float("nan")},
        {"typical_amount": float("inf")},
        {"typical_amount": float("-inf")},
    ],
)
def test_missing_estimated_total_does_not_mark_compliant_under_budget_cap(
    estimated_total: Any,
) -> None:
    preview = build_scenario_policy_preview(
        policy_state=FIXTURE_POLICY,
        trip_mode="business",
        estimated_total=estimated_total,
    )

    assert preview["compliant"] is None
    assert preview["status"] == "preview_incomplete"
    assert preview["status_label"] == "Trip cost unavailable (preview)"
    assert preview["snapshot_available"] is True
    assert preview["authoritative"] is False
    incomplete = next(item for item in preview["violations"] if item["rule_id"] == "BUD-001")
    assert incomplete["incomplete"] is True
    assert incomplete["actual_amount"] is None
    assert incomplete["cap_amount"] == 2300


def test_missing_cost_preserves_known_policy_violations() -> None:
    preview = build_scenario_policy_preview(
        policy_state=FIXTURE_POLICY,
        trip_mode="business",
        estimated_total=None,
        scenario_notes=["exception-nearest"],
    )

    assert preview["compliant"] is False
    assert preview["status"] == "non_compliant"
    assert {item["rule_id"] for item in preview["violations"]} == {"BUD-001", "POL-EXC"}


@pytest.mark.parametrize("budget_rules", [{}, {"max_trip_total_usd": "unknown"}])
def test_missing_cost_without_numeric_budget_cap_does_not_create_budget_violation(
    budget_rules: dict[str, Any],
) -> None:
    preview = build_scenario_policy_preview(
        policy_state={"constraint_set": {"budget_rules": budget_rules}},
        trip_mode="business",
        estimated_total=None,
    )

    assert preview["compliant"] is True
    assert preview["violations"] == []


def test_compliant_scenario_preview_when_under_trip_cap() -> None:
    preview = build_scenario_policy_preview(
        policy_state=FIXTURE_POLICY,
        trip_mode="business",
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
        estimated_total={"currency": "USD", "typical_amount": 2280},
    )

    assert preview["snapshot_available"] is False
    assert preview["status_label"] == "No policy snapshot available"
    assert preview["compliant"] is None


def test_leisure_scenario_preview_is_not_applicable() -> None:
    preview = build_scenario_policy_preview(
        policy_state=FIXTURE_POLICY,
        trip_mode="leisure",
        estimated_total={"currency": "USD", "typical_amount": 9999},
    )

    assert preview["status"] == "not_applicable"
    assert preview["compliant"] is None
    assert preview["snapshot_available"] is False


def test_lodging_cap_violation_includes_nightly_cap_vs_actual() -> None:
    preview = build_scenario_policy_preview(
        policy_state=FIXTURE_POLICY,
        trip_mode="business",
        estimated_total={
            "currency": "USD",
            "typical_amount": 1000,
            "nightly_typical_amount": 400,
        },
    )

    lodging = next(item for item in preview["violations"] if item["rule_id"] == "LOD-001")
    assert lodging["cap_amount"] == 325
    assert lodging["actual_amount"] == 400


def test_non_usd_scenario_skips_usd_budget_cap_comparison() -> None:
    preview = build_scenario_policy_preview(
        policy_state=FIXTURE_POLICY,
        trip_mode="business",
        estimated_total={"currency": "EUR", "typical_amount": 9999},
    )

    assert not any(item["rule_id"] == "BUD-001" for item in preview["violations"])


@pytest.mark.parametrize("cap", [True, False, float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("estimated_total", [None, {"currency": "USD", "typical_amount": 2400}])
def test_invalid_budget_cap_does_not_create_budget_finding(cap: Any, estimated_total: Any) -> None:
    preview = build_scenario_policy_preview(
        policy_state={"constraint_set": {"budget_rules": {"max_trip_total_usd": cap}}},
        trip_mode="business",
        estimated_total=estimated_total,
        scenario_notes=["exception-nearest"],
    )

    assert [item["rule_id"] for item in preview["violations"]] == ["POL-EXC"]
    assert preview["compliant"] is False


@pytest.mark.parametrize(
    "amount", [None, "unknown", True, float("nan"), float("inf"), float("-inf")]
)
def test_non_usd_missing_amount_skips_usd_budget_cap(amount: Any) -> None:
    preview = build_scenario_policy_preview(
        policy_state=FIXTURE_POLICY,
        trip_mode="business",
        estimated_total={"currency": "EUR", "typical_amount": amount},
    )

    assert preview["violations"] == []
    assert preview["status"] == "compliant"


def test_non_usd_absent_amount_preserves_known_policy_violation() -> None:
    preview = build_scenario_policy_preview(
        policy_state=FIXTURE_POLICY,
        trip_mode="business",
        estimated_total={"currency": "EUR"},
        scenario_notes=["exception-nearest"],
    )

    assert [item["rule_id"] for item in preview["violations"]] == ["POL-EXC"]
    assert preview["compliant"] is False


def test_policy_import_persists_budget_rules_for_scenario_preview(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TRIP_PLANNER_DATABASE_URL", f"sqlite:///{tmp_path / 'budget.db'}")
    fixture_path = (
        Path(__file__).resolve().parents[1]
        / "fixtures/integrations/tpp/policy/standard_policy_sync.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    budget_rules = {"rule_id": "BUD-IMPORT", "max_trip_total_usd": 2300}
    fixture["response"]["result_payload"]["constraint_set"]["budget_rules"] = budget_rules
    reset_database_state()
    try:
        with TestClient(create_app()) as client:
            signup = client.post(
                "/api/auth/signup",
                json={
                    "email": "budget@example.com",
                    "password": "password123",
                    "display_name": "Budget Owner",
                },
            )
            assert signup.status_code == 201
            created = client.post(
                "/api/trips", json={"title": "Budget policy import", "mode": "business"}
            )
            assert created.status_code == 201
            trip_id = created.json()["trip"]["trip_id"]
            policy_url = f"/api/workspace/{trip_id}/policy"
            imported = client.put(
                policy_url,
                json={"request": fixture["request"], "response": fixture["response"]},
            )
            assert imported.status_code == 200
            assert imported.json()["policy_state"]["constraint_set"]["budget_rules"] == budget_rules
            with get_session_factory()() as session:
                stored = session.get(PersistedPolicyState, f"policy-state:{trip_id}")
                assert stored is not None
                assert stored.constraint_set["budget_rules"] == budget_rules

        # Close the first app before reopening SQLite and loading persisted state.
        reset_database_state()
        with TestClient(create_app()) as client:
            login = client.post(
                "/api/auth/login",
                json={"email": "budget@example.com", "password": "password123"},
            )
            assert login.status_code == 200
            reloaded = client.get(policy_url)
            assert reloaded.status_code == 200
            policy_state = reloaded.json()["policy_state"]
            assert policy_state["constraint_set"]["budget_rules"] == budget_rules
            preview = build_scenario_policy_preview(
                policy_state=policy_state,
                trip_mode="business",
                estimated_total={"currency": "USD", "typical_amount": 2410},
            )
            assert preview["compliant"] is False
            violation = next(
                (item for item in preview["violations"] if item["rule_id"] == "BUD-IMPORT"),
                None,
            )
            assert violation is not None, "Expected the persisted BUD-IMPORT cap to be violated"
            assert violation["cap_amount"] == 2300
            assert violation["actual_amount"] == 2410
            assert preview["authoritative"] is False
    finally:
        reset_database_state()
