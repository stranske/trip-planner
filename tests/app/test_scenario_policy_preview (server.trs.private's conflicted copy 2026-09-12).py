import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from trip_planner.app.main import create_app
from trip_planner.app.services import workspace as workspace_service
from trip_planner.app.services.scenario_policy_preview import (
    build_scenario_policy_preview,
)
from trip_planner.persistence.db import get_session_factory, reset_database_state
from trip_planner.persistence.models.policy import PersistedPolicyState
from trip_planner.persistence.models.trip import PersistedTrip

FIXTURE_POLICY = {
    "constraint_set": {
        "budget_rules": {"rule_id": "BUD-001", "max_trip_total_usd": 2300},
        "lodging_rules": {"rule_id": "LOD-001", "max_nightly_rate_usd": 325},
    }
}


@pytest.mark.parametrize("trip_mode", ["business", "leisure"])
@pytest.mark.parametrize("compliant_notes", [[], ["exception-nearest"]])
def test_exception_nearest_saved_scenario_surfaces_pol_exc_preview_violation(
    trip_mode: str,
    compliant_notes: list[str],
) -> None:
    fixture_path = (
        Path(__file__).resolve().parents[2]
        / "trip_planner/resources/state/scenarios/business_compliant_vs_exception.json"
    )
    saved_scenarios = json.loads(fixture_path.read_text())["records"]
    # Prose on a compliant scenario must not turn it into an exception route.
    compliant_scenario = next(
        scenario
        for scenario in saved_scenarios
        if scenario["saved_scenario_id"] == "saved-scenario:compliant-first"
    )
    compliant_scenario["versions"][0]["notes"] = compliant_notes
    record = PersistedTrip(
        trip_id="trip-business-client-summit",
        title="Client summit",
        mode=trip_mode,
        duration_days=1,
        primary_regions=["Chicago"],
    )
    search = workspace_service._build_saved_scenario_runtime_search(
        record, saved_scenarios=saved_scenarios
    )
    exception_scenario = next(
        scenario
        for scenario in search["scenarios"]
        if scenario["scenario_id"] == "saved-scenario:exception-nearest"
    )
    assert "exception-nearest" not in exception_scenario["scenario_summary"]["notes"]
    comparison = workspace_service._build_runtime_scenario_comparison(
        trip_id=record.trip_id,
        trip_title=record.title,
        scenario_search=search,
        policy_state=FIXTURE_POLICY,
        trip_mode=trip_mode,
    )
    previews = {row["scenario_id"]: row["policy_preview"] for row in comparison["scenarios"]}
    exception = previews["saved-scenario:exception-nearest"]
    compliant = previews["saved-scenario:compliant-first"]
    assert exception["authoritative"] is False
    if trip_mode == "business":
        assert [item["rule_id"] for item in exception["violations"]] == ["POL-EXC"]
        assert exception["compliant"] is False
        assert compliant["violations"] == []
        assert compliant["compliant"] is True
    else:
        assert exception["status"] == "not_applicable"
        assert exception["violations"] == []


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
        {"typical_amount": 10**1000},
        {"typical_amount": -(10**1000)},
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
        scenario_label="exception_nearest",
    )

    assert preview["compliant"] is False
    assert preview["status"] == "non_compliant"
    assert {item["rule_id"] for item in preview["violations"]} == {
        "BUD-001",
        "LOD-001",
        "POL-EXC",
    }


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
        estimated_total={
            "currency": "USD",
            "typical_amount": 2280,
            "nightly_typical_amount": 300,
        },
        unresolved_tradeoffs=[],
        scenario_label="compliant_first",
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
        scenario_label="exception_nearest",
    )

    assert preview["compliant"] is False
    bud_violation = next(item for item in preview["violations"] if item["rule_id"] == "BUD-001")
    assert bud_violation["cap_amount"] == 2300
    assert bud_violation["actual_amount"] == 2410
    assert sum(item["rule_id"] == "POL-EXC" for item in preview["violations"]) == 1


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


@pytest.mark.parametrize(
    "nightly_fields",
    [
        {},
        {"nightly_typical_amount": None},
        {"nightly_typical_amount": "unknown"},
        {"nightly_typical_amount": True},
        {"nightly_typical_amount": float("nan")},
        {"nightly_typical_amount": float("inf")},
        {"nightly_typical_amount": float("-inf")},
        {"nightly_typical_amount": 10**1000},
        {"nightly_typical_amount": -(10**1000)},
    ],
)
def test_missing_nightly_amount_marks_lodging_preview_incomplete_not_compliant(
    nightly_fields: dict[str, Any],
) -> None:
    preview = build_scenario_policy_preview(
        policy_state=FIXTURE_POLICY,
        trip_mode="business",
        estimated_total={"currency": "USD", "typical_amount": 1000, **nightly_fields},
    )

    assert preview["compliant"] is None
    assert preview["status"] == "preview_incomplete"
    assert preview["snapshot_available"] is True
    assert preview["authoritative"] is False
    assert preview["violations"] == [
        {
            "rule_id": "LOD-001",
            "message": "Nightly rate is unavailable; the configured lodging cap cannot be checked.",
            "cap_amount": 325,
            "actual_amount": None,
            "currency": "USD",
            "incomplete": True,
        }
    ]


@pytest.mark.parametrize("nightly_amount", [0, 300, 325])
def test_lodging_preview_is_compliant_at_or_under_cap(nightly_amount: float) -> None:
    preview = build_scenario_policy_preview(
        policy_state=FIXTURE_POLICY,
        trip_mode="business",
        estimated_total={"typical_amount": 1000, "nightly_typical_amount": nightly_amount},
    )

    assert preview["compliant"] is True
    assert preview["violations"] == []


@pytest.mark.parametrize(
    "cap",
    [
        None,
        "unknown",
        True,
        float("nan"),
        float("inf"),
        pytest.param(10**1000, id="overflow"),
        pytest.param(-(10**1000), id="negative-overflow"),
    ],
)
def test_invalid_lodging_cap_does_not_create_lodging_finding(cap: Any) -> None:
    preview = build_scenario_policy_preview(
        policy_state={"constraint_set": {"lodging_rules": {"max_nightly_rate_usd": cap}}},
        trip_mode="business",
        estimated_total=None,
    )

    assert preview["violations"] == []


def test_missing_nightly_rate_preserves_known_budget_violation() -> None:
    preview = build_scenario_policy_preview(
        policy_state=FIXTURE_POLICY,
        trip_mode="business",
        estimated_total={"typical_amount": 2410},
    )

    assert preview["compliant"] is False
    assert preview["status"] == "non_compliant"
    assert {item["rule_id"] for item in preview["violations"]} == {"BUD-001", "LOD-001"}


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


@pytest.mark.parametrize(
    "cap",
    [
        True,
        False,
        float("nan"),
        float("inf"),
        float("-inf"),
        pytest.param(10**1000, id="overflow"),
        pytest.param(-(10**1000), id="negative-overflow"),
    ],
)
@pytest.mark.parametrize("estimated_total", [None, {"currency": "USD", "typical_amount": 2400}])
def test_invalid_budget_cap_does_not_create_budget_finding(cap: Any, estimated_total: Any) -> None:
    preview = build_scenario_policy_preview(
        policy_state={"constraint_set": {"budget_rules": {"max_trip_total_usd": cap}}},
        trip_mode="business",
        estimated_total=estimated_total,
        scenario_label="exception_nearest",
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
        scenario_label="exception_nearest",
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
