import json
from pathlib import Path

import pytest

from trip_planner.integrations.tpp import (
    BaseTPPIntegrationClient,
    PolicySyncError,
    TPPPolicySyncService,
    TPPRequestEnvelope,
    TPPResponseEnvelope,
    summarize_policy_import,
)


def _fixture_path(name: str) -> Path:
    return Path("tests/fixtures/integrations/tpp/policy") / name


def _load_fixture(name: str) -> dict:
    return json.loads(_fixture_path(name).read_text(encoding="utf-8"))


class FakeTPPPolicyClient(BaseTPPIntegrationClient):
    def __init__(self, response: TPPResponseEnvelope) -> None:
        self.response = response
        self.calls: list[str] = []

    def execute(self, request: TPPRequestEnvelope) -> TPPResponseEnvelope:
        self.calls.append(request.operation)
        return self.response


def test_import_standard_policy_sync_snapshot() -> None:
    fixture = _load_fixture("standard_policy_sync.json")
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPPolicySyncService(FakeTPPPolicyClient(response))

    imported = service.import_policy_constraints(request)
    summary = summarize_policy_import(imported, "2026-02-15T14:00:00Z")

    assert imported.constraint_set.policy_id == "policy-standard-2026-02"
    assert imported.organization_context.comparable_requirements == {
        "airfare": 2,
        "lodging": 2,
    }
    assert imported.constraint_set.required_booking_channels == ["Navan", "Concur"]
    assert summary["is_stale"] is False
    assert summary["documentation_rules"] == [
        "retain_receipts",
        "attach_comparables",
    ]


def test_import_stricter_org_policy_preserves_limits_and_triggers() -> None:
    fixture = _load_fixture("strict_policy_sync.json")
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPPolicySyncService(FakeTPPPolicyClient(response))

    imported = service.import_policy_constraints(request)

    assert imported.constraint_set.airfare_rules["max_cabin"] == "economy"
    assert imported.constraint_set.lodging_rules["max_nightly_rate_usd"] == 210
    assert imported.organization_context.class_of_service_limits["air"] == "economy"
    assert imported.organization_context.approval_triggers == [
        "international_travel",
        "lodging_above_cap",
        "vice_president_preapproval",
    ]


def test_invalidated_policy_snapshot_is_marked_stale() -> None:
    fixture = _load_fixture("invalidated_policy_sync.json")
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPPolicySyncService(FakeTPPPolicyClient(response))

    imported = service.import_policy_constraints(request)

    assert imported.is_stale("2026-02-18T12:00:00Z") is True
    assert imported.freshness.status == "invalidated"
    assert imported.freshness.invalidation_reason == "manual_policy_recall"


def test_policy_sync_rejects_malformed_comparable_requirements() -> None:
    fixture = _load_fixture("standard_policy_sync.json")
    fixture["response"]["result_payload"]["organization_context"][
        "comparable_requirements"
    ]["lodging"] = "two"
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPPolicySyncService(FakeTPPPolicyClient(response))

    with pytest.raises(ValueError, match="comparable_requirements\\[lodging\\]"):
        service.import_policy_constraints(request)


def test_policy_sync_rejects_missing_constraint_set_payload() -> None:
    fixture = _load_fixture("standard_policy_sync.json")
    del fixture["response"]["result_payload"]["constraint_set"]
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPPolicySyncService(FakeTPPPolicyClient(response))

    with pytest.raises(ValueError, match="result_payload.constraint_set"):
        service.import_policy_constraints(request)


def test_policy_sync_rejects_non_succeeded_execution_status() -> None:
    fixture = _load_fixture("standard_policy_sync.json")
    fixture["response"]["execution_status"]["state"] = "deferred"
    fixture["response"]["execution_status"]["terminal"] = False
    request = TPPRequestEnvelope.from_dict(fixture["request"])
    response = TPPResponseEnvelope.from_dict(fixture["response"])
    service = TPPPolicySyncService(FakeTPPPolicyClient(response))

    with pytest.raises(PolicySyncError, match="succeeded execution_status"):
        service.import_policy_constraints(request)
